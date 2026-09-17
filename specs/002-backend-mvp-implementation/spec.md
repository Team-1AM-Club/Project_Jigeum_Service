# 기능 명세: 백엔드 MVP — 계산 API, 대화 상태 저장·검증·전이, Idempotency-Key

**Feature Branch**: `feature/backend-mvp`

**Created**: 2026-09-15

**Status**: Draft

**Input**: 사용자 요청: "백엔드 MVP 구현(Spec 002)을 위한 문서(BACKEND_HANDOFF.md, API_SPEC.md, Docs/api/examples.json)와 명세(spec.md)를 최종 확정하고, 대화 상태 저장·검증·전이 설계의 세부 규칙을 확정하는 것. 이후 speckit-plan 워크플로우로 plan.md, data-model.md, quickstart.md, contracts/ 생성 완료."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 약속 이동 조건 확인 후 권장 출발시각 계산 (Priority: P1)

사용자가 자연어로 "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야."라고 말하면, 백엔드는 장소·시각·도착 여유·이동수단을 해석하고 확인 질문을 반환한다. 사용자가 장소를 확정하고 최종 조건을 확인하면, 백엔드는 실제 경로 후보 1~3개와 권장 출발시각·근거를 반환한다.

**Why this priority**: 가장 작은 약속 이동 흐름이며, Hermes → MCP → FastAPI 통합의 핵심 가치다.

**Independent Test**: 자연어 입력 → 조건 확인 → 장소 선택 → 계획 요청까지의 종단 간 흐름을 Mock과 실제 백엔드로 각각 검증할 수 있다.

**Acceptance Scenarios**:

1. **Given** 사용자가 "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야."라고 입력했을 때, **When** `/mobility/interpret`를 호출하면, **Then** 출발지·목적지 확인 질문이 반환되고, 도착 마감은 오늘 19:00으로 해석된다.
2. **Given** 출발지·목적지가 확정됐을 때, **When** `/journeys/plan`을 호출하면, **Then** 후보 경로 1~3개와 권장 출발시각·근거가 반환된다.
3. **Given** 도착 Deadline이 19:00이고 도착 여유가 10분일 때, **When** 계획 계산을 하면, **Then** target_arrival_at은 18:50이다.
4. **Given** origin/destination 확정 없이 계획 계산을 요청하면, **When** `/journeys/plan`을 호출하면, **Then** 422 VALIDATION_ERROR로 처리된다.

---

### User Story 2 - 막차 귀가 경로 계산 (Priority: P2)

사용자가 막차 귀가를 요청하면, 백엔드는 운행일·노선 지원 범위를 검증하고, 가능한 경우 자정 이후 도착하는 막차 경로를 반환한다. 지원 데이터가 없으면 LAST_JOURNEY_UNSUPPORTED, 지원 범위에서 경로가 없으면 NO_FEASIBLE_JOURNEY로 구분한다.

**Why this priority**: MVP의 핵심 가치 중 하나지만, 약속 이동보다 지원 범위 검증이 더 필요하다.

**Independent Test**: 운행일·노선 지원 범위 검증과 막차 경로 계산을 Mock과 실제 백엔드로 각각 검증할 수 있다.

**Acceptance Scenarios**:

1. **Given** 막차 운행일과 다음 날 도착시각이 있을 때, **When** 막차 계획을 요청하면, **Then** 운행일과 실제 도착 날짜가 구분돼 반환된다.
2. **Given** 지원 데이터가 없을 때, **When** 막차 계획을 요청하면, **Then** LAST_JOURNEY_UNSUPPORTED로 처리된다.
3. **Given** 지원 범위에서 경로가 없을 때, **When** 막차 계획을 요청하면, **Then** NO_FEASIBLE_JOURNEY로 처리된다.

---

### User Story 3 - 사용자 요청 재탐색 (Priority: P2)

