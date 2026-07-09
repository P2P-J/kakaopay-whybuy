#!/usr/bin/env python3
"""reports 내 DART 원문 링크 검증 (아엔 로컬 실행) — whybuy G9.

**HTTP 200만으로 판정하지 않는다**: DART 뷰어는 존재하지 않는 접수번호에도 200 상태의
오류 페이지를 반환할 수 있으므로, ①응답 본문에 오류 문구("조회된 자료가 없습니다" 류)가
없는지 ②문서 제목/뷰어 요소가 존재하는지까지 검사한다. 결과를 logs/link-check.txt로 남긴다.

사용법: .venv/bin/python tools/link_check.py [--limit N]
네트워크 불가 환경이면 각 URL을 SKIP으로 기록하고 exit 0(정직 고지) — 판정은 아엔 로컬에서.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_URL_RE = re.compile(r"https://dart\.fss\.or\.kr/dsaf001/main\.do\?rcpNo=\d{14}")
_ERROR_PHRASES = ["조회된 자료가 없습니다", "조회된 데이타가 없습니다", "일시적인 오류", "페이지를 찾을 수 없"]


def collect_urls() -> list[str]:
    urls = set()
    for f in (ROOT / "reports").rglob("*.md"):
        urls.update(_URL_RE.findall(f.read_text(encoding="utf-8")))
    return sorted(urls)


def check_url(url: str) -> tuple[str, str]:
    """(status, detail). status ∈ {OK, ERROR, SKIP}."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 whybuy-linkcheck"})
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.getcode()
            body = r.read(60000).decode("utf-8", "ignore")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return "SKIP", f"네트워크 불가: {type(e).__name__}"
    if code != 200:
        return "ERROR", f"HTTP {code}"
    for p in _ERROR_PHRASES:
        if p in body:
            return "ERROR", f"본문 오류 문구: {p}"
    if "<title" not in body.lower() and "dsaf" not in body.lower():
        return "ERROR", "문서 요소 부재"
    return "OK", "200 + 본문 정상"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    urls = collect_urls()
    if args.limit:
        urls = urls[:args.limit]
    lines, ok, err, skip = [], 0, 0, 0
    for u in urls:
        st, detail = check_url(u)
        lines.append(f"[{st}] {u} — {detail}")
        ok += st == "OK"; err += st == "ERROR"; skip += st == "SKIP"
    summary = f"링크 {len(urls)}개: OK {ok} · ERROR {err} · SKIP {skip}"
    log = ROOT / "logs" / "link-check.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(summary + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(summary)
    print(f"로그: {log.relative_to(ROOT)}")
    if skip and not ok:
        print("(네트워크 불가 — 링크 판정은 아엔 로컬에서 재실행)")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
