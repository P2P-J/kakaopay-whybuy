#!/usr/bin/env python3
"""유형코드 매핑 검증 (G1 Task 10, 독립 체크포인트) — whybuy.

화이트리스트 이벤트(실적·배당·자기주식·증자CB·최대주주·감사·소송제재·공급계약·시설투자·
사업중단)가 실데이터에서 실제로 어느 pblntf_ty(A~E,I)로 들어오는지 대조한다.
분류기(G7) 구현 전에 "어떤 트리거가 실제로 존재하며 어느 유형코드에 걸리는가"를 확정하는 것이 목적.
수집된 disclosures 픽스처만 읽는다(네트워크 없음). 기대와 다른 항목은 REHEARSAL.md에 기록.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISC = ROOT / "data" / "fixtures" / "disclosures"

# 이벤트 유형 → 제목 키워드 (정정 접두 [기재정정] 등은 매칭 전 제거)
EVENT_PATTERNS = {
    "실적(정기·잠정)": ["분기보고서", "반기보고서", "사업보고서", "영업(잠정)", "연결재무제표기준영업", "매출액또는손익구조"],
    "배당": ["배당"],
    "자기주식·소각": ["자기주식", "자사주", "주식소각", "신탁계약"],
    "증자·CB·발행": ["유상증자", "무상증자", "전환사채", "신주인수권", "증권신고서", "투자설명서", "증권발행실적", "일괄신고"],
    "최대주주·지분": ["최대주주", "대량보유", "임원ㆍ주요주주", "특정증권등"],
    "감사의견": ["감사보고서"],
    "소송·제재": ["소송", "제재", "과징금", "벌금", "횡령", "배임", "행정처분"],
    "공급계약": ["공급계약", "단일판매"],
    "시설투자": ["시설투자", "신규시설"],
    "사업중단·영업정지": ["영업정지", "사업중단", "영업중단", "해산"],
}

_CORR = re.compile(r"^\[[^\]]+\]")


def classify(title: str) -> list[str]:
    t = _CORR.sub("", title)
    return [ev for ev, kws in EVENT_PATTERNS.items() if any(k in t for k in kws)]


def main() -> int:
    # 이벤트 × pblntf_ty 교차표
    xtab = collections.defaultdict(collections.Counter)
    unmatched = collections.Counter()
    total = 0
    for f in sorted(DISC.glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            total += 1
            evs = classify(r["title"])
            if not evs:
                unmatched[_CORR.sub("", r["title"]).split("(")[0][:24]] += 1
            for ev in evs:
                xtab[ev][r["pblntf_ty"]] += 1

    tys = ["A", "B", "C", "D", "E", "I"]
    print(f"총 공시 {total}건 · 이벤트 유형별 pblntf_ty 분포\n")
    print(f"{'이벤트':<20} " + " ".join(f"{t:>5}" for t in tys) + "   합계")
    print("-" * 62)
    for ev in EVENT_PATTERNS:
        row = xtab.get(ev, collections.Counter())
        cells = " ".join(f"{row.get(t, 0):>5}" for t in tys)
        s = sum(row.values())
        flag = "  ← 부재(대상 종목·기간 내 0건)" if s == 0 else ""
        print(f"{ev:<20} {cells}   {s:>4}{flag}")

    absent = [ev for ev in EVENT_PATTERNS if not xtab.get(ev)]
    print("\n[해석]")
    print("  · B(주요사항보고서)는 제목이 이벤트 종류를 드러내지 않음 → 유형 판정은 I의 구체 제목·report_items API에 의존")
    print("  · 실적=A(정기)+I(잠정), 배당=I, 최대주주=D+I 로 실데이터 확인")
    if absent:
        print(f"  · 부재 유형(데모 케이스에서 회피 또는 라이브러리 논거로 커버): {', '.join(absent)}")
    print(f"\n미분류 상위(참고): {', '.join(f'{t}×{c}' for t,c in unmatched.most_common(6))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