사용자가 놓침·변경 후 재탐색을 요청하면, 백엔드는 현재 서버 시각 기준으로 새 경로를 계산하고 이전 선택 대비 시각 변화를 반환한다. 재탐색 실패·취소는 이전 선택을 삭제하지 않으며, 이전 경로가 여전히 유효하다는 보장으로 표시하지 않는다.

**Why this priority**: 실제 사용 흐름에서 중요하지만, 약속 이동과 막차보다 후순위다.

**Independent Test**: 재탐색 요청 → 새 계획 → 이전 선택 대비 시각 변화 반환을 Mock과 실제 백엔드로 각각 검증할 수 있다.

**Acceptance Scenarios**:

1. **Given** 이전 계획의 도착이 18:50이고 새 도착이 19:10일 때, **When** 재탐색을 요청하면, **Then** arrival_change_minutes는 20(양수=더 늦게 도착)이다.
2. **Given** 재탐색 실패·취소일 때, **When** 응답을 받으면, **Then** 이전 선택 계획이 삭제되지 않는다.
3. **Given** 재탐색 결과를 사용자가 선택하기 전일 때, **When** 응답을 받으면, **Then** 기존 계획이 자동 교체되지 않는다.

---

### User Story 4 - 대화 상태 저장·검증·전이 (Priority: P3)

백엔드는 대화 상태를 conversation_id로 식별해 저장하고, 상태 변경 요청 시 revision을 증가시킨다. 없거나 만료된 conversation은 410 CONVERSATION_EXPIRED로 처리하고, 이전 revision으로 상태 변경을 시도하면 409 CONVERSATION_VERSION_CONFLICT로 처리한다. Idempotency-Key를 통해 같은 요청의 중복 적용을 방지한다.

**Why this priority**: MVP의 상태 관리와 중복 방지 계약이지만, 핵심 이동 흐름보다 후순위다.

**Independent Test**: 대화 생성 → 상태 변경 → revision 증가 → 재시도 idempotency → 만료 처리 → tombstone 전환 → hard delete까지 흐름을 Mock과 실제 백엔드로 각각 검증할 수 있다.

**Acceptance Scenarios**:

1. **Given** 새 대화가 생성됐을 때, **When** 상태 변경 요청을 하면, **Then** 응답 meta에 conversation_id, revision, expires_at이 포함된다.
2. **Given** 현재 revision이 3일 때, **When** revision 2로 상태 변경을 시도하면, **Then** 409 CONVERSATION_VERSION_CONFLICT가 반환된다.
3. **Given** 없거나 만료된 conversation_id로 요청하면, **When** 요청을 처리하면, **Then** 410 CONVERSATION_EXPIRED가 반환된다.
4. **Given** 같은 Idempotency-Key로 다른 요청을 보내면, **When** 요청을 처리하면, **Then** 409 IDEMPOTENCY_KEY_REUSED가 반환된다.
5. **Given** 이미 성공한 같은 key·같은 payload 재요청을 보내면, **When** 요청을 처리하면, **Then** 상태를 다시 변경하지 않고 저장된 응답을 반환한다.
6. **Given** provider 호출이 실패할 때, **When** 실패 후 상태를 확인하면, **Then** domain 상태·revision·updated_at이 변경되지 않는다.
7. **Given** conversation은 유효하지만 후보 집합이 만료됐을 때, **When** 후보 선택 요청을 하면, **Then** 410 CANDIDATE_SET_EXPIRED가 반환된다.
8. **Given** Idempotency-Key가 없거나 형식이 잘못됐을 때, **When** 상태 변경 요청을 하면, **Then** 422 VALIDATION_ERROR가 반환된다.
9. **Given** 상태 변경 성공 응답을 받으면, **When** 응답 헤더를 확인하면, **Then** 응답 헤더에 동일한 Idempotency-Key가 반환된다.
10. **Given** 상태 변경 성공 응답을 받으면, **When** 응답 JSON envelope를 확인하면, **Then** Idempotency-Key가 JSON body에 중복 추가되지 않는다.
11. **Given** tombstone이 24시간 유지된 후 hard delete되면, **When** 동일 ID로 요청하면, **Then** 404 CONVERSATION_NOT_FOUND가 반환된다.
12. **Given** provider 호출 시 payload hash를 계산하면, **When** hash 범위를 확인하면, **Then** HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body를 포함해 SHA-256으로 hash한다.

