# 빠른 시작 검증 안내서: 이동 입력·조건 확인·출발 시각 계산

> 2026-09-14: 서비스 제공 형태는 MCP로 확정됐다. Hermes는 개발·시연용 클라이언트다. 기존 REST 스키마는 유지하며, 제품 전제의 정정은 구현·테스트 완료를 의미하지 않는다.


**생성일**: 2026-09-13
**관련 문서**: [spec.md](spec.md), [plan.md](plan.md), [data-model.md](data-model.md), [contracts/api-contract.md](contracts/api-contract.md)

이 안내서는 기능이 종단 간 동작하는지 검증하기 위한 최소 시나리오를 담는다. 구현 코드 전체나 테스트 스위트를 대체하지 않으며, 가장 작은 약속 이동 흐름과 재탐색·저장·상태 전이·오류 구분을 재현 가능하게 확인하는 데 집중한다.

## 1. 사전 준비

- 백엔드 실행 환경 또는 Mock 응답 사용 여부를 정한다.
- Mock 사용 시 `Docs/api/examples.json`의 case id를 요청·응답 매핑으로 사용한다.
- 실제 서버 연결 시 Base URL은 배포 확정 값으로 설정한다.
- Hermes + Solar Pro4 → stdio MCP → FastAPI 연결로 검증한다. 먼저 get_capabilities를 실제 호출해 백엔드 응답을 받고, 도구 기록과 데이터 모드를 확인한다.

## 2. 검증할 핵심 흐름

### 2.1 약속 출발 시각 흐름 (P1)

**목표**: 자연어 입력 → 조건 확인 → 실제/모의 데이터 기반 권장 출발시각·근거 표시

1. `/capabilities`를 호출해 기능·기본값·지원 범위를 확인한다.
2. 자연어 입력을 `/mobility/interpret`로 전송한다.
3. 응답이 `needs_confirmation`이면, missing_fields와 questions를 확인하고 장소 검색·선택 또는 폼 수정으로 context를 갱신한다.
4. `ready_for_plan=true`가 되면 Hermes 대화에서 조건을 요약하고 사용자가 최종 확인하도록 한다.
5. 사용자 확인 후 `/journeys/plan`을 `user_confirmed=true`로 호출한다.
6. 응답 plan의 recommended_option_id, recommended_leave_at, estimated_arrival_at, legs, buffer, sources, warnings를 확인한다.

**기대 결과**:

- 명확한 도착 마감과 확정된 출발지·목적지가 있으면 추가 질문 없이 요약 확인 후 계획 계산으로 진행할 수 있어야 한다.
- 출발 시각, 목표 도착 시각, 경로 구간, Buffer 근거, 데이터 출처·기준시각이 결과에 포함되어야 한다.
- demo 출처가 하나라도 있으면 meta.is_demo=true와 DEMO_DATA 경고를 함께 표시한다.

### 2.2 막차 귀가 흐름 (P2)

**목표**: 검증 가능한 범위에서 막차 마지막 여정과 권장 출발시각을 구분한다.

1. `kind=last_journey`로 조건을 확정한다.
2. `/journeys/plan`을 호출한다.
3. 지원 데이터가 없으면 `LAST_JOURNEY_UNSUPPORTED`로, 지원 범위에서 연결 경로가 없으면 `NO_FEASIBLE_JOURNEY`로 처리되는지 확인한다.
4. 지원 가능하면 hard_leave_at과 권장 출발시각이 구분되는지 확인한다.

**기대 결과**:

- 막차 지원 불가와 연결 경로 없음을 다른 사유로 안내한다.
- 임의 막차 시각을 생성하지 않는다.

### 2.3 재탐색 흐름 (P2)

**목표**: 사용자 요청 재탐색 → 새 경로 계산 → 이전 계획 비교 → 사용자 선택 후 적용

