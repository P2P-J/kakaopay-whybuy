#!/usr/bin/env python3
"""케이스 리허설 성립 검증 (G1 완료판정 tool) — whybuy.

cases.json의 각 케이스가 의도한 장면을 실데이터로 실제 만들어내는지 확인한다:
  · 매수일 이후 공시 ≥1 (재인 후보 원천)
  · 시세가 [매수일−마진, as_of] 구간을 커버 (z-score 창 확보)
  · 트리거·근거 rcp_no가 실제 공시 픽스처에 존재 (as_of 이전 제출)
  · case-002(급변 매칭): as_of까지 급변일(±abs 또는 z-score) ≥1
위반 시 목록 출력 + exit 1. 네트워크 없이 픽스처만 읽는다.
"""
from __future__ import annotations

import csv
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures"


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _prices(ticker: str) -> list[dict]:
    rows = list(csv.DictReader((FIX / "prices" / f"{ticker}.csv").open(encoding="utf-8")))
    for r in rows:
        r["change_pct"] = float(r["change_pct"])
    return rows


def _moves(rows: list[dict], as_of: str, cfg: dict) -> int:
    pm = cfg["price_move"]
    win, zt, at = pm["zscore_window"], pm["zscore_threshold"], pm["abs_threshold_pct"]
    n = 0
    for i, r in enumerate(rows):
        if r["date"] > as_of:
            break
        hit = abs(r["change_pct"]) >= at
        if not hit and i >= win:
            w = [x["change_pct"] for x in rows[i - win:i]]
            sd = st.pstdev(w)
            if sd > 0 and abs((r["change_pct"] - st.mean(w)) / sd) >= zt:
                hit = True
        n += hit
    return n


def check() -> list[str]:
    errs: list[str] = []
    cfg = _cfg()
    doc = json.loads((FIX / "cases.json").read_text(encoding="utf-8"))
    for c in doc["cases"]:
        cid, ticker, code = c["case_id"], c["ticker"], c["corp_code"]
        buy, asof = c["buy_date"], c["as_of"]

        # 공시 픽스처
        df = FIX / "disclosures" / f"{code}.json"
        disc = json.loads(df.read_text(encoding="utf-8")) if df.exists() else []
        if not disc:
            errs.append(f"{cid}: disclosures/{code}.json 없음/빈값")
            continue
        after = [d for d in disc if buy <= d["submitted"] <= asof]
        if not after:
            errs.append(f"{cid}: 매수일({buy})~as_of({asof}) 공시 0건")

        # rcp_no 존재 + as_of 이전 제출
        by_rcp = {d["rcp_no"]: d for d in disc}
        for label, rcp in [
            ("trigger", c["argument"].get("trigger_rcp_no")),
            ("evidence", c["expected_verdict"].get("evidence_rcp_no")),
        ]:
            if not rcp:
                continue
            if rcp not in by_rcp:
                errs.append(f"{cid}: {label} rcp {rcp} 공시 픽스처에 없음")
            elif by_rcp[rcp]["submitted"] > asof:
                errs.append(f"{cid}: {label} rcp {rcp} 제출일 as_of 이후 (미래 정보)")

        # 시세 커버 + 매수일 이전 마진
        pf = FIX / "prices" / f"{ticker}.csv"
        if not pf.exists():
            errs.append(f"{cid}: prices/{ticker}.csv 없음")
            continue
        rows = _prices(ticker)
        dates = [r["date"] for r in rows]
        if not (dates[0] <= buy and asof <= dates[-1]):
            errs.append(f"{cid}: 시세 구간이 [{buy}, {asof}]를 커버 못함 ({dates[0]}~{dates[-1]})")
        margin = cfg["price_move"]["zscore_window"] + cfg["price_move"]["price_history_margin_days"]
        before = sum(1 for d in dates if d < buy)
        if before < margin:
            errs.append(f"{cid}: 매수일 이전 거래일 {before} < 필요 마진 {margin} (z-score 창 부족)")

        # case-002: 급변일 ≥1
        if c.get("primary_mode") == "mirror" or cid == "case-002":
            m = _moves(rows, asof, cfg)
            if m < 1:
                errs.append(f"{cid}: as_of까지 급변일 0건 (급변–공시 매칭 불성립)")

    return errs


def main() -> int:
    cf = FIX / "cases.json"
    if not cf.exists():
        print(f"cases.json 없음: {cf} (아엔 승인 후 생성)")
        return 1
    errs = check()
    if errs:
        print(f"리허설 검증 실패 — {len(errs)}건:")
        for e in errs:
            print(f"  - {e}")
        return 1
    doc = json.loads(cf.read_text(encoding="utf-8"))
    print(f"리허설 검증 통과: {len(doc['cases'])}개 케이스 장면 성립 (공시·시세·rcp·급변)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