---

## Functional Requirements

### 자연어 해석 (FR-001 ~ FR-005)

- **FR-001**: 시스템은 자연어 입력을 구조화해 장소·시각·도착 여유·이동수단 초안을 반환해야 한다(MUST).
- **FR-002**: 시스템은 확인 질문 0~3개를 반환하고, 필요한 경우 장소 검색을 요청해야 한다(MUST).
- **FR-003**: 시스템은 사용자가 장소를 확정하고 최종 조건을 확인하면, 실제 경로 후보 1~3개와 권장 출발시각·근거를 반환해야 한다(MUST).
- **FR-004**: 시스템은 arrival_deadline과 arrival_preference_minutes를 기반으로 target_arrival_at을 계산해야 한다(MUST).
- **FR-005**: 시스템은 Buffer 시간을 leg·total_duration_minutes에 이미 반영하고, 재가산하지 않아야 한다(MUST).

### 막차 (FR-006 ~ FR-008)

- **FR-006**: 시스템은 막차 운행일과 다음 날 도착시각을 구분해야 한다(MUST).
- **FR-007**: 시스템은 지원 데이터가 없으면 LAST_JOURNEY_UNSUPPORTED, 지원 범위에서 경로가 없으면 NO_FEASIBLE_JOURNEY로 구분해야 한다(MUST).
- **FR-008**: 시스템은 재탐색 요청 시 현재 서버 시각 기준으로 새 경로를 계산하고, 이전 선택 대비 시각 변화를 반환해야 한다(MUST).

### 재탐색 (FR-009 ~ FR-011)

- **FR-009**: 시스템은 재탐색 실패·취소 시 이전 선택을 삭제하지 않아야 한다(MUST).
- **FR-010**: 시스템은 사용자가 새 후보를 선택하기 전까지 기존 계획을 자동 교체하지 않아야 한다(MUST).
- **FR-011**: 시스템은 재탐색 시 새 Plan과 이전 선택 대비 comparison을 반환해야 한다(MUST).

### 대화 상태 저장·검증·전이 (FR-012 ~ FR-022)

- **FR-012**: 시스템은 대화 상태를 conversation_id로 식별해 저장해야 한다(MUST).
- **FR-013**: 시스템은 상태 변경 요청 성공 시 revision을 증가시켜야 한다(MUST).
- **FR-014**: 시스템은 없거나 만료된 conversation_id로 요청하면 410 CONVERSATION_EXPIRED로 처리해야 한다(MUST).
- **FR-015**: 시스템은 이전 revision으로 상태 변경을 시도하면 409 CONVERSATION_VERSION_CONFLICT로 처리해야 한다(MUST).
- **FR-016**: 시스템은 Idempotency-Key를 생성하고, 상태 변경 요청에 포함해 전달해야 한다(MUST).
- **FR-017**: 시스템은 Idempotency-Key가 없거나 형식이 잘못되면 422 VALIDATION_ERROR로 처리해야 한다(MUST).
- **FR-018**: 시스템은 같은 Idempotency-Key로 다른 요청이 이미 처리됐으면 409 IDEMPOTENCY_KEY_REUSED로 처리해야 한다(MUST).
- **FR-019**: 시스템은 이미 성공한 같은 key·같은 payload 재요청은 상태를 다시 변경하지 않고 저장된 응답을 반환해야 한다(MUST).
- **FR-020**: 시스템은 provider 호출 실패 후 domain 상태·revision·updated_at을 변경하지 않아야 한다(MUST).
- **FR-021**: 시스템은 conversation은 유효하지만 후보 집합이 만료됐을 때 410 CANDIDATE_SET_EXPIRED로 처리해야 한다(MUST).
- **FR-022**: 시스템은 상태 변경 성공 응답의 응답 헤더에 동일한 Idempotency-Key를 반환하고, 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않아야 한다(MUST).

