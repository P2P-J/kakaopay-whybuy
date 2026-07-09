"""스킬 파이프라인 진입점 (컨트랙트 명령) — whybuy (G6).

파이프라인 규약(0.7 / 부록 D): 각 스킬의 파이프라인 로직은 import 가능한 순수
함수로 작성하고, argparse CLI는 그 함수를 호출하는 얇은 래퍼일 뿐이다. 테스트는
CLI를 거치지 않고 함수를 직접 호출한다. (HTTP 래핑 확장이 이 규약에 걸려 있다.)

timeline 서브커맨드: PRD 4.1 8단계(수집→분류→노이즈 필터→변하지 않은 것→급변 매칭
→수익률·시장 대비→템플릿 조립→게이트→저장). MCP 도구 대신 dart_client를 직접 호출한다
(같은 픽스처 계층). as_of 필터는 dart_client가 강제.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import dart_client as dc  # noqa: E402
import detect_moves as dmv  # noqa: E402
import render as rnd  # noqa: E402
import textstore as ts  # noqa: E402
import yaml  # noqa: E402
from classify import classify  # noqa: E402
from compliance_gate import check as gate_check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

# 타임라인 본문에 표기하는 화이트리스트 이벤트 (major_shareholder 반복성 지분공시는 접고,
# 최대주주 실체는 "변하지 않은 것"에서 report_item으로 대조 — 노이즈 필터 PRD 4.1 step4)
_WHITELIST = {"earnings", "dividend", "treasury", "capital_change", "audit",
              "litigation", "supply_contract", "facility_investment", "business_halt"}
_FIXED_ITEMS = [("major_shareholder", "최대주주"), ("audit_opinion", "감사의견"), ("dividend", "배당 정책")]


def _load_case(case_id: str) -> dict:
    cases = json.loads((FIX / "cases.json").read_text(encoding="utf-8"))["cases"]
    for c in cases:
        if c["case_id"] == case_id:
            return c
    raise KeyError(f"case_id 없음: {case_id}")


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _close_on(rows: list[dict], target: str):
    """target 이하 마지막 거래일의 (date, close). 휴장일이면 직전 거래일."""
    prior = [r for r in rows if r["date"] <= target]
    return (prior[-1]["date"], prior[-1]["close"]) if prior else (None, None)


def _won(s):
    if s in (None, "", "-"):
        return None
    try:
        return int(str(s).replace(",", ""))
    except ValueError:
        return None


def _money(a) -> str:
    if a is None:
        return "?"
    return f"{a/1e12:.1f}조원" if abs(a) >= 1e12 else f"{a/1e8:.0f}억원"


_PERIODS = [f"{y}{q}" for y in ("2026", "2025", "2024") for q in ("4Q", "3Q", "2Q", "1Q")]


def _latest_op_fact(corp_code: str, as_of: str):
    """as_of 이하 최신 '확정' 영업이익 사실(판정 딱지 없이 수치만). 없으면 None."""
    for p in sorted(_PERIODS, reverse=True):
        blk = dc.get_financials(corp_code, p[:4], p[4:], as_of)
        if blk.get("status") != "ok":
            continue
        op = next((a for a in blk["accounts"] if a["account_nm"] == "영업이익"), None)
        if not op:
            continue
        th, fr = _won(op["thstrm_amount"]), _won(op["frmtrm_amount"])
        if fr and fr > 0:
            yoy = f"전년 동기 대비 {(th - fr) / fr * 100:+.0f}%"
        elif fr is not None and fr <= 0 and th is not None and th > 0:
            yoy = "전년 동기 적자에서 흑자 전환"
        else:
            yoy = "전년 동기와 비교"
        return f"최근 확정 영업이익 {_money(th)}, {yoy} ({p}·{blk.get('basis')})"
    return None


# ── 단계별 순수 함수 ──────────────────────────────────────────────
def collect_changed(corp_code: str, buy_date: str, as_of: str) -> tuple[list, int]:
    """공시 수집 → 분류 → 노이즈 필터. (화이트리스트 이벤트, 접은 그 외 건수).

    실적(earnings) 이벤트에는 영업이익 사실 수치를 병기한다 — 판정 딱지(유효/반증)는
    붙이지 않는다(여기는 타임라인, 수치는 사실이라 허용, 딱지는 판단이라 금지)."""
    changed, other = [], 0
    op_fact = _latest_op_fact(corp_code, as_of)
    for d in dc.list_disclosures(corp_code, buy_date, as_of, None, as_of):
        c = classify(d.get("title", ""), d.get("pblntf_ty"))
        if c["type"] in _WHITELIST:
            e = {"date": d["submitted"], "event_type": c["type"],
                 "title": d["title"].strip(), "url": d["url"]}
            if c["type"] == "earnings" and op_fact:
                e["fact"] = op_fact
            changed.append(e)
        else:
            other += 1
    return changed, other


def _repr_fixed(item: str, state: dict):
    """report_item 상태에서 대표값·근거 rcp 추출."""
    latest = state["years"][max(state["years"])]
    if item == "major_shareholder":
        # 합계(계/합계) 행 제외, '최대주주 본인' 행 우선 선택
        named = [r for r in latest if r.get("nm") not in ("계", "합계", "-", "", None)]
        owner = [r for r in named if "본인" in r.get("relate", "")]
        row = (owner or named or latest)[0]
        return f"{row.get('nm', '?')} ({row.get('trmend_posesn_stock_qota_rt', '?')}%)", row.get("rcept_no", "")
    if item == "audit_opinion":
        row = latest[0]
        return row.get("adt_opinion", "?"), row.get("rcept_no", "")
    # dividend
    row = next((r for r in latest if "주당" in r.get("se", "") and "현금배당금" in r.get("se", "")
                and r.get("thstrm") not in (None, "-", "")), latest[0])
    return f"주당 현금배당금 {row.get('thstrm', '?')}원", row.get("rcept_no", "")


def collect_unchanged(corp_code: str, buy_date: str, as_of: str) -> list[dict]:
    """감시 고정 항목(최대주주·감사의견·배당)의 매수 시점 대비 as_of 상태."""
    out = []
    for item, label in _FIXED_ITEMS:
        now = dc.get_report_item(corp_code, item, as_of)
        if now.get("status") != "ok":
            continue
        val, rcp = _repr_fixed(item, now)
        then = dc.get_report_item(corp_code, item, buy_date)
        then_val = _repr_fixed(item, then)[0] if then.get("status") == "ok" else None
        if item == "audit_opinion":
            note = "최근 사업보고서 기준"
        elif then_val == val:
            note = "매수 시점과 동일"
        else:
            note = "매수 이후 변경됨"
        out.append({"label": label, "value": val, "note": note,
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"})
    return out


def _match_disclosures(move_date: str, disclosures: list[dict]) -> str:
    """급변일 [D-1,D+1] 창의 화이트리스트 공시만 매칭 (노이즈 필터와 동일 기준 —
    IR 등 반복성 공시가 급락 근거로 오인되지 않게)."""
    lo = date.fromisoformat(move_date).toordinal() - 1
    hi = date.fromisoformat(move_date).toordinal() + 1
    hits = [d["title"].strip() for d in disclosures
            if lo <= date.fromisoformat(d["submitted"]).toordinal() <= hi
            and classify(d.get("title", ""), d.get("pblntf_ty"))["type"] in _WHITELIST]
    if hits:
        return "매칭: " + ", ".join(hits[:3])
    return ts.MOVE_NO_MATCH


def build_moves_block(ticker: str, buy_date: str, as_of: str, disclosures: list[dict]) -> dict:
    rows = dc.price_get_daily(ticker, "2000-01-01", as_of)  # z-score용 이력 포함
    res = dmv.detect_moves(rows, CFG["price_move"])
    window = [m for m in res["moves"] if buy_date <= m["date"] <= as_of]
    cap = CFG["timeline"]["move_display_cap"]
    shown = window[:cap]
    for m in shown:
        m["match"] = _match_disclosures(m["date"], disclosures)
    note = res["threshold_note"]
    if len(window) > cap:
        note += f" · 급변 {len(window)}건 중 {cap}건 표기(초과분 접음)"
    missing = [d for d in res["missing_days"] if buy_date <= d <= as_of]
    return {"moves": shown, "missing_days": missing, "threshold_note": note}


def build_return_block(case: dict, as_of: str) -> dict:
    ticker, buy_date, market = case["ticker"], case["buy_date"], case["market"]
    prices = dc.price_get_daily(ticker, "2000-01-01", as_of)
    buy_d, buy_close = _close_on(prices, buy_date)
    _, asof_close = _close_on(prices, as_of)
    buy_price = case.get("scene", {}).get("buy_price")
    if buy_price:
        base, basis = float(buy_price), f"실제 체결가 {buy_price}원"
    else:
        base, basis = buy_close, f"매수일({buy_d}) 종가 {buy_close:.0f}원 — 실제 체결가와 다를 수 있는 참고치"
    stock_ret = (asof_close - base) / base * 100

    idx = dc.price_get_daily(f"index_{market}", "2000-01-01", as_of)
    _, ib = _close_on(idx, buy_date)
    _, ia = _close_on(idx, as_of)
    mkt_ret = (ia - ib) / ib * 100

    band = CFG["market_compare"]["similar_band_pp"]
    diff = stock_ret - mkt_ret
    tag = "유사" if abs(diff) <= band else ("상회" if diff > 0 else "하회")
    return {"stock_return_pct": stock_ret, "market_return_pct": mkt_ret,
            "market_tag": tag, "basis_note": basis}


def build_timeline(case_id: str, as_of: str | None = None, with_price_overlay: bool = True) -> dict:
    """PRD 4.1 파이프라인(저장·게이트 제외)을 실행해 render용 ctx를 만든다. 순수(디스크 읽기만)."""
    case = _load_case(case_id)
    as_of = as_of or case["as_of"]
    corp, ticker, buy_date = case["corp_code"], case["ticker"], case["buy_date"]

    disclosures = dc.list_disclosures(corp, buy_date, as_of, None, as_of)
    changed, other = collect_changed(corp, buy_date, as_of)
    unchanged = collect_unchanged(corp, buy_date, as_of)
    moves_block = (build_moves_block(ticker, buy_date, as_of, disclosures)
                   if with_price_overlay else {"moves": [], "missing_days": [], "threshold_note": ""})
    return {
        "case_id": case_id, "corp_name": case["corp_name"], "market": case["market"],
        "buy_date": buy_date, "as_of": as_of, "days_elapsed": _days(buy_date, as_of),
        "changed": changed, "other_count": other, "unchanged": unchanged,
        "moves_block": moves_block, "return_block": build_return_block(case, as_of),
    }


def run_timeline(case_id: str, as_of: str | None = None, with_price_overlay: bool = True) -> dict:
    """빌드 → 조립 → 게이트 → 저장. {path, violations} 반환."""
    ctx = build_timeline(case_id, as_of, with_price_overlay)
    md = rnd.render_timeline(ctx)
    violations = gate_check(md)
    out_dir = ROOT / "reports" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"timeline-{ctx['as_of']}.md"
    path.write_text(md, encoding="utf-8")
    return {"path": str(path), "violations": violations, "as_of": ctx["as_of"]}


# ── reason-recall (PRD 4.2) ───────────────────────────────────────
# 유형 → (보기 라벨, 클레임 템플릿 PRD 5.3)
_REASON_META = {
    "earnings_improvement": ("실적 개선 기대", "전사 영업이익이 개선 추세다"),
    "shareholder_return": ("주주환원 기대", "회사가 자기주식 취득 등 주주환원을 실행한다"),
    "dividend": ("배당 목적", "배당이 유지 또는 확대된다"),
    "growth_order": ("성장·수주 기대", "발표된 투자/계약이 정상 진행된다"),
    "new_business": ("신사업 기대", "신사업이 공식 기록상 진행된다"),
    "theme": ("시장·커뮤니티 분위기·추천", "당시 시장 분위기나 추천을 보고 샀다"),
    "price_anchor": ("저가 매수", "주가가 저점이라고 보고 샀다"),
    "unknown": ("잘 모르겠음", ""),
}
# 공시 세부유형 → 매수 논거 유형 (악재성 capital_change 등은 제외)
_DISC_BUYREASON = {"earnings": "earnings_improvement", "treasury": "shareholder_return",
                   "dividend": "dividend", "supply_contract": "growth_order",
                   "facility_investment": "growth_order"}
# 사유 라이브러리 보기 문구
_LIBRARY_LABEL = {
    "theme": "당시 해당 종목의 시장·커뮤니티 분위기나 추천 때문에",
    "price_anchor": "주가가 많이 떨어져서 싸 보여서",
    "dividend": "배당 받으려고",
    "earnings_improvement": "오래 갖고 갈 우량 기업이라고 생각해서",
    "unknown": "그냥 유명해서 / 잘 모르겠음",
}
_Q1_OPTIONS = ["유튜브·SNS", "커뮤니티·지인 추천", "뉴스 기사", "원래 알던 회사", "직접 입력"]
_Q3_OPTIONS = ["단기", "수개월", "장기", "생각 안 해봄"]
# 직접 입력 정적 키워드 분류 (보수적 — 확신 없으면 unknown)
_CUSTOM_KW = {"배당": "dividend", "영업이익": "earnings_improvement", "실적": "earnings_improvement",
              "자사주": "shareholder_return", "자기주식": "shareholder_return",
              "공급계약": "growth_order", "수주": "growth_order", "신사업": "new_business"}


def _has_valid_op(corp_code: str, as_of: str) -> bool:
    """영업이익 계정 존재·유효 여부 (금융지주 안전핀 — 없으면 earnings 라이브러리 미노출)."""
    for p in sorted(_PERIODS, reverse=True):
        blk = dc.get_financials(corp_code, p[:4], p[4:], as_of)
        if blk.get("status") == "ok":
            return any(a["account_nm"] == "영업이익" for a in blk["accounts"])
    return False


def classify_custom(text: str) -> str:
    """직접 입력 정적 분류 (보수적): 키워드 확신 시에만 유형, 아니면 unknown."""
    for kw, t in _CUSTOM_KW.items():
        if kw in text:
            return t
    return "unknown"


def build_recall(case_id: str, as_of: str | None = None) -> dict:
    """lookback 공시 → 결정적 후보(공시 r1..) + 라이브러리 + Q1/Q3. 미래 정보 차단."""
    case = _load_case(case_id)
    corp, buy = case["corp_code"], case["buy_date"]
    cfg = CFG["recall"]
    d_from = (date.fromisoformat(buy) - timedelta(days=cfg["lookback_before_days"])).isoformat()
    cand_asof = as_of or (date.fromisoformat(buy) + timedelta(days=cfg["lookback_after_days"])).isoformat()

    # 공시 후보 (스크립트 확정 분류분만, 매수 논거 유형, 매수일 근접순, 최대 4)
    seen, cands = set(), []
    for d in dc.list_disclosures(corp, d_from, cand_asof, None, cand_asof):
        c = classify(d.get("title", ""), d.get("pblntf_ty"))
        rt = _DISC_BUYREASON.get(c["type"])
        if not rt or (c["type"] == "treasury" and "처분" in d["title"]):
            continue
        if rt in seen:                      # 유형 중복 방지
            continue
        seen.add(rt)
        cands.append({"submitted": d["submitted"], "type": rt, "rcp_no": d["rcp_no"], "title": d["title"].strip()})
    cands.sort(key=lambda x: (abs(date.fromisoformat(x["submitted"]).toordinal()
                                  - date.fromisoformat(buy).toordinal()), x["rcp_no"]))
    disclosure = []
    for i, c in enumerate(cands[:4], 1):
        label, claim = _REASON_META[c["type"]]
        disclosure.append({"id": f"r{i}", "type": c["type"], "label": label, "claim": claim,
                           "source": "disclosure", "source_rcp_no": c["rcp_no"], "evidence_title": c["title"]})

    # 라이브러리 (노출 규칙): 항상 theme·price_anchor·unknown, dividend는 배당이력 있을 때,
    # earnings는 공시 후보에 실적 없고 영업이익 계정 유효할 때(안전핀). 총 Q2 ≤ 8.
    has_earn_disc = any(c["type"] == "earnings_improvement" for c in disclosure)
    lib_types = ["theme", "price_anchor", "unknown"]
    if dc.get_report_item(corp, "dividend", cand_asof).get("status") == "ok":
        lib_types.insert(0, "dividend")
    if (not has_earn_disc) and _has_valid_op(corp, cand_asof):
        lib_types.insert(0, "earnings_improvement")
    room = 8 - len(disclosure) - 1          # custom 슬롯 1 예약
    library = []
    for t in lib_types[:max(room, 2)]:      # 고정 보기 최소 2 보장
        label, claim = _REASON_META[t]
        library.append({"id": f"lib_{t}", "type": t, "label": _LIBRARY_LABEL[t], "claim": claim,
                        "source": "library", "source_rcp_no": None})

    return {"case_id": case_id, "corp_name": case["corp_name"], "buy_date": buy, "as_of": cand_asof,
            "q1_options": _Q1_OPTIONS, "q3_options": _Q3_OPTIONS,
            "disclosure_candidates": disclosure, "library_candidates": library,
            "unknown_mode_note": "‘잘 모르겠음’ 단독 선택 시 thesis-audit은 판정 대신 타임라인 요약 모드로 동작합니다."}


def choose_reasons(recall: dict, chosen_ids: list[str], custom_text: str | None = None) -> list[dict]:
    """선택된 후보 ID → 원장 reason 레코드. 미래 정보 없음(후보가 이미 lookback 내)."""
    by_id = {c["id"]: c for c in recall["disclosure_candidates"] + recall["library_candidates"]}
    reasons = []
    for i, cid in enumerate(chosen_ids, 1):
        c = by_id.get(cid)
        if not c:
            raise KeyError(f"후보 ID 없음: {cid} (가능: {', '.join(by_id)})")
        reasons.append({"reason_id": f"r{i}", "type": c["type"], "label": c["label"], "claim": c["claim"],
                        "source": c["source"], "user_text": None,
                        "source_rcp_no": c.get("source_rcp_no"), "selected_at": recall["as_of"]})
    if custom_text:
        t = classify_custom(custom_text)
        label, claim = _REASON_META[t]
        reasons.append({"reason_id": f"r{len(reasons)+1}", "type": t, "label": "직접 입력", "claim": claim,
                        "source": "custom", "user_text": custom_text,
                        "source_rcp_no": None, "selected_at": recall["as_of"]})
    return reasons


def commit_reasons(case_id: str, reasons: list[dict], context: dict | None = None) -> None:
    """선택 결과를 원장에 기록 (스키마 검증 통과 시에만 — ledger_store가 강제)."""
    import ledger_store as ls
    case = _load_case(case_id)
    record = {"case_id": case_id, "ticker": case["ticker"], "corp_code": case["corp_code"],
              "corp_name": case["corp_name"], "buy_date": case["buy_date"], "is_fixture": True,
              "context": context or {"q1_channel": "unspecified", "q3_horizon": "unspecified"},
              "reasons": reasons, "audits": []}
    ls.upsert_case(record)


def run_recall(case_id: str, choose: str | None, custom_text: str | None,
               commit: bool, as_of: str | None = None) -> dict:
    recall = build_recall(case_id, as_of)
    chosen = [c.strip() for c in choose.split(",")] if choose else []
    reasons = choose_reasons(recall, chosen, custom_text)
    md = rnd.render_recall_confirm(recall, reasons)
    violations = gate_check(md)
    if commit and not violations:
        commit_reasons(case_id, reasons)
    return {"recall": recall, "reasons": reasons, "briefing": md,
            "violations": violations, "committed": commit and not violations}


# ── thesis-audit + 거울 모드 (PRD 4.3) ────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verdict_engine as ve  # noqa: E402

# 신규 중대 사실 유형 (논거와 무관하게 알아야 할 것)
_MATERIAL_TYPES = {"capital_change", "litigation", "business_halt"}


def scan_new_material(corp_code: str, buy_date: str, as_of: str, linked_rcps=frozenset()) -> list[dict]:
    """신규 중대 사실: 중대 유형 ∧ 매수일 이후 제출 ∧ 원장 논거와 미연결(3조건 코드 고정).

    중대 유형 = 증자·CB·감자(capital_change)·소송(litigation)·사업중단(business_halt)
    ·자기주식 처분(treasury 처분)·최대주주 변경(major_shareholder 변경)."""
    out = []
    for e in dc.get_events(corp_code, None, buy_date, as_of, as_of):
        t, title = e["event_type"], e["title"].strip()
        material = (t in _MATERIAL_TYPES
                    or (t == "treasury" and "처분" in title)
                    or (t == "major_shareholder" and "최대주주변경" in title))
        if material and e["rcp_no"] not in linked_rcps:   # 원장 논거와 미연결
            out.append({"date": e["submitted"], "title": title,
                        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={e['rcp_no']}"})
    return out


def build_audit(case_id: str, as_of: str | None = None, mirror: bool = False) -> dict:
    """원장 논거를 as_of 시점 공시에 대조. 판정은 verdict_engine(결정적). 순수(디스크 읽기만)."""
    import ledger_store as ls
    case = _load_case(case_id)
    corp, buy = case["corp_code"], case["buy_date"]
    as_of = as_of or case["as_of"]
    ledger_case = ls.read(case_id)
    reasons = ledger_case["reasons"] if ledger_case else []

    verdicts = []
    for r in reasons:
        v = ve.evaluate(r, corp, as_of)
        verdicts.append({"reason_id": r["reason_id"], "label": r["label"], "claim": r["claim"],
                         "status": v["status"], "rule_id": v["rule_id"], "evidence": v["evidence"]})
    linked = frozenset(r.get("source_rcp_no") for r in reasons if r.get("source_rcp_no"))
    ctx = {"case_id": case_id, "corp_name": case["corp_name"], "market": case["market"],
           "buy_date": buy, "as_of": as_of, "days_elapsed": _days(buy, as_of),
           "verdicts": verdicts, "new_material": scan_new_material(corp, buy, as_of, linked)}
    if mirror:
        rb = build_return_block(case, as_of)
        ctx["return_block"] = rb
        # 상태별 거울 질문: 손실+반증→기본, 수익→수익률 프레이밍, 손실인데 유효→사실vs가격 엇갈림
        if any(v["status"] == "refuted" for v in verdicts):
            ctx["mirror_question"] = ts.MIRROR_QUESTION
        elif rb["stock_return_pct"] >= 0:
            ctx["mirror_question"] = ts.MIRROR_QUESTION_PROFIT
        else:
            ctx["mirror_question"] = ts.MIRROR_QUESTION_HOLD
    return ctx


def run_audit(case_id: str, as_of: str | None, mirror: bool, commit: bool) -> dict:
    """빌드 → 조립(mirror 여부) → 게이트 → 저장 → 원장 audits[] append(commit 시)."""
    ctx = build_audit(case_id, as_of, mirror)
    md = rnd.render_mirror(ctx) if mirror else rnd.render_audit(ctx)
    violations = gate_check(md)
    out_dir = ROOT / "reports" / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    kind = "mirror" if mirror else "audit"
    path = out_dir / f"{kind}-{ctx['as_of']}.md"
    path.write_text(md, encoding="utf-8")
    if commit and not violations:
        import ledger_store as ls
        audit = {"run_at": f"{ctx['as_of']}T00:00:00+09:00", "as_of": ctx["as_of"],
                 "verdicts": [{"reason_id": v["reason_id"], "status": v["status"],
                               "rule_id": v["rule_id"] or "RULE-NONE",
                               "evidence": {k: val for k, val in v["evidence"].items()}}
                              for v in ctx["verdicts"]],
                 "new_material_facts": [f["title"] for f in ctx["new_material"]]}
        ls.append_audit(case_id, audit)
    return {"path": str(path), "violations": violations, "briefing": md,
            "committed": commit and not violations}


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_skill")
    sub = ap.add_subparsers(dest="skill", required=True)
    t = sub.add_parser("timeline")
    t.add_argument("--case", required=True)
    t.add_argument("--as-of", default=None)
    t.add_argument("--no-price-overlay", action="store_true")
    r = sub.add_parser("recall")
    r.add_argument("--case", required=True)
    r.add_argument("--choose", default=None)
    r.add_argument("--custom-text", default=None)
    r.add_argument("--as-of", default=None)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--commit", action="store_true")
    a = sub.add_parser("audit")
    a.add_argument("--case", required=True)
    a.add_argument("--as-of", default=None)
    a.add_argument("--mirror", action="store_true")
    a.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    if args.skill == "timeline":
        res = run_timeline(args.case, args.as_of, not args.no_price_overlay)
        print(f"저장: {res['path']}")
        if res["violations"]:
            print("게이트 위반:")
            for v in res["violations"]:
                print(f"  - {v}")
            return 1
        print("게이트 PASS")
        return 0
    if args.skill == "recall":
        res = run_recall(args.case, args.choose, args.custom_text, args.commit and not args.dry_run, args.as_of)
        print(res["briefing"])
        if res["violations"]:
            print("게이트 위반:", res["violations"])
            return 1
        print(f"[{'커밋됨' if res['committed'] else 'dry-run(미기록)'}] 논거 {len(res['reasons'])}건")
        return 0
    if args.skill == "audit":
        res = run_audit(args.case, args.as_of, args.mirror, args.commit)
        print(f"저장: {res['path']}")
        if res["violations"]:
            print("게이트 위반:")
            for v in res["violations"]:
                print(f"  - {v}")
            return 1
        print(f"게이트 PASS{' · audits[] 기록됨' if res['committed'] else ''}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
