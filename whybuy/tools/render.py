"""브리핑 템플릿 조립 단일 모듈 (0.7-4) — whybuy (G6).

브리핑 조립은 이 한 모듈에만 존재한다. 스킬 코드에 템플릿 문자열을 인라인으로
흩뿌리지 않는다. 고정 문구는 textstore에서 임포트해 게이트와 어긋나지 않게 한다.
수치 포맷(±N%)도 여기 한 곳에서 생성한다. 에이전트 서술이 없어도 완성 브리핑이
나오는 정적 경로: 이벤트 유형별 기본 서술문(_EVENT_SUMMARY).
"""
from __future__ import annotations

import textstore as ts

# 이벤트 유형별 기본 서술문 (Codex 없이 도는 정적 실행 경로)
_EVENT_SUMMARY = {
    "earnings": "실적(잠정 또는 정기)이 공시되었습니다",
    "dividend": "배당 관련 결정이 공시되었습니다",
    "treasury": "자기주식 관련 결정 또는 결과가 공시되었습니다",
    "capital_change": "자본구조 변경(증자·전환사채·감자)이 공시되었습니다",
    "audit": "감사보고서가 제출되었습니다",
    "litigation": "소송·제재 관련 공시가 있었습니다",
    "supply_contract": "단일판매·공급계약이 공시되었습니다",
    "facility_investment": "신규 시설투자가 공시되었습니다",
    "business_halt": "영업정지·사업중단이 공시되었습니다",
}

_MARKET_KO = {"kospi": "코스피", "kosdaq": "코스닥", "konex": "코넥스"}


def pct(x: float) -> str:
    """수치 포맷 단일 출처: 항상 부호 + 소수 1자리 %."""
    return f"{x:+.1f}%"


def event_summary(event_type: str) -> str:
    return _EVENT_SUMMARY.get(event_type, "공시가 있었습니다")


def market_ko(market: str) -> str:
    return _MARKET_KO.get(market, market)


def render_timeline(ctx: dict) -> str:
    """PRD 4.1 타임라인 브리핑 마크다운 조립. ctx는 run_skill의 순수 파이프라인 산출."""
    L = []
    L.append(f"# {ctx['buy_date']}, 당신이 산 이후 {ctx['corp_name']}에 일어난 일")
    L.append("")
    L.append(f"> {ts.as_of_notice(ctx['as_of'])} (매수 후 {ctx['days_elapsed']}일 경과)")
    r = ctx["return_block"]
    L.append(
        f"> 보유 수익률(참고): {pct(r['stock_return_pct'])} "
        f"(기준: {r['basis_note']}, 배당 미반영) · 같은 기간 {market_ko(ctx['market'])} "
        f"{pct(r['market_return_pct'])} → 시장 대비 {r['market_tag']}"
    )
    L.append("")

    # 변한 것
    L.append("## 변한 것")
    if ctx["changed"]:
        for e in ctx["changed"]:
            line = f"- {e['date']}: {event_summary(e['event_type'])} [{e['title']}, 원문]({e['url']})"
            if e.get("fact"):
                line += f" · {e['fact']}"     # 사실 수치 병기(판정 딱지 없음)
            L.append(line)
    else:
        L.append("- 이 기간 화이트리스트 유형(실적·배당·자기주식·자본변경·감사·소송·공급·시설·사업중단)의 공시는 없었습니다.")
    if ctx["other_count"]:
        L.append(f"> 그 외 공시 {ctx['other_count']}건은 접었습니다 (임원 지분변동·기업설명회 등 반복성 공시). "
                 f"전체 목록은 원장 disclosures 픽스처에서 확인할 수 있습니다.")
    L.append("")

    # 변하지 않은 것
    L.append("## 변하지 않은 것")
    for u in ctx["unchanged"]:
        L.append(f"- {u['label']}: {u['value']} ({u['note']}) [근거 공시 원문]({u['url']})")
    L.append("")

    # 주가가 크게 움직인 날
    L.append("## 주가가 크게 움직인 날 (참고)")
    mv = ctx["moves_block"]
    if mv["moves"]:
        for m in mv["moves"]:
            L.append(f"- {m['date']}: {pct(m['change_pct'])} ← {m['match']}")
    else:
        L.append(f"- {mv['threshold_note']}을 넘는 가격 변동은 이 기간에 없었습니다.")
    if mv["missing_days"]:
        L.append(f"> 거래 데이터 결측일(거래정지 등): {', '.join(mv['missing_days'])}")
    L.append("")

    L.append("---")
    L.append(ts.DISCLAIMER)
    return "\n".join(L) + "\n"


