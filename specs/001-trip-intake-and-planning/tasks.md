# 작업 목록: 이동 입력·조건 확인·출발 시각 계산

> 2026-09-14: 서비스 제공 형태는 MCP로 확정됐다. Hermes는 개발·시연용 클라이언트다. 기존 REST 스키마는 유지하며, 제품 전제의 정정은 구현·테스트 완료를 의미하지 않는다.


**입력**: `/specs/001-trip-intake-and-planning/`의 설계 문서

**사전 준비**: plan.md(필수), spec.md(필수), research.md, data-model.md, contracts/

**테스트**: 이 작업 목록은 백엔드 계약·계산·도메인 로직·통합 검증을 우선한다. 테스트 항목은 요청된 범위만 포함하며, 지금은 빠른 시작 검증 시나리오를 계약/통합 검증으로 연결한다.

**구성**: 사용자 스토리 우선순위(P1→P2→P3) 순으로 작업 단계를 구성한다. 각 단계는 독립적으로 구현·검증할 수 있어야 한다.

---

## 1단계: 환경 설정(공유 인프라)

**목적**: 백엔드 프로젝트 구조와 기본 설정을 마련한다.

- [ ] T001 `backend/app/` 아래 `api/`, `schemas/`, `domain/`, `integrations/`, `agents/` 디렉토리 구조를 생성한다. (plan.md의 프로젝트 구조 참조)
- [ ] T002 `backend/`에 FastAPI 백엔드의 기본 진입점과 패키지 의존성을 설정한다.
- [ ] T003 [P] 공통 응답 envelope(`status`, `data`, `error`, `meta`)와 `meta.request_id`, `server_time`, `api_version`, `is_demo`를 반환하는 헬퍼를 구성한다.
- [ ] T004 [P] 시간대 Asia/Seoul만 허용하고, 오프셋 포함 ISO 8601을 다루는 공통 시간 유틸리티를 만든다.

**완료 기준**: 백엔드에서 `/health` 수준의 최소 응답이 가능하며, 공통 JSON envelope를 일관되게 사용할 수 있어야 한다.

---

## 2단계: 기반 작업(모든 스토리의 선행 조건)

**목적**: 공개 계약, 검증 규칙, 계산 도구의 기본 골격을 만든다. 이 단계가 끝나야 사용자 스토리 작업을 시작할 수 있다.

- [ ] T005 [P] `contracts/api-contract.md`에 정의된 공통 규칙과 오류 코드를 스키마·검증 규칙으로 문서화한다.
- [ ] T006 `schemas/`에 TripDraft, TripRequest, Plan, RouteOption, Leg, Buffer, Source, Warning, Point, Transit, Comparison 등 요청·응답 스키마를 계약 기준으로 작성한다.
- [ ] T007 `domain/`에 시간대·자정 경계·운행일/도착일 구분을 처리하는 시간 계산 헬퍼를 만든다. 모든 입력은 날짜와 시간대를 명시적으로 받는다.
- [ ] T008 `domain/`에 appointment 목표 도착시각 계산 규칙(`target_arrival_at = arrival_deadline − arrival_preference_minutes`)과 도착 상태 판정(on_time / preference_missed / late / not_applicable)을 코드로 구현한다.
- [ ] T009 `domain/`에 Buffer 중복 계산 방지 규칙을 구현한다. Buffer는 legs와 total_duration_minutes에 이미 반영되며, 연동 계층에서 다시 더하거나 권장 출발시각에서 다시 빼지 않는다.
- [ ] T010 `integrations/`에 장소·교통 어댑터 인터페이스와 Mock 어댑터를 먼저 만든다. 공개 계약 응답 구조는 어댑터 구현과 분리한다.
- [ ] T011 `backend/tests/` 아래 `contract/`, `integration/`, `unit/` 디렉토리를 생성하고 테스트 러너를 설정한다.

**완료 기준**: 계약서·스키마·계산 규칙·Mock 어댑터가 준비되어, 이후 스토리의 계약 검증과 통합 검증을 수행할 수 있어야 한다.

