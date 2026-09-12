# 서비스 Agent 역할 초안

이 파일들은 팀의 역할 명세이며 Hermes의 자동 Agent 등록 형식이 아니다. 실제 실행·Skill 로딩·도구 연결은 backend/app/agents에서 구현하고 검증한다.

| Agent | 역할 | 사용할 Skill |
|---|---|---|
| MainAgent | 요청 분류·작업 배정·결과 취합·사용자 확인 | 필요한 SubAgent 호출 |
| TripIntakeAgent | 이동 조건 해석·부족한 정보 확인 | resolve-trip-details, schedule-ready |
| DeparturePlannerAgent | 약속·막차 출발 계획과 위험 설명 | leave-by, maginot-line, route-risk-checker |
| RecoveryAgent | 계획 실패 후 재탐색·대안 비교 | plan-b-recovery, route-risk-checker |

하나의 SubAgent가 여러 Skill을 사용할 수 있고 같은 Skill을 여러 SubAgent가 사용할 수 있다. 모든 Skill을 매 요청마다 로드·실행하지 않는다. 위 묶음은 초기 역할 설계이며 실제 데이터·런타임 검증 후 공동 조정한다.

journey-check-in은 수동 상태 흐름에서 필요한 부분만, departure-alert는 선택 구현으로 연결한다. calendar-conflict, taxi-hybrid 및 자동 감시·재탐색 관련 기능은 IDEA.md의 보류 범위를 유지한다.

구현 전에 구조화 입출력, 도구 허용 범위, 모델 호출 횟수·전체 제한시간, 실패 반환 정책을 specs에 정의한다. 일반 코딩 도구나 개발자 자격증명을 서비스 사용자 요청에 무제한 노출하지 않는다.
