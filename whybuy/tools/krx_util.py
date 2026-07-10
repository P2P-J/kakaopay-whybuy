"""KRX 위험 목록 CSV 순수 변환 함수 — whybuy (G10).

data.krx.co.kr 정보데이터시스템 통계 CSV(아엔 수동 다운로드, EUC-KR)를 공통 스키마로
변환한다. 파일마다 컬럼 구성이 달라(관리종목/매매거래정지/불성실공시 등) **헤더 이름으로**
매핑한다. 출력: [{ticker, name, market, date(ISO), reason}]. 순수 함수(네트워크·상태 없음).
"""
from __future__ import annotations

import csv
import io

_TICKER_COL = "종목코드"
_NAME_COL = "종목명"
_MARKET_COL = "시장구분"
_DATE_COLS = ["지정일", "정지일", "최초지정일"]      # 우선순위 순
_REASON_COLS = ["지정사유", "정지사유", "불성실유형"]


def _first_idx(header_index: dict, names: list[str]):
    for n in names:
        if n in header_index:
            return header_index[n]
    return None


def parse_krx_risk_csv(text: str) -> list[dict]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    hidx = {h.strip(): i for i, h in enumerate(rows[0])}
    t_i = hidx.get(_TICKER_COL)
    n_i = hidx.get(_NAME_COL)
    m_i = hidx.get(_MARKET_COL)
    d_i = _first_idx(hidx, _DATE_COLS)
    r_i = _first_idx(hidx, _REASON_COLS)
    if t_i is None:
        return []

    def cell(cells, i):
        return cells[i].strip() if i is not None and len(cells) > i else ""

    out = []
    for cells in rows[1:]:
        ticker = cell(cells, t_i)
        if not ticker:
            continue
        out.append({
            "ticker": ticker,
            "name": cell(cells, n_i),
            "market": cell(cells, m_i),
            "date": cell(cells, d_i).replace("/", "-"),
            "reason": cell(cells, r_i),
        })
    return out
