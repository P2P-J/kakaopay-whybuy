"""스킬 파이프라인 진입점 (컨트랙트 명령) — whybuy.

파이프라인 규약(0.7 / 부록 D): 각 스킬의 파이프라인 로직은 import 가능한 순수
함수로 작성하고, argparse CLI는 그 함수를 호출하는 얇은 래퍼일 뿐이다. 테스트는
CLI를 거치지 않고 함수를 직접 호출한다. (HTTP 래핑 확장이 이 규약에 걸려 있다.)

TODO(G6): timeline 서브커맨드. TODO(G7): recall. TODO(G8): audit. G0 스켈레톤.
"""
