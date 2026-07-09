"""로컬 MCP 서버 (stdio) — whybuy.

PRD 6번의 도구 10종을 stdio MCP로 노출한다. dart_client의 얇은 래퍼 + 입력 검증.
실패는 예외가 아니라 구조화된 오류 응답({error, message, hint})으로 반환한다.

TODO(G3): mcp 파이썬 SDK로 서버 구현. 이 파일은 G0 스켈레톤이다.
"""
