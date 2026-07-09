"""G1 순수 변환 함수 (네트워크 무관) — whybuy.

fetch_dart.py의 I/O 계층이 임포트해 쓰는 결정적 헬퍼 모음. 네트워크·키에
의존하지 않아 단위 테스트로 완전 검증된다 (tests/test_fetch_util.py).
"""
import csv
import io
import re
import xml.etree.ElementTree as ET

# OpenDART 인증키는 40자리 hex. 로그·출력에서 이 패턴을 통째로 마스킹한다.
_KEY_RE = re.compile(r"[0-9a-fA-F]{40}")
_DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"

_CORP_CLS = {"Y": "kospi", "K": "kosdaq", "N": "konex", "E": "etc"}


def mask_key(text: str) -> str:
    """텍스트 내 DART 인증키(40-hex)를 마스킹한다. 로그 보존 전 필수."""
    return _KEY_RE.sub("***MASKED***", text)


def translate_corp_cls(code: str) -> str:
    """DART corp_cls 코드를 픽스처 저장용 시장 구분으로 번역한다."""
    return _CORP_CLS.get((code or "").strip(), "unknown")


def parse_corp_code_xml(xml_bytes: bytes, stock_code: str) -> str | None:
    """corpCode.xml에서 종목코드에 해당하는 corp_code를 찾는다. 없으면 None."""
    root = ET.fromstring(xml_bytes)
    for node in root.iter("list"):
        sc = (node.findtext("stock_code") or "").strip()
        if sc == stock_code:
            return (node.findtext("corp_code") or "").strip()
    return None


def merge_pages(pages: list[dict]) -> list[dict]:
    """list.json 페이지들의 list를 병합하고 rcept_no 기준 중복을 제거한다(순서 보존)."""
    seen, out = set(), []
    for page in pages:
        for row in page.get("list", []):
            rcp = row.get("rcept_no")
            if rcp in seen:
                continue
            seen.add(rcp)
            out.append(row)
    return out


def _yyyymmdd_to_iso(s: str) -> str:
    s = (s or "").strip()
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else s


def normalize_disclosure(row: dict, pblntf_ty: str) -> dict:
    """list.json 한 건을 픽스처 스키마로 정규화한다. 정정 플래그·원문 URL 포함."""
    rcp_no = row.get("rcept_no", "")
    title = row.get("report_nm", "")
    is_correction = row.get("rm", "").strip() == "정" or title.startswith("[기재정정]")
    return {
        "rcp_no": rcp_no,
        "submitted": _yyyymmdd_to_iso(row.get("rcept_dt", "")),
        "title": title,
        "pblntf_ty": pblntf_ty,
        "is_correction": is_correction,
        "url": _DART_VIEWER.format(rcp_no=rcp_no),
    }


def pick_cfs(rows: list[dict]) -> tuple[list[dict], str]:
    """재무 행에서 연결(CFS)을 우선 선택하고, 없으면 별도(OFS)로 폴백한다.

    반환: (선택된 행들, basis) — basis는 'CFS' 또는 'OFS'. 브리핑에 표기한다.
    """
    cfs = [r for r in rows if r.get("fs_div") == "CFS"]
    if cfs:
        return cfs, "CFS"
    return rows, "OFS"


def submitted_on_or_before(rows: list[dict], as_of: str, date_key: str = "submitted") -> list[dict]:
    """제출일이 as_of(YYYY-MM-DD) 이하인 행만 남긴다 (시점 시뮬레이션)."""
    return [r for r in rows if r.get(date_key, "") <= as_of]


_KRX_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


def parse_krx_index_csv(text: str) -> list[dict]:
    """KRX 정보데이터시스템 지수 CSV(아엔 다운로드)를 우리 스키마로 변환한다.

    입력 컬럼(위치): 일자,종가,대비,등락률,시가,고가,저가,거래량,거래대금,상장시총.
    헤더(EUC-KR)는 첫 필드가 날짜가 아니므로 자동으로 건너뛴다.
    출력: [{date(ISO), open, high, low, close, volume, change_pct}], 날짜 오름차순.
    """
    out = []
    for cells in csv.reader(io.StringIO(text)):
        if not cells or not _KRX_DATE_RE.match(cells[0].strip()):
            continue  # 헤더·빈 줄 스킵
        out.append({
            "date": cells[0].strip().replace("/", "-"),
            "close": float(cells[1]),
            "change_pct": float(cells[3]),
            "open": float(cells[4]),
            "high": float(cells[5]),
            "low": float(cells[6]),
            "volume": int(cells[7]),
        })
    out.sort(key=lambda r: r["date"])
    return out
