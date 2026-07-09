"""G8 thesis-audit + 거울 테스트. run_skill을 CLI 없이 함수로 직접 호출.

전 판정 rule_id+URL / 결정성 / 확인불가에 유효·반증 미부여 / 거울 게이트 통과 /
신규 중대 사실 3조건 / audits 누적 / 골든 스냅샷(audit-001·mirror-002·audit-003).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
os.environ.setdefault("WHYBUY_MODE", "fixture")

import render as rnd  # noqa: E402
import run_skill as rs  # noqa: E402
from compliance_gate import check as gate_check  # noqa: E402

_G = os.path.join(os.path.dirname(__file__), "golden")


def test_every_verdict_has_rule_id_and_url():
    for cid in ("case-001", "case-002", "case-003"):
        ctx = rs.build_audit(cid)
        assert ctx["verdicts"]
        for v in ctx["verdicts"]:
            assert v["rule_id"]
            assert v["evidence"].get("url", "").startswith("https://dart.fss.or.kr")


def test_determinism():
    a = rs.build_audit("case-002", mirror=True)
    b = rs.build_audit("case-002", mirror=True)
    assert a == b


def test_case002_refuted():
    ctx = rs.build_audit("case-002")
    v = ctx["verdicts"][0]
    assert v["status"] == "refuted" and v["rule_id"] == "RULE-EARN-01"


def test_unverifiable_never_gets_supported_or_refuted_tag():
    # 테마 논거 → 확인불가. 판정 라인에 유효/반증 딱지가 붙으면 안 된다
    v = {"label": "테마 편승", "claim": "x", "status": "unverifiable",
         "rule_id": "RULE-THM-01", "evidence": {"note": "검증 불가"}}
    line = rnd.verdict_line(v)
    assert "확인불가" in line
    assert "**유효**" not in line and "**반증**" not in line and "**약화**" not in line


def test_new_material_excludes_linked_reason():
    # 신규 중대 사실은 원장 논거(rcp)와 미연결이어야 한다
    ctx = rs.build_audit("case-002")
    import ledger_store as ls
    linked = {r.get("source_rcp_no") for r in ls.read("case-002")["reasons"]}
    urls = [f["url"] for f in ctx["new_material"]]
    assert all(not any(rcp and rcp in u for rcp in linked) for u in urls)


def test_mirror_gate_passes():
    ctx = rs.build_audit("case-002", mirror=True)
    assert gate_check(rnd.render_mirror(ctx)) == []


def test_audit_gate_passes_all_cases():
    for cid in ("case-001", "case-002", "case-003"):
        assert gate_check(rnd.render_audit(rs.build_audit(cid))) == []


def test_audits_append_accumulates(tmp_path, monkeypatch):
    # 원장 audits[]에 판정이 누적 기록되는지 (임시 원장으로 격리)
    import json
    import ledger_store as ls
    src = json.loads((rs.ROOT / "data" / "ledger" / "reasons.json").read_text(encoding="utf-8"))
    tmp = tmp_path / "reasons.json"
    tmp.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ls, "LEDGER", tmp)
    rs.run_audit("case-002", None, mirror=False, commit=True)
    case = ls.read("case-002")
    assert len(case["audits"]) == 1
    assert case["audits"][0]["verdicts"][0]["status"] == "refuted"


def test_golden_audit_case001():
    assert rnd.render_audit(rs.build_audit("case-001")) == open(os.path.join(_G, "audit-case-001.md"), encoding="utf-8").read()

def test_golden_mirror_case002():
    assert rnd.render_mirror(rs.build_audit("case-002", mirror=True)) == open(os.path.join(_G, "mirror-case-002.md"), encoding="utf-8").read()

def test_golden_audit_case003():
    assert rnd.render_audit(rs.build_audit("case-003")) == open(os.path.join(_G, "audit-case-003.md"), encoding="utf-8").read()
