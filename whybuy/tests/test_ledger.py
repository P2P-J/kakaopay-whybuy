"""G3 원장 스키마 검증 테스트 (네트워크 무관). validate_ledger.py 대상.

reasons.json(PRD 5.1)의 필수 필드·날짜 형식·rcp_no 14자리·status/type/source enum 검사.
"""
import copy
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import validate_ledger as vl


def _valid_doc():
    return {
        "schema_version": 1,
        "cases": [
            {
                "case_id": "case-001",
                "ticker": "005930",
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "buy_date": "2025-03-25",
                "is_fixture": True,
                "context": {"q1_channel": "youtube_sns", "q3_horizon": "long_term"},
                "reasons": [
                    {
                        "reason_id": "r1",
                        "type": "earnings_improvement",
                        "label": "실적 개선 기대",
                        "claim": "전사 영업이익이 개선 추세다",
                        "source": "disclosure",
                        "user_text": None,
                        "source_rcp_no": "20250311001085",
                        "selected_at": "2025-03-26",
                    }
                ],
                "audits": [
                    {
                        "run_at": "2025-04-09T09:00:00+09:00",
                        "as_of": "2025-04-09",
                        "verdicts": [
                            {
                                "reason_id": "r1",
                                "status": "supported",
                                "rule_id": "RULE-EARN-01",
                                "evidence": {
                                    "rcp_no": "20250408800003",
                                    "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250408800003",
                                    "item": "영업이익",
                                    "fs_div": "CFS",
                                },
                            }
                        ],
                        "new_material_facts": [],
                    }
                ],
            }
        ],
    }


def test_valid_ledger_has_no_errors():
    assert vl.validate_ledger(_valid_doc()) == []


def test_missing_required_case_field_fails():
    d = _valid_doc()
    del d["cases"][0]["buy_date"]
    assert vl.validate_ledger(d)


def test_bad_rcp_no_length_fails():
    d = _valid_doc()
    d["cases"][0]["reasons"][0]["source_rcp_no"] = "123456789"  # 9자리
    errs = vl.validate_ledger(d)
    assert any("rcp" in e.lower() for e in errs)


def test_null_rcp_allowed_for_library_reason():
    d = _valid_doc()
    r = d["cases"][0]["reasons"][0]
    r["source"], r["type"], r["source_rcp_no"], r["user_text"] = "library", "theme", None, None
    assert vl.validate_ledger(d) == []


def test_bad_status_enum_fails():
    d = _valid_doc()
    d["cases"][0]["audits"][0]["verdicts"][0]["status"] = "maybe"
    errs = vl.validate_ledger(d)
    assert any("status" in e.lower() for e in errs)


def test_bad_type_enum_fails():
    d = _valid_doc()
    d["cases"][0]["reasons"][0]["type"] = "vibes"
    assert vl.validate_ledger(d)


def test_bad_date_format_fails():
    d = _valid_doc()
    d["cases"][0]["buy_date"] = "2025/03/25"
    errs = vl.validate_ledger(d)
    assert any("date" in e.lower() or "buy_date" in e for e in errs)


def test_bad_source_enum_fails():
    d = _valid_doc()
    d["cases"][0]["reasons"][0]["source"] = "twitter"
    assert vl.validate_ledger(d)