- **FR-023 ~ FR-033**: (의도적 생략 — 현재 MVP 범위에 해당하는 요구사항이 없음. 향후 필요시 번호 재부여 또는 별도 섹션으로 추가)
### Provider 호출 순서 (FR-034)

- **FR-034**: 시스템은 provider가 필요한 상태 변경 시 다음 5단계 순서를 따라야 한다(MUST).
  1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
  2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
  3. provider 성공 결과를 검증한다.
  4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
  5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

### tombstone (FR-035 ~ FR-037)

- **FR-035**: 시스템은 expires_at <= 서버 현재 시각이면 즉시 만료로 판단하고, 상태 변화와 revision 증가 없이 410 CONVERSATION_EXPIRED로 반환해야 한다(MUST).
- **FR-036**: 시스템은 만료 시 확인 조건·후보·선택 계획 payload를 제거하고, conversation_id·마지막 revision·expired_at만 tombstone으로 보관해야 한다(MUST).
- **FR-037**: 시스템은 tombstone을 24시간 유지 후 hard delete하고, hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리해야 한다(MUST).

### Idempotency-Key 형식 (FR-038 ~ FR-040)

- **FR-038**: 시스템은 Idempotency-Key로 UUID v4 표준 문자열 36자를 사용해야 한다(MUST).
- **FR-039**: 시스템은 Idempotency-Key를 HTTP 요청 헤더 `Idempotency-Key`로 전달하고, 응답 헤더에도 동일한 값을 반환해야 한다(MUST).
- **FR-040**: 시스템은 응답 JSON envelope에 Idempotency-Key를 중복 추가하지 않아야 한다(MUST).

### 재시도 정책 (FR-041 ~ FR-042)

- **FR-041**: 시스템은 MVP 기본값 자동 재시도 최대 1회, 대기 500ms로 해야 한다(MUST).
- **FR-042**: 시스템은 네트워크 연결 실패·timeout 또는 계약상 retryable=true인 502/503/504에만 자동 재시도를 적용하고, 4xx·409·410·검증 실패·invalid response는 자동 재시도하지 않아야 한다(MUST).

---

## Success Criteria

- [ ] **SC-001**: 사용자는 자연어 입력 → 조건 확인 → 장소 선택 → 계획 요청까지의 종단 간 흐름을 완료할 수 있다.
- [ ] **SC-002**: 시스템은 도착 Deadline 19:00, 도착 여유 10분일 때 target_arrival_at 18:50을 반환한다.
- [ ] **SC-003**: 시스템은 막차 운행일과 다음 날 도착시각을 구분해 반환한다.
- [ ] **SC-004**: 시스템은 재탐색 요청 시 이전 선택 대비 시각 변화를 반환한다.
- [ ] **SC-005**: 시스템은 상태 변경 성공 응답의 meta에 conversation_id, revision, expires_at을 포함한다.
- [ ] **SC-006**: 시스템은 이전 revision으로 상태 변경을 시도하면 409 CONVERSATION_VERSION_CONFLICT를 반환한다.
- [ ] **SC-007**: 시스템은 없거나 만료된 conversation_id로 요청하면 410 CONVERSATION_EXPIRED를 반환한다.
- [ ] **SC-008**: 시스템은 같은 Idempotency-Key로 다른 요청을 보내면 409 IDEMPOTENCY_KEY_REUSED를 반환한다.
- [ ] **SC-009**: 시스템은 이미 성공한 같은 key·같은 payload 재요청은 상태를 다시 변경하지 않고 저장된 응답을 반환한다.
- [ ] **SC-010**: 시스템은 provider 호출 실패 후 domain 상태·revision·updated_at을 변경하지 않는다.
- [ ] **SC-011**: 시스템은 conversation은 유효하지만 후보 집합이 만료됐을 때 410 CANDIDATE_SET_EXPIRED를 반환한다.
- [ ] **SC-012**: 시스템은 Idempotency-Key 누락·형식 오류 시 422 VALIDATION_ERROR를 반환한다.
- [ ] **SC-013**: 시스템은 응답 헤더에 동일한 Idempotency-Key를 반환한다.
- [ ] **SC-014**: 시스템은 응답 JSON envelope에 Idempotency-Key를 중복 추가하지 않는다.
- [ ] **SC-015**: 시스템은 tombstone을 24시간 유지 후 hard delete하고, hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리한다.
- [ ] **SC-016**: 시스템은 payload hash를 HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body에 대해 SHA-256으로 계산한다.

