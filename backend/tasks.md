# Project Jigeum Service - Phase 3: User Story 1 태스크

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

### Implementation for User Story 4 (Phase 6) 🎯 P3

**Goal**: 백엔드가 대화 상태를 conversation_id로 식별해 저장하고, 상태 변경 요청 시 revision을 증가시킴. 없거나 만료된 conversation은 410 CONVERSATION_EXPIRED로 처리, 이전 revision으로 상태 변경 시도 시 409 CONVERSATION_VERSION_CONFLICT로 처리. Idempotency-Key를 통해 같은 요청의 중복 적용 방지

**Independent Test**: 대화 생성 → 상태 변경 → revision 증가 → 재시도 idempotency → 만료 처리 → tombstone 전환 → hard delete까지 흐름을 Mock과 실제 백엔드로 각각 검증 가능

- [X] T057 [P] [US4] `backend/app/models/conversation.py`에 Conversation 모델 보완: conversation_id (PK), revision, expires_at, confirmed_conditions, candidate_set, active_selected_plan, updated_at, created_at, 기타 메타데이터
- [X] T058 [P] [US4] `backend/app/models/idempotency.py`에 IdempotencyRecord 모델 생성: id (PK), conversation_id (FK), idempotency_key, method, path, payload_hash, expected_revision, created_at, response_data, UNIQUE 제약
- [X] T059 [P] [US4] `backend/app/services/conversation_service.py`에 conversation 상태 전이 로직 구현: 생성 → 조건 확인 완료 → 후보 도출 완료 → 계획 선택 → 만료/tombstone
- [X] T060 [P] [US4] `backend/app/services/conversation_service.py`에 tombstone 처리 구현: expires_at <= now 시 payload 제거, conversation_id + 마지막 revision + expired_at만 보관. 24시간 후 hard delete
- [X] T061 [P] [US4] `backend/app/services/idempotency_service.py`에 Idempotency-Key 처리 로직 구현: conversation_id + idempotency_key UNIQUE 제약, payload hash 계산 (HTTP method, 정규화된 path, conversation_id, expected revision, canonicalized body → SHA-256), 저장·조회
- [X] T062 [P] [US4] `backend/app/services/conversation_service.py`에 대화 상태 갱신 시 revision 증가 로직 구현
- [X] T063 [P] [US4] `backend/app/services/calculation_service.py`에 일반 상태 변경 검증 로직 구현: conversation 유효성 확인, 입력 검증, Idempotency-Key 기록·확인, revision 확인. US1 특유 검증은 T040에 위임
- [X] T064 [P] [US4] `backend/app/services/provider_client.py`에 재시도 정책 완성: 최대 1회, 500ms 대기, 연결 실패·timeout·retryable=true 502/503/504에만 적용, 같은 Idempotency-Key·같은 body로 재시도, 4xx·409·410·검증 실패·invalid response는 재시도 안 함
- [X] T065 [P] [US4] `backend/app/api/journeys.py`에 replan 라우터 보완: conversation_id, expected_revision, Idempotency-Key 처리. 응답 헤더에 Idempotency-Key 반환 (SC-013), Envelope에 미포함 (SC-014)
- [X] T066 [P] [US4] `backend/app/api/mobility.py`에 interpret 응답에 conversation_id, revision, expires_at 포함. 응답 헤더에 Idempotency-Key 반환 (SC-013), Envelope에 미포함 (SC-014)
- [X] T067 [P] [US4] `backend/tests/contract/test_conversations.py`에 대화 상태 계약 테스트 생성: 생성, 갱신, 만료, tombstone, hard delete, Idempotency-Key 처리, revision 충돌, candidate set 만료 (35개 테스트)
- [X] T068 [P] [US4] `backend/tests/integration/test_conversations_e2e.py`에 대화 상태 통합 테스트 생성: 정상 흐름, provider 실패 시 상태 불변, tombstone·hard delete 전체 흐름, T040/T063 통합 검증, payload hash 범위 검증 (26개 테스트)



# Project Jigeum Service - Phase 7: 검증 및 통합 테스트

## Phase 7: Polish & Cross-Cutting Concerns

**Goal**: 사용자 스토리 완료 후 최종 검증·정리. 모든 [P] 태스크는 병렬 실행 가능.

### Verification & Integration Tests

- [X] T069 [P] `backend/app/schemas/` 타입 힌트·정렬 일관성 점검 및 정리. 모든 파일이 일관된 스타일인지 확인.
- [X] T070 [P] `backend/app/api/` 라우터별 중복 코드 정리: 공통 검증·응답 생성 로직 추출 여부 점검. 이미 responses.py, errors.py 등에 있으면 Pass.
- [X] T071 [P] `backend/app/services/` 제공자 클라이언트 재시도·오류 처리 일관성 점검. provider_client.py 확인 - max_retries=1, 500ms, 502/503/504/연결실패/타임아웃만 재시도, 4xx/409/410/검증실패는 재시도 안 함.
- [X] T072 [P] `backend/app/config.py` 환경 변수 검증 로직 추가: 시작 시 필수 설정 확인.
- [X] T073 [P] `backend/tests/` 단위 테스트 커버리지 점검: 핵심 경로(interpret, plan, replan, 대화 상태, Idempotency-Key). tests/unit/에 6개 파일 존재.
- [X] T074 [P] `backend/tests/contract/` 계약 테스트 점검: 모든 엔드포인트, 모든 상태 코드 분기. tests/contract/에 7개 파일 존재.
- [X] T075 [P] `backend/tests/integration/` 종단 간 테스트 점검: 전체 흐름(health → capabilities → places → interpret → plan → replan → 대화 상태). tests/integration/에 7개 파일 존재.
- [X] T076 [P] `quickstart.md` 검증: curl 시나리오가 실제 백엔드에서 동작하는지 확인. curl 예시를 실제 API 필드명과 일치하도록 수정.
- [X] T077 [P] `API_SPEC.md`와 `examples.json` 정합성 최종 확인: 문서 변경 시 함께 갱신. examples.json의 last_journey_unsupported, no_feasible_journey 상태 코드를 200→422로 수정.
- [X] T078 [P] `backend/Dockerfile` 점검: Python 환경, 의존성 설치, 서버 기동 명령 확인. 실제 빌드 가능한 Dockerfile로 작성.
- [X] T079 `backend/README.md`에 개발·테스트·배포 안내 작성/보완.
- [X] T080 [P] 린터·포매터 일관성 점검: black, isort, ruff 설정 확인. pyproject.toml 생성.

