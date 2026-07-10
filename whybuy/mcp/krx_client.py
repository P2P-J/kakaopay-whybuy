"""KRX 위험 목록 접근 계층 (국내 전용) — whybuy (G10).

dart_client 옆의 소스별 클라이언트(분리 원칙). 층1 거래소 시장조치(관리종목·매매거래정지·
투자경고·불성실공시 등)를 종목코드로 조회한다. 소스는 data.krx.co.kr 정보데이터시스템
명단 CSV → 픽스처(krx/*.json). openapi.krx.co.kr 오픈API에는 이 신호가 없어(시세만) 명단
CSV를 쓰며, `KRX_API_KEY`는 위험 신호에 미사용(시세용). 종목별 원문 URL은 거래소 조치라
부재 — 대신 출처명·출처 URL·명단 기준일(as_of)을 붙여 추적성을 확보한다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KRX = ROOT / "data" / "fixtures" / "krx"


def _load() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(KRX.glob("*.json"))]


def snapshot_date() -> str:
    """명단 기준일(시점 스냅샷). 전 픽스처 공통 as_of — 브리핑 상단에 명시한다."""
    for d in _load():
        if d.get("as_of"):
            return d["as_of"]
    return ""


def risk_flags(ticker: str) -> list[dict]:
    """종목의 층1 KRX 신호 목록. 지정 안 됐으면 빈 목록(존재의 정직 — 없으면 없다).

    각 신호: {signal, source_name, source_url, as_of, date(지정일), reason(지정사유)}.
    """
    out = []
    for d in _load():
        for r in d["rows"]:
            if r["ticker"] == ticker:
                out.append({
                    "signal": d["signal"],
                    "source_name": d["source_name"],
                    "source_url": d["source_url"],
                    "as_of": d["as_of"],
                    "date": r["date"],
                    "reason": r["reason"],
                })
    return out
