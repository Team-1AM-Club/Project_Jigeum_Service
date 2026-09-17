---
description: "003 MCP HTTP 계약 정합화의 검토용 구현·검증 작업 목록"
---

# 작업 목록: MCP HTTP 계약 정합화와 실제 백엔드 통합

**대상**: `003-mcp-http-contract-alignment` · 작성일: 2026-09-16

**입력**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [HTTP 계약](contracts/http-contract.md), [MCP 계약](contracts/mcp-contract.md), [가상 예제](contracts/examples.json), [quickstart.md](quickstart.md).

**상태**: 검토용 작업 목록. 작업 목록 생성은 공동 API 합의나 구현 승인을 대신하지 않는다. 아래 체크박스는 모두 미완료이며 코드 구현·pytest·Hermes·교통 제공처 실행 결과를 뜻하지 않는다. 공통 계약 변경은 T001의 양측 합의 후 T002에서 진행한다.

**수정안 반영**: C1·C2·U1·G1을 003 문서에 동기화했다. 기존 T001~T061 ID를 보존하고 T062~T064를 추가했다. 추가 ID는 기존 참조 보존을 위한 번호이며, 아래 배치와 명시된 선행 조건이 실행 순서다. MCP 진단 필드와 REQUEST_TIMEOUT은 T001 미확정 권장안이다.

**테스트 근거**: 명세의 Acceptance Scenarios, SC-001~008과 계획의 V01~V12가 계약·상태·동시성·통합 검증을 요구하므로 테스트 작업을 포함한다. 각 단계에서 필요한 테스트를 먼저 작성해 현재 동작과의 차이를 확인하고 구현 뒤 같은 검증을 통과시킨다. 문서 생성 자체에는 애플리케이션 테스트를 실행하지 않는다.

## 형식·경로·담당

- 형식은 `- [ ] T번호 [P 선택] [US번호 해당 시] 설명 및 파일 경로`다. `[P]`는 해당 단계의 선행 조건 충족 후 서로 다른 파일에서 병행할 수 있는 작업만 뜻한다.
- 저장소 상대 경로의 기준은 `C:/Users/romai/Desktop/Develop/Project/Project_Jigeum_Service`다. 새 파일로 명시한 경로는 구현 시 만들 대상이며 현재 존재·구현을 주장하지 않는다.
- **백엔드 담당**: `backend/`의 상태·API·계산 연결. **MCP 담당**: 별도 실제 MCP 저장소의 도구·HTTP·Hermes 연결. **공동**: 계약 합의·fixture·종단 간 인수.
- MCP 소스 경로·진입점은 확인되지 않았다. T003에서 담당자가 실제 경로를 제공하고 이 문서의 MCP 대상 표와 관련 작업을 실제 파일 경로로 치환해야 한다. 그 전 MCP 구현 작업은 실행 보류다. 이 저장소에 임의의 MCP 소스 디렉터리를 만들지 않는다.
- MCP 작업에 적힌 `quickstart.md` 또는 `Docs/mcp-http-integration.md`는 로컬 인수 기록 경로다. 외부 구현 위치를 대신하는 것으로 해석하지 않는다. T003의 경로 확정 후 지정된 MCP 담당자가 구현하고 실행 증거를 연결한다.
- 기존 변경을 보존한다. 파일을 공유하는 004 제공처 작업과 먼저 조율하며, 004 구현이나 원격 배포를 이 목록에 포함하지 않는다. 새 의존성·인프라·영구 이력·독립 클라이언트를 추가하지 않는다.
- 후속 Spec Kit 실행은 003 경로를 명시한다. `.specify/feature.json`의 다른 기능 설정을 덮어쓰지 않는다. 커밋·푸시·배포는 이 목록의 자동 실행 단계가 아니다.

### T003에서 확정할 MCP 대상 표

| 대상 이름 | 확인할 실제 파일 | 현재 상태 |
|---|---|---|
| MCP 도구 | 5개 도구 등록·입력 schema·action dispatch | 담당자 경로 제공 대기 |
| MCP HTTP | URL/query 직렬화·HTTP client·응답 검증·재시도 | 담당자 경로 제공 대기 |
| MCP 상태 | 대화 binding·mode 고정·직렬 처리·보류 요청 | 담당자 경로 제공 대기 |
| MCP 승인 | elicitation capability·조건 확인·후보 선택 | 담당자 경로 제공 대기 |
| MCP demo | 기존 fixture·동일 상태 전이 adapter | 담당자 경로 제공 대기 |
| MCP 검증 | 기존 HTTP/stdio 테스트·가짜 호스트·실행 설정 예제 | 담당자 경로 제공 대기 |

T003의 완료 기준은 각 행에 실제 저장소 절대 경로, 파일 경로, 진입점·검증 명령 및 버전이 있고, 아래 MCP 작업마다 해당 파일이 명시된 상태다. 파일 경로를 모르는 상태에서 구현 작업을 완료 처리하지 않는다.

## Phase 1: 준비와 공동 계약 게이트

**목적**: 합의할 계약, 실제 작업 위치와 환경을 고정한다. 문서 검토는 지금 가능하며 T002의 공통 문서 개정과 Phase 2 구현은 실제 합의 이후다.

