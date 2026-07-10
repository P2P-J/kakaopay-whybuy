"""로컬 MCP 서버 (stdio) — whybuy.

PRD 6번의 도구 10종을 stdio MCP로 노출한다. dart_client/ledger_store의 얇은 래퍼 +
입력 검증. 실패는 예외가 아니라 구조화된 오류 응답({error, message, hint})으로 반환한다.
as_of 시점 필터는 dart_client 한 곳에서 강제되므로 도구 추가 시 시점 누출이 구조적으로 불가능.

도구 핸들러(TOOLS)는 순수 dict→dict 함수로 분리해 단위 테스트가 서버 기동 없이 호출한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import dart_client as dc  # noqa: E402
import krx_client as kx  # noqa: E402
import ledger_store as ls  # noqa: E402
import compliance_gate as cgate  # noqa: E402


def _err(kind: str, message: str, hint: str = "") -> dict:
    return {"error": kind, "message": message, "hint": hint}


# ── 도구 핸들러 (순수) ────────────────────────────────────────────
def _resolve_corp(a):
    return dc.resolve_corp(a["query"])


def _list_disclosures(a):
    return dc.list_disclosures(a["corp_code"], a["date_from"], a["date_to"], a.get("kinds"), a["as_of"])


def _get_financials(a):
    return dc.get_financials(a["corp_code"], a["year"], a["quarter"], a["as_of"])


def _get_report_item(a):
    return dc.get_report_item(a["corp_code"], a["item"], a["as_of"])


def _get_events(a):
    return dc.get_events(a["corp_code"], a.get("event_types"), a["date_from"], a["date_to"], a["as_of"])


def _get_insider(a):
    return dc.get_insider(a["corp_code"], a["date_from"], a["date_to"], a["as_of"])


def _price_get_daily(a):
    return dc.price_get_daily(a["ticker"], a["date_from"], a["date_to"])


def _ledger_read(a):
    return ls.read(a.get("case_id"))


def _ledger_write(a):
    if "audit" in a:
        ls.append_audit(a["case_id"], a["audit"])
        return {"status": "ok", "op": "append_audit", "case_id": a["case_id"]}
    if "case" in a:
        ls.upsert_case(a["case"])
        return {"status": "ok", "op": "upsert_case", "case_id": a["case"].get("case_id")}
    if "doc" in a:
        ls.write(a["doc"])
        return {"status": "ok", "op": "write_doc"}
    return _err("bad_request", "ledger_write는 case/audit/doc 중 하나가 필요", "case={...} 또는 case_id+audit")


def _gate_check(a):
    violations = cgate.check(a["text"])
    return {"status": "pass" if not violations else "blocked", "violations": violations}


def _krx_risk_flags(a):
    return {"ticker": a["ticker"], "as_of": kx.snapshot_date(), "flags": kx.risk_flags(a["ticker"])}


_DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}

TOOLS = [
    {"name": "dart_resolve_corp", "handler": _resolve_corp,
     "description": "ticker 또는 회사명을 corp_code로 해소",
     "schema": {"type": "object", "required": ["query"],
                "properties": {"query": {"type": "string"}}}},
    {"name": "dart_list_disclosures", "handler": _list_disclosures,
     "description": "공시 목록 (구간·유형 필터, as_of 이후 제출분 자동 제외)",
     "schema": {"type": "object", "required": ["corp_code", "date_from", "date_to", "as_of"],
                "properties": {"corp_code": {"type": "string"}, "date_from": _DATE, "date_to": _DATE,
                               "kinds": {"type": "array", "items": {"type": "string"}}, "as_of": _DATE}}},
    {"name": "dart_get_financials", "handler": _get_financials,
     "description": "분기 주요계정 (as_of 이전 제출분만)",
     "schema": {"type": "object", "required": ["corp_code", "year", "quarter", "as_of"],
                "properties": {"corp_code": {"type": "string"}, "year": {"type": "string"},
                               "quarter": {"type": "string"}, "as_of": _DATE}}},
    {"name": "dart_get_report_item", "handler": _get_report_item,
     "description": "고정 감시 항목(배당·최대주주·감사·자기주식) 값 + 근거",
     "schema": {"type": "object", "required": ["corp_code", "item", "as_of"],
                "properties": {"corp_code": {"type": "string"},
                               "item": {"enum": ["dividend", "major_shareholder", "audit_opinion", "treasury_stock"]},
                               "as_of": _DATE}}},
    {"name": "dart_get_events", "handler": _get_events,
     "description": "주요 이벤트 목록 (분류기 세부유형 필터)",
     "schema": {"type": "object", "required": ["corp_code", "date_from", "date_to", "as_of"],
                "properties": {"corp_code": {"type": "string"}, "date_from": _DATE, "date_to": _DATE,
                               "event_types": {"type": "array", "items": {"type": "string"}}, "as_of": _DATE}}},
    {"name": "dart_get_insider", "handler": _get_insider,
     "description": "임원·주요주주·최대주주 지분 변동 공시",
     "schema": {"type": "object", "required": ["corp_code", "date_from", "date_to", "as_of"],
                "properties": {"corp_code": {"type": "string"}, "date_from": _DATE, "date_to": _DATE, "as_of": _DATE}}},
    {"name": "price_get_daily", "handler": _price_get_daily,
     "description": "일별 종가·등락률 (구간)",
     "schema": {"type": "object", "required": ["ticker", "date_from", "date_to"],
                "properties": {"ticker": {"type": "string"}, "date_from": _DATE, "date_to": _DATE}}},
    {"name": "ledger_read", "handler": _ledger_read,
     "description": "논거 원장 읽기 (case_id 주면 해당 케이스, 없으면 전체)",
     "schema": {"type": "object", "properties": {"case_id": {"type": "string"}}}},
    {"name": "ledger_write", "handler": _ledger_write,
     "description": "논거 원장 쓰기 (case upsert / audit append / doc). 스키마 검증 통과 시에만 커밋",
     "schema": {"type": "object", "properties": {"case": {"type": "object"}, "case_id": {"type": "string"},
                                                 "audit": {"type": "object"}, "doc": {"type": "object"}}}},
    {"name": "gate_check", "handler": _gate_check,
     "description": "브리핑 컴플라이언스 게이트 검사 (pass/fail + 위반)",
     "schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}},
    {"name": "krx_risk_flags", "handler": _krx_risk_flags,
     "description": "종목의 KRX 층1 시장조치 신호(관리종목·매매거래정지·투자경고·불성실공시 등) + 명단 기준일",
     "schema": {"type": "object", "required": ["ticker"], "properties": {"ticker": {"type": "string"}}}},
]

_BY_NAME = {t["name"]: t for t in TOOLS}


def dispatch(name: str, arguments: dict) -> dict:
    """도구 핸들러 호출. 미지 도구·필수 인자 누락·예외를 구조화 오류로 반환(예외 안 던짐)."""
    tool = _BY_NAME.get(name)
    if not tool:
        return _err("unknown_tool", f"존재하지 않는 도구: {name}", f"사용 가능: {', '.join(_BY_NAME)}")
    args = arguments or {}
    missing = [k for k in tool["schema"].get("required", []) if k not in args]
    if missing:
        return _err("missing_arguments", f"필수 인자 누락: {missing}", f"{name} 필수: {tool['schema'].get('required', [])}")
    try:
        return tool["handler"](args)
    except NotImplementedError as e:
        return _err("not_implemented", str(e), "WHYBUY_MODE=fixture로 실행")
    except (KeyError, ValueError) as e:
        return _err("handler_error", str(e), "")


# ── MCP stdio 서버 ────────────────────────────────────────────────
def build_server():
    from mcp.server import Server
    import mcp.types as types

    server = Server("whybuy")

    @server.list_tools()
    async def list_tools():
        return [types.Tool(name=t["name"], description=t["description"], inputSchema=t["schema"]) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        result = dispatch(name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    return server


async def _amain():
    from mcp.server.stdio import stdio_server

    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    import anyio
    anyio.run(_amain)


if __name__ == "__main__":
    main()