---

## 3단계: 사용자 스토리 1 — 약속 출발 시각 확인 (우선순위: P1, MVP)

**목표**: 자연어 입력 → 조건 확인 → 실제/모의 데이터 기반 권장 출발시각·근거 표시를 완성한다.

**독립적 테스트**: 명확한 도착 마감과 확정된 출발지·목적지가 있는 입력은 추가 질문 없이 요약 확인 후 계획 계산으로 진행할 수 있어야 한다. 정보가 부족하면 최대 3개 질문으로 응답해야 한다.

### 테스트(계약/통합 우선)

- [ ] T012 [P] [US1] `tests/contract/`에 `/mobility/interpret`의 `needs_confirmation`과 `ready_for_plan` 응답 검증 케이스를 작성한다. examples.json의 `interpret_needs_confirmation`, `interpret_ready`를 준용한다.
- [ ] T013 [P] [US1] `tests/contract/`에 `/journeys/plan`의 appointment 성공 응답 구조와 Buffer·sources·warnings 포함 여부를 검증하는 케이스를 작성한다. examples.json의 `plan_appointment`를 준용한다.
- [ ] T014 [P] [US1] `tests/integration/`에 자연어 입력 → 조건 확인 → 계획 계산 흐름을 Mock으로 재현하는 시나리오를 작성한다.

### 구현

- [ ] T015 [P] [US1] `schemas/`에 POST `/mobility/interpret` 요청·응답 스키마를 구현한다. `text`(1~2000자), `reference_time`, `timezone`(Asia/Seoul), `context`(TripDraft 또는 null)를 포함한다.
- [ ] T016 [P] [US1] `api/`에 `/mobility/interpret`를 구현한다. 응답이 `needs_confirmation`일 때 `questions`는 최대 3개, `missing_fields`는 최대 3개로 자르지 않는다.
- [ ] T017 [P] [US1] `api/`에 POST `/journeys/plan`을 구현한다. `user_confirmed=false`일 때는 USER_CONFIRMATION_REQUIRED로 처리한다.
- [ ] T018 [P] [US1] `domain/`에 appointment 대상 경로 계산 흐름을 만든다. `target_arrival_at` 계산, 후보 1~3개 구성, 권장 후보 ID 선택, 결과 시간 직렬화 규칙을 포함한다.
- [ ] T019 [P] [US1] `integrations/`에 Mock용 계획 응답 생성을 examples.json의 `plan_appointment`와 같은 구조로 연결한다.
- [ ] T020 [P] [US1] `api/` 또는 공통 헬퍼에 meta.is_demo 결정 로직을 넣는다. demo 출처가 하나라도 있으면 meta.is_demo=true로 표시한다.
- [ ] T021 [US1] `integrations/`에 실제 장소·교통 어댑터 연결 지점과 실패 시 처리(ROUTE_PROVIDER_UNAVAILABLE 등)를 정리한다. 실제 조회 실패를 Mock/Demo로 자동 대체하지 않는다.

**완료 기준**: Mock 기준으로 `/mobility/interpret` → `/journeys/plan` 흐름이도와 일치하고, 권장 출발시각·목표 도착시각·경로 구간·Buffer·출처·경고가 결과에 포함되며, demo 표시 규칙이 동작해야 한다.

---

## 4단계: 사용자 스토리 2 — 막차로 귀가 시각 확인 (우선순위: P2)

**목표**: 검증 가능한 범위에서 마지막 여정과 권장 출발시각을 구분한다.

**독립적 테스트**: 출발지·목적지·운행일 입력 → 막차 가능 여부 확인 → 마지막 여정 시각과 권장 출발 시각 표시 흐름이 동작해야 한다. 지원 불가 시 `LAST_JOURNEY_UNSUPPORTED`, 지원 범위에서 경로가 없으면 `NO_FEASIBLE_JOURNEY`로 구분해야 한다.

