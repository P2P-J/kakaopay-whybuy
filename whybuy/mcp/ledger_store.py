"""논거 원장 접근 단일 진입점 (0.7-3) — whybuy.

reasons.json 읽기·쓰기·스키마 검증은 이 모듈만 거친다. 오늘은 JSON 파일,
고객 서비스 전환 시 DB — 이 모듈 하나만 교체하면 된다. schema_version이
마이그레이션 앵커. 스킬·판정 엔진은 저장 방식을 모른다.

쓰기는 **스키마 검증 통과 시에만 커밋**한다(validate_ledger). 위반 시 ValueError.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from validate_ledger import validate_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "ledger" / "reasons.json"


def load() -> dict:
    """원장 전체를 읽는다. 파일 없으면 빈 원장(schema_version 1)."""
    if not LEDGER.exists():
        return {"schema_version": 1, "cases": []}
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def read(case_id: str | None = None):
    """case_id를 주면 해당 케이스(dict) 또는 None, 없으면 원장 전체."""
    doc = load()
    if case_id is None:
        return doc
    for c in doc.get("cases", []):
        if c["case_id"] == case_id:
            return c
    return None


def _persist(doc: dict) -> None:
    errs = validate_ledger(doc)
    if errs:
        raise ValueError("원장 스키마 위반: " + "; ".join(errs[:5]))
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def write(doc: dict) -> None:
    """원장 전체를 검증 후 저장. 위반 시 ValueError로 쓰기 거부."""
    _persist(doc)


def upsert_case(case: dict) -> None:
    """케이스 하나를 삽입/갱신(case_id 기준)하고 검증 후 저장."""
    doc = load()
    cases = doc.setdefault("cases", [])
    for i, c in enumerate(cases):
        if c["case_id"] == case["case_id"]:
            cases[i] = case
            break
    else:
        cases.append(case)
    _persist(doc)


def append_audit(case_id: str, audit: dict) -> None:
    """케이스에 감사(audit) 한 건 추가 후 검증 저장. 케이스 없으면 KeyError."""
    doc = load()
    for c in doc.get("cases", []):
        if c["case_id"] == case_id:
            c.setdefault("audits", []).append(audit)
            _persist(doc)
            return
    raise KeyError(f"case_id 없음: {case_id}")
