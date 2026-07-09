"""OpenDART 호출 + 픽스처/캐시 스위치 (국내 전용) — whybuy.

WHYBUY_MODE=fixture(기본)면 fixtures만, live면 API 호출+캐시 저장.
as_of 필터를 이 계층에서 일괄 적용해 모든 도구가 시점 시뮬레이션을 공짜로 얻는다.
DART_API_KEY는 .env에서만 읽고 로그·커밋에 노출하지 않는다.

TODO(G3): 픽스처/캐시 읽기 계층 + as_of 필터 + status 코드 처리. G0 스켈레톤.
"""
