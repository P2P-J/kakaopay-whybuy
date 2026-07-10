# 제출 ZIP 빌드 절차 (아엔 최종 실행용)

이 문서는 **제출 직전 마지막에** submission.zip을 한 번에 다시 뜨기 위한 절차다.
구조·동작·자립 재현은 이미 리허설로 전부 검증됐다(아래 "검증 완료" 참고). 남은 건
모든 준비가 끝나고 **세션 로그가 최종본까지 쓰인 뒤** ZIP을 다시 뜨는 것뿐이다.

## 왜 "맨 마지막에" 떠야 하나 — 로그 정합성

log-hooks는 **세션 종료 시 최종 로그를 쓴다.** 대화 도중에 ZIP을 뜨면 그 안의
대화 로그가 끝까지 담기지 않는다. ZIP 만드는 과정·제출 직전 검토까지 전부 로그에
남아야 정합성이 완결된다. 따라서:

- 세션 도중 뜬 ZIP = **리허설** (구조·동작 검증용, 제출본 아님).
- 실제 제출 ZIP = **모든 준비 + 이 대화가 끝나고 세션을 정리해 로그가 최종본까지
  쓰인 뒤** `build_submission.sh` 재실행 결과.

## 제출 전 남은 준비 (아엔)

1. 제출 글 5문항 작성
2. 글자 수 확인
3. 센터장 인터뷰 출처 대조

이 셋이 끝나야 마지막 ZIP을 뜬다.

## 최종 빌드 순서

```bash
cd /mnt/d/aenproject/kakaopay-whybuy

# (1) 모든 변경이 커밋됐는지 확인 — ZIP은 HEAD(커밋본) 기준으로 뜬다
git status --short          # 깨끗해야 함

# (2) 세션 종료 후, 최종 대화 로그가 logs/claude-code/ 에 쌓였는지 확인
ls -la logs/claude-code/*.jsonl

# (3) 빌드 + ZIP 내부 재검사 (제외대상·키·구조 자동 점검)
bash tools/build_submission.sh dist

# (4) 깨끗한 환경 재현까지 한 번에 (새 venv·키 없이 pytest+컨트랙트)
bash tools/build_submission.sh dist --cleanroom
```

`dist/submission.zip` 이 제출본이다. 스크립트가 재검사 PASS를 찍고, `--cleanroom`이
**키 없는 새 환경에서 181 passed + 컨트랙트 PASS**를 재현하면 자립성까지 확정된다.

## 빌드 방식 (요점)

- **`git archive HEAD:whybuy` → src** — 추적 파일만 뽑히므로 `.venv`·`venv`·`.env`·
  `*.pyc`·`__pycache__`·`.pytest_cache`·`data/cache`가 구조적으로 자동 제외된다.
  수동 `--exclude` 불필요, ZIP이 어느 커밋 기준인지도 명확(HEAD).
- **문서 3개** — 루트 `README.md`(제출 안내·검증 재현·실로드 정직 고지) +
  `HOW_TO_USE.md`(명령+실제 출력 대조 실행 안내서) + `src/README.md`(플러그인 설치·
  스킬 4종·MCP 등록). 역할 분리, 내용 중복 없음.
- **logs/claude-code/** — 저장소 루트 정본 세션 로그(원본, 편집 없음)만 담는다.
- **src/verification/** — 개발 검증 산출물(final-verification.txt·link-check.txt).
  `logs`라는 이름은 대화 로그 전용으로 비워둠(심사 혼동 방지).

## 검증 완료 (리허설, 커밋 6ad5f76 기준)

- ZIP 내부: 제외대상 0 · `.env` 0 · 키 노출 0 · 필수구조(plugin.json·.mcp.json·
  skills 4종·logs 3세션) 완비.
- 깨끗한 환경(저장소 밖, 새 venv, **키 없음**): **pytest 181 passed** · 컨트랙트
  3종×3케이스 PASS · validator 2종 통과 · 데모 막4 산출물 생성 + 게이트 PASS.

→ 구조·동작·자립 재현 전부 검증됨. 남은 건 최종 준비 후 세션 정리하고 이 절차대로
다시 뜨는 것뿐이다.
