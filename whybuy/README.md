# 왜샀지 (whybuy) — 플러그인 사용법

> "이 주식 왜 샀지?" — 카카오페이증권의 '어땠지'가 **시장의 시간**에 답한다면, 왜샀지는 **나의 시간**에 답한다. 매수일을 기준으로 공시 사실을 재정렬하고, 산 이유를 객관식으로 되찾아주며, 그 이유가 아직 유효한지 DART 공시 원문으로 판정한다. **추천하지 않는다. 사실을 전달한다.**

국내 상장주식 전용 Codex 플러그인 — 스킬 4종 + 로컬 MCP 서버 11도구 + 오프라인 픽스처.

> 이 문서는 **플러그인을 설치·사용**하는 방법이다. 제출물 전체 구조와 검증 재현법은 저장소 루트의 [README.md](../README.md)를 본다.

## 스킬 4종 — 초보자 여정 순서

초보 투자자 A씨의 하루를 그대로 스킬 순서로 옮겼다. "사기 전 → 산 뒤 → 왜 샀나 → 아직 유효한가".

| 스킬 | 사용자의 질문 | 하는 일 |
|---|---|---|
| **`prebuy-check`** | "이거 사기 전에 알아둘 게 있나?" | 공식 기록 3층 점검 — 거래소 위험 명단(KRX)·재무(자본잠식·연속손실·감사의견)·지배구조(대량 희석). **판단하지 않고** 눈에 띄는 공식 기록만 정리한다. |
| **`buy-timeline`** | "내가 산 뒤로 뭐가 달라졌어?" | 매수일을 원점(0)으로 앵커. 그 뒤 공시를 시간순 재정렬하고 급변일에 매칭 공시를 붙인다. 없으면 "변한 사실 없음"을 고정 출력. |
| **`reason-recall`** | "나 이거 왜 샀더라?" | 산 이유를 서술형으로 묻지 않고 **객관식 재인**으로 되살린다. 고른 논거를 원장(`data/ledger`)에 기록. |
| **`thesis-audit`** | "그 이유 아직 유효해?" | 기록한 논거를 DART 공시 원문과 대조해 유효/반증/데이터부재로 판정. `--mirror`로 매도 버튼 앞 거울 모드(가격이 아니라 논거의 생사를 보여준다). |

## 설치

```bash
cd src            # 플러그인 루트 (.codex-plugin/ 가 있는 곳)
uv venv .venv && . .venv/bin/activate
uv pip install -r requirements.txt
# 기본은 픽스처 오프라인 모드(WHYBUY_MODE=fixture) — 키 없이 전부 동작한다.
# 라이브 모드로 실제 DART를 칠 때만:
cp .env.example .env   # DART_API_KEY 채우고 WHYBUY_MODE=live
```

픽스처가 함께 배포되므로 **외부 네트워크·API 키 없이** 개발·테스트·데모가 오프라인으로 재현된다.

## 스킬 실행 (3분 데모 경로)

A씨의 여정 = 스킬의 순서: 불안(−N%) → 타임라인(사실을 본다) → 재인(이유가 생긴다) → 판정(이유의 생사) → 거울(가격인가, 사실인가).

```bash
cd src
# 막1·2 — 산 뒤로 뭐가 달라졌나 (타임라인)
.venv/bin/python -m tools.run_skill timeline --case case-002
# 막3 — 왜 샀더라 (객관식 재인 → 원장 기록)
.venv/bin/python -m tools.run_skill recall  --case case-002 --choose r2 --dry-run
# 막4 — 매도 버튼 앞의 거울 (킬러 장면: 손실 + 논거 반증)
.venv/bin/python -m tools.run_skill audit   --case case-002 --mirror
# 대비 — case-001은 손실인데 논거 유효(가격↔사실 엇갈림)
.venv/bin/python -m tools.run_skill audit   --case case-001 --mirror
```

산출물은 `reports/<case>/`. 세 데모 케이스: **case-001 삼성전자(손실·유효)**, **case-002 카카오(손실·반증, 거울 킬러)**, **case-003 KT&G(수익·유효)**.

## 로컬 Codex에 MCP 서버 등록

`.codex-plugin/plugin.json`은 공식 규격대로 `skills`를 폴더(`./skills`)로, `mcpServers`를 `./.mcp.json` 경로로 가리킨다. `.mcp.json`의 command·args는 이식성을 위해 상대경로(`python`, `mcp/server.py`)로 커밋돼 있다.

로컬 Codex CLI에 직접 붙일 때는 Codex가 플러그인 루트를 cwd로 주지 않으므로 **절대경로로** 등록한다:

```bash
codex mcp add whybuy-dart -- /abs/경로/src/.venv/bin/python /abs/경로/src/mcp/server.py
codex mcp list                        # whybuy-dart 가 enabled 로 뜨는지 확인
```

MCP 도구 11종: `dart_resolve_corp`·`dart_list_disclosures`·`dart_get_financials`·`dart_get_report_item`·`dart_get_events`·`dart_get_insider`·`price_get_daily`·`ledger_read`·`ledger_write`·`gate_check`·`krx_risk_flags`.

## 설계 원칙 4가지

1. **공식 기록 원문만 인용** — 판정 근거는 전부 DART 공시 rcp_no + 원문 URL. 뉴스·커뮤니티는 판정에 안 쓴다.
2. **해석·권유 금지, 기계로 강제** — 모든 브리핑은 저장 전 `compliance_gate`를 통과한다(지시·예측·평가어 0건). 약속이 아니라 테스트로 증명. 범위는 정직하게 "이 시스템의 산출물에서 0건 보장"이다.
3. **부재의 정직** — 없으면 없다고 말한다. 급변일에 매칭 공시가 없으면 설명을 지어내지 않고 "공식 기록상 변한 사실 없음"을 고정 출력.
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
