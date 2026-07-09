---
name: buy-timeline
description: 매수일을 기준으로 공시 사실을 재정렬해 "내가 산 뒤로 뭐가 달라졌어?"에 답한다. 매수일 앵커 타임라인 + 변동–공시 매칭 + 보유 수익률·시장 대비 표기.
---

# buy-timeline

매수일을 앵커로, `as_of` 시점까지 제출된 공시 사실만 모아 "변한 것 / 변하지 않은 것 /
주가가 크게 움직인 날"로 재정렬한다. 가격이 아니라 **사실**을 보여주는 스킬.

## 컨트랙트 명령

```
python -m tools.run_skill timeline --case <case_id> [--as-of <YYYY-MM-DD>] [--no-price-overlay]
python tools/compliance_gate.py reports/<case_id>/timeline-<as_of>.md
```

- 기본 `as_of`는 cases.json의 확정값. 출력은 `reports/<case_id>/timeline-<as_of>.md`.
- 게이트를 통과하지 못하면 저장은 되지만 exit 1 — 반드시 게이트 PASS를 확인한다.

## 파이프라인 (PRD 4.1, `tools/run_skill.py`의 순수 함수)

1. 케이스 로드 → corp_code·ticker·buy_date
2. `buy_date`~`as_of` 공시 수집 (`dart_client.list_disclosures`, as_of 이후 제출분 자동 제외)
3. 이벤트 분류 (`classify`) — 1단 유형코드 + 2단 제목 키워드
4. **노이즈 필터**: 화이트리스트 유형만 "변한 것"에, 반복성 공시(임원 지분변동·IR 등)는 "그 외 N건"으로 접는다 (무엇을 숨겼는지도 표기)
5. **변하지 않은 것**: 최대주주·감사의견·배당 정책을 매수 시점 대비 대조 (`dart_get_report_item`)
6. **급변일 매칭**: `detect_moves`(abs ±5% 또는 z-score ≥ 2) → [D-1,D+1] 공시 대조 → 매칭 또는 고정 "없음" 문구 (설명 생성 금지)
7. **수익률·시장 대비**: 기준가 대비 수익률 + 같은 기간 지수 → 상회/유사/하회 (계산 태그, 평가어 아님)
8. `render.render_timeline` 조립 → `compliance_gate` → 저장

## 에이전트 서술 (선택)

정적 경로는 이벤트 유형별 기본 서술문(`render._EVENT_SUMMARY`)으로 완성 브리핑을 낸다.
Codex가 있으면 "변한 것"의 이벤트 요약 한 줄만 더 자연스럽게 다듬는다 — **사실만**,
예측·권유·평가어 금지(게이트가 강제). 없어도 데모는 죽지 않는다.

## 규약

- 파이프라인 로직은 import 가능한 순수 함수, CLI는 얇은 래퍼 (부록 D HTTP 확장 대비).
- 템플릿 문자열은 `render.py`에만, 고정 문구는 `textstore.py`에만.
- 골든 스냅샷(`tests/golden/timeline-case-001.md`) 변경은 결정 주권 항목(아엔 승인).