### 테스트

- [ ] T022 [P] [US2] `tests/contract/`에 `last_journey` 관련 응답 케이스(`plan_last_journey`, `last_journey_unsupported`, `no_feasible_journey`)를 검증한다.
- [ ] T023 [P] [US2] `tests/integration/`에 막차 조건에서 hard_leave_at과 권장 출발시각이 구분되는지 확인하는 시나리오를 작성한다.

### 구현

- [ ] T024 [P] [US2] `schemas/`와 `api/`에 `kind=last_journey`로 `/journeys/plan`을 처리할 수 있도록 TripRequest 검증 규칙을 확장한다. `service_date` 필수, `arrival_deadline` null, `arrival_preference_minutes=0`을 강제한다.
- [ ] T025 [P] [US2] `domain/`에 막차 전용 계산 규칙을 넣는다. 하드 데드라인과 권장 출발시각을 구분하고, 연결 가능한 마지막 여정 판별 로직을 포함한다.
- [ ] T026 [US2] `integrations/`에 막차 시간대 데이터 조회 어댑터 지점을 정리한다. 지원 범위 밖이면 `LAST_JOURNEY_UNSUPPORTED`, 지원 범위 내 경로가 없으면 `NO_FEASIBLE_JOURNEY`로 응답한다.
- [ ] T027 [US2] `api/`에 `capabilities.last_journey` 관련 필드(`available`, `scope_note`, `service_date_from`, `service_date_to`)를 반환 구조로 반영한다.

**완료 기준**: 막차 요청이 지원 범위·데이터 유무에 따라 올바르게 분기되고, 임의 막차 시각을 생성하지 않아야 한다.

---

## 5단계: 사용자 스토리 3 — 계획이 깨졌을 때 재탐색 (우선순위: P2)

**목표**: 사용자 요청 재탐색 → 새 경로 계산 → 이전 계획 비교 → 사용자 선택 후 적용을 구현한다.

**독립적 테스트**: 기존 계획 존재 → 재탐색 요청 → 새 후보 계산 → 이전 계획과 비교 표시 → 사용자 선택으로 적용 여부 결정 흐름이 동작해야 한다. 사용자가 선택 전에는 기존 계획을 교체하지 않아야 하며, 실패·취소된 재탐색이 기존 기록을 삭제하지 않아야 한다.

### 테스트

- [ ] T028 [P] [US3] `tests/contract/`에 `/journeys/replan` 응답 구조(plan + comparison)를 검증하는 케이스를 작성한다. examples.json의 `replan_late`를 준용한다.
- [ ] T029 [P] [US3] `tests/integration/`에 재탐색 후 이전 기록 유지 여부와 비교 변화량 부호 검증을 포함한 시나리오를 작성한다.

### 구현

- [ ] T030 [P] [US3] `schemas/`에 `/journeys/replan` 요청·응답 스키마를 구현한다. `previous_plan(PlanSummary)`, `current_origin_place_id`, `reason`, `user_confirmed=true`를 포함한다.
- [ ] T031 [P] [US3] `api/`에 `/journeys/replan`을 구현한다. 서버는 이전 plan_id로 DB 조회하지 않고, trip과 current_origin_place_id를 다시 검증해 현재 서버 시각 기준으로 새 경로를 계산한다.
- [ ] T032 [P] [US3] `domain/`에 비교 계산 로직을 구현한다. `arrival_change_minutes`, `leave_change_minutes`, `summary`를 계산하고, 양수/음수 의미를 계약 기준으로 맞춘다.
- [ ] T033 [US3] `api/` 또는 공통 응답 처리에서 재탐색 결과를 사용자 선택 전까지 기존 계획에 적용하지 않는 원칙을 클라이언트가 구분할 수 있도록 구조를 유지한다.
- [ ] T034 [US3] `integrations/`에 재탐색용 경로 재조회 어댑터 지점을 정리한다. 실패·취소 시에도 기존 선택 계획을 삭제하지 않는 원칙을 공유한다.

