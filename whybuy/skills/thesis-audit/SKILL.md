---
name: thesis-audit
description: 기록된 매수 논거를 최신 공시에 대조해 "그 이유 아직 유효해?"에 답한다. 유효/약화/반증/확인불가 판정 + 거울 모드(과거–현재 비교).
---

# thesis-audit

원장에 기록된 논거(reason-recall 산출)를 `as_of` 시점 공시에 대조해 판정한다. 판정은
`verdict_engine`의 결정적 룰. `--mirror`는 매도 검토 순간을 위한 과거–현재 거울 브리핑.

## 컨트랙트 명령

```
python -m tools.run_skill audit --case <case_id> [--as-of <YYYY-MM-DD>] [--commit]
python -m tools.run_skill audit --case <case_id> --mirror
python tools/compliance_gate.py reports/<case_id>/audit-<as_of>.md
```

- 판정은 `verdict_engine`(RULE-EARN/RET/DIV/GRW/NEW/THM/PRC). 같은 원장+같은 as_of → 같은 판정.
- `--commit`: 판정 이력을 원장 `audits[]`에 append(논거 생사 변천 추적). 게이트 통과 시에만.
- `--mirror`: 과거(기록한 이유) — 현재(수익률+판정+신규 사실) — 고정 질문으로 종결.

## 파이프라인 (PRD 4.3)

1. 원장에서 논거 로드 (`ledger_store.read`)
2. `verdict_engine.evaluate`로 논거별 판정 → `{status, evidence(rcp/url/item/delta), rule_id}`
3. **신규 중대 사실 스캔** — 3조건 코드 고정: 중대 유형(증자·CB·감자·소송·사업중단·자기주식 처분·최대주주 변경) ∧ 매수일 이후 제출 ∧ **원장 논거와 미연결**
4. 브리핑 조립(`render.render_audit` / `render_mirror`) — 판정 라인 `{상태} — {근거·대조항목·수치} [원문](url) (rule: id)`
5. `audits[]` append → 컴플라이언스 게이트 → 저장

## 판정 상태·안전 규약

- 상태 4종: 유효/약화/반증/확인불가. **확인불가에 유효·반증 딱지 절대 금지**(테마·저가매수 등 검증 불가 유형).
- 판정 라인 차등(게이트): 유효/약화/반증은 원문 URL 필수, 확인불가는 부재 사실 문구.
- **가격 격리**: 판정은 `verdict_engine`이 담당하며 시세를 쓰지 않는다. 거울의 수익률은 참고 표기(판정 근거 아님).
- 거울 고정 질문("이 매도의 근거는 가격인가요, 사실인가요?")은 게이트 허용 예외의 유일한 의문문.
- 골든 스냅샷(`tests/golden/{audit,mirror}-*.md`) 변경은 결정 주권 항목(아엔 승인).

## 규약

- 판정은 원장에 저장된 type 기준 결정적 연산 — LLM 재분류 금지(reason-recall에서 1회 고정).
- 조립은 `render.py`, 문구는 `textstore.py` 단일 출처.
