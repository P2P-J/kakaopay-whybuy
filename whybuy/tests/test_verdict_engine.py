"""G5 판정 룰 엔진 테스트. verdict_engine.py 대상.

① 룰-카탈로그 일치(유효/약화/반증/확인불가 각 분기, 흑자전환 부호 분기 포함)
② 결정성(동일 입력 2회 동일) ③ 가격 격리(모듈 의존성 검사)
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
os.environ.setdefault("WHYBUY_MODE", "fixture")

import verdict_engine as ve

SAMSUNG, KAKAO, KTG = "00126380", "00258801", "00244455"


# ── RULE-EARN 순수 부호 분기 ──
def test_earn_increase_supported():
    assert ve.earn_status(120, 100)[0] == "supported"

def test_earn_decrease_refuted():
    assert ve.earn_status(80, 100)[0] == "refuted"

def test_earn_turnaround_to_profit_supported():
    # 적자(전년) → 흑자(당기) = 유효 (음수 분모 정의불능 회피)
    assert ve.earn_status(50, -10)[0] == "supported"

def test_earn_turn_to_loss_refuted():
    assert ve.earn_status(-10, 50)[0] == "refuted"

def test_earn_loss_narrowing_weakened():
    # 적자 지속·적자폭 축소 = 약화
    assert ve.earn_status(-5, -10)[0] == "weakened"

def test_earn_loss_widening_refuted():
    assert ve.earn_status(-20, -10)[0] == "refuted"

def test_earn_growth_deceleration_weakened():
    # 증익이나 증가폭이 전기 대비 50%↓ 축소 = 약화
    assert ve.earn_status(105, 100, prev_th=200, prev_fr=100)[0] == "weakened"

def test_earn_strong_growth_supported():
    assert ve.earn_status(150, 100, prev_th=110, prev_fr=100)[0] == "supported"


# ── RULE-DIV 순수 분기 ──
def test_div_increase_supported():
    assert ve.div_status(6000, 5400)[0] == "supported"

def test_div_decrease_weakened():
    assert ve.div_status(1660, 3540)[0] == "weakened"

def test_div_omission_refuted():
    assert ve.div_status(0, 5400)[0] == "refuted"


# ── RULE-RET / GRW / NEW 순수 분기 ──
def test_ret_acquire_supported():
    assert ve.ret_status("주요사항보고서(자기주식취득결정)")[0] == "supported"

def test_ret_dispose_refuted():
    assert ve.ret_status("주요사항보고서(자기주식처분결정)")[0] == "refuted"

def test_growth_no_followup_supported():
    assert ve.growth_status([])[0] == "supported"

def test_growth_terminated_refuted():
    assert ve.growth_status(["단일판매ㆍ공급계약해지"])[0] == "refuted"

def test_growth_scaled_down_weakened():
    assert ve.growth_status(["[기재정정]단일판매ㆍ공급계약체결(규모 축소)"])[0] == "weakened"

def test_new_followup_supported():
    assert ve.new_status(has_followup=True, long_silence=False)[0] == "supported"

def test_new_long_silence_weakened():
    assert ve.new_status(has_followup=False, long_silence=True)[0] == "weakened"


# ── 실데이터 3케이스 (원장 논거 → 판정) ──
def _reason(rtype, rcp="20250311001085"):
    return {"type": rtype, "claim": "x", "source_rcp_no": rcp}

def test_case001_samsung_earnings_supported():
    v = ve.evaluate(_reason("earnings_improvement"), SAMSUNG, "2025-04-09")
    assert v["status"] == "supported" and v["rule_id"] == "RULE-EARN-01"
    assert v["evidence"]["rcp_no"] and v["evidence"]["url"].startswith("https://dart.fss.or.kr")

def test_case002_kakao_earnings_refuted():
    v = ve.evaluate(_reason("earnings_improvement"), KAKAO, "2025-05-14")
    assert v["status"] == "refuted" and v["rule_id"] == "RULE-EARN-01"

def test_case003_ktg_dividend_supported():
    v = ve.evaluate(_reason("dividend"), KTG, "2026-03-20")
    assert v["status"] == "supported" and v["rule_id"] == "RULE-DIV-01"


# ── 확인불가 (라이브러리 유형) ──
def test_theme_unverifiable():
    v = ve.evaluate(_reason("theme"), SAMSUNG, "2025-04-09")
    assert v["status"] == "unverifiable" and v["rule_id"] == "RULE-THM-01"

def test_price_anchor_unverifiable():
    v = ve.evaluate(_reason("price_anchor"), SAMSUNG, "2025-04-09")
    assert v["status"] == "unverifiable" and v["rule_id"] == "RULE-PRC-01"


# ── 데이터 부재: 직전 판정 유지 + 부재 고지 (PRD 제약 6) ──
def test_absence_before_any_financials():
    v = ve.evaluate(_reason("earnings_improvement"), SAMSUNG, "2024-01-01")
    assert v["status"] == "unverifiable"
    assert "부재" in v["evidence"].get("note", "")


# ── 결정성 ──
def test_determinism():
    a = ve.evaluate(_reason("earnings_improvement"), KAKAO, "2025-05-14")
    b = ve.evaluate(_reason("earnings_improvement"), KAKAO, "2025-05-14")
    assert a == b


# ── 가격 격리 (모듈 의존성 검사) ──
def test_price_isolation_source():
    src = inspect.getsource(ve)
    assert "price" not in src.lower(), "verdict_engine에 price 관련 참조 금지"

def test_price_isolation_namespace():
    assert not hasattr(ve, "price_get_daily")
    assert not any("price" in n.lower() for n in dir(ve))
