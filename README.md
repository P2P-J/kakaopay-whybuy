# 왜샀지 (whybuy) — 제출물 안내

**왜샀지는 초보 투자자의 투자 여정 전체를 지키는 도구다.** 판단은 사용자의 몫, 근거는 왜샀지의 몫. 없으면 없다고 말하는 **부재의 정직**과, 있는 사실은 해석 없이 그대로 보여주는 **존재의 정직** 위에 서 있다.

국내 상장주식 전용 Codex 플러그인 — 스킬 4종(사기 전 점검 → 산 뒤 타임라인 → 왜 샀나 재인 → 아직 유효한가 판정) + 로컬 MCP 서버 11도구 + 오프라인 픽스처.

---

## 제출물 구조

```
submission/
├── src/                       # 플러그인 루트 전체 (그대로 Codex 플러그인으로 로드된다)
│   ├── .codex-plugin/
│   │   └── plugin.json         # 플러그인 매니페스트 (필수)
│   ├── .mcp.json               # MCP 서버 선언 (whybuy-dart → mcp/server.py)
│   ├── skills/                 # 스킬 4종 (각 SKILL.md)
│   │   ├── prebuy-check/
│   │   ├── buy-timeline/
│   │   ├── reason-recall/
│   │   └── thesis-audit/
│   ├── mcp/                    # MCP stdio 서버 + DART/KRX 클라이언트 (as_of 필터)
│   ├── tools/                  # 파이프라인 순수 함수 + 얇은 CLI + 검증 스크립트
│   ├── data/fixtures/          # 오프라인 픽스처 (공시·재무·KRX 위험명단, 원천 raw 포함)
│   ├── tests/                  # 테스트 스위트 + golden 스냅샷
│   ├── requirements.txt
│   └── README.md               # ← 플러그인 설치·사용법
├── README.md                  # ← 이 문서 (제출물 안내·검증 재현법)
└── logs/
    └── claude-code/            # 개발 대화 로그 원본 (편집 없음, 공식 log-hooks 수집)
```

플러그인 설치·스킬 사용법·MCP 등록은 **[src/README.md](src/README.md)** 를 본다.

## 검증 재현법 — 키 없이, 오프라인으로 완전 재현

픽스처가 함께 배포되므로 **API 키·외부 네트워크 없이** 전부 재현된다. 기본 모드가 `WHYBUY_MODE=fixture`라 심사위원이 키 없이도 검증할 수 있다.

```bash
cd src
uv venv .venv && . .venv/bin/activate      # 또는: python -m venv .venv
uv pip install -r requirements.txt          # 또는: pip install -r requirements.txt

.venv/bin/python -m pytest -q               # 전체 테스트 스위트
bash tools/run_all_contracts.sh             # 컨트랙트 3종 × 3케이스, 전부 exit 0
.venv/bin/python tools/validate_fixtures.py # 픽스처 스키마 검증
.venv/bin/python tools/validate_ledger.py data/ledger/reasons.json
```

파이프라인·판정·게이트·산출물이 전부 오프라인 픽스처로 재현된다(정적 실행 경로 강제). 데모 실행 경로는 [src/README.md](src/README.md#스킬-실행-3분-데모-경로) 참조.

## 실로드 검증 — 부분 성공, 정직 고지

- **MCP 실연결 확인(아엔 로컬, 2026-07-10).** MCP 서버가 Codex CLI(v0.143.0)에 등록·연결되어 도구가 인식됨을 실증 확인(당시 스냅샷 기준).
- **정적 검증으로 보강한 범위.** 플러그인 카탈로그 등록은 마켓플레이스 스냅샷 규격상 별도 작업이 필요해 정적 검증으로 대체했다. 실로드 스냅샷 이후 추가된 `prebuy-check`(4번째 스킬)·`krx_risk_flags`(11번째 도구)는 실로드 밖이라 전체 테스트 + 컨트랙트로 확인했다.
- 되는 것은 됐다고, 정적 검증으로 대체한 것은 대체했다고 그대로 적는다. 이것도 부재의 정직이다.

## 범위·한계

- **국내 상장주식 전용.** 해외주식은 아직 다루지 않는다(확장 스텁도 없음).
- 종목 추천·매매 지시·시세 예측·가치 평가를 하지 않는다. 출력은 공시 원문 인용과 산술 비교뿐이다.
- 정정공시 계보 추적은 휴리스틱(제목 접두 기반). 대화형 UX 품질은 SKILL.md 지시문으로만 관리(자동 검증 밖).

## 개발 로그

`logs/claude-code/`는 이 플러그인을 만든 개발 대화의 **원본 세션 로그**다. 공식 log-hooks 도구가 수집했으며 편집·요약·키 노출이 없다(제출 전 전수 검사로 API 키 0건 확인).
