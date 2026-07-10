"""G10 krx_client 테스트 — 종목별 KRX 층1 신호 조회 (픽스처 읽기, 네트워크 무관).

dart_client 옆의 소스별 클라이언트. 위험 목록 픽스처(krx/*.json)를 종목코드로 조회한다.
각 신호에 출처명·출처 URL·명단 기준일(as_of)·지정일·사유가 붙는다(추적성).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
import krx_client as kc  # noqa: E402


def test_healthy_ticker_has_no_flags():
    assert kc.risk_flags("035720") == []      # 카카오 — 층1 6종 모두 없음


def test_designated_ticker_returns_flags():
    flags = kc.risk_flags("368970")            # 오에스피 — 관리종목 + 불성실공시
    signals = {f["signal"] for f in flags}
    assert "관리종목" in signals and "불성실공시법인 지정" in signals


def test_flag_carries_source_and_snapshot_date():
    f = next(f for f in kc.risk_flags("368970") if f["signal"] == "관리종목")
    assert f["source_name"] == "한국거래소 관리종목 지정 현황"
    assert f["source_url"].startswith("https://")
    assert f["as_of"] == "2026-07-10"
    assert f["date"] and f["reason"]           # 지정일·사유


def test_snapshot_date():
    assert kc.snapshot_date() == "2026-07-10"


def test_multiple_rows_same_signal_all_returned():
    # 069920 — 불성실공시 2건 등 다중 지정도 전부 반환
    flags = kc.risk_flags("069920")
    assert len([f for f in flags if f["signal"] == "불성실공시법인 지정"]) >= 2
