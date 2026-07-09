"""판정 룰 레지스트리 (판정의 심장) — whybuy.

PRD 5.3의 룰 7종(EARN/RET/DIV/GRW/NEW/THM/PRC)을 코드로 구현. 입력=원장 reason
+ as_of, 출력={status, evidence, rule_id}. 결정적 연산(같은 입력→같은 판정).
가격 격리: 이 모듈은 price 관련 임포트·도구 접근이 없다 (코드 수준 격리).

TODO(G5): 룰 레지스트리 구현. G0 스켈레톤.
"""
