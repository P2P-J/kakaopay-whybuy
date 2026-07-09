#!/usr/bin/env python3
"""원장 스키마 검증 (CI 역할) — whybuy.

reasons.json(PRD 5.1)의 필수 필드·날짜 형식·rcp_no 14자리·status/type/source enum을
jsonschema(Draft-07)로 검사한다. 원장 무결성의 최종 방어선. 스키마는
`data/ledger/reasons.schema.json`. 위반 목록 출력 + exit 1, 무결하면 exit 0.

사용법:
    .venv/bin/python tools/validate_ledger.py data/ledger/reasons.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data" / "ledger" / "reasons.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_ledger(doc: dict) -> list[str]:
    """원장 문서를 스키마로 검증하고 위반 목록(경로: 메시지)을 반환한다. 무결하면 []."""
    validator = Draft7Validator(_schema())
    errs = []
    for e in sorted(validator.iter_errors(doc), key=lambda x: list(x.absolute_path)):
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        errs.append(f"{path}: {e.message}")
    return errs


def main() -> int:
    if len(sys.argv) < 2:
        print("사용법: validate_ledger.py <reasons.json>")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"원장 파일 없음: {path}")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = validate_ledger(doc)
    if errs:
        print(f"원장 검증 실패 — {len(errs)}건:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"원장 검증 통과: {path.name} (스키마 {SCHEMA_PATH.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
