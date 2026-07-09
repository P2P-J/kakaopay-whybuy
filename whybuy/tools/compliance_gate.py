#!/usr/bin/env python3
"""컴플라이언스 게이트 — whybuy (G4).

모든 브리핑이 저장 전 반드시 통과하는 기계 검사. 금지 패턴(권유·예측·평가어·단정)과
필수 요소(기준일·면책·판정 라인 링크·반증 정의)를 검사한다. 규칙은 gate_rules.yaml에
외재화, 필수 문구는 textstore에서 임포트(단일 출처). 판정 상태별 필수 요소 차등:
유효/약화/반증 라인은 원문 URL 필수, 확인불가·부재 라인은 URL 대신 부재 사실 문구.

exit 0(통과)/1(위반) + 위반 리포트. --case 지정 시 reports/{case}/gate-log-*.txt 보존.

사용법:
    .venv/bin/python tools/compliance_gate.py <브리핑.md> [--case case-001]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

import textstore as ts

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = Path(__file__).resolve().parent / "gate_rules.yaml"


def _rules() -> dict:
    return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))


_R = _rules()
# 거울 고정 질문(상태별)은 textstore 단일 출처에서 자동 등재
_EXCEPTIONS = list(_R.get("allowed_exceptions") or []) + list(ts.ALL_MIRROR_QUESTIONS)


def scan_forbidden(text: str) -> list[str]:
    """금지 패턴(권유·예측·평가·단정) 위반 목록. 허용 예외 문장은 스캔 전 제거."""
    cleaned = text
    for exc in _EXCEPTIONS:
        cleaned = cleaned.replace(exc, "")
    hits = []
    for pat in _R["forbidden_patterns"]:
        m = re.search(pat["regex"], cleaned)
        if m:
            hits.append(f"[금지·{pat['category']}] '{m.group(0).strip()}' ({pat['id']})")
    return hits


def check_required(text: str) -> list[str]:
    """필수 요소 위반 목록. 판정 상태별 차등 적용."""
    req = _R["required"]
    errs = []
    if not re.search(req["as_of_pattern"], text):
        errs.append("[필수] 데이터 기준일 문구 없음")
    if ts.DISCLAIMER not in text:
        errs.append("[필수] 면책 문구 없음")

    verdict_lines = [ln for ln in text.splitlines() if re.search(req["verdict_marker"], ln)]
    if verdict_lines and (ts.REFUTED_DEFINITION not in text):
        errs.append("[필수] 판정 브리핑에 반증 정의 문구 없음")
    for ln in verdict_lines:
        status = re.search(req["verdict_marker"], ln).group(1)
        if status in req["linked_statuses"]:
            if not re.search(req["link_pattern"], ln):
                errs.append(f"[필수] {status} 판정 라인에 원문 링크 없음 → {ln.strip()[:32]}")
        else:  # 확인불가
            if not re.search(req["absence_pattern"], ln):
                errs.append(f"[필수] 확인불가 라인에 부재 사실 문구 없음 → {ln.strip()[:32]}")
    return errs


def check(text: str) -> list[str]:
    """금지 + 필수 전체 검사. 위반 목록(빈 리스트=통과)."""
    return scan_forbidden(text) + check_required(text)


def _write_log(case: str, path: Path, violations: list[str]) -> None:
    log_dir = ROOT / "reports" / case
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9]", "", str(path.stat().st_mtime))  # 결정적 스탬프(파일 mtime)
    verdict = "PASS" if not violations else "BLOCKED"
    lines = [f"gate {verdict}: {path.name}", ""] + (violations or ["(위반 없음)"])
    (log_dir / f"gate-log-{stamp}.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("--case", default=None)
    args = ap.parse_args()

    path = Path(args.markdown)
    if not path.exists():
        print(f"파일 없음: {path}")
        return 2
    violations = check(path.read_text(encoding="utf-8"))
    if args.case:
        _write_log(args.case, path, violations)
    if violations:
        print(f"게이트 BLOCKED — {len(violations)}건 위반:")
        for v in violations:
            print(f"  - {v}")
        return 1
    print(f"게이트 PASS: {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