- [ ] T001 [공동] `specs/003-mcp-http-contract-alignment/contract-review.md`에 HTTP/MCP 계약·상태 모델·20개 HTTP fixture와 별도 장애 시나리오의 양측 검토 결과·합의 버전을 기록한다. 확인·선택·revision·TTL·최초 응답 유실·재시도·로컬 신뢰 경계와 U1의 MCP `diagnostics.cause_code` 표현, G1의 `504 REQUEST_TIMEOUT / retryable=true` 도입 여부를 확정한다. `plan.md`의 II-b 개발 도구 조건 미충족 처리 근거도 확인하고 예외가 필요하면 범위·만료·명시적 승인 근거를 기록한다. 합의 또는 필수 조건 미충족 시 구현을 차단한다. 내부 예외와 외부 제출 적합성은 별개다.
- [ ] T002 [공동, T001 후] `API_SPEC.md`, `Docs/api/examples.json`, `IDEA.md`, `specs/002-backend-mvp-implementation/spec.md`, `specs/002-backend-mvp-implementation/plan.md`, `specs/002-backend-mvp-implementation/data-model.md`, `specs/002-backend-mvp-implementation/contracts/api-contract.md`, `Docs/mcp-http-integration.md`의 상충하는 상태 소유권·stateless·필드·경로·오류·재시도 설명을 합의 내용으로 동기화한다. 예제의 키는 headers로 옮기고 후보 만료는 select 거부로 정정한다. 002 작업 목록에 남은 충돌은 해당 담당자와 확인한다.
- [ ] T003 [MCP 담당] `specs/003-mcp-http-contract-alignment/quickstart.md`에 실제 MCP 저장소·진입점·SDK/Python 버전·테스트 명령을 기록하고, `specs/003-mcp-http-contract-alignment/tasks.md`의 MCP 대상 표 및 외부 구현 작업마다 실제 파일 경로를 확정한다. 연결 안내에 적힌 경로를 이 저장소의 소스로 가정하지 않는다.
- [ ] T004 [백엔드 담당] `specs/003-mcp-http-contract-alignment/quickstart.md`에 기존 DB·모델 등록·migration 방식과 테스트 실행 기준을 조사해 기록한다. `backend/app/db.py`, `backend/app/models/__init__.py`, `backend/app/services/idempotency.py`, `backend/app/services/idempotency_service.py`의 실제 사용 경로를 확인하고 데이터 보존 절차·단일 구현 경로를 정한다. T064의 health/capabilities/places/interpret/plan/replan timeout 처리·원자 확정·관련 테스트의 실제 파일 경로와 누락 경계를 기록한다. 삭제·새 migration 의존성이 필요하면 먼저 별도 결정을 받는다.
- [ ] T005 [MCP 담당, T003 후] `specs/003-mcp-http-contract-alignment/quickstart.md`에 설치 Hermes의 form elicitation, 대화별 stdio 프로세스, host timeout 500초 지원 및 실제 모델 식별자의 확인 결과를 기록한다. 미지원이면 해당 MCP 계산·선택 구현/인수의 차단 조건과 해결할 호환성 문제를 명시한다. 비밀 설정 원문을 수집하지 않는다.

**체크포인트**: T001~T002는 모든 새 계약 구현의 게이트다. T003~T005는 외부 MCP 구현·실행의 게이트이며, MCP 환경 미확인이 백엔드의 독립 계약 검증까지 막지는 않는다.

## Phase 2: 공통 상태·멱등성 기반

**목적**: US1에 필요한 최소 확인·선택·중복 방지까지 공통 기반으로 제공한다. US2·US3에서는 같은 구현을 재작성하지 않고 거부·경합·복구 경계를 완성한다.

**시작 조건**: 백엔드는 T001·T002·T004, MCP는 추가로 T003·T005 완료. 백엔드 기반 T006~T012가 준비되기 전 사용자 이야기의 서버 통합 구현을 시작하지 않는다.

- [ ] T006 [P] [백엔드 담당] 새 `backend/tests/unit/test_conversation_state.py`에 초안→확인→후보→선택, draft 소비, 변경 시 확인/후보 무효화와 선택 보존, 상태별 deadline 및 revision 증가 규칙 테스트를 작성한다.
- [ ] T007 [P] [백엔드 담당] 새 `backend/tests/unit/test_idempotency_service.py`에 canonical method/path/body/revision hash, 전역 키 충돌, 최초 요청 시각, 동일 성공 replay, 상태·응답 동시 commit/rollback 테스트를 작성한다.
- [ ] T008 [백엔드 담당] `backend/tests/conftest.py`에 검증 전용 SQLite·서버 시각·ID 생성기·provider spy fixture를 구성하고 새 `backend/tests/integration/test_state_storage.py`에 새 DB 초기화 및 기존 테스트 DB 데이터 보존 검증을 작성한다. 원본 DB를 덮어쓰지 않는다.
- [ ] T009 [백엔드 담당, T004·T006~T008 후] `backend/app/models/conversation.py`, `backend/app/models/idempotency.py`, `backend/app/models/__init__.py`, `backend/app/db.py`를 확장해 draft·확인·candidate_marker·선택 snapshot·단계별 만료·tombstone·전역 UNIQUE 키·최초 HTTP status/body를 하나의 등록된 모델 체계로 저장한다. T004에서 확정한 보존 가능한 migration/초기화 명령을 `specs/003-mcp-http-contract-alignment/quickstart.md`에 반영한다.
- [ ] T010 [백엔드 담당, T009 후] `backend/app/services/conversation_service.py`, `backend/app/services/idempotency_service.py`에 최초 대화 생성/초안/응답의 원자 저장과 기존 대화 CAS revision 갱신/응답의 원자 저장을 구현한다. provider 호출은 쓰기 트랜잭션 밖으로 분리하고 commit 직전 상태·만료를 재검증한다. `backend/app/services/idempotency.py`의 실제 호출처는 검증한 단일 경로에 연결하며 확인 없는 삭제는 하지 않는다.
- [ ] T011 [백엔드 담당, T010 후] `backend/app/services/conversation_service.py`에 초안 30분·확인 2시간·선택 ETA+2시간·전체 48시간 및 후보 provider 유효시각/기본 5분을 구현하고, `backend/app/main.py`에 시작·주기 정리의 생명주기를 연결한다. 요청 시에도 만료를 판정하고 GET/replay/실패는 수명·revision을 늘리지 않으며 tombstone/최소 키 매핑은 원래 만료 후 24시간까지만 보존한다.
- [ ] T012 [백엔드 담당, T010·T011 후] 새 `backend/app/schemas/conversations.py`, `backend/app/api/conversations.py`와 `backend/app/main.py`, `backend/app/api/responses.py`, `backend/app/schemas/errors.py`에 상태 GET·confirm·select를 연결한다. path/body 일치, 서버 hash·draft_revision·유효 evidence, candidate 소속/만료, 실제 상태 meta와 헤더 key 반향을 검증한다. 승인 재사용을 막고 confirm은 draft를 소비하며 select만 선택 snapshot을 바꾼다.
- [ ] T013 [MCP 담당, T003·T005·T012 후] 확정된 MCP 도구·상태·승인 파일에 5개 도구의 엄격한 action schema, 모델에게 숨긴 ID/revision/evidence/key, 대화별 binding·mode 고정·변경 직렬화와 직접 elicitation 응답 처리를 구현한다. `specs/003-mcp-http-contract-alignment/quickstart.md`에 fake-host 검증 결과를 기록하고 미지원·거절·취소·timeout에서는 confirm/select를 보내지 않음을 확인한다.
- [ ] T014 [공동, T006~T013 후] `backend/tests/unit/test_conversation_state.py`, `backend/tests/unit/test_idempotency_service.py`, `backend/tests/integration/test_state_storage.py` 및 T003에 기록한 MCP 기반 테스트를 실행해 결과를 `specs/003-mcp-http-contract-alignment/quickstart.md`에 연결한다. 합성 evidence 기반 REST 테스트와 실제 사람 승인 검증을 구분한다.

