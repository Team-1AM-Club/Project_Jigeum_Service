# Tasks: 백엔드 MVP — 계산 API, 대화 상태 저장·검증·전이, Idempotency-Key

**Input**: Design documents from `specs/002-backend-mvp-implementation/`

**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api-contract.md, research.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (예: [US1], [US2], [US3], [US4])

## Path Conventions

- Backend: `backend/`
- Models: `backend/app/models/`
- Schemas: `backend/app/schemas/`
- API routers: `backend/app/api/`
- Services: `backend/app/services/`
- DB: `backend/app/db.py`, `backend/app/config.py`
- Tests: `backend/tests/`, `backend/tests/contract/`, `backend/tests/integration/`, `backend/tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 프로젝트 초기화 및 기본 구조

- [X] T001 [P] `backend/` 디렉터리프로젝트 구조 생성: `app/`, `app/models/`, `app/schemas/`, `app/api/`, `app/services/`, `tests/`, `tests/contract/`, `tests/integration/`, `tests/unit/`
- [X] T002 [P] `backend/requirements.txt`에 FastAPI, SQLAlchemy, SQLite 드라이버, pytest, httpx, Pydantic, python-dotenv 의존성 명시
- [X] T003 [P] `backend/app/main.py`에 FastAPI 앱 초기 설정 및 `/api/v1/health`, `/api/v1/capabilities` 라우터 등록
- [X] T004 [P] `backend/app/config.py`에 환경 변수 기반 설정 클래스 생성 (Base URL, DB 경로, 외부 제공자 URL placeholder)
- [X] T005 [P] `backend/.env.example`에 환경 변수 placeholder 작성 (실제 값은 포함하지 않음)
- [X] T006 [P] `backend/app/schemas/`에 공통 응답 스키마 (`envelope.py` 또는 `common.py`) 생성: `{status, data, error, meta}` 구조 + `meta` 필드 (`request_id`, `server_time`, `api_version`, `is_demo`)
- [X] T007 [P] `backend/app/schemas/`에 장소 관련 요청·응답 스키마 생성 (`places.py`): GET `/api/v1/places` 요청 쿼리 파라미터, 응답 `places` 배열 형식
- [X] T008 [P] `backend/app/schemas/`에 이동 조건 해석 관련 스키마 생성 (`mobility.py`): POST `/api/v1/mobility/interpret` 요청 body, 응답 확인 질문 구조
- [X] T009 [P] `backend/app/schemas/`에 계획 관련 스키마 생성 (`journeys.py`): POST `/api/v1/journeys/plan` 요청 body, 응답 `Plan`, `PlanSummary`, `Comparison` 형식
- [X] T010 [P] `backend/app/schemas/`에 재탐색 관련 스키마 생성 (`journeys.py`): POST `/api/v1/journeys/replan` 요청 body, 응답 형식
- [X] T011 [P] `backend/app/db.py`에 SQLite 연결·세션 관리 함수 생성 (SQLAlchemy 2.0 스타일)
- [X] T012 [P] `backend/app/main.py`에 전역 예외 핸들러 등록: JSON envelope 유지, 상태 코드 매핑

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 모든 사용자 스토리가 의존하는 핵심 인프라

**⚠️ CRITICAL**: 이 페이즈가 완료되기 전에는 어떤 사용자 스토리 작업도 시작할 수 없음

- [X] T013 [P] `backend/app/schemas/errors.py`에 오류 코드 열거 및 오류 응답 스키마 생성: `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `VERSION_CONFLICT`, `PRECONDITION_FAILED`, `UNPROCESSABLE_ENTITY`, `RATE_LIMITED`, `INTERNAL_ERROR`, `BAD_GATEWAY`, `SERVICE_UNAVAILABLE`, `UPSTREAM_TIMEOUT`, `UPSTREAM_RESPONSE_INVALID`, `CONVERSATION_NOT_FOUND`, `CONVERSATION_VERSION_CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `CONVERSATION_EXPIRED`, `CANDIDATE_SET_EXPIRED` 및 `unavailable` 계열 (`NO_FEASIBLE_JOURNEY`, `LAST_JOURNEY_UNSUPPORTED`, `OUT_OF_SERVICE_AREA`, `APPOINTMENT_TIME_UNSUPPORTED`, `BUFFER_REQUIREMENT_NOT_MET`)
- [X] T014 [P] `backend/app/services/`에 제공자 클라이언트 인터페이스(추상 베이스 클래스) 생성: 라우팅 제공자, 대중교통 제공자, 장소 제공자, 모델 제공자 (자연어 해석). 실제 구현은 Mock으로 시작
- [X] T015 [P] `backend/app/services/mock/`에 Mock 제공자 구현 생성: 각 제공자 인터페이스에 대해 고정된 응답 returning 구현. 테스트·개발과 실제 제공자를 분리하기 위함
- [X] T016 [P] `backend/app/services/provider_client.py`에 HTTP 클라이언트 래퍼 생성: 연결 실패·timeout·502/503/504 재시도 로직 포함 (최대 1회, 500ms 대기). retryable 판단 로직 포함
- [X] T017 [P] `backend/app/config.py`에 제공자 설정(URL, 키 placeholder 등) 추가. 실제 키·비밀값은 포함하지 않음
- [X] T018 `backend/app/services/service_factory.py`에 서비스 팩토리 생성: config 기반으로 실제 제공자 또는 Mock 선택
- [X] T019 [P] `backend/app/schemas/conversation.py`에 대화 상태 관련 스키마 생성: `Conversation`, `ConfirmedConditions`, `CandidateSet`, `ActiveSelectedPlan`, `Revision`, `ExpiresAt` 형식
- [X] T020 [P] `backend/app/api/`에 라우팅 구조 생성: `possibilities.py` (GET /api/v1/places), `mobility.py` (POST /api/v1/mobility/interpret), `journeys.py` (POST /api/v1/journeys/plan, POST /api/v1/journeys/replan)
- [X] T021 `backend/app/main.py`에 Idempotency-Key 헤더 파싱 미들웨어/의존성 추가: UUID v4 36자 검증, 누락·형식 오류 시 422 처리
- [ ] T021b [US4] `backend/app/main.py`에 상태 변경 성공 응답 시 요청 시 전달받은 Idempotency-Key 값을 응답 헤더 `Idempotency-Key`로 그대로 반환하는 로직 추가 (SC-013)
- [ ] T021c [US4] `backend/app/schemas/` 응답 envelope 생성 로직에서 Idempotency-Key를 JSON body에 중복 추가하지 않도록 확인 (응답 JSON에는 Idempotency-Key를 포함하지 않음) (SC-014)
- [X] T022 [P] `backend/app/services/idempotency.py`에 Idempotency-Key 처리 서비스 생성: conversation_id + idempotency_key UNIQUE 제약, payload hash 계산 (HTTP method, 정규화된 path, conversation_id, expected revision, canonicalized body → SHA-256), 저장·조회 로직
- [X] T023 `backend/app/services/conversation_service.py`에 대화 상태 관리 서비스 생성: conversation 생성·조회·갱신·만료 처리·tombstone 전환·hard delete 로직
- [X] T024 `backend/app/models/conversation.py`에 Conversation 모델 생성: conversation_id (PK), revision, expires_at, confirmed_conditions, candidate_set, active_selected_plan, updated_at, 기타 메타데이터
- [X] T025 [P] `backend/app/models/plan.py`에 Plan/Candidate 모델 생성: plan_id, conversation_id, selected_option_id, recommended_leave_at, recommended_arrival_at, total_duration_minutes, legs, origin_place_id, destination_place_id, created_at
- [X] T026 [P] `backend/app/schemas/`에 Buffer 관련 스키마 보강: target_arrival_at, recommended_leave_at, total_duration_minutes, legs 구조, 시간 계산 규칙 반영
- [X] T027 `backend/app/services/time_calculation.py`에 시간 계산 서비스 생성: 도착 마감 기준 권장 출발시각 계산, Buffer 반영, 시간대·자정 경계·운행일 구분 처리. **버퍼 중복 가산 금지** 규칙 구현
- [X] T028 `backend/app/services/calculation_service.py`에 핵심 계산 서비스 생성: interpret → 후보 도출 → plan → replan 흐름 조정. Provider 호출 순서 5단계(① conversation 유효성·입력·Idempotency-Key 기록·revision 확인 → ② DB 쓰기 트랜잭션 밖에서 provider 호출 → ③ provider 성공 결과 검증 → ④ 짧은 DB 트랜잭션에서 만료 여부·Idempotency-Key·revision 재확인 → ⑤ domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자적 커밋)를 준수. Provider 호출이 필요 없는 경우 DB 트랜잭션 안에서 검증·커밋.
- [X] T029 `backend/tests/conftest.py`에 테스트 픽스처 생성: FastAPI 테스트 클라이언트, Mock 제공자 설정, DB 세션 관리
- [X] T030 `backend/tests/contract/`에 계약 테스트 폴더 구조 생성

**Checkpoint**: 기초 인프라 완료 — 모든 사용자 스토리 구현 시작 가능

---

## Phase 3: User Story 1 - 약속 이동 조건 확인 후 권장 출발시각 계산 (Priority: P1) 🎯 MVP

**Goal**: 사용자가 자연어로 약속 이동 조건을 입력하면, 백엔드가 장소·시각·도착 여유·이동수단을 해석하고 확인 질문을 반환한 뒤, 장소 확정 후 실제 경로 후보 1~3개와 권장 출발시각·근거를 반환

**Independent Test**: 자연어 입력 → 조건 확인 → 장소 선택 → 계획 요청까지 종단 간 흐름을 Mock과 실제 백엔드로 각각 검증 가능

### Tests for User Story 1 ⚠️

> **NOTE: 구현 전에 테스트를 먼저 작성하고 FAIL 확인**

- [X] T031 [P] [US1] `backend/tests/contract/test_journeys_plan.py`에 POST /api/v1/journeys/plan 계약 테스트 생성: 정상 요청 → Plan 응답 검증, 출발지 미확정 → 422 VALIDATION_ERROR 검증
- [X] T032 [P] [US1] `backend/tests/integration/test_journeys_plan_e2e.py`에 interpret → confirm → plan 종단 간 통합 테스트 생성 (Mock 제공자 사용)
- [X] T033 [P] [US1] `backend/tests/unit/test_time_calculation.py`에 시간 계산 단위 테스트 생성: target_arrival_at = arrival_deadline - arrival_preference_minutes 검증, Buffer 중복 가산 방지 검증

### Implementation for User Story 1

- [X] T034 [P] [US1] `backend/app/schemas/mobility.py`에 interpret 요청/응답 스키마 완성: TripDraft 구조 (origin_place_id, destination_place_id, departure_at, arrival_deadline, arrival_preference_minutes, transport_mode, natural_language)
- [X] T035 [P] [US1] `backend/app/schemas/journeys.py`에 plan 요청/응답 스키마 완성: TripRequest, Plan, PlanSummary, Comparison 구조
- [X] T036 [US1] `backend/app/services/interpret_service.py`에 해석 서비스 생성: 자연어 → TripDraft 변환 로직 (모델 제공자(자연어 해석) 호출). 확인 질문 생성 포함
- [X] T037 [US1] `backend/app/api/mobility.py`에 POST /api/v1/mobility/interpret 라우터 구현: 요청 검증, 해석 서비스 호출, 확인 질문 응답 반환
- [X] T038 [US1] `backend/app/api/journeys.py`에 POST /api/v1/journeys/plan 라우터 구현: TripRequest 검증, plan 서비스 호출, Plan 응답 반환, 출발지 미확정 시 422 처리
- [X] T039 [US1] `backend/app/services/plan_service.py`에 계획 서비스 생성: 출발지·목적지 기반 후보 1~3개 도출, 권장 출발시각·근거 계산, target_arrival_at = arrival_deadline - arrival_preference_minutes 반영
- [X] T040 [US1] `backend/app/services/calculation_service.py`에 해석→계획 흐름 조정 로직 추가: 확인 조건 충족 전 plan 요청 차단 (US1 특유 검증). 일반 상태 변경 검증(conversation 유효성·입력·Idempotency-Key·revision 확인)은 T063 [US4]에 위임
- [X] T041 [US1] `backend/tests/unit/test_plan_service.py`에 계획 서비스 단위 테스트 생성: 정상 케이스, 출발지 미확정 케이스, Buffer 계산 검증
- [X] T042 [US1] `backend/tests/integration/test_journeys_e2e.py`에 interpret→plan 종단 간 테스트 보완: 실제 Mock 흐름 검증

**Checkpoint**: User Story 1 완전 기능 — 독립 검증 가능

---

## Phase 4: User Story 2 - 막차 귀가 경로 계산 (Priority: P2)

**Goal**: 사용자가 막차 귀가를 요청하면, 백엔드가 운행일·노선 지원 범위를 검증하고 가능한 경우 자정 이후 도착하는 막차 경로를 반환. 지원 데이터 없으면 LAST_JOURNEY_UNSUPPORTED, 지원 범위 내 경로 없으면 NO_FEASIBLE_JOURNEY로 구분

**Independent Test**: 운행일·노선 지원 범위 검증과 막차 경로 계산을 Mock과 실제 백엔드로 각각 검증 가능

### Tests for User Story 2 ⚠️

- [X] T043 [P] [US2] `backend/tests/contract/test_journeys_plan_last_journey.py`에 막차 계획 계약 테스트 생성: LAST_JOURNEY_UNSUPPORTED, NO_FEASIBLE_JOURNEY, 정상 막차 계획 검증
- [X] T044 [P] [US2] `backend/tests/unit/test_last_journey_service.py`에 막차 서비스 단위 테스트 생성: 운행일 검증, 다음 날 도착 날짜 구분 검증

### Implementation for User Story 2

- [X] T045 [US2] `backend/app/services/last_journey_service.py`에 막차 서비스 생성: 운행일·노선 지원 범위 검증, 막차 경로 후보 계산, 자정 경계·다음 날 도착 처리
- [X] T046 [US2] `backend/app/schemas/journeys.py`에 막차 관련 응답 필드 보강: 운행일 구분, 도착 날짜 분리 표현
- [X] T047 [US2] `backend/app/services/plan_service.py`에 막차 계획 로직 통합: 일반 계획과 막차 계획 분기
- [X] T048 [US2] `backend/app/api/journeys.py`에 막차 계획 요청 처리 보완: 요청 파라미터로 막차 여부 식별
- [X] T049 [US2] `backend/tests/integration/test_last_journey_e2e.py`에 막차 종단 간 테스트 생성

**Checkpoint**: User Story 1 + 2 모두 독립적으로 동작

---

## Phase 5: User Story 3 - 사용자 요청 재탐색 (Priority: P2)

**Goal**: 사용자가 놓침·변경 후 재탐색을 요청하면, 백엔드가 현재 서버 시각 기준으로 새 경로를 계산하고 이전 선택 대비 시각 변화를 반환. 재탐색 실패·취소는 이전 선택을 삭제하지 않으며, 이전 경로가 여전히 유효하다는 보장으로 표시하지 않음

**Independent Test**: 재탐색 요청 → 새 계획 → 이전 선택 대비 시각 변화 반환을 Mock과 실제 백엔드로 각각 검증 가능

### Tests for User Story 3 ⚠️

- [X] T050 [P] [US3] `backend/tests/contract/test_journeys_replan.py`에 재탐색 계약 테스트 생성: 새 계획·비교 응답 검증, 이전 선택 유지 검증
- [X] T051 [P] [US3] `backend/tests/unit/test_replan_service.py`에 재탐색 서비스 단위 테스트 생성: arrival_change_minutes 계산 검증, 이전 선택 삭제 방지 검증

### Implementation for User Story 3

- [X] T052 [US3] `backend/app/services/replan_service.py`에 재탐색 서비스 생성: 현재 서버 시각 기준 새 경로 계산, 이전 선택 비교 (arrival_change_minutes, leave_change_minutes), 이전 선택 유지 보장
- [X] T053 [US3] `backend/app/api/journeys.py`에 POST /api/v1/journeys/replan 라우터 구현: 요청 검증 (trip, previous_plan, current_origin_place_id, reason, user_confirmed), 재탐색 서비스 호출, 비교 응답 반환
- [X] T054 [US3] `backend/app/services/calculation_service.py`에 재탐색 흐름 조정 로직 추가: 재탐색 실패·취소 시 이전 선택 삭제 금지, 자동 교체 금지
- [X] T055 [US3] `backend/app/schemas/journeys.py`에 replan 요청 스키마 최종 완성: reason 열거형 (missed_connection, route_changed, manual), user_confirmed 필드
- [X] T056 [US3] `backend/tests/integration/test_replan_e2e.py`에 재탐색 종단 간 테스트 생성

**Checkpoint**: User Story 1 + 2 + 3 모두 독립적으로 동작

---

## Phase 6: User Story 4 - 대화 상태 저장·검증·전이 (Priority: P3)

**Goal**: 백엔드가 대화 상태를 conversation_id로 식별해 저장하고, 상태 변경 요청 시 revision을 증가시킴. 없거나 만료된 conversation은 410 CONVERSATION_EXPIRED로 처리, 이전 revision으로 상태 변경 시도 시 409 CONVERSATION_VERSION_CONFLICT로 처리. Idempotency-Key를 통해 같은 요청의 중복 적용 방지

**Independent Test**: 대화 생성 → 상태 변경 → revision 증가 → 재시도 idempotency → 만료 처리 → tombstone 전환 → hard delete까지 흐름을 Mock과 실제 백엔드로 각각 검증 가능

### Tests for User Story 4 ⚠️

- [X] T057 [P] [US4] `backend/tests/contract/test_conversation_state.py`에 대화 상태 계약 테스트 생성: conversation 생성·조회·갱신·만료·tombstone·hard delete, Idempotency-Key 동일/다른 요청 처리, revision 충돌 처리
- [X] T058 [P] [US4] `backend/tests/integration/test_conversation_e2e.py`에 대화 상태 종단 간 테스트 생성: 정상 흐름 (plan 요청 → conversation 생성 → revision 증가 → 재요청 → 저장된 응답 반환 → 만료 → 410 → tombstone → hard delete → 404)
- [X] T059 [P] [US4] `backend/tests/unit/test_idempotency_service.py`에 Idempotency-Key 서비스 단위 테스트 생성: payload hash 계산, 같은 key·같은 payload → 저장된 응답 반환, 같은 key·다른 payload → 409, 누락·형식 오류 → 422
- [X] T060 [P] [US4] `backend/tests/unit/test_conversation_service.py`에 대화 상태 서비스 단위 테스트 생성: 만료 판단, tombstone 전환, hard delete, 후보만 만료 (CANDIDATE_SET_EXPIRED) 처리

### Implementation for User Story 4

- [X] T061 [US4] `backend/app/services/idempotency.py`에 Idempotency-Key 처리 완성: payload hash 계산 (HTTP method + 정규화된 path + conversation_id + expected revision + canonicalized body → SHA-256), 저장·조회, 같은 key·동일 payload → 최초 응답 반환, 같은 key·다른 payload → 409 IDEMPOTENCY_KEY_REUSED, 누락·형식 오류 → 422 VALIDATION_ERROR
- [X] T062 [US4] `backend/app/services/conversation_service.py`에 대화 상태 관리 완성: conversation 생성·조회·갱신·revision 증가, 만료 판단 (expires_at <= now → 410 CONVERSATION_EXPIRED), tombstone 전환 (payload 제거, conversation_id·마지막 revision·expired_at 보관), 24시간 후 hard delete → 404 CONVERSATION_NOT_FOUND, tombstone 충돌 멱등 처리 (조건부 UPDATE 또는 UNIQUE + ON CONFLICT DO NOTHING), 후보만 만료 (CANDIDATE_SET_EXPIRED) 처리
- [X] T063 [US4] `backend/app/services/calculation_service.py`에 대화 상태 검증 로직 통합: 모든 상태 변경 요청 시 conversation 유효성·입력·Idempotency-Key 기록·revision 확인 → provider 호출 (DB 트랜잭션 밖) → 성공 검증 → 짧은 DB 트랜잭션에서 만료·Idempotency-Key·revision 재확인 → domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자적 커밋
- [X] T064 [US4] `backend/app/services/provider_client.py`에 재시도 정책 완성: 최대 1회, 500ms 대기, 연결 실패·timeout·retryable=true 502/503/504에만 적용, 같은 Idempotency-Key·같은 body로 재시도, 4xx·409·410·검증 실패·invalid response는 재시도 안 함
- [X] T065 [US4] `backend/app/api/journeys.py`에 Idempotency-Key 헤더·대화 상태 연동 완성: 모든 상태 변경 요청 (plan, replan)에 Idempotency-Key 처리 적용
- [X] T066 [US4] `backend/app/services/service_factory.py`에 대화 상태 서비스 의존성 주입 완성
- [X] T067 [US4] `backend/app/db.py`에 SQLite 스키마 마이그레이션/초기화 함수 완성: Conversation, Plan 테이블 생성 (SQLAlchemy 모델 기반)
- [X] T068 [US4] `backend/tests/integration/test_conversation_e2e.py`에 전체 흐름 테스트 보완: provider 실패 시 상태 불변 검증 (domain 상태·revision·updated_at·TTL 유지), tombstone 전환·hard delete 전체 흐름 검증

**Checkpoint**: User Story 1~4 모두 독립적으로 동작. 백엔드 MVP 완전 기능.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 여러 사용자 스토리에 걸친 개선 사항

- [X] T069 [P] `backend/app/schemas/` 타입 힌트·정렬 일관성 점검 및 정리
- [X] T070 [P] `backend/app/api/` 라우터별 중복 코드 정리 (공통 검증·응답 생성 로직 추출)
- [X] T071 [P] `backend/app/services/` 제공자 클라이언트 재시도·오류 처리 일관성 점검
- [X] T072 [P] `backend/app/config.py` 환경 변수 검증 로직 추가 (시작 시 필수 설정 확인)
- [X] T073 [P] `backend/tests/` 단위 테스트 커버리지 보강 (핵심 경로: interpret, plan, replan, 대화 상태, Idempotency-Key)
- [X] T074 [P] `backend/tests/contract/` 계약 테스트 보강 (모든 엔드포인트, 모든 상태 코드 분기)
- [X] T075 [P] `backend/tests/integration/` 종단 간 테스트 보강 (전체 흐름: health → capabilities → places → interpret → plan → replan → 대화 상태)
- [X] T076 [P] `quickstart.md` 검증: curl 시나리오가 실제 백엔드에서 동작하는지 확인
- [X] T077 [P] `API_SPEC.md`와 `examples.json` 정합성 최종 확인 (문서 변경 시 함께 갱신)
- [X] T078 [P] `backend/Dockerfile` 점검: Python 환경, 의존성 설치, 서버 기동 명령 확인
- [X] T079 `backend/README.md`에 개발·테스트·배포 안내 작성/보완
- [X] T080 [P] 린터·포매터 일관성 점검: black, isort, ruff (설정이 있으면 실행)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 의존 없음 — 즉시 시작 가능
- **Foundational (Phase 2)**: Setup 완료에 의존 — 모든 사용자 스토리 차단
- **User Stories (Phase 3~6)**: 모두 Foundational 완료에 의존
  - 사용자 스토리 간에는 독립적일 수 있음 (병렬 실행 가능)
  - 또는 우선순위 순서로 순차 진행 (P1 → P2 → P3)
- **Polish (Phase 7)**: 원하는 모든 사용자 스토리 완료에 의존

### User Story Dependencies

- **User Story 1 (P1)**: Foundational (Phase 2) 후 시작 가능 — 다른 스토리에 의존 없음
- **User Story 2 (P2)**: Foundational (Phase 2) 후 시작 가능 — US1과 통합될 수 있으나 독립 검증 가능해야 함
- **User Story 3 (P2)**: Foundational (Phase 2) 후 시작 가능 — US1/US2와 통합될 수 있으나 독립 검증 가능해야 함
- **User Story 4 (P3)**: Foundational (Phase 2) 후 시작 가능 — 모든 상태 변경 요청 (US1~US3의 plan/replan)에 Idempotency-Key·대화 상태가 적용되므로 통합 필요. 단, 대화 상태 서비스는 독립적으로 구현·테스트 가능

### Within Each User Story

- 테스트 (포함 시) → 구현 전에 작성, FAIL 확인
- 모델 → 서비스 → 엔드포인트 순서
- 핵심 구현 → 통합
- 스토리 완료 후 다음 우선순위로 이동

### Parallel Opportunities

- Setup 페이즈의 [P] 태스크들은 모두 병렬 실행 가능
- Foundational 페이즈의 [P] 태스크들은 모두 병렬 실행 가능 (Phase 2 내)
- Foundational 완료 후: 모든 사용자 스토리 병렬 시작 가능 (팀 역량 허용 시)
- 각 사용자 스토리 내 [P] 테스트들은 병렬 실행 가능
- 각 사용자 스토리 내 [P] 모델들은 병렬 실행 가능
- 다른 사용자 스토리는 다른 팀원이 병렬 작업 가능

---

## Parallel Example: User Story 1

```bash
# User Story 1의 모든 테스트를 함께 실행 (테스트 요청 시):
테스트: "contract/test_journeys_plan.py"
테스트: "integration/test_journeys_plan_e2e.py"
테스트: "unit/test_time_calculation.py"

