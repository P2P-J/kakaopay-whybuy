# Codex 실로드 검증 체크리스트 (아엔 로컬 전용)

> **목적**: 계획 전체에서 유일하게 개발 환경에서 원리적으로 확인 불가능한 항목 — "실제 Codex가
> `plugin.json`을 로드해 스킬 3종을 인식하고, 컨트랙트 명령이 에이전트 경로로도 도는가" — 를
> 아엔 로컬 Codex에서 직접 확인한다. 각 단계에 **기대 결과**와 **실패 시 대응**을 붙였다.
> 결과(성공/실패)를 §5에 기록하고 README의 실로드 고지 문구를 실제 결과로 교체한다.

작업 디렉토리는 항상 **`whybuy/`** 기준. 표기 `$` 는 셸 프롬프트.

## 실행 결과 (아엔 로컬, 2026-07-10 · Codex CLI v0.143.0) — 부분 성공

| 단계 | 결과 |
|---|---|
| 0 사전 확인 | **PASS** — 새 venv+deps로 pytest 151 passed, 컨트랙트 3종×3케이스 PASS |
| 1~2 플러그인·스킬 인식 | **미검증(정적 대체)** — 이 Codex는 `codex plugin add`가 마켓플레이스 스냅샷 설치만 지원. 로컬 폴더 직접 로드 불가(우리는 단일 플러그인이라 카탈로그 매니페스트 없음) → 규격 맞추려면 별도 작업, 정적 검증으로 남김 |
| 3 MCP 서버 + 도구 10종 | **PASS(핵심 실증)** — `codex mcp add whybuy-dart -- <venv python> <server.py>`(절대경로) → `codex mcp list` enabled → `codex exec`(gpt-5.5) 세션에서 도구 10종 전부 인식·응답. workdir·실행한도 정상 |
| 4 대화형 컨트랙트 | 3단계로 갈음(MCP 실연결 증명 + 스킬은 마크다운 지시서) |

**결론**: MCP 서버의 Codex 실연결은 실증됨(가장 중요). 플러그인 카탈로그 로드만 마켓플레이스 규격 때문에 정적 검증으로 대체. README 실로드 고지를 이 결과로 갱신함.

---

## 0. 사전 준비 (한 번만)

- [ ] **0-1** venv·의존성: `cd whybuy && uv venv .venv && . .venv/bin/activate && uv pip install -r requirements.txt`
- [ ] **0-2** 정적 경로가 먼저 그린인지 확인(로드와 무관하게 코드가 도는지 선확인):
  ```
  .venv/bin/python -m pytest -q            # 151 passed 기대
  bash tools/run_all_contracts.sh          # "컨트랙트 3종 × 3케이스 전부 PASS" 기대
  ```
  - 기대: 둘 다 exit 0. **실패 시**: 로드 이전 문제이므로 여기부터 해결(로드 검증 진행 불가).
- [ ] **0-3** `.env`는 라이브 모드일 때만 필요. 로드 검증은 **픽스처 모드**(기본)로 충분 — 네트워크 불필요.

## 1. 플러그인 등록·발견

- [ ] **1-1** Codex가 플러그인을 어디서 찾는지 확인(로컬 Codex의 플러그인 디렉토리/설정). `.codex-plugin/plugin.json`이 있는 `whybuy/`를 그 위치에 등록(심볼릭 링크 또는 복사 또는 설정에 경로 추가 — Codex 문서 기준).
- [ ] **1-2** Codex 재시작 후 플러그인 목록에 **`whybuy` v1.0.0** 이 나타나는지.
  - 기대: 목록에 `whybuy` 표시.
  - **실패 시**: (a) plugin.json 위치가 Codex 탐색 경로에 있는지, (b) JSON 파싱 오류 없는지(`python -m json.tool .codex-plugin/plugin.json`), (c) Codex 플러그인 스키마 필드명이 우리와 일치하는지(`name/version/description/skills/mcpServers`) — 다르면 §부록 A.

## 2. 스킬 3종 인식

- [ ] **2-1** Codex 스킬/명령 목록에 **buy-timeline · reason-recall · thesis-audit** 3종이 각 description과 함께 뜨는지.
  - 기대: 3종 모두 인식. description은 각 `SKILL.md` 프론트매터와 일치.
  - **실패 시**: (a) plugin.json의 `skills[].path`가 실재하는지(`ls skills/*/SKILL.md`), (b) SKILL.md 프론트매터(`name:`, `description:`)가 유효한 YAML인지, (c) Codex가 스킬을 `path`가 아니라 디렉토리로 찾는다면 §부록 A.

## 3. MCP 서버 기동 + 도구 노출