**체크포인트**: 공통 기반의 성공 변경은 상태와 응답이 함께 저장된다. provider 실패는 성공 변경으로 기록하지 않는다. 백엔드 단독 테스트는 MCP 미완료 시에도 실행할 수 있으나 전체 기반 완료는 T014 이후다.

## Phase 3: US1 — 같은 조건과 결과로 약속 계획 받기 (P1)

**목표**: 지원 범위→장소→해석→조건 확인→약속 후보→명시적 선택의 최소 흐름을 연결한다.

**독립 검증**: 재탐색·막차 없이 V01을 실행한다. 19:00 마감/10분 여유는 목표 18:50이며 질문은 부족 정보만 최대 3개, 후보는 1~3개다. 모의 provider와 실제 provider의 결과를 구분한다.

### 테스트

- [ ] T015 [P] [US1] 새 `backend/tests/contract/test_mobility_interpret.py`와 `backend/tests/contract/test_journeys_plan.py`에 text/context, draft/ready_for_plan/questions, nested trip, data.plan.options, 엄격한 필수/추가 필드 및 status/HTTP 조합 검증을 작성한다. 기존 평탄한 입력이 조용히 수용되지 않도록 한다.
- [ ] T016 [P] [US1] `backend/tests/integration/test_journeys_plan_e2e.py`에 장소 확정→해석→confirm→plan→select 시나리오와 부족 정보·미지원·경로 없음·provider 오류를 작성한다. 19:00/10분 여유, 상태 meta, 출처·기준시각을 검증한다.

### 구현·인수

- [ ] T017 [US1] `backend/app/schemas/mobility.py`, `backend/app/schemas/journeys.py`, `backend/app/schemas/common.py`를 합의된 공개 도메인/상태 필드와 연결한다. 최초 interpret의 ID/revision 생략·request_started_at 필수, 후속 ID/revision 쌍, 후보 1~3개와 엄격한 user_confirmed=true를 검증하고 기존 사용자 확인 기본 True를 제거한다.
- [ ] T018 [US1] `backend/app/services/interpret_service.py`, `backend/app/api/mobility.py`에서 text/context 및 명확한 장소·시각을 보존하고, 불완전 초안도 정상 저장되면 서버 발급 ID/revision과 needs_confirmation 응답을 원자 저장한다. 모델/provider 실패로 대화를 성공 생성하지 않는다.
- [ ] T019 [US1] `backend/app/services/plan_service.py`, `backend/app/api/journeys.py`에서 유효한 서버 확인과 일치하는 trip만 provider로 보내고 data.plan 및 candidate_set을 원자 저장한다. 후보 생성은 확인 deadline·이전 선택을 바꾸지 않으며 Buffer를 다시 더하지 않는다.
- [ ] T020 [US1] `backend/app/api/capabilities.py`, `backend/app/api/places.py`, `backend/app/api/responses.py`의 조회 결과를 합의된 query/envelope로 정렬한다. 상태와 무관한 조회에 대화 ID를 임의 생성하지 않고 입력 오류·업무상 unavailable·provider 장애를 구별한다.
- [ ] T021 [US1] 확정된 MCP HTTP·검증 파일에 `/api/v1` Base URL, 한글/공백/특수문자 query 인코딩, nested JSON 전송, MIME/schema/헤더 키/status 조합 검증을 구현하고 `Docs/mcp-http-integration.md`에 대응 사례를 기록한다. HTTP 연결만으로 is_demo를 바꾸거나 잘못된 응답을 성공으로 변환하지 않는다.
- [ ] T022 [US1] 확정된 MCP 도구·승인 파일에 interpret/state와 plan calculate/select를 연결하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 흐름 검증을 기록한다. 서버 조건 요약의 accept+approve=true만 confirm으로 전달하고 confirm 성공 revision으로 계산한다. 선택은 GET의 현재 후보 enum을 별도 elicitation으로 제시한다.
- [ ] T023 [US1] 확정된 MCP demo·검증 파일에서 기존 demo 데이터를 동일한 상태·승인·선택 인터페이스로 유지하고 `Docs/mcp-http-integration.md`에 demo/HTTP 모드 회귀 결과를 기록한다. 가짜 호스트 승인은 테스트로 표시하고 HTTP 실패의 demo fallback을 만들지 않는다.
- [ ] T024 [US1] 확정된 MCP 결과 설명·검증 파일에서 서버 필드만으로 질문·권장 출발·도착·여유·출처·다음 행동을 표시하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 19:00/10분 사례를 기록한다. 재계산·여유 중복 적용·미확정 장소 보충·성공 계획 조작을 금지한다.
- [ ] T025 [US1] T015~T024의 테스트와 V01을 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 약속 흐름 각 단계의 실제 요청/응답·명시적 선택·도구 5개 discovery 결과를 기록한다. 가상 ID를 실제 서버 ID로 바꾼 최초 body는 replay용으로 보존한다.

**체크포인트**: US1의 로컬 기능 증명이다. US2·US3의 경계 검증 및 실제 Hermes/실데이터 인수 전에는 전체 기능이나 실제 데이터 MVP 완료로 보고하지 않는다.

## Phase 4: US2 — 확인한 조건만 현재 대화에서 계산하기 (P1)

**목표**: 확인·대화·버전·수명에 대한 거부 조건을 완성한다.

