"""원장 스키마 검증 (CI 역할) — whybuy.

reasons.json의 필수 필드, 날짜 형식, rcp_no 형식(14자리), status·type·source enum을
jsonschema로 검사한다. 원장 무결성의 최종 방어선.

TODO(G3): 스키마 검증 구현. G0 스켈레톤.
"""
