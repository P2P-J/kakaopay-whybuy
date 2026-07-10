#!/usr/bin/env python3
"""별도재무제표(OFS) 자본 계정 보완 수집 (아엔 로컬 1회 실행) — whybuy (G10).

자본잠식은 법적으로 개별 법인 기준 → **별도재무제표(OFS)**로 판정해야 한다(연결 CFS는
자회사 지분이 섞여 왜곡). G1 financials는 pick_cfs로 CFS만 저장해 OFS가 없으므로,
fnlttSinglAcnt를 재호출해 OFS의 자본총계·자본금만 뽑아 별도 픽스처로 저장한다.
기존 CFS financials·verdict_engine(RULE-EARN은 CFS 고정)은 건드리지 않는다.
출력: data/fixtures/financials_ofs/{corp}/{year}{q}.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dart import FIN_YEARS, REPRT, TARGETS, NoData, dart_get, load_corp_map, load_key, mask_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fixtures" / "financials_ofs"
_CAP = {"자본총계", "자본금"}


def fetch_ofs(corp: str, year: str, code: str, key: str):
    try:
        d = dart_get("fnlttSinglAcnt.json", {"corp_code": corp, "bsns_year": year, "reprt_code": code}, key)
    except NoData:
        return None
    ofs = [r for r in d.get("list", []) if r.get("fs_div") == "OFS" and r.get("account_nm") in _CAP]
    return ofs or None


def main() -> int:
    key = load_key()
    print(f"DART_API_KEY (masked): {mask_key(key)}")
    corp_map = load_corp_map(key)
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    for t in TARGETS:
        corp = corp_map[t["ticker"]]
        (OUT / corp).mkdir(parents=True, exist_ok=True)
        n = 0
        for year in FIN_YEARS:
            for code, label in REPRT.items():
                rows = fetch_ofs(corp, year, code, key)
                if not rows:
                    continue
                (OUT / corp / f"{year}{label}.json").write_text(
                    json.dumps({"basis": "OFS", "accounts": rows}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
                n += 1
        log.append(f"  {t['name']} {corp}: OFS 자본 {n}개 기간")
    print("\n".join(log))
    print("OFS 자본 수집 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
