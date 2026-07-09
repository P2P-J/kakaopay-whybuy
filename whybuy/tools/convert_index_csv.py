#!/usr/bin/env python3
"""KRX 지수 원본 CSV(아엔 다운로드, EUC-KR)를 우리 가격 스키마로 변환.

pykrx 지수 조회가 전면 실패(KRX 빈 응답)하는 환경의 폴백 경로(G1 plan Task 8).
입력: data/fixtures/raw/index_{kospi,kosdaq}.csv
출력: data/fixtures/prices/index_{kospi,kosdaq}.csv
컬럼: date,open,high,low,close,volume,change_pct (날짜 오름차순)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_util import parse_krx_index_csv  # noqa: E402

FIELDS = ["date", "open", "high", "low", "close", "volume", "change_pct"]
ROOT = Path(__file__).resolve().parents[1]  # whybuy/


def convert(name: str) -> int:
    raw = ROOT / "data" / "fixtures" / "raw" / f"index_{name}.csv"
    out = ROOT / "data" / "fixtures" / "prices" / f"index_{name}.csv"
    text = raw.read_text(encoding="euc-kr")
    rows = parse_krx_index_csv(text)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    span = f"{rows[0]['date']}..{rows[-1]['date']}" if rows else "(empty)"
    print(f"{name}: {len(rows)} rows {span} -> {out.relative_to(ROOT)}")
    return len(rows)


if __name__ == "__main__":
    total = sum(convert(n) for n in ("kospi", "kosdaq"))
    if total == 0:
        sys.exit(1)
