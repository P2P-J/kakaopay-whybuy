"""G2 공시 분류기 순수 함수 테스트 (네트워크 무관). classify.py 대상.

2단 분류: 1단 유형필드(pblntf_ty) + 2단 제목 키워드 사전. 제목 정규화 후 매칭.
`[기재정정]` 접두는 원 유형으로 분류하되 is_correction=True. 미매칭은 etc.
"""
import glob
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import classify as cl

_LABELS = os.path.join(os.path.dirname(__file__), "labels")


# --- 실적 (정기·잠정) ---
def test_provisional_earnings_is_earnings():
    r = cl.classify("연결재무제표기준영업(잠정)실적(공정공시)", "I")
    assert r["type"] == "earnings"
    assert r["is_correction"] is False

def test_periodic_report_is_earnings():
    assert cl.classify("분기보고서 (2025.03)", "A")["type"] == "earnings"
    assert cl.classify("사업보고서 (2024.12)", "A")["type"] == "earnings"

def test_income_structure_change_is_earnings():
    assert cl.classify("매출액또는손익구조30%(대규모법인은15%)이상변경", "I")["type"] == "earnings"


# --- 배당 ---
def test_dividend():
    assert cl.classify("현금ㆍ현물배당결정", "I")["type"] == "dividend"


# --- 자기주식 ---
def test_treasury_from_material_report():
    assert cl.classify("주요사항보고서(자기주식처분결정)", "B")["type"] == "treasury"

def test_treasury_stock_cancellation():
    assert cl.classify("주식소각결정", "I")["type"] == "treasury"


# --- 자본구조 변경 (증자·CB·감자) → capital_change ---
def test_convertible_bond_is_capital_change():
    assert cl.classify("주요사항보고서(전환사채권발행결정)", "B")["type"] == "capital_change"

def test_securities_registration_is_capital_change():
    assert cl.classify("증권신고서(지분증권)", "C")["type"] == "capital_change"

def test_capital_reduction_is_capital_change():
    # 감자(자본감소)는 증자·CB와 같은 급의 자본구조 변경 중대사실 → etc 아님
    assert cl.classify("주요사항보고서(감자결정)", "B")["type"] == "capital_change"
    assert cl.classify("주요사항보고서(무상감자결정)", "B")["type"] == "capital_change"


# --- 최대주주·지분 ---
def test_insider_ownership_is_major_shareholder():
    assert cl.classify("임원ㆍ주요주주특정증권등소유상황보고서", "D")["type"] == "major_shareholder"

def test_bulk_holding_is_major_shareholder():
    assert cl.classify("주식등의대량보유상황보고서(일반)", "D")["type"] == "major_shareholder"


# --- 감사의견 ---
def test_audit():
    assert cl.classify("감사보고서제출", "I")["type"] == "audit"


# --- 공급계약 ---
def test_supply_contract():
    assert cl.classify("단일판매ㆍ공급계약체결", "I")["type"] == "supply_contract"


# --- etc 폴백 ---
def test_unmatched_is_etc():
    assert cl.classify("기업설명회(IR)개최(안내공시)", "I")["type"] == "etc"

def test_shareholder_meeting_is_etc():
    assert cl.classify("주주총회소집공고", "E")["type"] == "etc"

def test_ceo_change_is_not_major_shareholder():
    # '대표집행임원'의 '임원'이 지분공시로 과대매칭되면 안 된다 (거버넌스 → etc)
    assert cl.classify("대표이사(대표집행임원)변경(안내공시)", "I")["type"] == "etc"

def test_value_up_plan_is_not_dividend():
    # '고배당'의 '배당'이 배당결정으로 과대매칭되면 안 된다 (기업가치제고계획 → etc)
    assert cl.classify("기업가치제고계획(자율공시)", "I")["type"] == "etc"
    assert cl.classify("기업가치제고계획(자율공시)(고배당기업 표시를 위한 재공시)", "I")["type"] == "etc"


# --- 정정 접두 처리 ---
def test_correction_prefix_stripped_and_flagged():
    r = cl.classify("[기재정정]현금ㆍ현물배당결정", "I")
    assert r["type"] == "dividend"
    assert r["is_correction"] is True

def test_attachment_correction_prefix():
    r = cl.classify("[첨부정정]주요사항보고서(자기주식처분결정)", "B")
    assert r["type"] == "treasury"
    assert r["is_correction"] is True


# --- 제목 정규화 (공백·괄호·특수문자 변형) ---
def test_normalizes_halfwidth_middle_dot():
    # 반각 가운뎃점(·)·전각 변형이 사전(ㆍ)과 달라도 동일 분류
    assert cl.classify("현금·현물배당결정", "I")["type"] == "dividend"

def test_normalizes_trailing_spaces_and_fullwidth_parens():
    assert cl.classify("현금ㆍ현물배당결정   ", "I")["type"] == "dividend"
    assert cl.classify("증권신고서（지분증권）", "C")["type"] == "capital_change"


# --- 골든 스냅샷: 실데이터 라벨 세트 전건 대조 (아엔 검수 2026-07-09) ---
def test_golden_labels_match():
    files = sorted(glob.glob(os.path.join(_LABELS, "*.json")))
    assert files, "골든 라벨 세트(tests/labels/*.json) 없음"
    total = 0
    for path in files:
        for row in json.loads(open(path, encoding="utf-8").read()):
            r = cl.classify(row["title"], row["pblntf_ty"])
            assert r["type"] == row["type"], (
                f"{os.path.basename(path)} {row['rcp_no']}: {r['type']} != {row['type']} "
                f"({row['title'][:30]})"
            )
            assert r["is_correction"] == row["is_correction"], f"{row['rcp_no']} is_correction 불일치"
            total += 1
    assert total >= 3600, f"라벨 전건 대조 수 부족: {total}"
