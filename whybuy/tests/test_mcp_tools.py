"""G3 MCP 도구 단위 테스트 (서버 기동 없이 dispatch 계층 호출). 실 픽스처 대상.

핵심: as_of 필터가 dart_client 한 곳에서 강제돼 어떤 도구도 미래 제출분을 누출하지 않는다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
os.environ.setdefault("WHYBUY_MODE", "fixture")

import server as srv  # noqa: E402

SAMSUNG = "00126380"
KTG = "00244455"


def d(name, **args):
    return srv.dispatch(name, args)


# ── resolve ──
def test_resolve_corp_by_ticker():
    r = d("dart_resolve_corp", query="005930")
    assert r["corp_code"] == SAMSUNG and r["market"] == "kospi"

def test_resolve_corp_by_name():
    assert d("dart_resolve_corp", query="삼성전자(주)")["corp_code"] == SAMSUNG

def test_resolve_corp_absent():
    assert d("dart_resolve_corp", query="없는회사")["status"] == "absent"


# ── list_disclosures + as_of ──
def test_list_disclosures_as_of_hides_future():
    early = d("dart_list_disclosures", corp_code=SAMSUNG, date_from="2025-01-01", date_to="2026-12-31", as_of="2025-03-01")
    late = d("dart_list_disclosures", corp_code=SAMSUNG, date_from="2025-01-01", date_to="2026-12-31", as_of="2026-07-09")
    assert len(early) < len(late)
    assert all(r["submitted"] <= "2025-03-01" for r in early)  # 미래 제출분 없음

def test_list_disclosures_kinds_filter():
    only_a = d("dart_list_disclosures", corp_code=SAMSUNG, date_from="2025-01-01", date_to="2026-12-31",
               kinds=["A"], as_of="2026-07-09")
    assert only_a and all(r["pblntf_ty"] == "A" for r in only_a)


# ── financials as_of 게이트 ──
def test_financials_absent_before_submission():
    r = d("dart_get_financials", corp_code=SAMSUNG, year="2025", quarter="1Q", as_of="2025-01-01")
    assert r["status"] == "absent"

def test_financials_ok_after_submission():
    r = d("dart_get_financials", corp_code=SAMSUNG, year="2025", quarter="1Q", as_of="2026-01-01")
    assert r["status"] == "ok" and r["basis"] == "CFS" and r["accounts"]


# ── report_item ──
def test_report_item_dividend_ktg():
    r = d("dart_get_report_item", corp_code=KTG, item="dividend", as_of="2026-07-09")
    assert r["status"] == "ok" and r["years"]

def test_report_item_absent_before_asof():
    r = d("dart_get_report_item", corp_code=KTG, item="dividend", as_of="2024-01-01")
    assert r["status"] == "absent"


# ── events / insider ──
def test_get_events_dividend_type():
    ev = d("dart_get_events", corp_code=KTG, event_types=["dividend"], date_from="2025-01-01",
           date_to="2026-12-31", as_of="2026-07-09")
    assert ev and all(e["event_type"] == "dividend" for e in ev)

def test_get_insider_all_major_shareholder():
    ins = d("dart_get_insider", corp_code=SAMSUNG, date_from="2025-01-01", date_to="2025-06-30", as_of="2025-06-30")
    assert ins and all(e["event_type"] == "major_shareholder" for e in ins)


# ── prices ──
def test_price_get_daily_range():
    px = d("price_get_daily", ticker="005930", date_from="2025-03-24", date_to="2025-03-26")
    assert [r["date"] for r in px] == ["2025-03-24", "2025-03-25", "2025-03-26"]


# ── ledger ──
def test_ledger_read_case():
    c = d("ledger_read", case_id="case-001")
    assert c and c["corp_code"] == SAMSUNG

def test_ledger_read_all():
    doc = d("ledger_read")
    assert doc["schema_version"] == 1 and len(doc["cases"]) >= 3


# ── 구조화 오류 ──
def test_unknown_tool_structured_error():
    assert d("nope")["error"] == "unknown_tool"

def test_missing_arguments_structured_error():
    assert d("dart_get_financials", corp_code=SAMSUNG)["error"] == "missing_arguments"

def test_ledger_write_invalid_rejected():
    bad = {"case_id": "x"}  # 필수 필드 없는 케이스
    r = d("ledger_write", case=bad)
    assert r["error"] == "handler_error"


# ── gate_check (G4 배선) ──
def test_gate_check_pass():
    ok = ("이 브리핑은 2025-04-09까지 제출된 공시 기준입니다. 영업이익 +32%. "
          "본 브리핑은 공개된 공시 사실의 정리이며, 특정 종목의 매매를 권유하는 투자자문이 아닙니다.")
    assert d("gate_check", text=ok)["status"] == "pass"

def test_gate_check_blocked():
    r = d("gate_check", text="지금 파세요.")
    assert r["status"] == "blocked" and r["violations"]
