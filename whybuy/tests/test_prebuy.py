"""G10 매수 전 점검 — 층2·3 DART 위험 스캔 테스트. prebuy_check.py 대상.

순수 분기 헬퍼(오탐 위험 축은 각 분기 명시 테스트) + 실데이터(카카오=클린, KT&G=최대주주
2회 양성) + 가격 격리(scan에 시세 임포트 0). 자본잠식은 별도재무제표(OFS) 기준.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
os.environ.setdefault("WHYBUY_MODE", "fixture")

import prebuy_check as pc  # noqa: E402

KAKAO, KTG = "00258801", "00244455"
AS_OF = "2026-07-10"


# ── 순수 분기 헬퍼 ──
def test_capital_impairment_true_when_total_below_capital():
    assert pc.capital_impairment(50, 100) is True
    assert pc.capital_impairment(150, 100) is False

def test_consecutive_op_loss_needs_full_streak():
    assert pc.consecutive_op_loss([-1, -2, -3, -4], 4) is True
    assert pc.consecutive_op_loss([-1, -2, 5, -4], 4) is False   # 중간 흑자
    assert pc.consecutive_op_loss([-1, -2], 4) is False          # 분기 수 부족

def test_bad_audit_opinion():
    assert pc.is_bad_audit("의견거절") and pc.is_bad_audit("부적정") and pc.is_bad_audit("한정")
    assert not pc.is_bad_audit("적정의견")

def test_going_concern_precise_not_naive():
    assert pc.going_concern("계속기업 관련 중요한 불확실성이 존재") is True
    assert pc.going_concern("계속기업으로서의 존속능력에 유의적 의문") is True
    assert pc.going_concern("해당사항 없음") is False
    assert pc.going_concern("계속기업 가정에 문제 없음") is False   # '계속기업'만으론 오탐 안 남

def test_dilution_count_excludes_corrections_and_capital_reduction():
    events = [
        {"title": "주요사항보고서(전환사채권발행결정)", "is_correction": False},
        {"title": "[기재정정]주요사항보고서(전환사채권발행결정)", "is_correction": True},   # 정정 제외
        {"title": "주요사항보고서(감자결정)", "is_correction": False},                      # 감자 제외(희석 아님)
        {"title": "주요사항보고서(유상증자결정)", "is_correction": False},
    ]
    assert pc.dilution_count(events) == 2   # CB 1 + 유증 1 (정정·감자 제외)


# ── 실데이터: 카카오 = 층2·3 클린 ──
def test_kakao_financial_risk_clean():
    assert pc.scan_financial_risk(KAKAO, AS_OF) == []

def test_kakao_governance_risk_clean():
    assert pc.scan_governance_risk(KAKAO, AS_OF) == []


# ── 자본잠식은 OFS(별도) 기준으로 읽는다 ──
def test_capital_impairment_reads_ofs_basis():
    total, capital, basis, rcp = pc.latest_ofs_capital(KAKAO)
    assert basis == "OFS"
    assert total is not None and capital is not None
    # OFS 자본총계(7.5조)는 CFS(15.2조)와 다름 — 별도 기준으로 읽는다는 증거
    assert total < 10_000_000_000_000


# ── 실데이터: KT&G = 최대주주 2회 변경 양성 ──
def test_ktg_governance_flags_major_change():
    signals = pc.scan_governance_risk(KTG, AS_OF)
    assert any(s["type"] == "major_shareholder_change" for s in signals)


# ── 가격 격리 ──
def test_price_isolation():
    assert "price" not in inspect.getsource(pc).lower()


# ── Task 4: 파이프라인 + render + 게이트 ──
import run_skill as rs  # noqa: E402
import render as rnd  # noqa: E402
from compliance_gate import check as gate_check  # noqa: E402


def test_build_prebuy_kakao_clean_with_facts():
    ctx = rs.build_prebuy("035720")
    assert ctx["has_signals"] is False
    assert ctx["facts"].get("profit_streak", 0) >= 4     # 연속 흑자 사실
    assert ctx["facts"].get("audit")                      # 감사의견 사실

def test_build_prebuy_krx_signals_ticker_based():
    ctx = rs.build_prebuy("368970")                       # 오에스피 — corp 픽스처 밖
    assert ctx["has_signals"] is True
    assert ctx["dart_scope"] is False                     # DART 범위 밖
    assert any(s["source_kind"] == "KRX" and s["label"] == "관리종목" for s in ctx["signals"])

def test_prebuy_no_market_cap_price_data():
    # 시가총액 순위는 가격 데이터라 뺐다 — 브리핑에 순위·시총 없음
    md = rnd.render_prebuy(rs.build_prebuy("035720"))
    assert "시가총액" not in md and "시총" not in md

def test_prebuy_gate_passes_all_paths():
    for tk in ["035720", "368970", "033780"]:            # 없음·KRX있음·DART있음
        assert gate_check(rnd.render_prebuy(rs.build_prebuy(tk))) == [], tk

def test_prebuy_layer_source_distinction():
    md = rnd.render_prebuy(rs.build_prebuy("368970"))
    assert "[KRX]" in md and "개별 공시 원문이 제공되지 않아" in md   # KRX 출처 표기 + 차이 명시


def test_prebuy_disclaimer_unified_no_valuation_word():
    # 면책은 3경로 공통 단일 상수, '우량' 등 판정 단어 없음
    import textstore as ts
    assert "우량" not in ts.PREBUY_DISCLAIMER
    for tk in ["035720", "368970", "033780"]:
        assert ts.PREBUY_DISCLAIMER in rnd.render_prebuy(rs.build_prebuy(tk))


def test_golden_prebuy_kakao():
    md = rnd.render_prebuy(rs.build_prebuy("035720"))
    golden = open(os.path.join(os.path.dirname(__file__), "golden", "prebuy-035720.md"), encoding="utf-8").read()
    assert md == golden, "카카오 매수 전 점검 브리핑이 골든과 다름 (픽스처/템플릿 변경 시 아엔 승인 후 갱신)"


# ── 이름 입력 == 티커 입력 (입구 정규화 보장, 픽스처 모드) ──
def test_prebuy_name_input_equals_ticker_input():
    """종목명으로 쳐도 티커와 완전히 동일한 브리핑(제목·확인가능한 사실 포함)이 나온다.

    corp 픽스처 종목(DART): 카카오·KT&G / KRX 전용 종목: 오에스피. 셋 다 이름==티커."""
    for name, tk in [("카카오", "035720"), ("오에스피", "368970"), ("케이티앤지", "033780")]:
        by_name = rnd.render_prebuy(rs.build_prebuy(name))
        by_ticker = rnd.render_prebuy(rs.build_prebuy(tk))
        assert by_name == by_ticker, f"{name} 이름 입력이 {tk} 티커 입력과 다름"

def test_prebuy_name_input_has_full_facts():
    """이름 입력(카카오)에서도 확인 가능한 사실(감사의견·연속흑자·배당)이 빠지지 않는다."""
    ctx = rs.build_prebuy("카카오")
    assert ctx["dart_scope"] is True                          # 이름으로도 DART 범위 연결
    assert ctx["corp_name"] == "(주)카카오" and ctx["ticker"] == "035720"   # 정식명·정식 티커로 정규화
    assert ctx["facts"].get("profit_streak", 0) >= 4 and ctx["facts"].get("audit")

def test_prebuy_name_input_krx_only_keeps_signals():
    """KRX 전용 종목(오에스피)도 이름 입력에서 층1 신호가 유지된다(이름으로 쳤을 때만 빠지면 안 됨)."""
    ctx = rs.build_prebuy("오에스피")
    assert ctx["ticker"] == "368970" and ctx["has_signals"] is True
    assert any(s["source_kind"] == "KRX" and s["label"] == "관리종목" for s in ctx["signals"])

def test_resolve_corp_name_normalization():
    import dart_client as dc
    for q in ["카카오", "(주)카카오", "035720", "케이티앤지", "삼성전자"]:
        assert dc.resolve_corp(q).get("status") != "absent", f"{q} 정규화 실패"
