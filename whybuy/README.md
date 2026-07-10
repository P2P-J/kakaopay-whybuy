# 왜샀지 (whybuy) — 플러그인 사용법

국내 상장주식 전용 Codex 플러그인. 초보 투자자의 투자 여정 전체 — **사기 전 → 산 뒤 → 왜 샀나 → 아직 유효한가** — 를 스킬 4종으로 지킨다. 종목을 추천하지 않고, 공시 원문·거래소 명단이라는 **공식 기록의 사실만** 전달한다.

> 이 문서는 **플러그인을 설치·등록**하는 방법이다. 실제로 스킬을 하나씩 돌려보며 동작을 확인하려면 **[HOW_TO_USE.md](../HOW_TO_USE.md)**, 제출물 전체 안내·검증 재현은 루트 **[README.md](../README.md)** 를 본다.

## 스킬 4종

초보 투자자 A씨의 하루를 그대로 스킬 순서로 옮겼다.

| 스킬 | 사용자의 질문 | 하는 일 |
|---|---|---|
| **`prebuy-check`** | "이거 사기 전에 알아둘 게 있나?" | 공식 기록 3층(거래소 위험명단·재무·지배구조)을 훑어 **눈에 띄는 사실만** 정리한다. 판단은 하지 않는다. |
| **`buy-timeline`** | "내가 산 뒤로 뭐가 달라졌어?" | 매수일을 원점으로 앵커해 그 뒤 공시를 재정렬하고, 수익률을 시장 대비로 병기한다. 급변일에 매칭 공시가 없으면 "변한 사실 없음"을 고정 출력. |
| **`reason-recall`** | "나 이거 왜 샀더라?" | 산 이유를 서술형이 아니라 매수일 주변 공시로 만든 **객관식**으로 되살려 원장에 기록한다. |
| **`thesis-audit`** | "그 이유 아직 유효해?" | 기록한 논거를 DART 공시 원문과 대조해 유효/반증/데이터부재로 판정한다. `--mirror`는 매도 버튼 앞의 거울(가격이 아니라 논거의 생사를 보여준다). |

## 설치

```bash
cd src                       # 플러그인 루트 (.codex-plugin/ 이 있는 곳)
python -m venv .venv && . .venv/bin/activate    # 또는: uv venv .venv
pip install -r requirements.txt                  # 또는: uv pip install -r requirements.txt
```

**데이터는 픽스처 모드(`WHYBUY_MODE=fixture`)가 기본**이라 API 키·네트워크 없이 전부 동작한다. 실제 DART를 조회하는 라이브 모드로 바꿀 때만 키가 필요하다:

```bash
cp .env.example .env         # DART_API_KEY 채우고 WHYBUY_MODE=live
```

## Codex에 MCP 서버 등록

`.codex-plugin/plugin.json`은 공식 규격대로 `skills`를 폴더(`./skills`)로, `mcpServers`를 `./.mcp.json` 경로로 가리킨다. `.mcp.json`의 command·args는 이식성을 위해 상대경로(`python`, `mcp/server.py`)로 커밋돼 있다.

로컬 Codex CLI에 직접 붙일 때는 Codex가 플러그인 루트를 cwd로 주지 않으므로 **command·args를 절대경로로** 지정한다:

```bash
codex mcp add whybuy-dart -- /abs/경로/src/.venv/bin/python /abs/경로/src/mcp/server.py
codex mcp list               # whybuy-dart 가 enabled 로 뜨는지 확인
```

MCP 도구 11종: `dart_resolve_corp`·`dart_list_disclosures`·`dart_get_financials`·`dart_get_report_item`·`dart_get_events`·`dart_get_insider`·`price_get_daily`·`ledger_read`·`ledger_write`·`gate_check`·`krx_risk_flags`.

## 설계 원칙 4가지

1. **공식 기록 원문만 인용** — 판정 근거는 전부 DART 공시 rcp_no + 원문 URL. 뉴스·커뮤니티는 판정에 안 쓴다.
2. **해석·권유 금지, 기계로 강제** — 모든 브리핑은 저장 전 `compliance_gate`를 통과한다(지시·예측·평가어 0건). 약속이 아니라 테스트로 증명한다.
3. **부재의 정직** — 없으면 없다고 말한다. 매칭 공시가 없으면 설명을 지어내지 않고 "변한 사실 없음"을 고정 출력.
4. **판정의 근거를 열어 보인다** — 같은 원장 + 같은 `as_of` → 항상 같은 판정(결정성). 모든 판정에 `rule_id` + 원문 링크.

`as_of` 필터는 `mcp/dart_client` 한 곳에서 강제되어 도구가 늘어도 시점 누출이 구조적으로 불가능하고, 판정 엔진(`tools/verdict_engine`)은 시세를 임포트하지 않는다(가격 격리, 소스+네임스페이스 이중 테스트).
