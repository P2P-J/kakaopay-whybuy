"""매수 전 점검 — 층2·3 DART 위험 스캔 (판정 아님, 공식 기록의 사실 전달) — whybuy (G10).

존재의 정직: 공식 기록에 정해진 사실이 있으면 있다고, 없으면 없다고. 우리가 위험을 판단하지
않고 거래소·회사·회계법인이 남긴 사실만 전달한다. 시세(가격)는 위험 판정에 쓰지 않는다
(격리 — 소스에 시세 임포트 0). 오탐 위험 축(연속 영업손실·잦은 증자CB)의 기준값은 config에서
읽고 브리핑에 표기한다. 자본잠식은 별도재무제표(OFS) 기준(개별 법인 — CFS는 자회사 지분 왜곡).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from classify import classify  # noqa: F401  (분류는 dart_client.get_events가 사용)
from dart_client import get_events, get_financials, get_report_item

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["prebuy"]

_BAD_AUDIT = ("의견거절", "부적정", "한정")
_DILUTION_KW = ("증자", "전환사채", "신주인수권")   # 감자는 자본 감소라 희석 아님 → 제외
_PERIODS = [f"{y}{q}" for y in ("2026", "2025", "2024") for q in ("4Q", "3Q", "2Q", "1Q")]


def _won(s):
    if s in (None, "", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


def _viewer(rcp: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}" if rcp else ""


# ── 순수 분기 헬퍼 (결정적, 데이터 무관) ─────────────────────────
def capital_impairment(total, capital) -> bool:
    """자본잠식: 자본총계 < 자본금 (별도재무제표 기준으로 호출)."""
    return total is not None and capital is not None and total < capital


def consecutive_op_loss(op_series: list, quarters: int) -> bool:
    """최신 quarters개 분기가 모두 영업손실(음수)일 때만 True. op_series는 최신순."""
    return len(op_series) >= quarters and all(v is not None and v < 0 for v in op_series[:quarters])


def is_bad_audit(opinion: str) -> bool:
    return any(b in (opinion or "") for b in _BAD_AUDIT)


def going_concern(emphs_matter: str) -> bool:
    """계속기업 불확실성: '계속기업' + ('불확실' 또는 '의문') 동시 — 단어만으론 오탐 방지."""
    e = emphs_matter or ""
    return "계속기업" in e and ("불확실" in e or "의문" in e)


def dilution_count(events: list[dict]) -> int:
    """희석 이벤트(유상증자·CB·신주인수권) 건수. 정정·감자 제외."""
    n = 0
    for ev in events:
        t = ev.get("title", "")
        if ev.get("is_correction") or "감자" in t:
            continue
        if any(k in t for k in _DILUTION_KW):
            n += 1
    return n


# ── 데이터 배선 ───────────────────────────────────────────────────
def latest_ofs_capital(corp_code: str):
    """별도재무제표(OFS) 최신 자본총계·자본금. (total, capital, basis, rcp)."""
    d = FIX / "financials_ofs" / corp_code
    for p in sorted(_PERIODS, reverse=True):
        f = d / f"{p}.json"
        if not f.exists():
            continue
        blk = json.loads(f.read_text(encoding="utf-8"))
        g = {a["account_nm"]: _won(a.get("thstrm_amount")) for a in blk["accounts"]}
        rcp = blk["accounts"][0].get("rcept_no", "") if blk["accounts"] else ""
        return g.get("자본총계"), g.get("자본금"), blk.get("basis"), rcp
    return None, None, None, ""


def _op_series(corp_code: str, as_of: str) -> list:
    out = []
    for p in sorted(_PERIODS, reverse=True):
        blk = get_financials(corp_code, p[:4], p[4:], as_of)
        if blk.get("status") != "ok":
            continue
        op = next((a for a in blk["accounts"] if a["account_nm"] == "영업이익"), None)
        if op:
            out.append(_won(op["thstrm_amount"]))
    return out


def scan_financial_risk(corp_code: str, as_of: str) -> list[dict]:
    """층 2 재무 건전성: 자본잠식(OFS)·연속 영업손실·감사의견 비적정·계속기업 불확실성."""
    signals = []
    total, capital, basis, rcp = latest_ofs_capital(corp_code)
    if capital_impairment(total, capital):
        signals.append({"layer": 2, "type": "capital_impairment", "label": "자본잠식",
                        "detail": f"자본총계가 자본금보다 적습니다 ({basis}·별도재무제표 기준)",
                        "source_kind": "DART", "basis": basis,
                        "evidence": {"rcp_no": rcp, "url": _viewer(rcp)}})

    ops = _op_series(corp_code, as_of)
    q = CFG["consecutive_op_loss_quarters"]
    if consecutive_op_loss(ops, q):
        signals.append({"layer": 2, "type": "consecutive_op_loss",
                        "label": f"최근 {q}분기 연속 영업손실", "detail": f"기준: 최근 {q}분기 연속 영업손실",
                        "threshold": q, "source_kind": "DART", "evidence": {}})

    audit = get_report_item(corp_code, "audit_opinion", as_of)
    if audit.get("status") == "ok":
        latest = audit["years"][max(audit["years"])][0]
        opinion = latest.get("adt_opinion", "")
        arcp = latest.get("rcept_no", "")
        if is_bad_audit(opinion):
            signals.append({"layer": 2, "type": "bad_audit", "label": f"감사의견 {opinion}",
                            "detail": f"최근 감사의견: {opinion}", "source_kind": "DART",
                            "evidence": {"rcp_no": arcp, "url": _viewer(arcp)}})
        if going_concern(latest.get("emphs_matter", "")):
            signals.append({"layer": 2, "type": "going_concern", "label": "계속기업 관련 불확실성",
                            "detail": "감사보고서 강조사항에 계속기업 관련 불확실성 기재",
                            "source_kind": "DART", "evidence": {"rcp_no": arcp, "url": _viewer(arcp)}})
    return signals


def scan_governance_risk(corp_code: str, as_of: str) -> list[dict]:
    """층 3 지배구조·주주가치: 횡령·배임·최대주주 2회↑ 변경·잦은 증자CB·영업정지."""
    signals = []
    events = get_events(corp_code, None, "2000-01-01", as_of, as_of)

    embezzle = [e for e in events if e["event_type"] == "litigation" and re.search("횡령|배임", e["title"])]
    if embezzle:
        e = embezzle[-1]
        signals.append({"layer": 3, "type": "embezzlement", "label": "횡령·배임 관련 공시",
                        "detail": e["title"].strip(), "source_kind": "DART",
                        "evidence": {"rcp_no": e["rcp_no"], "url": e["url"]}})

    changes = [e for e in events if "최대주주변경" in e["title"] and not e.get("is_correction")]
    if len(changes) >= CFG["major_change_threshold"]:
        signals.append({"layer": 3, "type": "major_shareholder_change",
                        "label": f"최대주주 변경 {len(changes)}회",
                        "detail": f"기준: 최대주주 변경 {CFG['major_change_threshold']}회 이상",
                        "source_kind": "DART", "evidence": {"rcp_no": changes[-1]["rcp_no"], "url": changes[-1]["url"]}})

    lo = (date.fromisoformat(as_of) - timedelta(days=CFG["dilution_window_days"])).isoformat()
    window = [e for e in events if e["event_type"] == "capital_change" and lo <= e["submitted"] <= as_of]
    dc = dilution_count(window)
    if dc >= CFG["dilution_count_threshold"]:
        signals.append({"layer": 3, "type": "frequent_dilution",
                        "label": f"최근 1년 내 유상증자·CB 등 {dc}건",
                        "detail": f"기준: 최근 {CFG['dilution_window_days']}일 내 희석 이벤트 {CFG['dilution_count_threshold']}건 이상",
                        "source_kind": "DART", "evidence": {}})

    halt = [e for e in events if e["event_type"] == "business_halt"]
    if halt:
        e = halt[-1]
        signals.append({"layer": 3, "type": "business_halt", "label": "영업정지·사업중단 관련 공시",
                        "detail": e["title"].strip(), "source_kind": "DART",
                        "evidence": {"rcp_no": e["rcp_no"], "url": e["url"]}})
    return signals
