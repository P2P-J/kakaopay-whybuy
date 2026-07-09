#!/usr/bin/env python3
"""픽스처 수집 (아엔 로컬에서 1회 실행) — whybuy G1.

corpCode.xml → corp_code, 기업개황(corp_cls→kospi/kosdaq/konex/etc 번역), 공시목록
(유형 A~E·I 각각 별도 호출·페이지네이션), 분기 재무(전년 동기까지·fs_div 연결),
배당·최대주주·감사의견·자기주식, 일별 시세+지수(폴백 CSV)를 fixtures/에 저장.
DART_API_KEY는 .env에서만 읽고 로그·커밋에 노출 금지(crtfc_key 마스킹). 재실행 안전.

사용법:
    .venv/bin/python tools/fetch_dart.py [--force] [--only 005930] [--schema]
    --force   이미 존재하는 픽스처도 덮어씀 (기본: 스킵)
    --only    특정 ticker만 수집 (반복 가능)
    --schema  삼성전자로 각 엔드포인트 1회 호출해 스키마만 관찰(저장 안 함)
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_util import (  # noqa: E402
    mask_key,
    merge_pages,
    normalize_disclosure,
    parse_corp_code_xml,
    pick_cfs,
    translate_corp_cls,
)

ROOT = Path(__file__).resolve().parents[1]  # whybuy/
FIX = ROOT / "data" / "fixtures"
BASE = "https://opendart.fss.or.kr/api"

# 대상 종목 (G1 plan)
TARGETS = [
    {"ticker": "005930", "name": "삼성전자"},
    {"ticker": "035720", "name": "카카오"},
    {"ticker": "105560", "name": "KB금융"},
    {"ticker": "017670", "name": "SK텔레콤"},
    {"ticker": "033780", "name": "KT&G"},
]

# 공시 유형 (list.json pblntf_ty) — 화이트리스트 이벤트가 걸리는 6종
PBLNTF_TYPES = ["A", "B", "C", "D", "E", "I"]

# 재무: 최근 사업연도 × 보고서 종류 (전년 동기는 API가 frmtrm으로 동봉)
FIN_YEARS = ["2024", "2025"]
REPRT = {"11013": "1Q", "11012": "2Q", "11014": "3Q", "11011": "4Q"}

# 공시 목록 조회 구간 (지수 CSV와 동일 창)
LIST_BGN, LIST_END = "20250101", "20260709"


class DartError(RuntimeError):
    pass


class NoData(Exception):
    """status 013 (조회된 데이타가 없습니다) — 정상적 빈 결과."""


def load_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line.startswith("DART_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise DartError(".env에서 DART_API_KEY를 찾지 못함")


def _get(url: str, *, binary: bool = False, retries: int = 3):
    """지수 백오프 3회. 마지막 실패는 예외로 올린다."""
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.read() if binary else r.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:  # noqa: PERF203
            last = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise DartError(f"네트워크 실패: {mask_key(str(last))}")


def dart_get(endpoint: str, params: dict, key: str) -> dict:
    """JSON 엔드포인트 호출. crtfc_key 주입·status 처리.

    000 정상 / 013 데이터없음(NoData) / 020 사용한도초과(중단) / 010·011·012 키오류(중단).
    """
    q = "&".join(f"{k}={v}" for k, v in {"crtfc_key": key, **params}.items())
    url = f"{BASE}/{endpoint}?{q}"
    data = json.loads(_get(url))
    status = data.get("status")
    if status == "000":
        return data
    if status == "013":
        raise NoData()
    msg = data.get("message", "")
    if status in ("010", "011", "012", "020"):
        raise DartError(f"[{status}] {msg} — 중단 (endpoint={endpoint})")
    raise DartError(f"[{status}] {msg} (endpoint={endpoint}, params={mask_key(str(params))})")


# ── corp_code 매핑 ────────────────────────────────────────────────
def load_corp_map(key: str) -> dict:
    """corpCode.xml(zip) 1회 다운로드 → {ticker: corp_code}."""
    raw = _get(f"{BASE}/corpCode.xml?crtfc_key={key}", binary=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read(z.namelist()[0])
    out = {}
    for t in TARGETS:
        code = parse_corp_code_xml(xml, t["ticker"])
        if not code:
            raise DartError(f"corp_code 미발견: {t['name']} {t['ticker']}")
        out[t["ticker"]] = code
    return out


# ── 수집 단위 ─────────────────────────────────────────────────────
def fetch_company(corp_code: str, key: str) -> dict:
    d = dart_get("company.json", {"corp_code": corp_code}, key)
    return {
        "corp_code": corp_code,
        "corp_name": d.get("corp_name"),
        "stock_code": d.get("stock_code"),
        "corp_cls": d.get("corp_cls"),
        "market": translate_corp_cls(d.get("corp_cls", "")),
        "ceo_nm": d.get("ceo_nm"),
        "est_dt": d.get("est_dt"),
        "acc_mt": d.get("acc_mt"),
    }


def fetch_disclosures(corp_code: str, key: str) -> list[dict]:
    """유형 6종 각각 페이지네이션 수집 → 정규화·병합."""
    all_rows = []
    for ty in PBLNTF_TYPES:
        pages = []
        page = 1
        while True:
            try:
                d = dart_get(
                    "list.json",
                    {
                        "corp_code": corp_code,
                        "bgn_de": LIST_BGN,
                        "end_de": LIST_END,
                        "pblntf_ty": ty,
                        "page_no": page,
                        "page_count": 100,
                    },
                    key,
                )
            except NoData:
                break
            pages.append({"list": d.get("list", []), "total_page": d.get("total_page", 1)})
            if page >= int(d.get("total_page", 1)):
                break
            page += 1
        merged = merge_pages(pages)
        all_rows.extend(normalize_disclosure(r, ty) for r in merged)
    # 유형 간 중복 rcp_no 제거 (한 공시가 복수 유형에 걸릴 수 있음)
    seen, uniq = set(), []
    for r in sorted(all_rows, key=lambda x: x["submitted"]):
        if r["rcp_no"] in seen:
            continue
        seen.add(r["rcp_no"])
        uniq.append(r)
    return uniq


def fetch_financials(corp_code: str, key: str) -> dict:
    """사업연도×보고서 종류 주요계정. fs_div 연결(CFS) 우선."""
    out = {}
    for year in FIN_YEARS:
        for code, label in REPRT.items():
            try:
                d = dart_get(
                    "fnlttSinglAcnt.json",
                    {"corp_code": corp_code, "bsns_year": year, "reprt_code": code},
                    key,
                )
            except NoData:
                continue
            rows, basis = pick_cfs(d.get("list", []))
            out[f"{year}{label}"] = {"basis": basis, "accounts": rows}
    return out


def fetch_report_items(corp_code: str, key: str) -> dict:
    """배당·최대주주·감사의견·자기주식 — 고정 감시 항목의 최근 값."""
    items = {}
    endpoints = {
        "dividend": "alotMatter.json",
        "major_shareholder": "hyslrSttus.json",
        "audit_opinion": "accnutAdtorNmNdAdtOpinion.json",
        "treasury_stock": "tesstkAcqsDspsSttus.json",
    }
    for label, ep in endpoints.items():
        year_rows = {}
        for year in FIN_YEARS:
            try:
                d = dart_get(ep, {"corp_code": corp_code, "bsns_year": year, "reprt_code": "11011"}, key)
            except NoData:
                continue
            year_rows[year] = d.get("list", [])
        items[label] = year_rows
    return items


# ── 시세 (pykrx) ──────────────────────────────────────────────────
def fetch_prices(ticker: str) -> list[dict]:
    from pykrx import stock  # 지연 임포트 (fetch 전용)

    df = stock.get_market_ohlcv("20250101", "20260709", ticker)
    rows = []
    prev_close = None
    for idx, r in df.iterrows():
        close = float(r["종가"])
        change = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
        rows.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(r["시가"]),
            "high": float(r["고가"]),
            "low": float(r["저가"]),
            "close": close,
            "volume": int(r["거래량"]),
            "change_pct": change,
        })
        prev_close = close
    return rows


# ── 직렬화 (재실행 안전) ──────────────────────────────────────────
def _write_json(path: Path, obj, force: bool) -> str:
    if path.exists() and not force:
        return "skip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return "write"


def _write_prices_csv(path: Path, rows: list[dict], force: bool) -> str:
    import csv

    if path.exists() and not force:
        return "skip"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume", "change_pct"])
        w.writeheader()
        w.writerows(rows)
    return "write"


def collect_one(t: dict, corp_code: str, key: str, force: bool, log: list) -> None:
    name, ticker = t["name"], t["ticker"]

    company = fetch_company(corp_code, key)
    log.append(f"  {name} corp={corp_code} market={company['market']}")
    _write_json(FIX / "corp" / f"{corp_code}.json", company, force)

    disc = fetch_disclosures(corp_code, key)
    _write_json(FIX / "disclosures" / f"{corp_code}.json", disc, force)
    log.append(f"    disclosures: {len(disc)}건")

    fin = fetch_financials(corp_code, key)
    for period, block in fin.items():
        _write_json(FIX / "financials" / corp_code / f"{period}.json", block, force)
    log.append(f"    financials: {len(fin)}개 기간")

    items = fetch_report_items(corp_code, key)
    _write_json(FIX / "report_items" / f"{corp_code}.json", items, force)
    log.append(f"    report_items: {sum(len(v) for v in items.values())}개 연도블록")

    prices = fetch_prices(ticker)
    _write_prices_csv(FIX / "prices" / f"{ticker}.csv", prices, force)
    span = f"{prices[0]['date']}..{prices[-1]['date']}" if prices else "(empty)"
    log.append(f"    prices: {len(prices)}행 {span}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", action="append", default=[])
    ap.add_argument("--schema", action="store_true")
    args = ap.parse_args()

    key = load_key()
    print(f"DART_API_KEY loaded (masked): {mask_key(key)}")

    if args.schema:
        return schema_probe(key)

    targets = [t for t in TARGETS if not args.only or t["ticker"] in args.only]
    print("corpCode.xml 다운로드…")
    corp_map = load_corp_map(key)

    log, failures = [], []
    for t in targets:
        try:
            print(f"수집: {t['name']} ({t['ticker']})")
            collect_one(t, corp_map[t["ticker"]], key, args.force, log)
        except DartError as e:
            failures.append(f"{t['name']}: {mask_key(str(e))}")
        except Exception as e:  # noqa: BLE001
            failures.append(f"{t['name']}: {type(e).__name__}: {mask_key(str(e))}")

    print("\n".join(log))
    if failures:
        print("\n실패:")
        print("\n".join(f"  - {f}" for f in failures))
        return 1
    print("\n수집 완료.")
    return 0


def schema_probe(key: str) -> int:
    """삼성전자로 각 엔드포인트 1회 호출해 스키마(키 목록) 관찰."""
    corp = load_corp_map(key)["005930"]
    print(f"삼성전자 corp_code={corp}")
    probes = [
        ("company.json", {"corp_code": corp}),
        ("list.json", {"corp_code": corp, "bgn_de": LIST_BGN, "end_de": LIST_END, "pblntf_ty": "A", "page_count": 3}),
        ("fnlttSinglAcnt.json", {"corp_code": corp, "bsns_year": "2025", "reprt_code": "11013"}),
        ("alotMatter.json", {"corp_code": corp, "bsns_year": "2024", "reprt_code": "11011"}),
        ("hyslrSttus.json", {"corp_code": corp, "bsns_year": "2024", "reprt_code": "11011"}),
        ("accnutAdtorNmNdAdtOpinion.json", {"corp_code": corp, "bsns_year": "2024", "reprt_code": "11011"}),
        ("tesstkAcqsDspsSttus.json", {"corp_code": corp, "bsns_year": "2024", "reprt_code": "11011"}),
    ]
    for ep, params in probes:
        try:
            d = dart_get(ep, params, key)
            rows = d.get("list", [])
            keys = sorted(rows[0].keys()) if rows else "(no list)"
            print(f"\n{ep}: rows={len(rows) if isinstance(rows, list) else '-'}")
            print(f"  keys={keys}")
        except NoData:
            print(f"\n{ep}: 013 데이터없음")
        except DartError as e:
            print(f"\n{ep}: {mask_key(str(e))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