**완료 기준**: 재탐색 결과가 이전과 비교를 제공하고, 사용자 선택 전 자동 교체가 발생하지 않으며, 실패/취소가 기존 기록을 지우지 않아야 한다.

---

## 6단계: 이전 US4 작업 — 현재 비적용

2026-09-14 MCP 서비스 확정에 따라 T035~T040은 현재 실행 작업에서 제외한다. 완료한 것으로 체크하지 않으며 ID는 이력 추적용으로 보존한다.

- T035: 이전 출발/도착 상태 전이 테스트 — 비적용.
- T036: 이전 종료 상태의 자동 알림 테스트 — 비적용.
- T037: 이전 Local Journey 영구 저장 모델 — 비적용.
- T038: 이전 저장·진행 상태 변경 흐름 — 비적용.
- T039: 이전 출발/도착 상태 전이 구현 — 비적용.
- T040: 이전 로컬 알림 갱신·취소 — 비적용.

현재 대화의 조건 확인·후보 선택·재탐색 문맥은 유지한다. MCP 스키마·오류 매핑·문맥 수명·실제 사용자 확인 연결의 상세 작업은 공동 합의 후 명세화한다.

## 7단계: 사용자 스토리 5 — 계산 근거·데이터 출처 확인 (우선순위: P3)

**목표**: MCP 결과·Hermes 설명으로 경로 구간, 예상 도착 시각, Safety Buffer 근거, 데이터 출처와 기준 시각을 확인할 수 있게 한다.

**독립적 테스트**: Plan 응답의 legs, buffer, sources, warnings가 MCP 도구 응답에 유지되고 Hermes에 정확하게 전달되는지 검증한다.

### 테스트

- [ ] T041 [P] [US5] `tests/contract/`에 Plan 응답의 legs, buffer.items, sources, warnings 필드가 계약대로 포함되는지 검증하는 케이스를 작성한다.
- [ ] T042 [P] [US5] `tests/integration/`에 demo 출처 포함 시 meta.is_demo=true와 DEMO_DATA 경고가 함께 표시되는지 확인하는 시나리오를 작성한다.

### 구현

- [ ] T043 [US5] `api/` 또는 응답 직렬화 계층에 legs, buffer, sources, warnings, calculation_method, navigation_url이 누락 없이 포함되도록 정리한다.
- [ ] T044 [US5] `integrations/`의 Source 기록 규칙을 확정한다. provider, basis, retrieved_at, service_date를 남기고, demo 출처가 하나라도 있으면 meta.is_demo=true가 되도록 연결한다.
- [ ] T045 [US5] 경고 코드(`DEMO_DATA`, `SCHEDULE_ONLY`, `DATA_REFRESH_RECOMMENDED` 등)와 message 표시 규칙을 클라이언트가 코드 비교 없이 처리할 수 있도록 유지한다.

**완료 기준**: 사용자가 계산 근거와 데이터 한계를 함께 볼 수 있고, demo/실제 구분 표시가 일관되게 동작해야 한다.

---

## 마지막 단계: 정리 및 교차 관심사

**목적**: 여러 스토리에 걸친 품질, 문서, 검증 준비를 마무리한다.

- [ ] T046 `quickstart.md`의 핵심 흐름 5개와 예외 사례를 실제/Mock 실행 체크리스트로 정리한다.
- [ ] T047 `research.md`에 남은 미확정 항목(Buffer 실제 수치·버전, 막차 지원 노선·운행일 범위, AI 호출 설정, Base URL, 제공처별 한도·최신성)을 후속 확정 대상으로 명시한다.
- [ ] T048 Mock과 실제 서버의 JSON 구조가 동일한지, 실제 조회 실패가 Mock/Demo로 자동 대체되지 않는지 검증 점검을 추가한다.
- [ ] T049 `contracts/api-contract.md`와 `Docs/api/examples.json`을 함께 갱신해야 하는 변경 사유를 작업 노트로서 남긴다.
- [ ] T050 MCP 제공 형태와 확인·문맥·선택 상태의 소유권을 관련 문서에 맞추고, 영구 이동 이력·회원가입·자동 알림이 현재 필수 범위가 아님을 확인한다.

