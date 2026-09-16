# 계약: 이동 입력·조건 확인·출발 시각 계산

> 2026-09-14: 서비스 제공 형태는 MCP로 확정됐다. Hermes는 개발·시연용 클라이언트다. 기존 REST 스키마는 유지하며, 제품 전제의 정정은 구현·테스트 완료를 의미하지 않는다.


**생성일**: 2026-09-13
**기준**: API_SPEC.md, examples.json, spec.md
**대상 독자**: 클라이언트·서버 두 개발자, 통합 검증자

이 계약은 공개 API 경로·요청·응답·상태·오류 의미를 정리한다. 구현 상세는 기재하지 않으며, 변경은 두 개발자 합의 후 API_SPEC.md와 examples.json을 함께 갱신한다.

## 1. 공통 규칙

- Base URL은 배포 시 확정되는 HTTPS 서버 주소 + `/api/v1`.
- GET은 `Accept: application/json`, POST는 `Content-Type: application/json`, `Accept: application/json`.
- 문자는 UTF-8, 필드명은 snake_case.
- 시각은 오프셋 포함 ISO 8601(예: `2026-09-13T18:00:00+09:00`), 시간대는 `Asia/Seoul`만 허용.
- 성공/업무 결과는 HTTP 200 + status로 분기하고, 전송·검증·장애는 HTTP 4xx/5xx + status=error.
- 모든 응답은 `status`, `data`, `error`, `meta`를 포함한다. 성공 응답에서도 error는 null로 둔다.
- meta에는 `request_id`, `server_time`, `api_version`, `is_demo`를 포함한다.

## 2. GET /health

서버가 요청에 응답하는지 확인한다. 교통 API·모델의 모든 상태가 정상이라는 보장은 아니다.

- 응답 예: `status=ok`, `data.service`, `data.health`.
- meta.is_demo는 환경에 따라 true일 수 있다.

## 3. GET /capabilities

실제 서버 설정과 확인된 제공처 기능을 반환한다.

- 필수 데이터 필드: `timezone`, `place_search.available`, `interpretation.available`, `appointment.available`, `appointment.time_basis`, `last_journey.available`, `last_journey.scope_note`, `last_journey.service_date_from`, `last_journey.service_date_to`, `transport_modes`, `max_options`, `defaults.arrival_preference_minutes`, `defaults.transport_modes`, `buffer_policy.version`, `buffer_policy.label`, `limitations`.
- `last_journey.available=true`여도 모든 서울 경로 지원을 뜻하지 않으며, 요청별 범위 검증은 계산 API에서 다시 수행한다.

## 4. GET /places

장소 검색.

- 필수 쿼리: `query`(앞뒤 공백 제거 후 1~100자, URL 인코딩).
- 선택 쿼리: `limit`(1~10 정수, 기본 5).
- 응답 data: `query`, `places[Place]`, `source.provider`, `source.retrieved_at`, `has_more`.
- 검색 성공 후 결과가 없으면 HTTP 200, status=ok, places=[].
- 계산 요청에는 place_id만 보내고, 클라이언트는 좌표 직접 입력·수정으로 교통 계산을 수행하지 않는다.

## 5. POST /mobility/interpret

자연어 입력과 확인 답변을 구조화해 이동 조건 초안을 만든다.

- 요청 필드: `text`(1~2000자), `reference_time`, `timezone`(Asia/Seoul), `context`(TripDraft 또는 null).
- context에는 이전 초안과 연동 계층에서 수정·확정한 값을 보낸다. 서버가 반환한 초안의 확인된 값을 새 문장만 보고 덮어쓰지 않는다.
- 응답 data: `draft`, `ready_for_plan`, `missing_fields`, `questions`(0~3개), `applied_defaults`, `summary`.
- question은 `field`, `type`, `prompt`, `options`(select일 때만)를 포함한다.
- 필수 정보가 완성되면 status=ok, ready_for_plan=true, missing_fields=[], questions=[]를 반환한다. 이 상태도 사용자의 최종 확인 응답을 대체하지 않는다.
- AI는 모델 미사용 시에도 명시적 조건 입력으로 계산을 진행할 수 있어야 하며, AI_UNAVAILABLE 시 수동 입력을 제공한다.

## 6. POST /journeys/plan

사용자가 이동 조건을 확인한 뒤 계산을 요청한다.