_STATUS_KO = {"supported": "유효", "weakened": "약화", "refuted": "반증", "unverifiable": "확인불가"}


def verdict_line(v: dict) -> str:
    """판정 한 줄. 유효/약화/반증은 원문 URL 필수, 확인불가는 부재 사실 문구(게이트 차등 대응)."""
    ko = _STATUS_KO[v["status"]]
    e = v.get("evidence", {})
    if v["status"] == "unverifiable":
        return f"- {v['label']}: **{ko}** — {e.get('note', '')} (대조를 시도한 공시 기록에 해당 사실 부재)"
    return (f"- {v['label']}: **{ko}** — {e.get('item', '')} {e.get('compared', '')}, "
            f"{e.get('delta', '')} [원문]({e.get('url', '')}) (rule: {v['rule_id']})")


def _material_lines(facts: list[dict]) -> list[str]:
    if not facts:
        return ["- 논거와 무관한 새로운 중대 사실은 없었습니다."]
    return [f"- {f['date']}: {f['title']} [원문]({f['url']}){ts.gloss(f['title'])}" for f in facts]


def render_audit(ctx: dict) -> str:
    """thesis-audit 브리핑. 판정 + 신규 중대 사실."""
    L = [f"# {ctx['corp_name']} — 산 이유, 아직 유효한가 ({ctx['as_of']})", ""]
    L.append(f"> {ts.as_of_notice(ctx['as_of'])}")
    L.append("")
    L.append("## 논거 판정")
    for v in ctx["verdicts"]:
        L.append(verdict_line(v))
    L.append("")
    L.append(f"## {ts.NEW_FACTS_HEADER}")
    L.extend(_material_lines(ctx["new_material"]))
    L.append("")
    L.append(ts.REFUTED_DEFINITION)
    L.append("")
    L.append("---")
    L.append(ts.DISCLAIMER)
    return "\n".join(L) + "\n"


def render_mirror(ctx: dict) -> str:
    """거울 모드: 과거(기록한 이유) — 현재(수익률+판정+신규사실) — 고정 질문."""
    L = [f"# {ctx['corp_name']} — 매도 버튼 앞에서", ""]
    L.append(f"> {ts.as_of_notice(ctx['as_of'])} (매수 후 {ctx['days_elapsed']}일 경과)")
    L.append("")
    L.append("## 그때 — 당신이 기록한 매수 이유")
    for v in ctx["verdicts"]:
        L.append(f"- {v['label']}: “{v['claim']}”")
    L.append("")
    L.append(f"## 지금 — {ctx['as_of']}")
    r = ctx["return_block"]
    L.append(f"> 보유 수익률(참고): {pct(r['stock_return_pct'])} · 같은 기간 {market_ko(ctx['market'])} "
             f"{pct(r['market_return_pct'])} → 시장 대비 {r['market_tag']}")
    for v in ctx["verdicts"]:
        L.append(verdict_line(v))
    L.append("")
    L.append(f"### {ts.NEW_FACTS_HEADER}")
    L.extend(_material_lines(ctx["new_material"]))
    L.append("")
    L.append(f"## {ctx.get('mirror_question', ts.MIRROR_QUESTION)}")
    L.append("")
    L.append(ts.REFUTED_DEFINITION)
    L.append("")
    L.append("---")
    L.append(ts.DISCLAIMER)
    return "\n".join(L) + "\n"


