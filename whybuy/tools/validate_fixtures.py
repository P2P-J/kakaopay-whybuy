#!/usr/bin/env python3
"""픽스처 스키마·완결성 검증 (G1 완료판정 tool) — whybuy.

data/fixtures/의 corp/disclosures/financials/report_items/prices가 PRD 5.2 스키마와
필수 파일 존재 조건을 만족하는지 검사한다. 위반 목록을 출력하고 exit 1, 무결하면 exit 0.
네트워크 없이 디스크만 읽는다 (수집과 분리된 방어선).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"

EXPECTED_TICKERS = {"005930", "035720", "105560", "017670", "033780"}
PRICE_COLS = ["date", "open", "high", "low", "close", "volume", "change_pct"]
RCP_RE = re.compile(r"^\d{14}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKETS = {"kospi", "kosdaq", "konex", "etc", "unknown"}


def _err(errs: list, msg: str) -> None:
    errs.append(msg)


def validate() -> list[str]:
    errs: list[str] = []

    # corp: 5개 존재 + 필수 필드, ticker 매핑
    corp_files = sorted((FIX / "corp").glob("*.json"))
    tickers_seen = set()
    corp_by_code = {}
    for f in corp_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        code = f.stem
        corp_by_code[code] = d
        for field in ("corp_code", "corp_name", "stock_code", "market"):
            if not d.get(field):
                _err(errs, f"corp/{f.name}: 필수 필드 누락 {field}")
        if d.get("market") not in MARKETS:
            _err(errs, f"corp/{f.name}: market 값 이상 {d.get('market')}")
        if d.get("stock_code"):
            tickers_seen.add(d["stock_code"])
    missing = EXPECTED_TICKERS - tickers_seen
    if missing:
        _err(errs, f"corp: 대상 종목 누락 {sorted(missing)}")

    # disclosures: 각 corp별 파일 존재 + 행 스키마
    for code in corp_by_code:
        f = FIX / "disclosures" / f"{code}.json"
        if not f.exists():
            _err(errs, f"disclosures/{code}.json 없음")
            continue
        rows = json.loads(f.read_text(encoding="utf-8"))
        if not rows:
            _err(errs, f"disclosures/{code}.json: 공시 0건")
        seen_rcp = set()
        for r in rows:
            if not RCP_RE.match(r.get("rcp_no", "")):
                _err(errs, f"disclosures/{code}: rcp_no 형식 오류 {r.get('rcp_no')!r}")
            if not ISO_RE.match(r.get("submitted", "")):
                _err(errs, f"disclosures/{code}: submitted 형식 오류 {r.get('submitted')!r}")
            for field in ("title", "pblntf_ty", "url"):
                if field not in r:
                    _err(errs, f"disclosures/{code}: 필드 누락 {field}")
            if "is_correction" not in r:
                _err(errs, f"disclosures/{code}: is_correction 누락 (rcp={r.get('rcp_no')})")
            if r.get("rcp_no") in seen_rcp:
                _err(errs, f"disclosures/{code}: rcp_no 중복 {r.get('rcp_no')}")
            seen_rcp.add(r.get("rcp_no"))

    # financials: corp별 디렉토리에 최소 1개, basis·accounts 검증
    for code in corp_by_code:
        fdir = FIX / "financials" / code
        periods = sorted(fdir.glob("*.json")) if fdir.exists() else []
        if not periods:
            _err(errs, f"financials/{code}/: 기간 파일 0개")
        for pf in periods:
            block = json.loads(pf.read_text(encoding="utf-8"))
            if block.get("basis") not in ("CFS", "OFS"):
                _err(errs, f"financials/{code}/{pf.name}: basis 이상 {block.get('basis')}")
            if not block.get("accounts"):
                _err(errs, f"financials/{code}/{pf.name}: accounts 비어있음")

    # report_items: corp별 파일 존재 + 4개 항목 키
    for code in corp_by_code:
        f = FIX / "report_items" / f"{code}.json"
        if not f.exists():
            _err(errs, f"report_items/{code}.json 없음")
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for k in ("dividend", "major_shareholder", "audit_opinion", "treasury_stock"):
            if k not in d:
                _err(errs, f"report_items/{code}.json: 항목 누락 {k}")

    # prices: 종목 5 + 지수 2, 헤더·날짜 오름차순
    price_files = {"index_kospi", "index_kosdaq"} | EXPECTED_TICKERS
    for name in sorted(price_files):
        f = FIX / "prices" / f"{name}.csv"
        if not f.exists():
            _err(errs, f"prices/{name}.csv 없음")
            continue
        with f.open(encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            if header != PRICE_COLS:
                _err(errs, f"prices/{name}.csv: 헤더 불일치 {header}")
                continue
            prev_date = ""
            n = 0
            for row in reader:
                n += 1
                if not ISO_RE.match(row[0]):
                    _err(errs, f"prices/{name}.csv: 날짜 형식 오류 {row[0]!r}")
                elif row[0] <= prev_date:
                    _err(errs, f"prices/{name}.csv: 날짜 비오름차순 {prev_date}->{row[0]}")
                prev_date = row[0]
            if n == 0:
                _err(errs, f"prices/{name}.csv: 데이터 행 0")

    return errs


def main() -> int:
    if not FIX.exists():
        print(f"픽스처 디렉토리 없음: {FIX}")
        return 1
    errs = validate()
    if errs:
        print(f"픽스처 검증 실패 — {len(errs)}건:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("픽스처 검증 통과: corp/disclosures/financials/report_items/prices 스키마·완결성 OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
