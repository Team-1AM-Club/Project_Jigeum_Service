# MCP HTTP 연결 계약

> 과거 연결 계약 기록이다. 현재 통합본은 환경변수로 HTTP 모드를 선택하고 confirm_trip을 포함한 6개 도구를 제공한다. [현재 MCP 안내](../mcp-server/README.md)와 [통합 결과](integration-status.md)를 우선 확인한다.

5개 도구 모두 mode="http"로 내부 FastAPI에 연결한다. 기본 mode="demo"와 기존 fixture 입력은 유지한다. JIGEUM_API_BASE_URL은 /api/v1을 포함한다. 각 도구 호출에 mode를 명시해 같은 대화에서 demo와 HTTP 데이터를 섞지 않는다.

| 도구 | HTTP | 전달 내용 |
|---|---|---|
| get_capabilities | GET /capabilities | Accept 헤더 |
| search_places | GET /places | query, limit 쿼리 파라미터; 공백 제거·URL 인코딩 |
| interpret_trip | POST /mobility/interpret | text, reference_time, timezone, context |
| plan_journey | POST /journeys/plan | trip, user_confirmed; 막차도 trip.kind로 구분 |
| replan_journey | POST /journeys/replan | trip, previous_plan, current_origin_place_id, reason, user_confirmed |

REST 본문은 API_SPEC.md 및 Docs/api/examples.json과 동일하다. mode/idempotency_key는 MCP 전용 선택 인자로 본문에 넣지 않는다. REST 필드 이름을 추측하거나 conversation_id를 임의 생성하지 않는다. 현재 nested dict의 상세 검증은 백엔드 책임이다.

POST에는 UUIDv4 Idempotency-Key 헤더를 넣는다. 생략 시 호출마다 생성하고, 같은 논리 요청을 명시적으로 재시도할 때는 호출자가 동일한 idempotency_key를 다시 제공한다. 자동 재시도는 없다. 다른 payload에는 다른 키를 사용한다. 서버가 반환한 409 error envelope는 보존한다. 실제 중복 저장 방지·동일 결과 재생은 서버 책임이며 헤더 전달만으로 입증되지 않는다.

사용자가 확인하지 않은 plan/replan은 네트워크 호출 전에 USER_CONFIRMATION_REQUIRED로 거부한다. 실제 사람의 동의 인증, persisted confirmed_conditions 존재, 조건·장소 확인 상태를 서버가 검증하는 기능과는 별개다.

응답의 status/data/error/meta를 보존한다. HTTP 200의 unavailable을 성공 계획으로 바꾸지 않는다. 비200의 error/unavailable envelope도 유지한다. 비계약 본문·HTML·잘못된 JSON을 그대로 노출하지 않고 UPSTREAM_RESPONSE_INVALID로 반환한다. 응답 meta.is_demo와 출처·기준시각을 임의로 변경하지 않는다.

## 실제 백엔드 연결 전 확인

확인한 백엔드 기준 커밋 a9e3d1f는 공유 계약과 다르다.

| 항목 | 공유 API_SPEC 기준 | 확인한 백엔드 라우터 |
|---|---|---|
| interpret 요청 | text 및 context | natural_language, conversation_id 참조 |
| interpret 응답 | data.draft, ready_for_plan, questions | trip_draft, requires_confirmation, confirmation_questions |
| plan 요청 | {trip, user_confirmed} | 평탄한 TripRequest 및 conversation_id 필수 |
| plan 응답 | data.plan.options | data에 평탄한 Plan 반환 |
| 막차 | /journeys/plan, trip.kind | 별도 /journeys/plan/last_journey |

현재 연결 계층은 공유 API_SPEC에 맞춘다. 실제 백엔드가 위 차이를 정리하거나 공동 계약을 수정한 뒤 통합해야 한다. 백엔드 응답을 임의 재구성해 호환되는 것처럼 보이게 하지 않는다.

친구에게 받을 항목: 수정 커밋, /api/v1 포함 실행 주소, interpret/plan/replan 실제 요청·응답, 확인 게이트 및 키 재생·충돌 결과. 실제 통합에서 장소 검색→해석→확인→계획→재탐색을 검증하고 meta.is_demo 및 데이터 출처를 확인한다.

## 검증 범위

tests/test_http_tools.py는 로컬 가짜 HTTP 서버를 실제로 띄워 경로·JSON·헤더·응답 보존·오류를 검사한다. 같은 테스트의 stdio 사례는 MCP 프로세스에서 도구 스키마를 발견하고 네 도구를 호출해 HTTP까지 전달되는지 확인한다. 실제 FastAPI, 교통 API 및 Hermes 모델의 HTTP 대화 시연은 별도 검증 대상이다.

2026-09-16 검증: 전체 pytest 93 passed, 1 skipped, 40 subtests passed (123.59초, exit 0). 기존 verify_http.py도 exit 0. skip 1건은 기존 user_confirmed 누락 테스트의 예외 처리 방식에 따른 것이며 완전한 거부 검증 성공으로 간주하지 않는다.