**독립 검증**: 공통 기반과 약속 API에 상태 fixture를 넣고 V02·V03·V06·V10을 실행한다. US4/US5 없이 미확인·변경 후 과거 확인·다른 대화·stale revision·만료 요청의 잘못된 적용이 0건이어야 한다.

### 테스트

- [ ] T026 [P] [US2] `backend/tests/contract/test_conversations.py`에 path/body 불일치, 확인 누락/불일치, 다른 대화 후보·승인, interaction_id 재사용, 404/409/410/422와 오래된 revision 우선순위를 작성한다. 거부 시 provider 호출 0회 및 기존 선택 보존을 확인한다.
- [ ] T027 [P] [US2] `backend/tests/integration/test_conversations_e2e.py`에 독립 DB Session·barrier로 같은 revision 경쟁, provider 대기 중 조건 변경/만료, 늦은 결과 적용 거부를 작성한다. 한 세션의 순차 mock을 동시성 근거로 쓰지 않는다.

### 구현·인수

- [ ] T028 [US2] `backend/app/services/conversation_service.py`, `backend/app/api/conversations.py`에서 대화 생존→replay→revision→대상/수명/evidence 검증 순서를 공통 기반에 보강한다. 승인 시각의 과거 5분/미래 30초와 대상 결부·중복 사용을 검사하고 같은 성공 replay에는 승인 나이를 다시 적용하지 않는다.
- [ ] T029 [US2] `backend/app/api/mobility.py`, `backend/app/api/journeys.py`, `backend/app/services/plan_service.py`에서 확인 변경·만료·조건 불일치와 계산 도중 상태 변경을 모두 거부하도록 통합한다. 실패 시 상태·revision·updated_at·TTL을 보존한다.
- [ ] T030 [US2] 확정된 MCP 도구·승인·검증 파일에 모델의 ID/revision/confirmation/evidence/option 직접 주입, accept지만 approve=false, 미지원·decline·cancel·timeout 거부 검증을 추가하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 결과를 기록한다. 승인 대기 중 변경된 초안을 자동으로 새 승인 처리하지 않는다.
- [ ] T031 [US2] `backend/tests/unit/test_conversation_state.py`, `backend/app/services/conversation_service.py`에 각 TTL의 직전/동일/직후, confirm 후 draft=null, 후보 payload 정리 후 marker 보존, 선택 기록으로만 살아 있는 대화, tombstone 24시간 뒤 404를 검증·보완한다. GET/replay/실패와 정리가 수명·revision을 늘리지 않는지 확인한다.
- [ ] T032 [US2] 확정된 MCP 상태·검증 파일에서 두 Hermes 대화의 프로세스 분리, mode 혼용 거부, 동시 변경 직렬화와 재시작 시 과거 ID 자동 복원 금지를 검증하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 fake-host 결과를 기록한다. 실제 Hermes 확인은 확장 전 T062에서 수행한다.
- [ ] T033 [US2] T026~T032와 V02·V03·V06·V10의 상태 관련 사례를 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 잘못된 적용 0건 및 시간 경계의 관측 결과를 기록한다.

## Phase 5: US3 — 요청을 재전송해도 중복 적용하지 않기 (P1)

**목표**: 응답 유실·경합·취소를 포함한 재생과 제한적 자동 재시도를 검증한다.

**독립 검증**: 초기 interpret 및 약속 API를 대상으로 V04·V05·V06·V11 복구 사례를 실행한다. 상태 적용은 논리 요청당 1회, 허용 오류만 500ms 뒤 자동 추가 1회, 금지 오류의 추가 시도는 0회다.

### 테스트

- [ ] T034 [P] [US3] 새 `backend/tests/integration/test_idempotency_e2e.py`에 첫 성공 응답의 socket 유실, 동일 초기 키 동시 요청, 동일 키의 다른 body/path/revision, stale 성공 replay, commit 중 예외, 만료/매핑 정리 후 초기 요청을 작성한다. 독립 세션에서 대화·적용 횟수와 부분 저장 부재를 검사한다.
- [ ] T035 [P] [US3] 확정된 MCP HTTP·검증 파일에 connect error/timeout/유효 retryable 502·503·504와 4xx/업무상 unavailable/invalid JSON·schema·헤더 키·status 불일치 테스트를 작성하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 실행 명령을 기록한다. 서버 commit 후 최초 응답을 각각 파손시켜 자동 추가 시도 0회·즉시 OUTCOME_UNKNOWN·원본 요청 보존을 검증한다. GET 파손은 새 변경 보류를 만들지 않는다. 가짜 clock과 요청 캡처로 500ms·시도 횟수·키/body/revision 동일성을 검사한다.

### 구현·인수

