"""G10 KRX 위험 목록 CSV 파서 테스트 (네트워크 무관). krx_util.py 대상.

data.krx.co.kr 통계 CSV(EUC-KR)를 공통 스키마 {ticker,name,market,date,reason}로 변환.
파일마다 컬럼이 달라(관리종목/매매거래정지/불성실공시 등) 헤더 이름으로 매핑한다.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import krx_util as ku


def test_parse_admin_issues_row():
    text = (
        "번호,종목코드,종목명,시장구분,최초지정일,지정사유,상장일,업종,액면가,상장주식수\n"
        '"1","368970","오에스피","KOSDAQ","2026/07/10","시가총액 미달","2022/10/14","음식료","1000","7283547"\n'
    )
    rows = ku.parse_krx_risk_csv(text)
    assert rows == [{"ticker": "368970", "name": "오에스피", "market": "KOSDAQ",
                     "date": "2026-07-10", "reason": "시가총액 미달"}]


def test_parse_trading_halt_uses_정지일_정지사유():
    text = (
        "번호,종목코드,종목명,시장구분,정지일,정지사유\n"
        '"1","265690","ACE 러시아","KOSPI","2022/03/07","투자유의종목"\n'
    )
    r = ku.parse_krx_risk_csv(text)[0]
    assert r["ticker"] == "265690" and r["date"] == "2022-03-07" and r["reason"] == "투자유의종목"


def test_parse_handles_missing_market_column():
    text = (
        "번호,종목코드,종목명,최초지정일,지정사유,상장일,업종,액면가,상장주식수\n"
        '"1","221800","지구홀딩스","2026/05/26","제3자유상증자대금 부당사용","2023/11/02","일반서비스","500","16318851"\n'
    )
    r = ku.parse_krx_risk_csv(text)[0]
    assert r["ticker"] == "221800" and r["market"] == "" and r["reason"].startswith("제3자")


def test_parse_unfaithful_uses_지정사유():
    text = (
        "번호,종목코드,종목명,시장구분,주식종류,지정일,벌점,제재금,공시책임자등 교체요구,불성실유형,지정사유,누적벌점\n"
        '"1","396690","미래에셋리츠","KOSPI","보통주","2026/07/06","3","0",,"공시불이행","지연공시","3"\n'
    )
    r = ku.parse_krx_risk_csv(text)[0]
    assert r["ticker"] == "396690" and r["reason"] == "지연공시"


def test_ticker_zero_padding_preserved():
    text = ("번호,종목코드,종목명,시장구분,지정일,지정사유\n"
            '"1","035760","CJ ENM","KOSDAQ","2026/07/10","종가급변"\n')
    assert ku.parse_krx_risk_csv(text)[0]["ticker"] == "035760"


def test_skips_header_and_blank_lines():
    text = "번호,종목코드,종목명,시장구분,지정일,지정사유\n\n"
    assert ku.parse_krx_risk_csv(text) == []