1. 기존 계획이 저장된 상태에서 재탐색 요청을 `/journeys/replan`로 전송한다.
2. response의 plan과 comparison을 확인한다.
3. arrival_change_minutes, leave_change_minutes의 부호와 summary가 기대한 방향인지 확인한다.
4. 사용자가 새 계획을 선택해야만 기존 계획에 적용하고, 선택 전에는 교체하지 않는다.
5. 실패·취소된 재탐색이 기존 로컬 기록을 삭제하지 않는지 확인한다.

**기대 결과**:

- 재탐색 결과는 이전 계획과 비교를 제공한다.
- 사용자가 선택 전에는 기존 계획을 교체하지 않는다.

### 2.4 현재 대화의 확인·선택 문맥

1. 사용자가 확인한 조건으로만 계획을 요청하는지 확인한다.
2. Plan과 사용자가 선택한 option_id를 현재 대화에서 재탐색에 전달한다.
3. 재탐색 조회 성공만으로 기존 선택을 덮어쓰지 않는지 확인한다.
4. 조건이 바뀌면 재확인을 받고, 문맥을 잃으면 임의 복원 대신 다시 확인한다.
5. 실패·취소 시 기존 선택은 유지하되 기존 경로의 유효성을 보장하지 않는지 확인한다.

이 검증은 영구 저장·출발/도착 상태·자동 알림 구현을 요구하지 않는다. 기존 US4 저장·진행 상태 테스트는 현재 비적용이다.

### 2.5 계산 근거·데이터 출처 확인 (P3)

**목표**: MCP 도구 응답과 Hermes 설명에서 legs, buffer, sources, warnings 확인

1. Plan 응답의 각 leg 구간(walk/wait/subway/bus), estimated_arrival_at, buffer.items, sources.provider/basis/retrieved_at, warnings가 MCP 결과에 포함되고 Hermes 설명으로 전달되는지 확인한다.
2. demo 출처 포함 시 경고가 함께 표시되는지 확인한다.

**기대 결과**:

- 사용자가 계산 근거와 데이터 한계를 함께 볼 수 있다.

## 3. 예외 사례 검증

- Deadline이 이미 지난 경우에도 이용 가능한 경로가 있으면 late 상태로 반환되고, 경로가 없으면 unavailable로 처리되는지 확인한다.
- "집", "잠실" 같은 모호한 표현이 임의 좌표로 확정되지 않고 장소 검색·선택으로 연결되는지 확인한다.
- 자정 경계를 넘는 이동이 날짜와 시간대를 포함해 처리되는지 확인한다.
- 도착 여유·도보·대기·환승 시간이 이미 total_duration_minutes에 포함되어 있으면 별도로 다시 더하지 않는지 확인한다.
- 요청 정보 부족 시 최대 3개 질문을 한 번에 제공하고, 이미 확인된 조건을 반복 질문하지 않는지 확인한다.
- 교통 제공처 장애, 데이터 없음, 지원 범위 밖이 서로 다른 사유로 구분되는지 확인한다.
- 운영 조회 실패를 Demo 결과로 자동 대체하지 않는지 확인한다.

## 4. 되풀이 확인 포인트

- Mock과 실제 서버 응답이 동일 JSON 구조를 유지하는지 확인한다.
- API 필드·상태·오류 의미는 API_SPEC.md와 examples.json 기준으로만 변경한다.
- AI는 구조화·질문·설명만 담당하고, 시간 계산·경로 유효성·상태 전이·횟수 제한·권한 검증은 코드로 처리하는지 확인한다.
- Buffer 시간이 legs와 total_duration_minutes에 이미 반영되어 있고, 연동 계층에서 다시 더하거나 권장 출발시각에서 다시 빼지 않는지 확인한다.
- 재탐색은 MVP에서 사용자 요청으로 시작하는지 확인한다.

## 5. 참고

- 계약 상세는 `contracts/api-contract.md`를 참고한다.
- 엔티티·검증 규칙·상태 전이는 `data-model.md`를 참고한다.
- 미확정 사항 결정 내역은 `research.md`를 참고한다.