---

## Key Entities

### Conversation

- conversation_id: string (PK)
- revision: integer
- created_at: datetime
- updated_at: datetime
- expires_at: datetime
- confirmed_conditions: jsonb (확인된 이동 조건)
- candidate_set: jsonb (후보 계획 집합, 만료 시각 포함)
- active_selected_plan: jsonb (사용자가 선택한 계획)
- status: enum (active, expired, tombstone)

### Plan

- plan_id: string
- conversation_id: string (FK)
- selected_option_id: string
- recommended_leave_at: datetime
- estimated_arrival_at: datetime
- total_duration_minutes: integer
- legs: jsonb

### RouteOption

- option_id: string
- plan_id: string (FK)
- summary: string
- recommended_leave_at: datetime
- estimated_arrival_at: datetime
- total_duration_minutes: integer
- buffer: jsonb
- legs: jsonb

### IdempotencyRecord

- id: integer (PK)
- conversation_id: string
- idempotency_key: string (UNIQUE with conversation_id)
- payload_hash: string (SHA-256)
- http_method: string
- api_path: string
- expected_revision: integer
- response_body: jsonb
- response_status: integer
- created_at: datetime

---

## Edge Cases

- 자연어에 모호한 장소 표현이 포함된 경우: 확인 질문으로 명확화
- 출발지·목적지가 모두 확정되지 않은 상태에서 plan 요청: 422 VALIDATION_ERROR
- arrival_preference_minutes가 0~120 범위를 벗어난 경우: 422 VALIDATION_ERROR
- transport_modes에 미지원 모드(taxi 등) 포함: 422 VALIDATION_ERROR
- 막차 운행일이지만 지원 데이터가 없는 경우: LAST_JOURNEY_UNSUPPORTED
- 지원 범위에서 막차 경로가 없는 경우: NO_FEASIBLE_JOURNEY
- 재탐색 결과가 이전 선택보다 나쁜 경우: 비교 정보와 함께 반환, 자동 선택 안 함
- 동일한 Idempotency-Key로 다른 페이로드 요청: 409 IDEMPOTENCY_KEY_REUSED
- conversation이 만료된 상태에서 요청: 410 CONVERSATION_EXPIRED
- candidate_set만 만료된 상태에서 후보 선택 요청: 410 CANDIDATE_SET_EXPIRED
- tombstone 24시간 경과 후 동일 ID 요청: 404 CONVERSATION_NOT_FOUND

---

## Assumptions

