"""G7 reason-recall 테스트. run_skill을 CLI 없이 함수로 직접 호출(대화/정적 동일 경로).

미래 정보 누출 0 / 후보 ID 결정성 / 보기 상한·노출 규칙 / 어떤 선택도 스키마 통과 /
unknown 단독 모드 안내 / custom 정적 키워드 분류(골든 원장 밖 — 보수적).
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
os.environ.setdefault("WHYBUY_MODE", "fixture")

import run_skill as rs  # noqa: E402
import validate_ledger as vl  # noqa: E402

KB = "00688996"  # 금융지주 (영업이익 계정 없음 — 안전핀 대상)


def test_no_future_info_leak():
    rc = rs.build_recall("case-001")
    buy = rc["buy_date"]
    lo = (date.fromisoformat(buy) - timedelta(days=30)).isoformat()
    for c in rc["disclosure_candidates"]:
        sub = c["source_rcp_no"][:4] + "-" + c["source_rcp_no"][4:6] + "-" + c["source_rcp_no"][6:8]
        assert lo <= sub <= rc["as_of"], f"미래/구간밖 후보: {sub}"


def test_candidate_ids_deterministic():
    a = rs.build_recall("case-001")
    b = rs.build_recall("case-001")
    assert [c["id"] for c in a["disclosure_candidates"]] == [c["id"] for c in b["disclosure_candidates"]]
    assert [c["source_rcp_no"] for c in a["disclosure_candidates"]] == [c["source_rcp_no"] for c in b["disclosure_candidates"]]


def test_q2_choice_cap_and_fixed_options():
    rc = rs.build_recall("case-001")
    total = len(rc["disclosure_candidates"]) + len(rc["library_candidates"]) + 1  # +custom
    assert total <= 8
    lib_types = {c["type"] for c in rc["library_candidates"]}
    assert {"theme", "unknown"} <= lib_types  # 고정 보기 항상 존재


def test_earnings_library_suppressed_when_earnings_disclosure_present():
    rc = rs.build_recall("case-001")  # r1이 실적(사업보고서) → earnings 라이브러리 중복 미노출
    has_earn_disc = any(c["type"] == "earnings_improvement" for c in rc["disclosure_candidates"])
    lib_earn = any(c["type"] == "earnings_improvement" for c in rc["library_candidates"])
    assert has_earn_disc and not lib_earn


def test_safety_pin_no_op_income_no_earnings_library():
    # 금융지주(영업이익 계정 없음)는 earnings 라이브러리 미노출 (RULE-EARN 오작동 방지)
    assert rs._has_valid_op("00126380", "2025-04-09")   # 삼성: 영업이익 있음
    assert not rs._has_valid_op(KB, "2026-03-20")        # KB금융: 영업이익 없음


def test_any_choice_combo_passes_schema():
    rc = rs.build_recall("case-001")
    combos = [["r1"], ["lib_theme"], ["r1", "lib_theme", "lib_dividend"], ["lib_unknown"]]
    for combo in combos:
        reasons = rs.choose_reasons(rc, combo)
        doc = {"schema_version": 1, "cases": [{
            "case_id": "case-001", "ticker": "005930", "corp_code": "00126380",
            "corp_name": "삼성전자", "buy_date": rc["buy_date"], "is_fixture": True,
            "context": {"q1_channel": "unspecified", "q3_horizon": "unspecified"},
            "reasons": reasons, "audits": []}]}
        assert vl.validate_ledger(doc) == [], f"{combo}: {vl.validate_ledger(doc)}"


def test_unknown_solo_mode_note():
    rc = rs.build_recall("case-001")
    res = rs.run_recall("case-001", "lib_unknown", None, commit=False)
    assert "타임라인 요약 모드" in res["briefing"]
    assert res["violations"] == []


def test_dry_run_does_not_write():
    res = rs.run_recall("case-001", "r1", None, commit=False)
    assert res["committed"] is False


# ── custom 정적 키워드 분류 (골든 원장 밖 — 보수적) ──
def test_custom_keyword_classification():
    assert rs.classify_custom("배당 받으려고 샀어요") == "dividend"
    assert rs.classify_custom("실적이 좋아질 것 같아서") == "earnings_improvement"
    assert rs.classify_custom("자사주 매입한다길래") == "shareholder_return"

def test_custom_conservative_unknown_when_no_keyword():
    # 키워드로 확신 못 하면 확인불가(unknown) — 정적 경로에서 규칙 위반 불가
    assert rs.classify_custom("그냥 느낌이 좋아서") == "unknown"

def test_custom_reason_stored_with_user_text():
    rc = rs.build_recall("case-001")
    reasons = rs.choose_reasons(rc, [], custom_text="배당 보고 샀어요")
    assert reasons[-1]["source"] == "custom" and reasons[-1]["user_text"] == "배당 보고 샀어요"
    assert reasons[-1]["type"] == "dividend"
