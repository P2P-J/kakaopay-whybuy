# 왜샀지 (whybuy)

> "이 주식 왜 샀지?" — 카카오페이증권의 '어땠지'가 **시장의 시간**에 답한다면, 왜샀지는 **나의 시간**에 답한다. 매수일을 기준으로 공시 사실을 재정렬하고, 산 이유를 객관식으로 되찾아주며, 그 이유가 아직 유효한지 DART 공시 원문으로 판정한다. **추천하지 않는다. 판정한다.**

국내 상장주식 전용 Codex 플러그인 (스킬 4종 + 로컬 MCP 서버 + 픽스처).

## 구성 — 초보자 여정 순서

- `prebuy-check` — "이거 사기 전에 알아둘 게 있나?" (공식 기록 3층 점검 — 거래소 명단·재무·지배구조)
- `buy-timeline` — "내가 산 뒤로 뭐가 달라졌어?" (매수일 앵커 타임라인)
- `reason-recall` — "나 이거 왜 샀더라?" (객관식 논거 재인)
- `thesis-audit` — "그 이유 아직 유효해?" (공시 원문 대조 판정 + 거울 모드)

## 설치 (개발 환경)

```bash
cd whybuy
uv venv .venv && . .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env   # OpenDART 키가 필요할 때만 (라이브 모드). 기본은 픽스처 오프라인
```

픽스처가 커밋된 뒤에는 외부 네트워크 없이 오프라인으로 개발·테스트·데모가 재현된다.

## 3분 데모 경로

A씨의 여정 = 스킬의 순서: 불안(−N%) → 타임라인(사실을 본다) → 재인(이유가 생긴다) → 판정(이유의 생사) → 거울(가격인가, 사실인가).

```bash
cd whybuy
# 막1·2 — 산 뒤로 뭐가 달라졌나 (타임라인)
.venv/bin/python -m tools.run_skill timeline --case case-002
# 막3 — 왜 샀더라 (객관식 재인 → 원장 기록)
.venv/bin/python -m tools.run_skill recall  --case case-002 --choose r2 --dry-run
# 막4 — 매도 버튼 앞의 거울 (킬러 장면: 손실 + 논거 반증)
.venv/bin/python -m tools.run_skill audit   --case case-002 --mirror
# 대비 — case-001은 손실인데 논거 유효(가격↔사실 엇갈림)
.venv/bin/python -m tools.run_skill audit   --case case-001 --mirror
```

산출물은 `reports/<case>/`. 세 케이스: **case-001 삼성(손실·유효)**, **case-002 카카오(손실·반증, 거울 킬러)**, **case-003 KT&G(수익·유효)**.

## 4원칙과 게이트 (설득의 과정 = 심사 기준)

1. **공식 기록 원문만 인용** — 판정 근거는 전부 DART 공시 rcp_no + 원문 URL. 뉴스·커뮤니티는 판정에 안 쓴다.
2. **해석·권유 금지, 기계로 강제** — 모든 브리핑은 저장 전 `compliance_gate`를 통과한다(지시·예측·평가어 0건). 약속이 아니라 테스트로 증명(`tests/test_gate.py`). 범위는 정직하게 "이 시스템의 산출물에서 0건 보장"이지 "세상 모든 권유 표현 검출"이 아니다.
3. **부재의 정직** — 없으면 없다고 말한다. 급변일에 매칭 공시가 없으면 설명을 지어내지 않고 "공식 기록상 변한 사실 없음"을 고정 출력. 데이터 부재 판정은 URL 대신 부재 사실 문구.
4. **판정의 근거를 열어 보인다** — 같은 원장 + 같은 `as_of` → 항상 같은 판정(결정성). 모든 판정에 `rule_id` + 원문 링크.

## 아키텍처

```
스킬(SKILL.md) ──▶ tools/run_skill.py (파이프라인 순수 함수 + 얇은 CLI)
                     │
   ┌─────────────────┼──────────────────────────────┐
   ▼                 ▼                               ▼
 classify        verdict_engine(가격 격리)        detect_moves
 (공시→유형)     RULE-EARN/RET/DIV/GRW/NEW/THM/PRC   (급변 감지)
   │                 │                               │
   └──▶ render.py(조립·문구 textstore 단일출처) ──▶ compliance_gate ──▶ reports/
                     ▲                                             
        mcp/dart_client·krx_client(픽스처, as_of 필터) ◀── mcp/server.py(MCP 도구 11종)
        mcp/ledger_store(원장 읽기·쓰기, 스키마 검증) ── data/ledger/reasons.json
```

as_of 필터는 `dart_client` 한 곳에서 강제 → 도구가 늘어도 시점 누출이 구조적으로 불가능. 판정(`verdict_engine`)은 시세를 임포트하지 않는다(가격 격리, 소스+네임스페이스 이중 테스트).

## 검증 방법 (Codex 없이 완전 재현)

```bash
.venv/bin/python -m pytest -q                              # 전체 스위트
bash tools/run_all_contracts.sh                            # 컨트랙트 3종 × 3케이스 exit 0
.venv/bin/python tools/validate_fixtures.py                # 픽스처 스키마
.venv/bin/python tools/validate_ledger.py data/ledger/reasons.json
.venv/bin/python tools/link_check.py                       # reports 내 DART 원문 링크(아엔 로컬)
```

파이프라인·판정·게이트·산출물은 전부 오프라인 픽스처로 재현된다(정적 실행 경로 강제).

### 로컬 Codex에 MCP 서버 붙이기

`plugin.json`의 `mcpServers`는 이식성을 위해 상대경로(`python`, `mcp/server.py`)로 커밋돼 있다.
로컬 Codex CLI에 실제로 등록할 때는 `codex mcp add`로 붙이되 **command·args를 절대경로로** 지정한다
(Codex가 플러그인 루트를 cwd로 주지 않으므로):

```bash
codex mcp add whybuy-dart -- /abs/경로/whybuy/.venv/bin/python /abs/경로/whybuy/mcp/server.py
codex mcp list                        # whybuy-dart 가 enabled 로 뜨는지 확인
```

## 범위·한계 (정직 고지)

- **국내 상장주식 전용.** 해외주식은 아직 다루지 않는다 (확장 스텁도 없음).
- 종목 추천·매매 지시·시세 예측·가치 평가를 하지 않는다. 출력은 공시 원문 인용과 산술 비교뿐이다.
- **Codex 실로드 — 부분 확인(아엔 로컬, 2026-07-10).** MCP 서버가 Codex CLI(v0.143.0)에 등록·연결되어 도구 10종이 인식됨을 실증 확인(당시 스냅샷 기준). 플러그인 카탈로그 등록은 마켓플레이스 스냅샷 규격상 별도 작업이 필요하여 정적 검증으로 대체. 이후 추가된 prebuy-check(4번째 스킬)·krx_risk_flags(11번째 도구)는 실로드 스냅샷 밖이라 정적 검증(전체 테스트 + 컨트랙트)으로 확인.
- 정정공시 계보 추적은 휴리스틱(제목 접두 기반). 대화형 UX 품질은 SKILL.md 지시문으로만 관리(자동 검증 밖).
