"""G6 급변일 감지 테스트. detect_moves.py 대상.

기준: 일간 변동률 절대값 ≥ 5% 또는 20거래일 롤링 z-score ≥ 2.
방어 ①분산 0/NaN → z 건너뛰고 abs만 ②가격 0/NaN(거래정지) → 후보 제외 + 결측 표기.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import detect_moves as dm

CFG = {"abs_threshold_pct": 5.0, "zscore_threshold": 2.0, "zscore_window": 20}


def _rows(changes, close=100.0):
    # change_pct 리스트 → 가격 행(날짜는 순번, close 고정/지정)
    out = []
    for i, c in enumerate(changes):
        cl = close[i] if isinstance(close, list) else close
        out.append({"date": f"2025-01-{i+1:02d}", "close": cl, "change_pct": c})
    return out


def test_abs_move_detected():
    rows = _rows([0.1] * 20 + [6.2])
    res = dm.detect_moves(rows, CFG)
    assert any(m["date"] == "2025-01-21" for m in res["moves"])

def test_no_move_when_flat():
    res = dm.detect_moves(_rows([0.1] * 25), CFG)
    assert res["moves"] == []

def test_zscore_move_below_abs():
    # 이전 20일 잔잔한 변동(±0.1, 분산>0), 그다음 +4% (abs 5 미만이나 z-score 급변)
    rows = _rows([0.1, -0.1] * 10 + [4.0])
    res = dm.detect_moves(rows, CFG)
    assert any(m["date"] == "2025-01-21" and any("z" in t for t in m["tags"]) for m in res["moves"])

def test_zero_variance_skips_zscore():
    # 이전 20일 표준편차 0 → z 건너뛰고 abs만. 21일차 +4%는 abs 미만 → 급변 아님
    rows = _rows([2.0] * 20 + [4.0])
    res = dm.detect_moves(rows, CFG)
    assert all(m["date"] != "2025-01-21" for m in res["moves"])

def test_missing_day_excluded_and_flagged():
    closes = [100.0] * 22
    closes[21] = 0.0  # 거래정지(가격 0)
    rows = _rows([0.1] * 21 + [9.0], close=closes)
    res = dm.detect_moves(rows, CFG)
    assert "2025-01-22" in res["missing_days"]
    assert all(m["date"] != "2025-01-22" for m in res["moves"])

def test_threshold_note_present():
    res = dm.detect_moves(_rows([0.1] * 5), CFG)
    assert "5" in res["threshold_note"] and "2" in res["threshold_note"]