# User Story 1의 모든 모델을 함께 생성:
모델: "schemas/mobility.py"
모델: "schemas/journeys.py"
```

---

## Parallel Example: User Story 4

```bash
# User Story 4의 모든 테스트를 함께 실행:
테스트: "contract/test_conversation_state.py"
테스트: "integration/test_conversation_e2e.py"
테스트: "unit/test_idempotency_service.py"
테스트: "unit/test_conversation_service.py"

# User Story 4의 독립 구현 가능한 컴포넌트:
서비스: "services/idempotency.py"
서비스: "services/conversation_service.py"
모델: "models/conversation.py"
모델: "models/plan.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup 완료
2. Phase 2: Foundational 완료 (**CRITICAL — 모든 스토리 차단**)
3. Phase 3: User Story 1 완료
4. **STOP and VALIDATE**: User Story 1 독립 검증
5. 배포/시연 가능할 경우 진행

### Incremental Delivery

1. Setup + Foundational → 기초 준비
2. User Story 1 → 독립 검증 → 배포/시연 (MVP!)
3. User Story 2 → 독립 검증 → 배포/시연
4. User Story 3 → 독립 검증 → 배포/시연
5. User Story 4 → 독립 검증 → 배포/시연 (백엔드 MVP 완성)
6. 각 스토리는 이전 스토리를 깨지 않고 가치 추가

