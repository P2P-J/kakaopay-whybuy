"""픽스처 수집 (아엔 로컬에서 1회 실행) — whybuy.

corpCode.xml → corp_code, 기업개황(corp_cls→kospi/kosdaq/konex/etc 번역), 공시목록
(유형 A~E·I 각각 별도 호출·페이지네이션), 분기 재무(전년 동기까지·fs_div 연결),
배당·최대주주·감사의견, 일별 시세+지수(매수일 30거래일 이전부터)를 fixtures/에 저장.
DART_API_KEY는 .env에서만 읽고 로그·커밋에 노출 금지(crtfc_key 마스킹). 재실행 안전.

TODO(G1): 수집 스크립트 구현. G0 스켈레톤. (개발환경에서 작성 → 아엔 로컬 실행)
"""