- [ ] T036 [US3] `backend/app/services/idempotency_service.py`, `backend/app/services/conversation_service.py`에서 UNIQUE/CAS 경쟁 loser가 winner를 유한 시간 내 재조회해 replay/충돌/일시 장애로 끝나도록 보완한다. 만료는 replay보다 먼저, 성공 replay는 stale revision보다 먼저 처리하고 원래 status/body를 그대로 반환한다.
- [ ] T037 [US3] 확정된 MCP HTTP·상태 파일에 UUIDv4 키와 직렬화 body·reference_time·request_started_at·accepted_at·revision 고정, 논리 HTTP 단계당 자동 추가 1회만 허용하는 재시도를 구현하고 `Docs/mcp-http-integration.md`에 검증 결과를 기록한다. 숨겨진 transport retry를 끄고 backend/004와 호출 예산 중첩 여부를 확인한다.
- [ ] T038 [US3] 확정된 MCP 상태·도구 파일에 OUTCOME_UNKNOWN, REQUEST_PENDING, 도구별 resume과 T001에서 합의한 원인 진단 표현을 구현하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 confirm/plan/select 응답 유실·최초 파손 복구를 기록한다. 첫 깨진 POST 응답부터 시도 횟수와 무관하게 보류하고 GET 외 새 변경을 차단한다. 직접 elicitation 후 원래 단계·키·본문·revision·시각으로 POST 1회만 전송하며 자동 재시도 예산을 초기화하지 않는다. GET revision만으로 결과를 확정하지 않고 유효 성공 replay·미적용 확정 오류·만료 종료를 구별한다.
- [ ] T039 [US3] 확정된 MCP HTTP·승인·상태 파일에 HTTP GET 15초/POST 30초, elicitation 최대 1회·300초, 전체 480초 예산과 취소 처리를 구현하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 경계 테스트를 기록한다. 남은 예산 부족 시 새 HTTP를 보내지 않고 전송 후 취소는 rollback이 아닌 결과 미수신으로 취급한다.
- [ ] T040 [US3] 확정된 MCP 응답·상태·검증 파일에서 오래된 성공 replay가 관측 최대 revision을 낮추지 않게 하고 필요 시 GET으로 동기화한다. `specs/003-mcp-http-contract-alignment/quickstart.md`에 최초 응답 파손 뒤 GET으로 revision 4 관측→resume의 revision 3 replay 사례와 만료된 후보를 새 후보처럼 제시하지 않는 결과를 기록한다. GET만으로 보류 요청 성공을 단정하지 않는다.
- [ ] T064 [US3] [백엔드 담당, T004·T010·T019·T020·T029 후] `specs/003-mcp-http-contract-alignment/quickstart.md`에 T004에서 확인한 timeout 구현·테스트 파일 경로와 검증 명령을 연결한다. 기존 처리를 재사용하고 부족한 부분만 보강해 핸들러 진입부터 결과 검증·원자 확정까지 단조 시간으로 health/capabilities 3초, places 10초, interpret/plan/replan 25초를 적용한다. provider는 남은 예산을 공유하며 004와 조율한다. 시간 제어 테스트로 각 제한의 직전·동일·초과, provider 지연·늦은 성공·commit 뒤 응답 지연을 검사한다. 미확정 timeout은 상태·revision·updated_at·TTL·늦은 적용 0회, 확정 성공의 응답 지연은 성공 기록 유지·중복 적용 0회를 검증한다. 자연 만료를 구별하고 confirm 성공 뒤 plan timeout은 plan 직전 상태와 비교한다. 취소만으로 commit 차단을 대신하지 않는다. REQUEST_TIMEOUT은 T001/T002 합의대로만 적용한다. US4 구현 후 replan 검증은 T048에서 재실행한다.
- [ ] T041 [US3] T034~T040·T064 및 V04·V05·V06·V10·V11의 복구·시간 경계 사례를 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 적용 횟수·재전송 byte·대기시간·오류별 호출 수를 기록한다. confirm/plan/select의 최초 파손 응답→보류→직접 승인 resume→유효 성공 replay를 각각 확인한다. provider 호출 자체의 exactly-once 보장과 서버 상태 적용 1회를 구별한다.

## Phase 5A: US1 — 확장 전 실제 약속 인수 (P1)

**시작 조건**: T041 완료. 이 인수는 US1의 완료 범위이며 US2/US3 안전 경계 위에서 실행한다. US4/US5 확장 전에 통과해야 한다.

- [ ] T062 [US1] [공동, T003·T005·T041 후] 설치 Hermes에서 실제 Solar Pro4 식별자·도구 5개 discovery, 약속의 실제 accept/decline/cancel/timeout·직접 후보 선택·대화 A/B 프로세스 분리·동일 키 resume을 검증하고 `specs/003-mcp-http-contract-alignment/quickstart.md` V11에 기록한다. 가짜 approval client는 실제 승인 증거로 쓰지 않는다. T055의 약속 인수 부분을 이 선행 단계로 분리한다.
- [ ] T063 [US1] [공동, T062 및 004 약속 제공처 준비 후] 같은 로컬 Hermes→MCP→FastAPI 환경에서 실제 데이터 기반 약속 1건 이상을 장소 확인→실제 승인→권장 출발·도착·근거 표시→후보 선택까지 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md` V01·V09·V12에 양측 버전·입출력·출처·기준시각·is_demo=false 증거를 기록한다. T056의 약속 인수 부분을 분리하며 막차 제공처 준비에는 의존하지 않는다. 미준비면 모의 약속·실패 검증은 계속하되 이 작업과 US4/US5 확장을 보류한다.

## Phase 6: US4 — 재탐색 후보를 비교하고 직접 선택하기 (P2)

**목표**: 기존 선택을 보존하며 현재 출발지로 재탐색하고, 직접 선택한 후보만 적용한다.

**시작 조건**: T063 통과. 실제 약속 인수 전에는 이 확장 단계에 착수하지 않는다.

**독립 검증**: 유효한 기존 선택 fixture에서 V07·V10을 실행한다. US5 없이 성공/미선택/취소/실패/만료와 다른 후보 선택을 검사한다.

### 테스트

- [ ] T042 [P] [US4] `backend/tests/contract/test_journeys_replan.py`, `backend/tests/contract/test_replan_service_contract.py`에 서버 선택 snapshot과 previous_plan 일치, effective trip의 출발지만 변경, 확인 불일치 거부, data.plan/comparison 구조를 작성한다.
- [ ] T043 [P] [US4] `backend/tests/integration/test_replan_e2e.py`에 출발점 변경→interpret→새 confirm→replan→select, 불변 조건의 유효 확인 재사용, 취소/실패/후보 만료 보존 사례를 작성한다. 18:50→19:10은 변화 20분이고 19:00 대비 지각 10분임을 검증한다.

### 구현·인수

- [ ] T044 [US4] `backend/app/services/replan_service.py`, `backend/app/services/conversation_service.py`에서 서버의 기존 선택 trip/snapshot과 previous_plan을 대조하고 출발지만 교체한 effective trip이 현재 확인 조건과 같을 때 계산한다. 새 후보·comparison만 저장하고 기존 선택은 유지한다.
- [ ] T045 [US4] `backend/app/schemas/journeys.py`, `backend/app/api/journeys.py`의 replan을 공통 상태/멱등 트랜잭션에 연결한다. reason·confirmation_id·엄격한 user_confirmed, SELECTION_MISMATCH 및 유효 provider 오류를 전달하고 실패의 revision·TTL 갱신을 막는다.
- [ ] T046 [US4] 확정된 MCP 도구·승인 파일에 새 초안/출발점 변경 시 새 confirm 필수, 조건 불변·유효 확인 시 재탐색 의사만 elicitation으로 받고 confirm 생략하는 두 흐름을 구현한다. `specs/003-mcp-http-contract-alignment/quickstart.md`에 두 요청 순서를 기록하고 목적지·마감 등 다른 변경은 새 plan으로 보낸다.
- [ ] T047 [US4] 확정된 MCP 선택·설명·검증 파일에서 권장 후보와 다른 후보 선택 시 권장 전용 comparison을 숨기거나 해당 후보의 서버 값으로 설명하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 비교 검증을 기록한다. 지각·여유 부족·이전 경로 이용 가능성을 혼동하지 않는다.
- [ ] T048 [US4] `backend/tests/integration/test_replan_e2e.py`와 확정된 MCP 복구 테스트에 replan/select 응답 유실·commit 뒤 최초 응답 파손, 계산 중 조건 변경, 선택 대기 중 후보 교체/만료를 추가한다. T064의 25초 직전·동일·초과·늦은 commit 차단·commit 뒤 응답 지연을 실제 replan 경로에서 재검증한다. `specs/003-mcp-http-contract-alignment/quickstart.md`에 자동 추가 시도 0회·보류·동일 키 resume·중복 적용 0회 및 실제 새 선택 성공 외 기존 선택 보존을 기록한다.
- [ ] T049 [US4] T042~T048과 V07·V10을 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md`에 미선택·취소·실패·만료에서 선택 보존율 100% 및 명시적 선택의 revision 증가 결과를 기록한다.