### Parallel Team Strategy

여러 개발자와 함께:

1. 팀이 Setup + Foundational 함께 완료
2. Foundational 완료 후:
   - 개발자 A: User Story 1
   - 개발자 B: User Story 2
   - 개발자 C: User Story 3
   - 개발자 D: User Story 4 (대화 상태·Idempotency-Key)
3. 스토리 완료 후 독립 통합

---

## Notes

- `[P]` 태스크 = 다른 파일, 의존 없음 → 병렬 가능
- `[Story]` 레이블 = 특정 사용자 스토리에 태스크 매핑 (추적성)
- 각 사용자 스토리는 독립적으로 완료·검증 가능해야 함
- 검증 전에 테스트가 FAIL하는지 확인
- 태스크 또는 논리적 그룹마다 커밋
- 언제든 체크포인트에서 멈춰 스토리 독립 검증
- 피할 것: 모호한 태스크, 같은 파일 충돌, 독립성을 깨는 크로스-스토리 의존

---

## Context & References

- **Spec**: `specs/002-backend-mvp-implementation/spec.md`
- **Plan**: `specs/002-backend-mvp-implementation/plan.md`
- **Data Model**: `specs/002-backend-mvp-implementation/data-model.md`
- **API Contract**: `specs/002-backend-mvp-implementation/contracts/api-contract.md`
- **Research**: `specs/002-backend-mvp-implementation/research.md`
- **Quickstart**: `specs/002-backend-mvp-implementation/quickstart.md`
- **API Spec**: `API_SPEC.md`
- **Examples**: `Docs/api/examples.json`
- **Backend Handoff**: `Docs/BACKEND_HANDOFF.md`
- **Backend Target Directory**: `backend/`
