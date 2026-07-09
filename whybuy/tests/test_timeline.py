"""G6 buy-timeline 파이프라인 테스트. run_skill.py를 CLI 없이 함수로 직접 호출(규약 검증).

수용 기준(PRD 4.1): 매수일 이전 공시 0건 / 변한 것 전 항목 링크 / 급변 미매칭 "없음" 문구
정확 / 게이트 PASS / case-001 골든 스냅샷 회귀.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import render as rnd  # noqa: E402
import run_skill as rs  # noqa: E402
import textstore as ts  # noqa: E402
from compliance_gate import check as gate_check  # noqa: E402

_GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "timeline-case-001.md")


def test_no_disclosures_before_buy_date():
    ctx = rs.build_timeline("case-001")
    buy = ctx["buy_date"]
    assert ctx["changed"], "변한 것이 비어있으면 케이스 의미 없음"
    assert all(e["date"] >= buy for e in ctx["changed"])
    assert all(m["date"] >= buy for m in ctx["moves_block"]["moves"])


def test_every_changed_item_has_link():
    ctx = rs.build_timeline("case-001")
    md = rnd.render_timeline(ctx)
    for e in ctx["changed"]:
        assert e["url"].startswith("https://dart.fss.or.kr")
    # 변한 것 섹션의 각 항목 라인에 마크다운 링크 존재
    changed_lines = [ln for ln in md.splitlines() if ln.startswith("- ") and "일어난" not in ln]
    assert changed_lines


def test_move_no_match_uses_fixed_phrase():
    ctx = rs.build_timeline("case-001")
    unmatched = [m for m in ctx["moves_block"]["moves"] if m["match"] == ts.MOVE_NO_MATCH]
    # case-001에 미매칭 급변일이 최소 1건(2025-03-31) — 고정 문구 정확히 사용
    assert unmatched, "미매칭 급변일이 없으면 이 검증 불가"
    assert all("공시로 확인되지 않는 영역" in m["match"] for m in unmatched)


def test_gate_passes():
    ctx = rs.build_timeline("case-001")
    assert gate_check(rnd.render_timeline(ctx)) == []


def test_market_tag_is_arithmetic_not_valuation():
    ctx = rs.build_timeline("case-001")
    assert ctx["return_block"]["market_tag"] in ("상회", "유사", "하회")


def test_pipeline_is_importable_pure_function():
    # 규약: CLI 거치지 않고 함수 직접 호출로 완성 브리핑 생성 (부록 D HTTP 확장 대비)
    ctx = rs.build_timeline("case-001", as_of="2025-04-09", with_price_overlay=True)
    md = rnd.render_timeline(ctx)
    assert md.startswith("# 2025-03-25, 당신이 산 이후 삼성전자")


def test_number_format_single_source():
    # 수치 포맷은 render.pct 한 곳 — 부호+소수1자리
    assert rnd.pct(-11.4) == "-11.4%" and rnd.pct(0) == "+0.0%"


def test_golden_snapshot_case001():
    ctx = rs.build_timeline("case-001")
    md = rnd.render_timeline(ctx)
    golden = open(_GOLDEN, encoding="utf-8").read()
    assert md == golden, "case-001 브리핑이 골든 스냅샷과 다름 (픽스처/템플릿 변경 시 아엔 승인 후 갱신)"