- [ ] **3-1** 플러그인 로드 시 MCP 서버 `whybuy-dart`가 기동되는지(Codex의 MCP 상태/로그 확인).
- [ ] **3-2** 도구 10종 노출 확인: `dart_resolve_corp, dart_list_disclosures, dart_get_financials, dart_get_report_item, dart_get_events, dart_get_insider, price_get_daily, ledger_read, ledger_write, gate_check`.
  - 기대: 10종 노출(수동 스모크와 동일): `WHYBUY_MODE=fixture timeout 20 .venv/bin/python mcp/server.py < tests/mcp_smoke_input.jsonl` 이 initialize + tools/list(10종)를 반환.
  - **실패 시 (가장 흔함)**: plugin.json의 `mcpServers.whybuy-dart.command`가 `"python"`이라 **deps 없는 인터프리터**를 잡았을 수 있음.
    → 대응: command를 venv 파이썬 절대경로로 바꾸거나(예: `"/…/whybuy/.venv/bin/python"`), Codex가 플러그인 루트를 cwd로 주지 않으면 args를 절대경로로. §부록 A에 수정 예시.

## 4. 컨트랙트 명령을 에이전트 경로로 실행

각 스킬을 Codex 대화로 호출해 **정적 CLI와 같은 산출물**이 나오는지 확인(대화 경로와 정적 경로가 같은 함수를 호출하도록 설계됨).

- [ ] **4-1** buy-timeline: Codex에 "case-002 타임라인 보여줘" → `reports/case-002/timeline-2025-05-14.md` 생성, 게이트 PASS.
- [ ] **4-2** reason-recall: "case-002 산 이유 후보 보여줘" → Q1/Q2/Q3 객관식 제시(공시 후보 + 라이브러리). 정적 대조: `.venv/bin/python -m tools.run_skill recall --case case-002 --choose r2 --dry-run`.
- [ ] **4-3** thesis-audit 거울: "case-002 지금 팔까 고민돼" → 거울 브리핑(그때/지금/고정 질문), 게이트 PASS. 정적 대조: `--case case-002 --mirror`.
  - 기대: 에이전트 산출물의 **사실·수치·판정이 정적 산출물과 일치**(문장 다듬기 차이만 허용). 골든: `tests/golden/`.
  - **실패 시**: 에이전트가 게이트 우회로 권유/예측 문구를 넣으면 → SKILL.md 지시문 강화(사실만, 게이트 강제 명시). 산출물이 저장 경로에서 게이트에 막히는지 확인.

## 5. 결과 기록 → README 업데이트

검증 결과에 따라 README의 실로드 고지 문구를 **실제 결과로** 교체한다(현재는 "확인 가능하다"는 유보형).

- [ ] **5-1 성공 시** — README 해당 문구를 아래로 교체:
  > **Codex 실로드 확인됨(아엔 로컬, YYYY-MM-DD).** plugin.json 로드 → 스킬 3종 인식 → MCP 도구 10종 노출 → 컨트랙트 3종 에이전트 경로 동작 확인. 심사위원도 동일 절차로 직접 열어볼 수 있다.
- [ ] **5-2 실패 시** — 어느 단계에서 막혔는지 기록하고 README를 아래로 교체:
  > **Codex 실로드는 미확인(아엔 로컬 시도, YYYY-MM-DD, 단계 N에서 막힘: <원인>).** 파이프라인·판정·게이트·산출물은 정적 검증으로 완전 재현된다(README "검증 방법" 참조). 실로드는 Codex 플러그인 규격 <필요 수정>으로 후속 대응.
- [ ] **5-3** 실패 원인이 plugin.json 규격 불일치면 §부록 A의 수정을 적용하고 2·3단계 재시도.

---

## 부록 A — 흔한 로드 실패와 수정

| 증상 | 원인 | 수정 |
|---|---|---|
| MCP 서버 기동 실패, `ModuleNotFoundError: mcp` | `command:"python"`이 deps 없는 인터프리터 | `command`를 `whybuy/.venv/bin/python` 절대경로로 |
| `FileNotFoundError: mcp/server.py` | Codex가 플러그인 루트를 cwd로 안 줌 | `args`를 `["/…/whybuy/mcp/server.py"]` 절대경로로, 필요 시 `cwd`/`env` 필드 추가 |
| 스킬 미인식 | Codex 스킬 탐색 규약이 `skills[].path`와 다름 | Codex 플러그인 문서의 스킬 등록 필드에 맞춰 plugin.json 조정 |
| 플러그인 자체 미발견 | 등록 위치/방식 불일치 | Codex 플러그인 설치 절차(디렉토리·설정 키) 재확인 |

**원칙**: plugin.json 규격 수정은 코드 로직을 건드리지 않는다 — 파이프라인·판정·게이트는 이미 정적으로 검증됨. 로드는 "배선" 문제이지 "동작" 문제가 아니다.
