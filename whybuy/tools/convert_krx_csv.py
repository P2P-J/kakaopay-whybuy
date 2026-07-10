#!/usr/bin/env python3
"""KRX 위험 목록 raw CSV(아엔 다운로드, EUC-KR) → 픽스처 변환 — whybuy (G10).

openapi.krx.co.kr 오픈API에는 층1 위험 신호가 없어(시세·지수만), data.krx.co.kr
정보데이터시스템 통계 CSV를 수동 다운로드해 변환한다(G1 지수 CSV와 동일 폴백 경로).
입력: data/fixtures/raw/krx_*.csv → 출력: data/fixtures/krx/{kind}.json
투자위험종목은 현재 지정 0건이라 빈 카테고리로 생성한다(존재의 정직 — 카테고리는 있고 값만 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from krx_util import parse_krx_risk_csv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "fixtures" / "raw"
OUT = ROOT / "data" / "fixtures" / "krx"

# 명단 기준일(스냅샷) = 아엔 CSV 다운로드일. KRX 명단은 시점 스냅샷이라 기준일이 핵심.
# 재다운로드 시 이 값을 갱신한다. 브리핑에 "이 점검은 {as_of} 거래소 명단 기준"으로 노출.
DOWNLOADED_ON = "2026-07-10"

# KRX 위험 신호는 DART rcp_no 같은 종목별 원문 URL이 CSV에 없다(거래소 조치라). 대신 신호별
# 출처명 + KRX 공식 채널 통계 페이지 URL을 근거로 붙인다(추적 가능성: "거래소 명단에서 왔다").
_KIND_ALERT = "https://kind.krx.co.kr/investwarn/investattentwarnrisky.do?method=investattentwarnriskyMain"
_KRX_DATA = "https://data.krx.co.kr/"

# kind(raw 파일명) → (중립 공식 신호명, 출처명, 출처 URL)
SIGNALS = {
    "krx_admin_issues": ("관리종목", "한국거래소 관리종목 지정 현황", _KRX_DATA),
    "krx_trading_halt": ("매매거래정지", "한국거래소 매매거래정지 종목 현황", _KRX_DATA),
    "krx_investment_alert": ("투자주의", "한국거래소 시장경보 — 투자주의종목", _KIND_ALERT),
    "krx_investment_warning": ("투자경고", "한국거래소 시장경보 — 투자경고종목", _KIND_ALERT),
    "krx_warning_kosdaq": ("투자주의환기종목", "한국거래소 투자주의환기종목(코스닥) 현황", _KRX_DATA),
    "krx_unfaithful_disclosure": ("불성실공시법인 지정", "한국거래소 불성실공시법인 지정 현황", _KRX_DATA),
}
EMPTY_SIGNALS = {"krx_investment_risk": ("투자위험종목", "한국거래소 시장경보 — 투자위험종목", _KIND_ALERT)}


def _write(kind: str, label: str, source: str, url: str, rows: list) -> None:
    meta = {"signal": label, "kind": kind, "source_name": source, "source_url": url,
            "as_of": DOWNLOADED_ON, "rows": rows}
    (OUT / f"{kind}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def convert() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for kind, (label, source, url) in SIGNALS.items():
        raw = RAW / f"{kind}.csv"
        rows = parse_krx_risk_csv(raw.read_text(encoding="euc-kr")) if raw.exists() else []
        _write(kind, label, source, url, rows)
        total += len(rows)
        print(f"  {label:<16} {len(rows):>4}건 → krx/{kind}.json")
    for kind, (label, source, url) in EMPTY_SIGNALS.items():
        _write(kind, label, source, url, [])
        print(f"  {label:<16} {0:>4}건 → krx/{kind}.json (빈 카테고리)")
    print(f"총 {total}건 · 명단 기준일 {DOWNLOADED_ON}")
    return total


if __name__ == "__main__":
    convert()
