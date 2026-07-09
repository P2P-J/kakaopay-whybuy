"""판정 룰 레지스트리 (판정의 심장) — whybuy (G5).

PRD 5.3의 룰 7종(EARN/RET/DIV/GRW/NEW/THM/PRC)을 코드로 구현. 입력=원장 reason
(type·claim·source_rcp_no) + as_of, 출력={status, evidence, rule_id}. 결정적 연산
(같은 입력→같은 판정). 시세(가격) 격리: 이 모듈은 시세 데이터 임포트·도구 접근이 없다
(코드 수준 격리 — 확인불가 유형 문자열은 verdict_rules.yaml로 외재화). status enum:
supported/weakened/refuted/unverifiable.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from dart_client import get_events, get_financials, get_report_item

ROOT = Path(__file__).resolve().parents[1]
_CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
_UNVERIFIABLE = yaml.safe_load((Path(__file__).resolve().parent / "verdict_rules.yaml").read_text(encoding="utf-8"))["unverifiable_types"]
_SHRINK_PCT = _CFG["verdict"]["earn_weaken_shrink_pct"]

_CHECKABLE = ("earnings_improvement", "shareholder_return", "dividend", "growth_order", "new_business")


def _viewer(rcp: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"


def _won(s) -> int | None:
    if s in (None, "", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


# ── 순수 판정 로직 (결정적, 데이터 무관) ─────────────────────────
def earn_status(th, fr, prev_th=None, prev_fr=None, shrink_pct=_SHRINK_PCT):
    """전사 영업이익 YoY 판정. 흑자전환 등 부호 분기를 명시적으로 처리."""
    if fr <= 0:                                   # 전년 적자
        if th > 0:
            return "supported", "적자→흑자 전환"
        if th > fr:
            return "weakened", "적자 지속(적자폭 축소)"
        return "refuted", "적자 지속(적자폭 확대)"
    if th <= 0:                                   # 흑자→적자 전환
        return "refuted", "흑자→적자 전환"
    yoy = (th - fr) / fr * 100
    if th < fr:                                   # 감익
        return "refuted", f"{yoy:+.0f}% YoY (감익)"
    # 증익
    if prev_fr and prev_fr > 0 and prev_th is not None and prev_th > prev_fr:
        prev_growth = (prev_th - prev_fr) / prev_fr
        cur_growth = (th - fr) / fr
        if prev_growth > 0 and cur_growth < prev_growth * (1 - shrink_pct / 100):
            return "weakened", f"{yoy:+.0f}% YoY (증익이나 증가폭 축소)"
    return "supported", f"{yoy:+.0f}% YoY (개선)"


def div_status(th, fr):
    """주당배당금 동일 주기 비교. 유지·확대=유효 / 감소=약화 / 무배당=반증."""
    if th is None or th == 0:
        return "refuted", "무배당 전환"
    if fr is None:
        return "supported", f"{th}원"
    if th >= fr:
        return "supported", f"{fr}→{th}원 (유지·확대)"
    return "weakened", f"{fr}→{th}원 (감소)"


def ret_status(title: str):
    """자기주식: 취득·소각·신규 결정=유효 / 처분·중단=반증."""
    if "처분" in title or "중단" in title:
        return "refuted", "자기주식 처분·중단"
    if "취득" in title or "소각" in title:
        return "supported", "자기주식 취득·소각"
    return "supported", "주주환원 실행"


def growth_status(follow_titles: list[str]):
    """시설투자·공급계약: 해지·중단=반증 / 규모 축소 정정=약화 / 후속 정정 없음=유효."""
    for t in follow_titles:
        if "해지" in t or "중단" in t:
            return "refuted", "후속 해지·중단 공시"
    for t in follow_titles:
        if "정정" in t and "축소" in t:
            return "weakened", "규모 축소 정정"
    return "supported", "후속 정정·해지 없음"


def new_status(has_followup: bool, long_silence: bool):
    """신사업: 관련 후속 공시 존재=유효 / 장기 무소식=약화 / 중단=반증(중단은 상위에서 처리)."""
    if has_followup:
        return "supported", "관련 후속 공시 존재"
    if long_silence:
        return "weakened", "장기 무소식"
    return "supported", "진행 중"


# ── 데이터 접근 + 룰 배선 ─────────────────────────────────────────
_PERIODS = [f"{y}{q}" for y in ("2026", "2025", "2024") for q in ("4Q", "3Q", "2Q", "1Q")]


def _op(block: dict):
    for a in block.get("accounts", []):
        if a["account_nm"] == "영업이익":
            return _won(a["thstrm_amount"]), _won(a["frmtrm_amount"]), a.get("rcept_no", "")
    return None


def _available_quarters(corp: str, as_of: str) -> list[tuple[str, dict]]:
    """as_of 이하 제출된 분기 재무를 최신순으로."""
    out = []
    for period in sorted(_PERIODS, reverse=True):
        year, q = period[:4], period[4:]
        blk = get_financials(corp, year, q, as_of)
        if blk.get("status") == "ok" and _op(blk):
            out.append((period, blk))
    return out


def _absence(rule_id: str) -> dict:
    return {"status": "unverifiable", "rule_id": rule_id,
            "evidence": {"note": "as_of 시점 대조 데이터 부재 — 직전 판정 유지·부재 고지"}}


def _rule_earn(reason, corp, as_of) -> dict:
    qs = _available_quarters(corp, as_of)
    if not qs:
        return _absence("RULE-EARN-01")
    period, blk = qs[0]
    th, fr, rcp = _op(blk)
    prev = _op(qs[1][1]) if len(qs) > 1 else (None, None, None)
    status, delta = earn_status(th, fr, prev[0], prev[1])
    return {"status": status, "rule_id": "RULE-EARN-01",
            "evidence": {"rcp_no": rcp, "url": _viewer(rcp), "item": "영업이익",
                         "fs_div": blk.get("basis"), "baseline": "전년 동기(동일 보고서)",
                         "compared": period, "delta": delta}}


def _dividend_row(rows):
    for r in rows:
        if "주당" in r.get("se", "") and "현금배당금" in r.get("se", "") and _won(r.get("thstrm")) is not None:
            return r
    return None


def _rule_div(reason, corp, as_of) -> dict:
    item = get_report_item(corp, "dividend", as_of)
    if item.get("status") != "ok":
        return _absence("RULE-DIV-01")
    latest_year = max(item["years"])
    row = _dividend_row(item["years"][latest_year])
    if not row:
        return _absence("RULE-DIV-01")
    status, delta = div_status(_won(row["thstrm"]), _won(row.get("frmtrm")))
    rcp = row.get("rcept_no", "")
    return {"status": status, "rule_id": "RULE-DIV-01",
            "evidence": {"rcp_no": rcp, "url": _viewer(rcp), "item": "주당 현금배당금",
                         "baseline": f"직전 동일 주기({latest_year} 전기)", "compared": f"{latest_year} 당기", "delta": delta}}


def _rule_ret(reason, corp, as_of) -> dict:
    events = get_events(corp, ["treasury"], "2000-01-01", as_of, as_of)
    if not events:
        return _absence("RULE-RET-01")
    latest = events[-1]
    status, note = ret_status(latest["title"])
    rcp = latest["rcp_no"]
    return {"status": status, "rule_id": "RULE-RET-01",
            "evidence": {"rcp_no": rcp, "url": _viewer(rcp), "item": "자기주식", "delta": note}}


def _rule_grw(reason, corp, as_of) -> dict:
    events = get_events(corp, ["supply_contract", "facility_investment", "capital_change"],
                        "2000-01-01", as_of, as_of)
    status, note = growth_status([e["title"] for e in events])
    rcp = reason.get("source_rcp_no") or ""
    return {"status": status, "rule_id": "RULE-GRW-01",
            "evidence": {"rcp_no": rcp, "url": _viewer(rcp) if rcp else "", "item": "투자·계약", "delta": note}}


def _rule_new(reason, corp, as_of) -> dict:
    events = get_events(corp, ["new_business"], "2000-01-01", as_of, as_of)
    status, note = new_status(has_followup=bool(events), long_silence=not events)
    rcp = reason.get("source_rcp_no") or ""
    return {"status": status, "rule_id": "RULE-NEW-01",
            "evidence": {"rcp_no": rcp, "url": _viewer(rcp) if rcp else "", "item": "신사업", "delta": note}}


_RULES = {
    "earnings_improvement": _rule_earn,
    "shareholder_return": _rule_ret,
    "dividend": _rule_div,
    "growth_order": _rule_grw,
    "new_business": _rule_new,
}


def _unverifiable(rtype: str) -> dict:
    meta = _UNVERIFIABLE.get(rtype, {"rule_id": None, "note": "판정 대상이 아닙니다."})
    return {"status": "unverifiable", "rule_id": meta.get("rule_id"),
            "evidence": {"note": meta.get("note")}}


def evaluate(reason: dict, corp_code: str, as_of: str) -> dict:
    """원장 reason 하나를 as_of 시점 공시에 대조해 판정한다."""
    rtype = reason.get("type")
    if rtype in _RULES:
        return _RULES[rtype](reason, corp_code, as_of)
    return _unverifiable(rtype)
