#!/usr/bin/env bash
# build_submission.sh — 제출용 submission.zip 재현 빌드 (저장소 루트에서 실행)
#
# 원칙: ZIP은 항상 "커밋본(HEAD)" 기준으로 뜬다. git archive가 추적 파일만
#       뽑으므로 .venv/venv/.env/*.pyc/__pycache__/.pytest_cache/data/cache 가
#       구조적으로 자동 제외된다(수동 --exclude 불필요).
#
# ⚠ 제출 순서: 실제 제출 ZIP은 "모든 준비 + 이 대화(세션)가 끝난 뒤" 떠야 한다.
#   로그 훅은 세션 종료 시 최종본을 쓰므로, 세션 도중 뜬 ZIP의 대화 로그는
#   끝까지 담기지 않는다(→ 리허설). 최종 ZIP = 세션 정리 후 이 스크립트 재실행.
#
# 사용법:
#   bash tools/build_submission.sh [OUT_DIR] [--cleanroom]
#     OUT_DIR       출력 폴더 (기본: ./dist)
#     --cleanroom   빌드 후, 저장소 밖 임시 폴더에 풀어 새 venv로 pytest+컨트랙트 재현
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$REPO/dist}"
CLEANROOM=0
for a in "$@"; do [ "$a" = "--cleanroom" ] && CLEANROOM=1; done

echo "== 0) 커밋 상태 확인 =="
if [ -n "$(git -C "$REPO" status --porcelain -- whybuy README.md)" ]; then
  echo "⚠ 커밋되지 않은 변경이 있습니다. ZIP은 HEAD 기준으로 뜹니다 — 먼저 커밋하세요."
  git -C "$REPO" status --short -- whybuy README.md
fi
HEAD_SHA="$(git -C "$REPO" rev-parse --short HEAD)"
echo "   빌드 기준 커밋: $HEAD_SHA"

echo "== 1) 트리 구성 (git archive HEAD:whybuy → src) =="
rm -rf "$OUT/submission"
mkdir -p "$OUT/submission/src" "$OUT/submission/logs/claude-code"
git -C "$REPO" archive HEAD:whybuy | tar -x -C "$OUT/submission/src"
git -C "$REPO" show HEAD:README.md > "$OUT/submission/README.md"

echo "== 2) 대화 로그 복사 (저장소 루트 정본) =="
shopt -s nullglob
logs=("$REPO"/logs/claude-code/*.jsonl)
if [ ${#logs[@]} -eq 0 ]; then echo "⚠ logs/claude-code/*.jsonl 이 없습니다!"; else cp "${logs[@]}" "$OUT/submission/logs/claude-code/"; fi
echo "   세션 로그: ${#logs[@]}개"

echo "== 3) 압축 (python zipfile; zip 미설치 대비) =="
python3 - "$OUT" <<'PY'
import sys, os, zipfile
out=sys.argv[1]; root=os.path.join(out,'submission'); zp=os.path.join(out,'submission.zip')
if os.path.exists(zp): os.remove(zp)
with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
    for dp,dirs,fs in os.walk(root):
        dirs.sort()
        for f in sorted(fs):
            full=os.path.join(dp,f); z.write(full, os.path.relpath(full,out))
print(f"   생성: {zp} ({os.path.getsize(zp):,} bytes)")
PY

echo "== 4) ZIP 내부 재검사 (제외대상·키·구조) =="
python3 - "$OUT/submission.zip" "$REPO/whybuy/.env" <<'PY'
import sys, zipfile, re, os
zp, envp = sys.argv[1], sys.argv[2]
dart=""
if os.path.exists(envp):
    for line in open(envp,encoding='utf-8'):
        if line.startswith("DART_API_KEY="): dart=line.split("=",1)[1].strip()
z=zipfile.ZipFile(zp); names=z.namelist(); ok=True
# 제외대상
for pat in ['.venv/','/venv/','.git/','.pytest_cache','__pycache__','.pyc','data/cache']:
    h=[n for n in names if pat in n]
    if h: ok=False; print(f"   ✗ 제외대상 잔재 {pat}: {h[:3]}")
env=[n for n in names if n.split('/')[-1]=='.env']
if env: ok=False; print(f"   ✗ .env 포함됨: {env}")
# 키 스캔
kh=[]
for n in names:
    if n.endswith('/'): continue
    d=z.read(n).decode('utf-8','replace')
    if dart and dart in d: kh.append((n,'DART키'))
    if re.search(r'crtfc_key=[0-9a-fA-F]{20,}', d): kh.append((n,'crtfc실값'))
    kh += [(n,'40hex') for _ in re.findall(r'\b[0-9a-f]{40}\b', d)]
if kh: ok=False; print(f"   ✗ 키 노출: {kh[:5]}")
# 필수 구조
req=['submission/README.md','submission/src/.codex-plugin/plugin.json','submission/src/.mcp.json','submission/src/README.md']
for r in req:
    if r not in names: ok=False; print(f"   ✗ 필수 파일 없음: {r}")
skills=sorted(set(n.split('/')[3] for n in names if n.startswith('submission/src/skills/') and n.count('/')>=4))
logs=[n for n in names if n.startswith('submission/logs/claude-code/') and n.endswith('.jsonl')]
print(f"   제외대상 0 · .env 0 · 키 0 · 필수구조 OK · skills {len(skills)}종 {skills} · logs {len(logs)}세션")
print("   ==> 재검사 " + ("PASS ✓" if ok else "FAIL ✗ (위 항목 수정 필요)"))
sys.exit(0 if ok else 1)
PY

if [ "$CLEANROOM" = "1" ]; then
  echo "== 5) 깨끗한 환경 재현 (저장소 밖 임시 폴더, 키 없이) =="
  ROOM="$(mktemp -d)"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$OUT/submission.zip" "$ROOM"
  cd "$ROOM/submission/src"
  if command -v uv >/dev/null; then uv venv .venv >/dev/null && uv pip install -q -r requirements.txt
  else python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; fi
  echo "   -- pytest (키 없음) --"; env -u DART_API_KEY -u WHYBUY_MODE .venv/bin/python -m pytest -q
  echo "   -- 컨트랙트 --"; env -u DART_API_KEY -u WHYBUY_MODE bash tools/run_all_contracts.sh | tail -2
  echo "   클린룸: $ROOM (확인 후 rm -rf 로 삭제)"
fi

echo ""
echo "빌드 완료: $OUT/submission.zip  (커밋 $HEAD_SHA 기준)"
echo "제출 전 확인: 이 세션이 최종본이고 로그가 끝까지 쓰였는지 → 그 뒤에 이 스크립트를 다시 실행해 최종 ZIP을 뜬다."