---

## 의존성 및 실행 순서

### 단계 의존성

- 1단계(환경 설정): 의존성 없음.
- 2단계(기반 작업): 1단계 완료 후 시작. 모든 사용자 스토리가 이 단계에 의존.
- 3~7단계(사용자 스토리): 2단계 완료 후 시작 가능. 서로 다른 파일은 병렬로 진행할 수 있지만, 같은 파일 충돌은 피한다.
- 마지막 단계(정리): 원하는 스토리가 완료된 뒤 진행.

### 사용자 스토리 의존성

- US1(P1): 기반 작업 완료 후 시작. 다른 스토리 의존성 없음.
- US2(P2): 기반 작업 완료 후 시작. US1과 독립적으로 검증 가능해야 함.
- US3(P2): 기반 작업 완료 후 시작. US1/US2와 독립적으로 검증 가능해야 함.
- US4: 비적용. T035~T040은 현재 의존성·완료 기준에서 제외한다.
- US5(P3): 기반 작업 완료 후 시작. 결과 표시는 계산 결과 구조에 의존.

### 병렬 기회

- 각 단계 내 [P] 표시 작업은 서로 다른 파일/모듈이면 병렬로 진행 가능.
- US1/US2/US3의 계약 테스트와 통합 테스트는 각 스토리 구현이 시작되기 전에도 Mock 기준으로 준비할 수 있다.
- Mock 어댑터, 스키마, 도메인 계산 규칙은 초기 단계에서 병렬로 준비 가능.

---

## 병렬 예시: 사용자 스토리 1

```bash
# 병렬로 동시 진행 가능한 예시
Task: "T012 [P] [US1] interpret 응답 계약 테스트 작성"
Task: "T013 [P] [US1] plan 응답 계약 테스트 작성"
Task: "T015 [P] [US1] interpret 요청·응답 스키마 작성"
Task: "T016 [P] [US1] /mobility/interpret 구현"
Task: "T017 [P] [US1] /journeys/plan 구현"
```

---

## 구현 전략

### MVP 우선(US1만)

1. 1단계 환경 설정
2. 2단계 기반 작업
3. 3단계 US1 전체(계약 테스트 → 스키마 → API → 도메인 계산 → Mock 연결)
4. **중단 후 검증**: Mock 기준으로 자연어 입력 → 조건 확인 → 출발시각·근거 표시 흐름을 확인한다.

### 점진적 전달

1. 1~2단계 완료 후 기반 준비
2. US1 추가 → 독립 검증 → 데모 가능
3. US2 추가 → 독립 검증
4. US3 추가 → 독립 검증
5. US5 추가 → 독립 검증. 비적용 US4는 실행하지 않는다.
6. 각 스토리는 이전 스토리를 깨지 않도록 독립적으로 검증한다.

### 병렬 팀 전략

- 두 개발자 중 한 명은 백엔드 계약·계산·통합 검증에 집중하고, 다른 한 명은 클라이언트 흐름을 Mock으로 먼저 맞추는 방식이 가능하다.
- 계약·스키마·도메인 계산 규칙은 초반에 함께 고정한다.

---

## 참고

- 작업 항목의 파일 경로는 plan.md의 `backend/` 구조를 기준으로 작성했다.
- 계약 상세는 `contracts/api-contract.md`, 엔티티·검증 규칙은 `data-model.md`, 미확정 결정 내역은 `research.md`, 검증 시나리오는 `quickstart.md`를 참고한다.
- 제공 형태는 MCP로 확정됐다. 본인은 MCP·Hermes 연결을, 친구는 백엔드·계산·데이터 연동을 맡는다. 도구 5개와 확인·선택 흐름은 IDEA.md를 따른다.