- 백엔드는 Python 3.11+, FastAPI, Uvicorn, Pydantic 기반으로 구현한다.
- 저장소: SQLite + SQLAlchemy. 대화 상태는 TTL 방식으로 저장한다.
- MCP 도구는 5개(get_capabilities, search_places, interpret_trip, plan_journey, replan_journey)이며, 각각 REST 엔드포인트와 1:1 매핑된다.
- Hermes + Upstage Solar Pro4를 개발·시연에 사용한다.
- Buffer 정책 이름만 두고(예: demo-v1), 세부 항목·분은 실제 정책 확정 전까지 세부 보장값처럼 주장하지 않는다.
- 실제 장소·교통 API 서비스명·엔드포인트·키·한도·호출 가이드는 사용자 양식 제출 후 확정한다.
- Solar 모델 ID·호출 경로·접근 권한은 사용자 양식 제출 후 확정한다.
- 배포 Base URL·포트·환경변수 이름·접근 제어는 구현 시점에 확정한다.
- 대화 상태 SQLite TTL 저장소의 기본 만료 시점은 구현 시점에 확정한다. 별도 지정 없으면 기본값 사용.
- Provider 호출 실패 시 재시도 여부·재시도 횟수·대기 시간은 MVP 기본값(최대 1회, 500ms)으로 고정한다. 변경하려면 두 사람이 함께 바꾼다.
- Idempotency-Key는 MCP 서버가 상태 변경 MCP 도구 호출 시작 시 UUID v4로 생성한다. 모델이나 사용자에게 입력받지 않는다.
- Payload hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body. body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256을 hash한다.
- MCP는 최초 요청 body와 expected revision을 보관한다. 같은 논리적 요청 재시도 시 그대로 재전송하며, 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.
- 백엔드 canonicalization은 JSON 객체 키 순서와 공백 차이만 흡수한다. 배열 순서, null과 필드 생략, 값 변경은 동일하다고 간주하지 않는다.
- Tombstone 충돌 처리는 멱등하게 수행한다. 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환하고, 별도 테이블 사용 시 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- Provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다.
- provider 실패는 domain 상태·revision·updated_at·TTL을 갱신하지 않는다. 백엔드는 workflow 수준의 자동 재시도를 하지 않으며, provider 호출을 DB 트랜잭션 내부에 포함하지 않는다.
- MCP는 네트워크 연결 실패, timeout, 또는 계약상 retryable=true인 HTTP 502/503/504에 한해 최초 호출 후 최대 1회 자동 재시도할 수 있다.
- MCP 기본 재시도 정책은 자동 재시도 최대 1회, 대기 500ms로 한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.
- MCP는 같은 Idempotency-Key와 같은 body로 재시도하며, 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.
- 해석 가능한 오류 응답이 retryable=false이면 HTTP 상태만 보고 재시도하지 않는다.
- 409, 410, 검증 실패, invalid JSON/invalid response는 자동 재시도하지 않는다.
- tombstone 생성 충돌은 멱등하게 처리한다. 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환하고, 별도 테이블 사용 시 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다. 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다. 충돌 후 해당 tombstone이 존재함을 확인하면 동일하게 410 CONVERSATION_EXPIRED로 응답한다. 기존 expired_at을 재설정하거나 tombstone 보존 기간을 연장하지 않는다. 중복 키 이외의 DB 오류는 무시하거나 410으로 감추지 않는다. hard delete 이후에는 404 CONVERSATION_NOT_FOUND를 반환하고, 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.
- expires_at <= 서버 현재 시각이면 즉시 만료로 판단하고, 상태 변화와 revision 증가 없이 410 CONVERSATION_EXPIRED로 반환한다. 만료 시 확인 조건·후보·선택 계획 payload를 제거하고, conversation_id·마지막 revision·expired_at만 tombstone으로 보관한다. tombstone은 24시간 유지 후 hard delete한다. 정리는 백엔드 시작 시 한 번, 실행 중 주기적으로 수행하고, 요청 시 만료가 발견되면 cleanup 주기를 기다리지 않고 즉시 tombstone 처리한다. tombstone 전환으로 사용자 revision은 증가시키지 않고 마지막 revision을 유지한다.
- conversation과 confirmed_conditions는 유지하고, active_selected_plan도 유지한다. 만료된 candidate_set은 선택할 수 없고, 해당 candidate 선택 요청은 410 CANDIDATE_SET_EXPIRED로 처리한다. revision은 변경하지 않는다. 사용자는 기존 확인 조건으로 새 후보 생성을 요청할 수 있다. 새 후보가 생성돼도 active_selected_plan은 자동 교체하지 않고, 새 후보 중 하나를 명시적으로 선택했을 때만 active_selected_plan을 변경한다.
- Idempotency-Key 형식: UUID v4 표준 문자열 36자 사용. 요청·응답 모두 헤더명 Idempotency-Key 사용. 응답 envelope에는 같은 값을 중복 추가하지 않음. 필수 요청에서 누락·형식 오류 시 422 VALIDATION_ERROR. 동일 key에 다른 요청 시 409 IDEMPOTENCY_KEY_REUSED.
- 재시도 정책: MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 확정. 연결 실패·timeout 또는 계약상 retryable=true인 502/503/504에만 적용. 같은 Idempotency-Key와 같은 body로 재시도. 4xx·409·410·검증 실패·invalid response는 자동 재시도하지 않음.


