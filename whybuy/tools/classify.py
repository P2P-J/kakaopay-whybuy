#!/usr/bin/env python3
"""공시 세부유형 분류기 (G2) — whybuy.

2단 분류: 1단은 픽스처의 유형필드(pblntf_ty, G1에서 확정) 그대로, 2단은 제목 키워드
사전(`classify_rules.yaml`)으로 세부 유형 매핑. 매칭 전 제목 정규화(공백 제거, 가운뎃점
통일, 전각괄호→반각). `[…정정]` 접두는 원 유형으로 분류하되 is_correction=True. 미매칭 etc.

CLI:
    .venv/bin/python tools/classify.py --stats data/fixtures/disclosures/
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_RULES_PATH = Path(__file__).resolve().parent / "classify_rules.yaml"

# 선행 대괄호 접두 (하나 이상 연속): [기재정정][첨부정정][발행조건확정] 등
_BRACKETS = re.compile(r"^(?:\[[^\]]*\])+")
# 정규화: 제거할 가운뎃점 변형(·ㆍ・∙), 전각괄호→반각
_STRIP = {0x00B7: None, 0x318D: None, 0x30FB: None, 0x2219: None, 0xFF08: "(", 0xFF09: ")"}


def _load_rules() -> list[dict]:
    return yaml.safe_load(_RULES_PATH.read_text(encoding="utf-8"))["rules"]


_RULES = _load_rules()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).translate(_STRIP)


def classify(title: str, pblntf_ty: str | None = None) -> dict:
    """공시 제목·유형필드를 세부유형으로 분류한다.

    반환: {type, is_correction, pblntf_ty}. type은 화이트리스트 유형 또는 etc.
    """
    stripped = title.strip()
    m = _BRACKETS.match(stripped)
    prefix = m.group(0) if m else ""
    is_correction = "정정" in prefix
    body = _normalize(stripped[len(prefix):])
    for rule in _RULES:
        if any(kw in body for kw in rule["keywords"]):
            return {"type": rule["type"], "is_correction": is_correction, "pblntf_ty": pblntf_ty}
    return {"type": "etc", "is_correction": is_correction, "pblntf_ty": pblntf_ty}


def classify_file(path: Path) -> list[dict]:
    """disclosures 픽스처 한 파일의 각 공시에 분류 라벨을 부착한다."""
    out = []
    for r in json.loads(path.read_text(encoding="utf-8")):
        c = classify(r.get("title", ""), r.get("pblntf_ty"))
        out.append({"rcp_no": r.get("rcp_no"), "title": r.get("title"), **c})
    return out


def _stats(disc_dir: Path) -> int:
    from collections import Counter

    counts, total, etc_samples = Counter(), 0, []
    for f in sorted(disc_dir.glob("*.json")):
        for row in classify_file(f):
            counts[row["type"]] += 1
            total += 1
            if row["type"] == "etc" and len(etc_samples) < 20:
                etc_samples.append(row["title"].strip()[:30])
    print(f"공시 {total}건 세부유형 분포:")
    for ty, c in counts.most_common():
        print(f"  {ty:<18} {c:>5}  ({c/total*100:4.1f}%)")
    etc_pct = counts.get("etc", 0) / total * 100 if total else 0
    print(f"\netc 비율 {etc_pct:.1f}% · etc 표본:")
    for s in etc_samples[:12]:
        print(f"  · {s}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", metavar="DISC_DIR")
    args = ap.parse_args()
    if args.stats:
        return _stats(Path(args.stats))
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
