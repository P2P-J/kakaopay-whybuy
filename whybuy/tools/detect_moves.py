"""급변일 감지 — whybuy (G6).

일별 시세에서 급변일을 감지한다 (config: abs ±5% 또는 20거래일 롤링 z-score ≥ 2).
방어: ①롤링 표준편차 0/NaN이면 z-score 건너뛰고 절대값 기준만 ②가격 0/NaN(거래정지)
날짜는 급변 후보에서 제외하고 "거래 데이터 결측일"로 표기. 가격은 x축 좌표로만 쓴다.

detect_moves(rows, cfg) → {moves, missing_days, threshold_note}. 급변 0건이어도 moves=[]
(부재의 정직 — 호출자가 고정 문구 출력). 순수 함수(네트워크·상태 없음).
"""
from __future__ import annotations

import math
import statistics as st


def _is_bad(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def detect_moves(rows: list[dict], cfg: dict) -> dict:
    win = cfg["zscore_window"]
    zt = cfg["zscore_threshold"]
    at = cfg["abs_threshold_pct"]

    moves, missing = [], []
    for i, r in enumerate(rows):
        if _is_bad(r.get("close")) or r.get("close") == 0 or _is_bad(r.get("change_pct")):
            missing.append(r["date"])
            continue
        chg = r["change_pct"]
        tags = []
        if abs(chg) >= at:
            tags.append(f"abs{chg:+.1f}%")
        # z-score (거래정지 결측일 제외한 직전 유효 change_pct 창)
        prior = [x["change_pct"] for x in rows[max(0, i - win):i]
                 if not _is_bad(x.get("change_pct")) and not _is_bad(x.get("close")) and x.get("close") != 0]
        if len(prior) >= win:
            sd = st.pstdev(prior)
            if sd and not math.isnan(sd):          # 방어①: 분산 0/NaN이면 z 건너뜀
                z = (chg - st.mean(prior)) / sd
                if abs(z) >= zt:
                    tags.append(f"z{z:+.1f}")
        if tags:
            moves.append({"date": r["date"], "change_pct": chg, "tags": tags})

    note = f"일간 변동률 절대값 {at:.0f}% 이상 또는 {win}거래일 롤링 z-score {zt:.0f} 이상"
    return {"moves": moves, "missing_days": missing, "threshold_note": note}