---

- confirmed_conditions: jsonb (확인된 이동 조건)
- candidate_set: jsonb (후보 계획 집합, 만료 시각 포함)
- active_selected_plan: jsonb (사용자가 선택한 계획)
- status: enum (active, expired, tombstone)

### Plan

- plan_id: string
- conversation_id: string (FK)
- selected_option_id: string
- recommended_leave_at: datetime
- estimated_arrival_at: datetime
- total_duration_minutes: integer
- legs: jsonb

### RouteOption

- option_id: string
- plan_id: string (FK)
- summary: string
- recommended_leave_at: datetime
- estimated_arrival_at: datetime
- total_duration_minutes: integer
- buffer: jsonb
- legs: jsonb

### IdempotencyRecord

- id: integer (PK)
- conversation_id: string
- idempotency_key: string (UNIQUE with conversation_id)
- payload_hash: string (SHA-256)
- http_method: string
- api_path: string
- expected_revision: integer
- response_body: jsonb
- response_status: integer
- created_at: datetime

## Clarifications

### Session 2026-09-15

- - Q: tasks.md T014의 'AI 제공자' 용어가 모호함 (AI의 역할 범위가 불분명). → A: '모델 제공자 (자연어 해석)'로 명확화. AI(모델)는 자연어 입력 해석·확인 질문 생성 역할만 담당하며, 이동 경로 계산·실제 교통 데이터 제공은 별도 제공자(라우팅·대중교통·장소 제공자)가 담당.
- - Q: tasks.md T028에 Provider 호출 순서 5단계가 명시되지 않음 (단순한 '흐름 조정'만 기술). → A: Provider 호출 순서 5단계(① conversation 유효성·입력·Idempotency-Key 기록·revision 확인 → ② DB 쓰기 트랜잭션 밖에서 provider 호출 → ③ provider 성공 결과 검증 → ④ 짧은 DB 트랜잭션에서 만료 여부·Idempotency-Key·revision 재확인 → ⑤ domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자적 커밋)를 명시하고, provider 호출 필요 없는 경우 DB 트랜잭션 안에서 검증·커밋하도록 명확화.
- - Q: Idempotency-Key 고유성 신뢰 모델 - MCP가 생성한 Idempotency-Key의 고유성을 MCP가 보장하고, 백엔드는 형식 검증(UUID v4 36자)과 conversation_id + Idempotency-Key UNIQUE 제약만으로 멱등성 처리해도 되는가? → A: 예. 백엔드가 직접 키 고유성을 재검증하거나 새 키를 요구하지 않고, MCP가 UUID v4 고유성을 보장한 것으로 신뢰한다. 백엔드는 형식 검증과 UNIQUE 제약으로 중복 재사용을 방지한다.
- - Q: tasks.md T040(확인 조건 충족 전 plan 요청 차단)과 T063(일반 상태 변경 검증: conversation 유효성·입력·Idempotency-Key·revision 확인)의 역할 경계가 중복되는 것처럼 보임. → A: T040은 US1 특유 검증(확인 조건 충족 전 plan 요청 차단)으로 한정하고, 일반 상태 변경 검증(conversation 유효성·입력·Idempotency-Key·revision 확인)은 T063에 위임하는 것으로 명확화.
- - Q: tasks.md T021에 SC-013(응답 헤더 Idempotency-Key 반환)과 SC-014(응답 envelope 중복 추가 금지) 태스크가 없음. → A: T021a(응답 헤더 Idempotency-Key 반환), T021b(응답 envelope Idempotency-Key 중복 추가 금지)을 T021에 추가. (이미 처리됨)