- 요청 필드: `trip(TripRequest)`, `user_confirmed=true`.
- TripRequest는 kind, origin_place_id, destination_place_id, arrival_deadline, arrival_preference_minutes, service_date, transport_modes를 모두 포함한다.
- appointment는 arrival_deadline 필수, service_date null. last_journey는 service_date 필수, arrival_deadline null, arrival_preference_minutes 0.
- transport_modes에 taxi 입력 시 검증 오류.
- 계산 동작:
  1. 필수 필드·사용자 확인·지원 지역·제공처 기능 검증.
  2. place_id를 실제 장소로 해석하고 서버 시각 기준 유효 경로 조회.
  3. appointment 목표 도착시각 = arrival_deadline − arrival_preference_minutes.
  4. 시간표·조회 결과와 코드 기반 Buffer 규칙을 함께 적용해 후보 1~3개와 권장 후보 ID를 반환.
  5. 데이터 기준시각과 계산 방법을 포함.
- 응답 data: `{ plan: Plan }`.
- PLAN 응답에는 legs, buffer, sources, warnings가 포함되며, demo 출처가 하나라도 있으면 meta.is_demo=true 및 DEMO_DATA 경고.
- last_journey는 hard_leave_at과 권장 출발시각을 구분해 반환한다.
- Deadline이 과거여도 요청 자체를 잘못된 JSON으로 처리하지 않고, 이용 가능한 경로가 있으면 late 상태로 반환한다.

## 7. POST /journeys/replan

사용자가 재탐색을 요청한다.

- 요청 필드: `trip(TripRequest)`, `previous_plan(PlanSummary)`, `current_origin_place_id`, `reason`(missed_connection/route_changed/manual), `user_confirmed=true`.
- PlanSummary는 plan_id, selected_option_id, recommended_leave_at, estimated_arrival_at.
- 서버는 이전 plan_id로 DB 조회하지 않고, trip과 current_origin_place_id를 다시 검증해 현재 서버 시각 기준으로 새 경로를 계산한다.
- 응답 data: `plan(Plan)`, `comparison`.
- comparison은 previous_plan_id, previous_selected_option_id, compared_option_id, arrival_change_minutes, leave_change_minutes, summary를 포함한다.
- 새 결과는 사용자가 선택하기 전까지 기존 계획에 적용하지 않는다. 실패·취소된 재탐색이 기존 로컬 기록을 삭제하지 않는다.

## 8. 상태 코드 요약

- ok: HTTP 200, business result in data.
- needs_confirmation: HTTP 200, 해석 초안·질문.
- unavailable: HTTP 200, data=null, error에 업무 사유.
- error: HTTP 4xx/5xx, data=null, error에 오류 정보.

주요 오류 코드:

- INVALID_JSON(400), VALIDATION_ERROR(422), USER_CONFIRMATION_REQUIRED(422), PLACE_NOT_RESOLVABLE(422).
- OUT_OF_SERVICE_AREA(200), APPOINTMENT_TIME_UNSUPPORTED(200), LAST_JOURNEY_UNSUPPORTED(200), NO_FEASIBLE_JOURNEY(200), BUFFER_REQUIREMENT_NOT_MET(200).
- RATE_LIMITED(429), ROUTING_PROVIDER_UNAVAILABLE(503), PLACE_PROVIDER_UNAVAILABLE(503), AI_UNAVAILABLE(503), UPSTREAM_RESPONSE_INVALID(502), UPSTREAM_TIMEOUT(504), INTERNAL_ERROR(500).

## 9. 현재 대화의 문맥·선택 계약

영구 Local Journey 저장·출발/도착 버튼·알림 모델은 현재 필수 범위가 아니다. 요청별 REST 서버가 과거 대화를 저장하거나 plan_id로 DB를 조회한다고 가정하지 않는다.

- 현재 확인 조건·선택 Plan·option_id를 관리하고 기존 재탐색 스키마에 맞춰 이전 계획 요약을 전달한다.
- 문맥·확인·선택 상태의 위치와 수명, 다른 대화와의 격리 방식은 공동 합의한다.
- ready_for_plan=true는 사용자 동의가 아니다. 모델이 user_confirmed=true를 생성했다는 사실만으로 동의를 검증했다고 보지 않는다.
- 조건 변경 후 재확인하며 사용자 후보 선택 전 기존 계획을 교체하지 않는다.
- 기존 REST 필드·오류와 예제 JSON은 유지한다. MCP 세부 스키마·오류 매핑은 별도 합의한다.

## 10. Mock/실제 전환 규칙

- MCP 담당은 examples.json의 case id로 도구 결과·오류 전달과 Hermes 확인 흐름을 먼저 검증한다.
- 백엔드는 실제 데이터 어댑터 연결 전에도 같은 JSON 구조를 유지한 채 Mock 응답을 반환할 수 있다.
- Mock과 실제 서버의 JSON 구조는 동일하게 유지한다.
- 실제 제공처 조회 실패를 Mock/Demo 결과로 자동 대체하지 않는다.