## Phase 7: US5 — 검증된 막차와 실제 연결 범위 확인하기 (P2)

**목표**: 같은 계획 도구로 막차를 처리하고, 모의 연결·실제 백엔드·실제 Hermes·실데이터 인수를 구분한다.

**시작 조건**: T063·T049 통과. 막차 제공처 미준비는 이미 완료한 약속 인수를 취소하지 않으며 막차 실데이터 인수만 미완료로 남긴다.

**독립 검증**: 막차 fixture로 V08·V09를 먼저 실행한다. 실제 데이터 검증은 004가 검증한 지원 범위·권한·설정을 제공한 후 진행한다. 실제 막차 자료가 없으면 SC-006 실데이터 인수는 미완료다.

### 테스트

- [ ] T050 [P] [US5] `backend/tests/contract/test_journeys_plan_last_journey.py`, `backend/tests/unit/test_last_journey_service.py`에 `/journeys/plan`의 trip.kind=last_journey, 운행일/다음 날 도착, 지원/미지원/경로 없음/권장 여유 미확보와 출처 필드를 작성한다.
- [ ] T051 [P] [US5] `backend/tests/integration/test_last_journey_e2e.py`에 실제 HTTP로 demo 결과 수신, provider 실패·잘못된 응답의 demo 전환 금지, 내부 별도 막차 경로 호출처 전환을 검증한다. HTTP 연결과 실데이터 여부를 별도로 assert한다.

### 구현·인수

- [ ] T052 [US5] `backend/app/api/journeys.py`, `backend/app/services/plan_service.py`, `backend/app/services/last_journey_service.py`에서 trip.kind로 기존 계산 서비스를 분기하고 동일한 확인·후보·멱등 계약을 적용한다. 기존 별도 경로의 호출처는 T002 합의대로 전환하며 검증되지 않은 운행시각·경로를 생성하지 않는다.
- [ ] T053 [US5] `backend/app/api/capabilities.py`, `backend/app/api/responses.py`와 기존 `backend/app/services/provider_interfaces.py`의 연결을 확인해 004가 검증한 지원 범위·출처·기준시각·is_demo를 유지한다. 제공처 구현은 004 담당 범위에 두고 실패를 가짜 성공으로 대체하지 않는다.
- [ ] T054 [US5] 확정된 MCP 도구·설명·검증 파일에 같은 plan_journey에서 막차 유형·운행일·이론상 최후 출발/권장 출발·미지원 사유를 전달하는 검증을 추가하고 `Docs/mcp-http-integration.md`에 T050~T053 및 V08·V09 결과를 기록한다.
- [ ] T055 [US5] T062의 실제 Hermes 환경에서 재탐색·막차·동일 키 resume과 약속 회귀를 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md` V11에 기록한다. 모델·버전·승인 표면이 바뀌었으면 실제 거부·프로세스 분리도 재검증한다. T062의 선행 약속 인수를 대신하지 않으며 fake approval client를 실제 승인 증거로 사용하지 않는다.
- [ ] T056 [US5] 004의 검증된 제공처·지원 범위·권한·설정으로 로컬 Hermes→MCP→FastAPI에서 재탐색·막차 4종 결과와 약속 회귀를 검증하고 `specs/003-mcp-http-contract-alignment/quickstart.md` V08·V09에 실데이터 결과를 기록한다. T063의 선행 약속 인수를 대신하지 않는다. 미지원/미실행 사례는 남겨두며 새 제공처 구현·원격 배포로 범위를 확장하지 않는다.
- [ ] T057 [US5] `Docs/mcp-http-integration.md`에 양측 SHA/미커밋 여부, `/api/v1` 포함 실제 주소, SDK/Hermes/모델 버전, 해석·계획·재탐색 요청/응답, 승인 거부·재생·충돌 결과를 정리하고 다른 담당자가 약속/재탐색 각 1건과 거부/중복 사례를 재현해 V12를 확인한다. 가상 fixture·모의 HTTP·실데이터·작성 도구 출처를 구분하고 비밀키·불필요한 개인정보는 제거한다.

## Phase 8: 공통 마무리와 회귀 검증

**목적**: 합의 문서·구현·예제·인수 자료의 같은 계약 적용을 확인한다. 이 단계는 실행하지 않은 작업을 일괄 완료 표시하는 단계가 아니다.

- [ ] T058 [P] [공동] `README.md`, `Docs/BACKEND_HANDOFF.md`, `Docs/mcp-http-integration.md`, `specs/003-mcp-http-contract-alignment/quickstart.md`에 실제 설치/초기화/실행 명령·소유 경계·로컬 신뢰 범위·알려진 제한을 반영한다. 원격 공유 저장소·접근 제어·배포 인수는 별도 게이트임을 유지한다.
- [ ] T059 [P] [공동] `specs/003-mcp-http-contract-alignment/checklists/plan-review.md`에 변경한 공개 필드·오류·경로·상태 symbol의 호출처/문서/fixture/test 영향 점검을 추가한다. `API_SPEC.md`, `Docs/api/examples.json`, 002 문서, 관련 `agent_specs/main-agent.md`, `agent_specs/trip-intake-agent.md`, `agent_specs/recovery-agent.md`의 상충 사항을 확인하고 해당 담당자가 필요한 부분만 함께 갱신한다. `.hermes/skills` 원본이나 준비 폴더의 구현 상태를 꾸미지 않는다.
- [ ] T060 [공동, T058·T059 후] `backend/tests/contract/`, `backend/tests/integration/`, 변경 관련 `backend/tests/unit/` 및 확정된 MCP 테스트를 실행하고 `specs/003-mcp-http-contract-alignment/quickstart.md`의 V01~V12에 결과를 연결한다. 기존 프로젝트에 정의된 lint/type/format 검사도 해당 변경에 적용하며 새 검사 도구를 임의 도입하지 않는다.
- [ ] T061 [공동] `specs/003-mcp-http-contract-alignment/tasks.md`와 `specs/003-mcp-http-contract-alignment/checklists/plan-review.md`에 실제 완료/차단/미실행 상태, FR/SC 충족 여부 및 재현 증거 위치를 갱신한다. 검증 불충족 작업은 체크하지 않으며 로컬 계약 통과·Hermes 통과·실데이터 통과·원격 미인수를 구분해 보고한다.

## 의존성과 실행 순서

```text
T001 계약 합의 → T002 기준 문서/예제 동기화 ─┐
T004 기존 저장/초기화 방식 확인 ───────────┼→ T006~T012 백엔드 기반
T003 실제 MCP 파일 경로 → T005 호환성 확인 ─┘        │
                                                   ↓
                                         T013~T014 MCP 기반·검증
                                                   ↓
                                           US1 약속 기본 흐름
                                                   ↓
                                         US2 상태·승인 거부 경계
                                                   ↓
                                    US3 멱등·복구·T064 서버 제한
                                                   ↓
                                        T041 약속 안전 경계 인수
                                                   ↓
                                        T062 실제 Hermes 약속
                                                   ↓
                                  T063 실제 데이터 약속 (004 준비)
                                                   ↓
                                           US4 재탐색·선택
                                                   ↓
                                           US5 막차·실행 인수
                                                   ↓
                                            T058~T061 마무리
