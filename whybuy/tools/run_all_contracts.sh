#!/usr/bin/env bash
# 스킬 컨트랙트 3종 × 데모 3케이스 일괄 실행 (정적 검증 폴백의 원천) — whybuy G9.
# CWD = whybuy/. 전 케이스의 timeline·recall·audit·mirror 브리핑을 reports/에 산출하고
# 각 산출물을 컴플라이언스 게이트로 재검사한다. 하나라도 실패하면 exit 1.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
fail=0

echo "== prebuy-check =="
$PY -m tools.run_skill prebuy --ticker 035720 >/dev/null || fail=1   # 카카오 — 없음 경로
$PY -m tools.run_skill prebuy --ticker 368970 >/dev/null || fail=1   # 오에스피 — KRX 층1 있음
$PY -m tools.run_skill prebuy --ticker 033780 >/dev/null || fail=1   # KT&G — DART 층3 있음

echo "== buy-timeline =="
for c in case-001 case-002 case-003; do
  $PY -m tools.run_skill timeline --case "$c" >/dev/null || fail=1
done

echo "== reason-recall (dry-run) =="
$PY -m tools.run_skill recall --case case-001 --choose r1 --dry-run >/dev/null || fail=1
$PY -m tools.run_skill recall --case case-002 --choose r2 --dry-run >/dev/null || fail=1
$PY -m tools.run_skill recall --case case-003 --choose r2 --dry-run >/dev/null || fail=1

echo "== thesis-audit + mirror =="
for c in case-001 case-002 case-003; do
  $PY -m tools.run_skill audit --case "$c" >/dev/null || fail=1
  $PY -m tools.run_skill audit --case "$c" --mirror >/dev/null || fail=1
done

echo "== 산출물 게이트 재검사 =="
for f in reports/case-00*/*.md reports/prebuy/*.md; do
  [ -f "$f" ] || continue
  $PY tools/compliance_gate.py "$f" >/dev/null || { echo "게이트 실패: $f"; fail=1; }
done

if [ "$fail" -ne 0 ]; then
  echo "컨트랙트 실행 실패"; exit 1
fi
echo "컨트랙트 3종 × 3케이스 전부 PASS"
