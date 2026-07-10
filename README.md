# 왜샀지 (whybuy) — 제출물 안내

**왜샀지는 초보 투자자의 투자 여정 전체를 지키는 도구다.** 살 때(사기 전 공식 기록 점검), 산 뒤(매수일 기준 타임라인), 흔들릴 때(왜 샀는지 재구성), 팔기 직전(그 이유가 아직 유효한지 판정)까지 — 매 국면에서 **추천하지 않고 사실만 전달한다.** 판단은 사용자의 몫, 근거는 왜샀지의 몫이다. 없으면 없다고 말하는 **부재의 정직**과, 있는 사실은 해석 없이 그대로 보여주는 **존재의 정직** 위에 서 있다. 국내 상장주식 전용 Codex 플러그인 — 스킬 4종 + 로컬 MCP 서버 11도구 + 오프라인 픽스처.

> **두 개의 문서만 보면 됩니다.** 이 **README**로 제출물이 무엇인지 이해하고, **[HOW_TO_USE.md](HOW_TO_USE.md)** 를 따라 직접 돌려보며 동작을 두 눈으로 확인할 수 있습니다.

---

## 제출물 구조

```
submission/
├── src/                       # 플러그인 본체 (그대로 Codex 플러그인으로 로드된다)
│   ├── .codex-plugin/plugin.json   # 플러그인 매니페스트 (필수)
│   ├── .mcp.json                   # MCP 서버 선언 (whybuy-dart → mcp/server.py)
│   ├── skills/                     # 스킬 4종 (각 SKILL.md)
│   │   └── prebuy-check/  buy-timeline/  reason-recall/  thesis-audit/
│   ├── mcp/                        # MCP stdio 서버 + DART/KRX 클라이언트 (as_of 필터)
│   ├── tools/                      # 파이프라인 순수 함수 + 얇은 CLI + 검증 스크립트
│   ├── data/fixtures/              # 오프라인 픽스처 (공시·재무·KRX 위험명단, 원천 raw 포함)
│   ├── verification/               # 검증 재현 결과 (final-verification·link-check) — 대화 로그 아님
│   ├── tests/                      # 테스트 스위트 + golden 스냅샷
│   ├── requirements.txt
│   └── README.md                   # ← 플러그인 설치·스킬·MCP 등록 사용법
├── README.md                  # ← 이 문서 (제출물 안내·검증 재현·실로드 고지)
├── HOW_TO_USE.md              # ← 직접 돌려보는 실행 안내서 (명령 + 실제 출력 대조)
└── logs/claude-code/          # 개발 대화 로그 원본 (편집·요약 없음, 공식 log-hooks 수집)
```

- **`src/`** — 플러그인 본체. 이 폴더가 그대로 Codex 플러그인이다.
- **`logs/claude-code/`** — 이 플러그인을 만든 개발 대화의 **원본 세션 로그**(편집 없음, API 키 0건 전수 검사 완료).
- **`src/verification/`** — 개발 중 실행한 **검증 재현 결과**(최종 검증 요약·DART 원문 링크 점검). 대화 로그가 아니다. 대화 원본은 `logs/claude-code/`에만 있다.

## 검증 재현법 — 키 없이, 오프라인으로 완전 재현

픽스처가 함께 배포되므로 **API 키·외부 네트워크 없이** 전부 재현된다. 기본 모드가 `WHYBUY_MODE=fixture`라 심사위원이 **키 없이** 검증할 수 있다.

```bash
cd src
python -m venv .venv && . .venv/bin/activate    # 또는: uv venv .venv
pip install -r requirements.txt                  # 또는: uv pip install -r requirements.txt

.venv/bin/python -m pytest -q                    # → 181 passed
bash tools/run_all_contracts.sh                  # → 컨트랙트 3종 × 3케이스 전부 PASS
.venv/bin/python tools/validate_fixtures.py      # 픽스처 스키마 검증
.venv/bin/python tools/validate_ledger.py data/ledger/reasons.json
```

저장소 밖 임시 폴더에 풀어 새 가상환경에서 **키 없이 `pytest` → 181 passed**, 컨트랙트 전부 PASS가 재현됨을 확인했다. 스킬을 실제로 돌려보는 단계별 안내는 **[HOW_TO_USE.md](HOW_TO_USE.md)** 를, 플러그인 설치·MCP 등록은 **[src/README.md](src/README.md)** 를 본다.

## 실로드 검증 — 부분 성공, 정직 고지

- **MCP 서버 실연결 확인(아엔 로컬, 2026-07-10).** MCP 서버를 Codex CLI(v0.143.0)에 `codex mcp add`로 등록해 **도구 11종이 실제로 연결·인식됨**을 확인했다.
- **플러그인 카탈로그 로드는 정적 검증으로 대체.** 플러그인 카탈로그 등록은 마켓플레이스 스냅샷 규격상 별도 작업이 필요해, 전체 테스트(181 passed) + 컨트랙트로 대체 검증했다. 실로드 스냅샷 이후 추가된 `prebuy-check`(4번째 스킬)·`krx_risk_flags`(11번째 도구)도 정적 검증으로 확인했다.
- 되는 것은 됐다고, 정적 검증으로 대체한 것은 대체했다고 그대로 적는다. 과장하지 않는다 — 이것도 부재의 정직이다.

## 범위·한계

- **국내 상장주식 전용.** 해외주식은 아직 다루지 않는다(확장 스텁도 없음).
- 종목 추천·매매 지시·시세 예측·가치 평가를 하지 않는다. 출력은 공시 원문 인용과 산술 비교뿐이다.
- 정정공시 계보 추적은 휴리스틱(제목 접두 기반). 대화형 UX 품질은 SKILL.md 지시문으로만 관리(자동 검증 밖).
