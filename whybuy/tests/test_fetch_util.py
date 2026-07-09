"""G1 순수 변환 함수 테스트 (네트워크 무관). fetch_util.py 대상."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import fetch_util as fu


# --- 키 마스킹 ---
def test_mask_key_in_url_query():
    key = "a" * 40
    out = fu.mask_key(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={key}&page_no=1")
    assert key not in out
    assert "***" in out
    assert "page_no=1" in out  # 다른 파라미터는 보존

def test_mask_standalone_40hex_token():
    key = "1e09f3" + "0" * 34
    out = fu.mask_key(f"OPEN DART API KEY : {key}")
    assert key not in out
    assert "***" in out

def test_mask_dart_api_key_env_line():
    out = fu.mask_key("DART_API_KEY=" + "b" * 40)
    assert "b" * 40 not in out


# --- corp_cls 번역 ---
def test_translate_corp_cls():
    assert fu.translate_corp_cls("Y") == "kospi"
    assert fu.translate_corp_cls("K") == "kosdaq"
    assert fu.translate_corp_cls("N") == "konex"
    assert fu.translate_corp_cls("E") == "etc"

def test_translate_corp_cls_unknown():
    assert fu.translate_corp_cls("Z") == "unknown"
    assert fu.translate_corp_cls("") == "unknown"


# --- corpCode.xml 파싱 ---
SAMPLE_CORPCODE_XML = (
    "<?xml version='1.0' encoding='utf-8'?>"
    "<result>"
    "<list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name>"
    "<stock_code>005930</stock_code><modify_date>20260101</modify_date></list>"
    "<list><corp_code>00258801</corp_code><corp_name>카카오</corp_name>"
    "<stock_code>035720</stock_code><modify_date>20260101</modify_date></list>"
    "<list><corp_code>00999999</corp_code><corp_name>비상장</corp_name>"
    "<stock_code> </stock_code><modify_date>20260101</modify_date></list>"
    "</result>"
).encode("utf-8")

def test_parse_corp_code_found():
    assert fu.parse_corp_code_xml(SAMPLE_CORPCODE_XML, "005930") == "00126380"
    assert fu.parse_corp_code_xml(SAMPLE_CORPCODE_XML, "035720") == "00258801"

def test_parse_corp_code_missing_returns_none():
    assert fu.parse_corp_code_xml(SAMPLE_CORPCODE_XML, "000000") is None


# --- 페이지 병합 + 중복 제거 ---
def test_merge_pages_dedup_by_rcp_no():
    pages = [
        {"list": [{"rcept_no": "1"}, {"rcept_no": "2"}]},
        {"list": [{"rcept_no": "2"}, {"rcept_no": "3"}]},
    ]
    merged = fu.merge_pages(pages)
    assert [r["rcept_no"] for r in merged] == ["1", "2", "3"]

def test_merge_pages_empty():
    assert fu.merge_pages([{"list": []}]) == []


# --- 공시 정규화 ---
def test_normalize_disclosure_basic():
    row = {"rcept_no": "20260430000456", "rcept_dt": "20260430",
           "report_nm": "분기보고서 (2026.03)", "rm": ""}
    d = fu.normalize_disclosure(row, "A")
    assert d["rcp_no"] == "20260430000456"
    assert d["submitted"] == "2026-04-30"
    assert d["title"] == "분기보고서 (2026.03)"
    assert d["pblntf_ty"] == "A"
    assert d["is_correction"] is False
    assert d["rcp_no"] in d["url"]

def test_normalize_disclosure_correction_by_rm():
    row = {"rcept_no": "1", "rcept_dt": "20260501", "report_nm": "사업보고서", "rm": "정"}
    assert fu.normalize_disclosure(row, "A")["is_correction"] is True

def test_normalize_disclosure_correction_by_prefix():
    row = {"rcept_no": "1", "rcept_dt": "20260501", "report_nm": "[기재정정]주요사항보고서", "rm": ""}
    assert fu.normalize_disclosure(row, "B")["is_correction"] is True


# --- 재무 연결(CFS) 선택 ---
def test_pick_cfs_prefers_consolidated():
    rows = [{"fs_div": "OFS", "account_nm": "영업이익"}, {"fs_div": "CFS", "account_nm": "영업이익"}]
    picked, basis = fu.pick_cfs(rows)
    assert basis == "CFS"
    assert all(r["fs_div"] == "CFS" for r in picked)

def test_pick_cfs_falls_back_to_separate():
    rows = [{"fs_div": "OFS", "account_nm": "영업이익"}]
    picked, basis = fu.pick_cfs(rows)
    assert basis == "OFS"
    assert len(picked) == 1


# --- 제출일 as_of 필터 ---
def test_submitted_on_or_before():
    rows = [{"submitted": "2026-04-30"}, {"submitted": "2026-06-15"}, {"submitted": "2026-05-14"}]
    kept = fu.submitted_on_or_before(rows, "2026-05-14")
    assert [r["submitted"] for r in kept] == ["2026-04-30", "2026-05-14"]


# --- KRX 지수 CSV 변환 (아엔 다운로드 → 우리 스키마) ---
# 실제 KRX 정보데이터시스템 포맷: header(EUC-KR) + "일자,종가,대비,등락률,시가,고가,저가,거래량,거래대금,상장시총"
# 데이터 행은 ASCII. 헤더는 무시하고 컬럼 위치로 매핑, 날짜 오름차순 정렬.
KRX_INDEX_SAMPLE = (
    '\xc0\xcf\xc0\xda,close,...\n'  # 헤더(모지바케) — 무시되어야 함
    '"2026/07/09","7271.26","24.47","0.34","7486.64","7543.86","7063.76","530549066","3.1E7","5.9E9"\n'
    '"2026/03/10","5532.59","280.72","5.35","5523.21","5595.88","5427.88","923209866","2.8E7","4.5E9"\n'
    '"2025/01/02","2398.94","-0.55","-0.02","2400.87","2410.99","2386.84","350691927","6958649.0","1.9E9"\n'
)

def test_parse_krx_index_sorts_ascending_and_converts_date():
    rows = fu.parse_krx_index_csv(KRX_INDEX_SAMPLE)
    assert len(rows) == 3
    assert rows[0]["date"] == "2025-01-02"   # 오름차순 정렬
    assert rows[-1]["date"] == "2026-07-09"

def test_parse_krx_index_field_mapping():
    rows = fu.parse_krx_index_csv(KRX_INDEX_SAMPLE)
    r = rows[0]  # 2025-01-02
    assert r["close"] == 2398.94
    assert r["change_pct"] == -0.02
    assert r["open"] == 2400.87 and r["high"] == 2410.99 and r["low"] == 2386.84
    assert r["volume"] == 350691927

def test_parse_krx_index_skips_header():
    # 헤더(첫 필드가 날짜가 아님)는 데이터로 잡히지 않는다
    rows = fu.parse_krx_index_csv(KRX_INDEX_SAMPLE)
    assert all(len(r["date"]) == 10 and r["date"][4] == "-" for r in rows)
