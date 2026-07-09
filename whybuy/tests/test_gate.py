"""G4 컴플라이언스 게이트 테스트. compliance_gate.py 대상.

범위(정직): "세상 모든 권유 표현 검출"이 아니라 "이 시스템 산출물에서 권유·예측·평가어
0건 보장 + 테스트로 증명". 음성 세트 검출률 100% · 양성 세트 오탐 0.
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import compliance_gate as cg
import textstore as ts

_GATE = os.path.join(os.path.dirname(__file__), "gate")


# ── 금지 패턴: 검출돼야 (negative) ──
def test_directive_forms_blocked():
    for s in ["지금 파세요.", "삼성전자를 매수하세요.", "손절하시기 바랍니다.",
              "파는 게 낫습니다.", "매도를 고려해 보시길 권합니다."]:
        assert cg.scan_forbidden(s), f"미검출: {s}"

def test_prediction_blocked():
    for s in ["곧 반등할 것으로 예상됩니다.", "주가가 오를 전망입니다.", "하락할 가능성이 높습니다."]:
        assert cg.scan_forbidden(s), f"미검출: {s}"

def test_valuation_blocked():
    for s in ["현재 저평가 상태입니다.", "지금이 저가 매수 기회입니다.", "밸류에이션이 매력적입니다."]:
        assert cg.scan_forbidden(s), f"미검출: {s}"

def test_certainty_blocked():
    for s in ["확실히 오릅니다.", "분명히 상승할 것입니다."]:
        assert cg.scan_forbidden(s), f"미검출: {s}"


# ── 사실 서술: 오탐 0 (positive) ──
def test_factual_statements_not_flagged():
    facts = (
        "임원이 주식을 매도했다는 공시가 있습니다. "
        "사용자의 매수 논거는 실적 개선이었습니다. "
        "최신 분기 영업이익은 전년 동기 대비 +32%입니다. "
        "보유 수익률은 시장 대비 하회했습니다."
    )
    assert cg.scan_forbidden(facts) == []

def test_mirror_question_allowed():
    assert cg.scan_forbidden(ts.MIRROR_QUESTION) == []


def test_market_compare_allowed_but_valuation_blocked():
    # 경계 고정: "시장 대비 상회/유사/하회"는 산술 비교라 허용,
    #           "저평가/고평가/매력적"은 평가어라 금지. 이 대비가 무너지면 안 된다.
    for allowed in ["시장 대비 상회했습니다.", "시장 대비 유사합니다.", "시장 대비 하회했습니다."]:
        assert cg.scan_forbidden(allowed) == [], f"산술 비교 오탐: {allowed}"
    for blocked in ["저평가입니다.", "고평가입니다.", "밸류에이션이 매력적입니다."]:
        assert cg.scan_forbidden(blocked), f"평가어 미검출: {blocked}"


# ── 필수 요소 ──
def _briefing(body, *, as_of=True, disclaimer=True):
    parts = []
    if as_of:
        parts.append(ts.as_of_notice("2025-04-09"))
    parts.append(body)
    if disclaimer:
        parts.append(ts.DISCLAIMER)
    return "\n\n".join(parts)

def test_missing_as_of_notice_blocked():
    assert cg.check(_briefing("타임라인 요약입니다.", as_of=False))

def test_missing_disclaimer_blocked():
    assert cg.check(_briefing("타임라인 요약입니다.", disclaimer=False))

def test_plain_timeline_passes():
    assert cg.check(_briefing("2025-03-25 매수. 이후 공시 3건. 영업이익 +32% YoY.")) == []


# ── 판정 라인 상태별 차등 ──
def test_verdict_supported_requires_link():
    body = "실적 개선 기대: **유효**"  # 링크 없음
    out = _briefing(body + "\n\n" + ts.REFUTED_DEFINITION)
    assert cg.check(out)

def test_verdict_supported_with_link_and_definition_passes():
    body = "실적 개선 기대: **유효** [근거](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250408800003)"
    out = _briefing(body + "\n\n" + ts.REFUTED_DEFINITION)
    assert cg.check(out) == []

def test_unverifiable_line_needs_absence_phrase_not_url():
    # 확인불가 라인은 URL 대신 부재 사실 문구를 요구 (부재의 정직)
    body = "테마 편승: **확인불가** — 대조를 시도한 공시에서 관련 매출·수주 기록 부재"
    out = _briefing(body + "\n\n" + ts.REFUTED_DEFINITION)
    assert cg.check(out) == []

def test_verdict_present_requires_refuted_definition():
    body = "실적 개선 기대: **유효** [근거](https://dart.fss.or.kr/x?rcpNo=20250408800003)"
    out = _briefing(body)  # REFUTED_DEFINITION 누락
    assert cg.check(out)


# ── 샘플 세트 (완료판정) ──
def test_positive_samples_pass():
    files = glob.glob(os.path.join(_GATE, "positive", "*.md"))
    assert files
    for f in files:
        assert cg.check(open(f, encoding="utf-8").read()) == [], f"양성 오탐: {os.path.basename(f)}"

def test_negative_samples_blocked():
    files = glob.glob(os.path.join(_GATE, "negative", "*.md"))
    assert files
    for f in files:
        assert cg.check(open(f, encoding="utf-8").read()), f"음성 미검출: {os.path.basename(f)}"