```

- 같은 P1 안에서는 US1→US2→US3 순서로 진행한다. 기본 동작은 공통 기반에서 이미 강제하고, US2/US3는 경계와 장애 검증을 완성한다. 안전 조건을 후순위 선택 기능으로 취급하지 않는다.
- T064는 T004·T010·T019·T020·T029 뒤, T041 앞이다. US3에서는 공통 deadline 처리와 약속 경로를 검증하고 기존 replan 진입점의 예산은 제어된 workflow로 확인한다. 확장한 replan 전체 경로는 T048에서 다시 검증한다. US4 구현을 T064의 선행 조건으로 두지 않는다.
- US1 기본 흐름→US2→US3/T041→T062→T063 순서로 최소 약속 인수를 끝낸 뒤 US4→US5를 구현한다. T062/T063은 US1에 속하지만 안전 경계 검증 후 수행하는 인수 단계다. T063 전 US4/US5 확장은 보류하며 공유 파일은 순차 작업한다.
- T062는 실제 Hermes, T063은 004의 약속용 제공처에 의존한다. 하나라도 미준비면 모의 약속·실패 검증만 계속하고 선행 실제 인수는 미완료로 남긴다. T056의 막차 제공처 준비를 T063 선행 조건으로 추가하지 않는다. T055/T056은 확장 인수와 약속 회귀다.
- 각 이야기의 독립 테스트는 명시한 선행 기반과 fixture만으로 재현할 수 있다는 의미다. 공유 기반 없이 각 기능을 별도 구현하거나 모든 이야기의 동시 수정을 권장한다는 뜻이 아니다.

## 병렬 실행 예시

선행 조건이 완료된 뒤 다음 쌍을 병행할 수 있다. `[P]`가 없는 작업이나 같은 파일을 고치는 구현 작업은 이 예시로 병행을 허용하지 않는다.

| 범위 | 병행할 작업 | 분리 근거 |
|---|---|---|
| 기반 | T006 / T007 | 서로 다른 새 단위 테스트 파일 |
| US1 | T015 / T016 | 계약 테스트와 약속 통합 테스트 |
| US2 | T026 / T027 | 상태 계약 테스트와 독립 세션 통합 테스트 |
| US3 | T034 / T035 | 백엔드 socket/DB 테스트와 외부 MCP HTTP 테스트 |
| US4 | T042 / T043 | 재탐색 계약 테스트와 통합 테스트 |
| US5 | T050 / T051 | 막차 단위/계약 테스트와 통합 테스트 |
| 마무리 | T058 / T059 | 실행 안내 문서와 별도 변경 영향 체크리스트 |

MCP와 백엔드 담당자가 구현을 분담할 때도 합의된 같은 fixture 버전을 사용한다. 동일 문서의 최종 쓰기는 한 담당자가 순차 반영하고 다른 사람의 변경을 덮어쓰지 않는다.

## 요구사항·검증 추적

| 요구사항 | 주요 작업 | 검증 |
|---|---|---|
| FR-001 | T002, T013, T017~T025, T054 | V01 / SC-001 |
| FR-002 | T015, T017, T020~T021, T035 | V01, V05 / SC-001 |
| FR-003 | T015~T016, T018, T024 | V01 / SC-001 |
| FR-004 | T006, T012~T014, T022, T026, T028~T030, T062, T055 | V02, V11 / SC-002 |
| FR-005 | T009~T014, T027~T032 | V03, V11 / SC-002 |
| FR-006 | T010, T012, T027~T029, T036 | V03 / SC-002 |
| FR-007 | T011, T026, T031, T034 | V06 / SC-002 |
| FR-008 | T015~T019, T024~T025 | V01 / SC-001 |
| FR-009 | T050~T054, T056 | V08 / SC-006 |
| FR-010 | T042~T046 | V07 / SC-005 |
| FR-011 | T012, T022, T043~T049 | V07 / SC-005 |
| FR-012 | T027, T043~T049 | V07, V10 / SC-005 |
| FR-013 | T007, T010, T034~T041, T048, T062 | V04, V05, V11 / SC-003, SC-004 |
| FR-014 | T007, T010~T011, T034, T036, T040~T041 | V04, V06 / SC-003 |
| FR-015 | T035, T037~T041 | V05 / SC-004 |
| FR-016 | T004, T010~T011, T027~T029, T031, T040~T041, T048, T064 | V03, V06, V10 / SC-002, SC-005, SC-008 |
| FR-017 | T020~T021, T024, T035, T051, T053~T054 | V05, V09 / SC-007 |
| FR-018 | T021, T023, T051, T053~T056 | V09 / SC-007 |
| FR-019 | T001~T002, T057, T059~T061 | V01, V12 / SC-008 |
| FR-020 | T003~T005, T025, T033, T041, T049, T054~T057, T062~T063 | V01, V09, V11, V12 / SC-001, SC-007, SC-008 |
| FR-021 | T001, T005, T055, T057~T063 | V11, V12 / SC-008 |

20개 가상 fixture는 해당 상태의 preconditions와 동결 시각/ID를 구성해 검증한다. fixture의 고정 ID를 실서버에 그대로 보내거나 문서 예제를 실행 증거로 대신하지 않는다. `plan_replay_after_selection`, `initial_response_lost`, `initial_request_too_old`는 T034·T040에서, 나머지 해석/계산/선택/거부/재탐색/막차 사례는 각 이야기의 계약 테스트에서 다룬다.

`contracts/examples.json`의 별도 `fault_scenarios`는 유효 HTTP fixture가 아닌 장애 주입 절차다. T035/T038/T041/T048은 최초 POST 파손을, T064는 시간 경계를 검증한다. `proposed_error_examples`의 REQUEST_TIMEOUT 예제는 T001 합의 전 미확정이며 공통 fixture로 간주하지 않는다.

## 구현 전략과 MVP

1. T001~T005로 적용할 계약과 실제 경로·환경을 확인한다. 공동 합의 전에는 제안 문서 검토만 진행한다.
2. 공통 기반과 US1으로 가장 작은 약속 흐름을 만든다. 이 시점의 결과는 로컬 계약/기능 증명이다.
3. US2·US3와 T064의 경계를 검증한 뒤 T062의 실제 Hermes, T063의 실제 약속 데이터 인수를 완료해야 최소 실제 약속 MVP로 인정한다. 개발 도구 조건과 제출 적합성은 이 실행 성공과 별도다.
4. T063 통과 후 US4 재탐색, US5 막차를 순차 확장한다. T055/T056에서 확장 기능과 약속 회귀를 검증한다. 원격 배포는 별도 인수다.
5. 마지막으로 상대 담당자가 자료만으로 재현하고 완료/미완료를 구분한다. 개발·작성 도구와 실제 시연 모델의 기록은 사실대로 남긴다.

## 최초 작업 목록 생성 기록

- 생성 범위는 이 파일 하나다. 003 기존 설계, 공통 API/예제, 004 활성 설정, 백엔드 및 다른 기능 작업을 수정하지 않는다.
- `setup-tasks.ps1 -Json`의 경로/템플릿 탐색은 실행했다. 004 설정 보존을 위해 스크립트를 메모리에 로드해 common 참조를 절대 경로로, 경로 해석을 `Get-FeaturePathsEnv -NoPersist -ReturnNullOnError`로 바꾼 변형으로 실행했다. 원본 스크립트는 수정하지 않았으며 기본 명령 그대로 실행했다고 주장하지 않는다.
- 반환된 FEATURE_DIR은 003 절대 경로였고, TASKS_TEMPLATE_CONTENT와 research/data-model/contracts/quickstart 목록을 읽어 작성했다. `.specify/extensions.yml`은 생성 시작 시 존재하지 않았다.
- 총 61개 작업: 준비 5, 공통 기반 9, US1 11, US2 8, US3 8, US4 8, US5 8, 마무리 4. MCP 실제 파일 경로 확정은 T003의 명시적 선행 조건이다.
- 이 목록의 문서 형식 검증과 이후 구현 시 실행할 애플리케이션 테스트를 구분한다. 아직 구현·런타임 검증을 실행하지 않았다.
- 생성 후 정적 검증: T001~T061 연속·중복 없음, 모든 체크박스/이야기 라벨/대상 경로 형식, FR 21개·SC 8개 추적, 상대 링크 8개, 병렬 쌍 7개의 문서상 대상 파일 비중복을 확인했다. 경로 점검에서 인수 문서 위치를 실제 `Docs/BACKEND_HANDOFF.md`로 바로잡았다. 외부 MCP 경로 미확인은 T003에 남아 있다.
- 생성 후에도 `.specify/extensions.yml`은 없어 before_tasks/after_tasks hook 실행 대상이 없었다. 공통 API/예제, 활성 004 설정, setup-tasks/common 스크립트의 작업 전후 SHA-256이 같음을 확인했다.

## 수정안 반영 기록 — 2026-09-16

- 사용자 답변에 따라 003 관련 문서를 동기화했다. 공통 API·예제 및 004 활성 설정은 보존한다. 최초 생성 기록의 61개는 수정 전 이력이다.
- 현재 총 64개: 준비 5, 공통 기반 9, US1 13(T062/T063 포함), US2 8, US3 9(T064 포함), US4 8, US5 8, 마무리 4. 병렬 후보는 기존 7쌍·14개를 유지한다. 새 3개는 의존성이 있으므로 [P]를 붙이지 않는다.
- setup-plan/setup-tasks는 메모리에서 common 경로를 절대 경로로, 경로 해석을 NoPersist로 바꿔 실행했다. 원본 스크립트와 feature marker는 수정하지 않았다. 반환 기능 경로는 003이며 BRANCH 값은 기능 이름이었다. 이를 Git 브랜치 변경으로 해석하지 않는다.
- 문서 반영과 정적 검증만 수행한다. 작업 완료 체크, 실제 공동 합의·실행 승인·헌법 예외·Hermes 인수·제공처 실행을 대신하지 않는다. MCP 실제 경로는 T003, timeout 실제 경로는 T004에서 확정해야 한다.
