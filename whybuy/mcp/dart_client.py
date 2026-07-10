"""OpenDART 호출 + 픽스처/캐시 스위치 (국내 전용) — whybuy.

WHYBUY_MODE=fixture(기본)면 fixtures만 읽고, live면 API 호출+캐시(향후 G8 배선).
**as_of 필터를 이 계층에서 일괄 적용**해 모든 도구가 시점 시뮬레이션을 공짜로 얻는다 —
공시 제출일(submitted) 또는 rcp_no 앞 8자리(=제출일)가 as_of 이하인 것만 노출한다.
데이터 부재는 예외가 아니라 {"status":"absent"} 구조로 반환(부재의 정직).
DART_API_KEY는 .env에서만 읽고 로그·커밋에 노출하지 않는다.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from classify import classify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"


def _mode() -> str:
    return os.environ.get("WHYBUY_MODE", "fixture").lower()


def _rcp_date(rcp_no: str) -> str:
    """rcp_no(14자리) 앞 8자리 YYYYMMDD → ISO 날짜. 형식 밖이면 빈 문자열."""
    if rcp_no and len(rcp_no) >= 8 and rcp_no[:8].isdigit():
        s = rcp_no[:8]
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return ""


def _live_guard():
    if _mode() == "live":
        raise NotImplementedError("live 모드는 G8에서 배선 (현재 fixture 모드만 지원)")


# ── corp 매핑 ─────────────────────────────────────────────────────
def _norm_name(s: str) -> str:
    """회사명 정규화: 주식회사 마커·공백 제거 + 소문자화. 이름 입력 관용 처리용
    (예: '카카오'·'(주)카카오'·'삼성전자(주)' → 같은 키)."""
    s = s.strip()
    for m in ("주식회사", "(주)", "㈜", "(유)"):
        s = s.replace(m, "")
    return s.replace(" ", "").lower()


def _corp_index() -> dict:
    idx = {}
    for f in (FIX / "corp").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        idx[d["stock_code"]] = d
        idx[d["corp_name"]] = d
        idx.setdefault(_norm_name(d["corp_name"]), d)   # 정규화 이름('카카오' 등)
    return idx


def resolve_corp(query: str) -> dict:
    """ticker 또는 회사명 → {corp_code, corp_name, ticker, market}. 미발견 시 absent.

    회사명은 주식회사 마커 유무와 무관하게 정규화 매칭한다('카카오' == '(주)카카오')."""
    _live_guard()
    idx = _corp_index()
    d = idx.get(query.strip()) or idx.get(_norm_name(query))
    if not d:
        return {"status": "absent", "query": query}
    return {"corp_code": d["corp_code"], "corp_name": d["corp_name"],
            "ticker": d["stock_code"], "market": d["market"]}


# ── 공시 목록 ─────────────────────────────────────────────────────
def _disclosures(corp_code: str) -> list[dict]:
    f = FIX / "disclosures" / f"{corp_code}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def list_disclosures(corp_code: str, date_from: str, date_to: str,
                     kinds: list[str] | None, as_of: str) -> list[dict]:
    """공시 목록. [date_from, date_to] 구간 + kinds(pblntf_ty) 필터 + as_of 이후 제출분 제외."""
    _live_guard()
    out = []
    for r in _disclosures(corp_code):
        sub = r.get("submitted", "")
        if sub > as_of:            # as_of 시점 시뮬레이션: 미래 제출분 차단
            continue
        if not (date_from <= sub <= date_to):
            continue
        if kinds and r.get("pblntf_ty") not in kinds:
            continue
        out.append(r)
    return sorted(out, key=lambda x: x["submitted"])


# ── 재무 (as_of는 rcp_no 제출일로 게이트) ─────────────────────────
_REPRT = {"1": "1Q", "2": "2Q", "3": "3Q", "4": "4Q",
          "1Q": "1Q", "2Q": "2Q", "3Q": "3Q", "4Q": "4Q"}


def get_financials(corp_code: str, year: str, quarter: str, as_of: str) -> dict:
    """분기 주요계정. 해당 보고서 제출일(rcp_no 앞 8자리)이 as_of 이하일 때만 반환."""
    _live_guard()
    q = _REPRT.get(str(quarter).upper(), str(quarter))
    f = FIX / "financials" / corp_code / f"{year}{q}.json"
    if not f.exists():
        return {"status": "absent", "corp_code": corp_code, "period": f"{year}{q}"}
    block = json.loads(f.read_text(encoding="utf-8"))
    rcp = block["accounts"][0].get("rcept_no", "") if block.get("accounts") else ""
    if _rcp_date(rcp) and _rcp_date(rcp) > as_of:
        return {"status": "absent", "reason": "as_of 이전 미제출", "period": f"{year}{q}"}
    return {"status": "ok", "period": f"{year}{q}", "basis": block.get("basis"),
            "accounts": block.get("accounts", [])}


# ── 고정 감시 항목 (배당·최대주주·감사·자기주식) ─────────────────
def get_report_item(corp_code: str, item: str, as_of: str) -> dict:
    """report_items의 한 항목. 각 행을 rcp 제출일로 as_of 게이트. 부재 시 absent."""
    _live_guard()
    f = FIX / "report_items" / f"{corp_code}.json"
    if not f.exists():
        return {"status": "absent", "item": item}
    data = json.loads(f.read_text(encoding="utf-8"))
    if item not in data:
        return {"status": "absent", "item": item}
    rows_by_year = {}
    for year, rows in data[item].items():
        kept = [r for r in rows if not _rcp_date(r.get("rcept_no", "")) or _rcp_date(r["rcept_no"]) <= as_of]
        if kept:
            rows_by_year[year] = kept
    if not rows_by_year:
        return {"status": "absent", "item": item, "reason": "as_of 이전 데이터 없음"}
    return {"status": "ok", "item": item, "years": rows_by_year}


# ── 이벤트 (분류기로 유형 매핑 후 필터) ───────────────────────────
def get_events(corp_code: str, event_types: list[str] | None,
               date_from: str, date_to: str, as_of: str) -> list[dict]:
    """공시를 분류기로 세부유형 매핑 후 event_types·구간·as_of로 필터."""
    _live_guard()
    out = []
    for r in list_disclosures(corp_code, date_from, date_to, None, as_of):
        c = classify(r.get("title", ""), r.get("pblntf_ty"))
        if event_types and c["type"] not in event_types:
            continue
        out.append({**r, "event_type": c["type"], "is_correction": c["is_correction"]})
    return out


def get_insider(corp_code: str, date_from: str, date_to: str, as_of: str) -> list[dict]:
    """임원·주요주주·최대주주 지분 변동 공시(major_shareholder)."""
    return get_events(corp_code, ["major_shareholder"], date_from, date_to, as_of)


# ── 시세 ──────────────────────────────────────────────────────────
def price_get_daily(ticker: str, date_from: str, date_to: str) -> list[dict]:
    """일별 OHLCV·등락률. [date_from, date_to] 구간(시세는 시장 데이터라 as_of 무관, 호출자가 to=as_of)."""
    _live_guard()
    f = FIX / "prices" / f"{ticker}.csv"
    if not f.exists():
        return []
    rows = []
    for r in csv.DictReader(f.open(encoding="utf-8")):
        if date_from <= r["date"] <= date_to:
            rows.append({"date": r["date"], "close": float(r["close"]),
                         "change_pct": float(r["change_pct"]), "open": float(r["open"]),
                         "high": float(r["high"]), "low": float(r["low"]),
                         "volume": int(r["volume"])})
    return rows