def render_prebuy(ctx: dict) -> str:
    """매수 전 점검 브리핑. 존재의 정직(있으면 있다/없으면 없다) + 층위별 근거 구분.

    DART 신호(층2·3)는 rcp 원문 링크, KRX 신호(층1)는 명단 출처+기준일 + 왜 링크가
    다른지 한 줄. "위험 신호" 단어 앞세우지 않고 공식 명칭 + 판단 아님 명시(표현 규칙).
    """
    L = [f"# {ctx['corp_name']}({ctx['ticker']}) 매수 전 점검", ""]
    L.append(f"> {ts.as_of_notice(ctx['as_of'])}")
    L.append(f"> {ts.prebuy_asof_notice(ctx['as_of'])}")     # KRX 명단은 시점 스냅샷 — 기준일 강조
    L.append("")

    L.append(f"## {ts.PREBUY_SECTION_TITLE}")
    if ctx["has_signals"]:
        has_krx = False
        for s in ctx["signals"]:
            line = f"- {s['label']}"
            if s.get("detail"):
                line += f": {s['detail']}"
            if s["source_kind"] == "KRX":
                has_krx = True
                line += f" · 출처: {s['source_name']}, {s['as_of']} 기준 [KRX]({s['source_url']})"
            else:
                url = s.get("evidence", {}).get("url", "")
                if url:
                    line += f" [원문]({url})"
            L.append(line + ts.gloss(s.get("detail", "") + s["label"]))
        if has_krx:
            L.append(f"> {ts.PREBUY_KRX_SOURCE_NOTE}")
    else:
        L.append(f"- {ts.PREBUY_CLEAN} ({ctx['as_of']} 거래소 명단 기준)")
    if not ctx.get("dart_scope", True):
        L.append(f"> {ts.PREBUY_DART_OUT_OF_SCOPE}")
    L.append("")

    if not ctx["has_signals"] and ctx.get("facts"):
        L.append("## 참고로 확인 가능한 사실")
        f = ctx["facts"]
        if f.get("audit"):
            L.append(f"- 최근 감사의견: {f['audit']['opinion']} [원문]({f['audit']['url']})")
        if f.get("profit_streak"):
            L.append(f"- 최근 {f['profit_streak']}분기 연속 영업흑자")
        if f.get("dividend"):
            L.append(f"- 배당: {f['dividend']['value']} [원문]({f['dividend']['url']})")
        if f.get("established"):
            L.append(f"- 업력: {f['established']}년 설립")
        L.append("")

    L.append(f"> {ts.PREBUY_DISCLAIMER}")     # 있음/없음 공통 단일 면책 문구
    L.append("")

    L.append("---")
    L.append(ts.DISCLAIMER)
    return "\n".join(L) + "\n"


def render_recall_confirm(recall: dict, reasons: list[dict]) -> str:
    """reason-recall 선택 확인 브리핑. 사용자가 고른 논거를 사실로 되읽어준다(판정 없음)."""
    L = []
    L.append(f"# {recall['corp_name']} — 산 이유 재구성 (확인)")
    L.append("")
    L.append(f"> {ts.as_of_notice(recall['as_of'])} (후보는 매수일 전후 창의 공시로만 생성)")
    L.append("")
    if reasons:
        L.append("## 기록할 논거")
        for r in reasons:
            src = {"disclosure": "공시 근거", "library": "일반 사유", "custom": "직접 입력"}.get(r["source"], r["source"])
            tail = f" (원문 rcp {r['source_rcp_no']})" if r.get("source_rcp_no") else ""
            L.append(f"- [{src}] {r['label']}: “{r['claim'] or r.get('user_text', '')}”{tail}")
        if any(r["type"] == "unknown" for r in reasons):
            L.append("")
            L.append(f"> {recall['unknown_mode_note']}")
    else:
        L.append("선택된 논거가 없습니다.")
    L.append("")
    L.append("---")
    L.append(ts.DISCLAIMER)
    return "\n".join(L) + "\n"
