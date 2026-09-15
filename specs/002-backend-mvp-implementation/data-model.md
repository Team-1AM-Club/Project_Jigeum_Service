# Data Model: Backend MVP Implementation

**Feature**: [specs/002-backend-mvp-implementation/spec.md](../spec.md)

이 문서는 백엔드 MVP에서 다루는 데이터 모델을 공개 계약 모델, 내부 계산/도메인 모델, 대화 문맥·선택 상태 모델로 나눠 정리한다. 저장 스키마·ORM 확정은 범위 밖이면 보류하고, 우선 공개 JSON 계약과 계산 불변식을 맞춘다.

## 1. 공개 요청/응답 모델

이 모델들은 API_SPEC.md와 examples.json fixture와 1:1로 맞춰야 한다.

### TripDraft

자연어 해석 결과로 생성된 이동 조건 초안.

| 필드 | 타입 | 규칙 |
|---|---|---|
| kind | appointment / last_journey / null | 약속 도착 또는 막차 귀가 |
| origin | PlaceSlot | 원문 표현과 확정 장소 분리 |
| destination | PlaceSlot | 원문 표현과 확정 장소 분리 |
| arrival_deadline | datetime 또는 null | appointment의 도착 마감 |
| arrival_preference_minutes | integer 또는 null | 0~120분. null=미지정, 0=정시 선호 |
| service_date | date 또는 null | last_journey의 운행일 |
| transport_modes | enum[] 또는 null | subway / bus, 중복 금지, 지정 시 1개 이상 |
| ambiguities | string[] | 모호한 필드 경로 |

검증 규칙:
- 없거나 모호한 필수 필드는 `missing_fields`와 `questions`로 드러낸다.
- 넓은 지역명·학교·“집”을 임의의 장소로 확정하지 않는다.

### TripRequest

계획 계산에 사용되는 확정된 이동 조건.

| 필드 | 타입 | 규칙 |
|---|---|---|
| kind | enum | appointment / last_journey |
| origin_place_id | string | 선택·확정한 출발지 ID |
| destination_place_id | string | 선택·확정한 목적지 ID |
| arrival_deadline | datetime 또는 null | appointment는 필수, last_journey는 null |
| arrival_preference_minutes | integer | 0~120, last_journey는 0 |
| service_date | date 또는 null | last_journey는 필수, appointment는 null |
| transport_modes | enum[] | subway / bus, 1~2개, 중복 금지 |

검증 규칙:
- user_confirmed=true 없이 계산하지 않는다.
- taxi 등 미지원 모드는 검증 오류로 거부한다.
- 마지막 날/시간대에 따라 지원 범위를 벗어나는 조건은 지원 불가로 처리한다.

### Plan

계산 결과.

| 필드 | 타입 | 의미 |
|---|---|---|
| plan_id | string | 이번 계산 결과 ID. 서버 저장 리소스 주소가 아님 |
| generated_at | datetime | 계산 완료 시각 |
| refresh_after | datetime | 데이터 재확인을 권할 시각. 운행 보장/만료 시각이 아님 |
| trip | TripRequest | 검증한 요청 조건 |
| origin | Place | 검증한 출발 장소 |
| destination | Place | 검증한 도착 장소 |
| target_arrival_at | datetime 또는 null | appointment의 목표 도착. last_journey는 null |
| recommended_option_id | string | options 안의 한 option_id |
| options | RouteOption[] | 성공이면 1~3개. 빈 배열 성공 금지 |

불변식:
- 첫 leg.departure_at = recommended_leave_at
- 마지막 leg.arrival_at = estimated_arrival_at
- refresh_after는 제공처의 최신성 조건을 반영하며, 이번 MVP 기본값은 generated_at + 5분

### RouteOption

개별 경로 후보.

| 필드 | 타입 | 의미 |
|---|---|---|
| option_id | string | Plan 안의 후보 ID |
| summary | string | 경로 요약 |
| recommended_leave_at | datetime | 출발 기준점을 떠나도록 권장하는 시각 |
| hard_leave_at | datetime 또는 null | last_journey의 검증된 이론상 최후 출발. appointment는 null |
| estimated_arrival_at | datetime | 해당 권장 출발 계획의 예상 목적지 도착 |
| total_duration_minutes | number ≥ 0 | 권장 출발부터 도착까지 전체 시간. 도보·대기·추가 여유 포함 |
| buffer | Buffer | 이미 Journey 시간에 포함된 추가 Safety Buffer의 근거 |
| arrival_status | enum | on_time / preference_missed / late / not_applicable |
| late_by_minutes | integer ≥ 0 또는 null | Deadline 초과 분. last_journey는 null |
| target_margin_minutes | integer 또는 null | 목표 도착 - 예상 도착의 분 차이 |
| legs | Leg[] | 실제 순서의 이동·대기 구간 |
| calculation_method | enum | schedule_search / departure_search |
| sources | Source[] | 데이터 출처, 최소 1개 |
| warnings | Warning[] | 없으면 [] |
| navigation_url | string 또는 null | 지원되는 외부 지도 HTTPS/딥링크. 미확인 URL은 null |

불변식:
- buffer.total_minutes는 total_duration_minutes에 이미 포함되어 있으며 별도 재가산하지 않는다.
- arrival_status 판정은 datetime 차이로 수행하며 반올림된 숫자로 상태를 바꾸지 않는다.
- demo 출처가 하나라도 있으면 응답 meta.is_demo=true여야 한다.

### Place / PlaceSlot

| 모델 |필드| 규칙 |
|---|---|---|
| Place | place_id, name, address, latitude, longitude | 서버가 해석할 수 있는 제공처 기반 불투명 ID |
| PlaceSlot | query, place, confirmed | 원문 표현과 확정 장소를 분리. confirmed=true면 place 필요 |

규칙:
- place_id만 계산 요청으로 보내고, 서버는 제공처/검증 캐시에서 좌표를 해석한다.
- 클라이언트가 임의 수정한 좌표로 교통 계산을 수행하지 않는다.

### PlanSummary

재탐색 요청에서 이전 선택 비교용으로 사용하는 최소 요약.

| 필드 | 타입 |
|---|---|
| plan_id | string |
| selected_option_id | string |
| recommended_leave_at | datetime |
| estimated_arrival_at | datetime |

규칙:
- server DB 조회 키로 쓰지 않는다. 과거 비교 기준으로만 사용한다.
- 위조 여부를 보장하는 저장 기록이 아니므로, 추후 보안/공유 기능이 필요하면 별도 저장 모델을 도입한다.

### Comparison

재탐색 성공 응답에서 이전 선택과 새 권장 후보를 비교한 결과.

| 필드 | 타입 | 의미 |
|---|---|---|
| previous_plan_id | string | |
| previous_selected_option_id | string | |
| compared_option_id | string | 새 plan.recommended_option_id |
| arrival_change_minutes | number | 새 권장 ETA - 이전 선택 ETA. 양수=더 늦게 도착 |
| leave_change_minutes | number | 새 권장 출발 - 이전 선택 권장 출발. 양수=더 늦은 시각 |
| summary | string | 확인된 차이를 설명하는 한국어 문장 |

## 2. 내부 계산/도메인 모델

공개 JSON과 달리, 내부에서는 시간대·자정 경계·운행일·목표 도착시각 역산을 다루기 쉬운 형태로 변환한다.

핵심 계산 개념:
- 목표 도착시각 = arrival_deadline − arrival_preference_minutes
- 권장 출발시각은 해당 시각에 유효한 경로·운행시간을 기준으로 결정한다.
- 막차의 이론상 최후 시각(hard_leave_at)과 여유를 반영한 권장 시각을 구분한다.
- total_duration_minutes는 전체 datetime 차이로 구하고, 구간 합계와 일치해야 한다.
- buffer는 leg·total_duration_minutes에 이미 반영되어 있으며 다시 더하거나 빼지 않는다.

검증 규칙:
- appointment의 estimated_arrival_at이 arrival_deadline을 넘으면 late로 판정한다.
- last_journey는 not_applicable로 판정하며 late_by_minutes/target_margin_minutes는 null로 둔다.
- 현재 시각만 기준으로 받은 ETA를 미래 경로/막차의 증거로 쓰지 않는다.

## 3. 대화 문맥·선택 상태 모델(합의 후 확정)

MVP에서는 대화 문맥·확인 상태·선택 계획을 어떻게/어디에 보관할지 구현 전에 두 개발자가 합의해야 한다. 여기서는 현재 논의 중인 범위만 정리한다.

보관 대상 후보:
- 최신 미확인 초안
- 사용자가 확인한 조건
- 현재 후보 계획과 만료 시각
- 사용자가 최종 선택한 계획
- revision, created_at, updated_at, expires_at

보관하지 않는 것 후보:
- 원문 대화 전체
- 과거 계획 이력

수명 후보:
- 미확인 초안: 마지막 활동 후 30분
- 확인된 조건: 마지막 활동 후 2시간
- 후보 계획: provider valid_until까지, 없으면 5분
- 선택 계획: estimated_arrival_at 이후 2시간
- 전체 대화 상태 절대 상한: 48시간

상태 전이 후보:
- 새 입력은 기존 미확인 초안과 후보를 무효화
- 기존 선택 계획은 새 후보가 생성돼도 유지
- 사용자가 새 계획을 명시적으로 선택한 경우에만 선택 계획 교체
- 확인·선택 요청에는 conversation_id와 revision을 사용해 오래된 요청의 덮어쓰기 방지

이 모델은 공개 API 계약보다 먼저 합의되어야 하며, 합의 전에는 실제 저장/복원 구현을 확정하지 않는다.



### IdempotencyRecord (상태 변경 중복 방지 기록)

상태 변경 요청의 멱등성을 보장하기 위해 저장하는 레코드.

| 필드 | 타입 | 규칙 |
|---|---|---|
| id | integer (PK) | 자동 증가 |
| conversation_id | string | 대화 식별자 |
| idempotency_key | string | MCP가 생성한 UUID v4 36자, conversation_id와 UNIQUE 복합 키 |
| payload_hash | string | SHA-256, HTTP method + 정규화된 API path + conversation_id + expected revision + canonicalized body |
| http_method | string | 요청 HTTP 메서드 |
| api_path | string | 정규화된 API 경로 |
| expected_revision | integer | 요청 시 기대한 conversation revision |
| canonicalized_body | string | UTF-8, key 정렬, 불필요한 공백 제거된 JSON body |
| response_status | integer | 저장한 응답 HTTP 상태 |
| response_body | jsonb | 저장한 응답 본문 (envelope 전체) |
| created_at | datetime | 기록 생성 시각 |

규칙:
- idempotency_key는 MCP가 상태 변경 MCP 도구 호출 시작 시 UUID v4로 생성한다. 모델이나 사용자에게 입력받지 않는다.
- payload_hash는 HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body를 포함해 SHA-256으로 hash한다.
- body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한다.
- 같은 key + 같은 payload 재시도는 최초 응답을 반환한다 (effectively-once).
- 같은 key + 다른 payload는 409 IDEMPOTENCY_KEY_REUSED로 처리하고 저장하지 않는다.
- 응답 envelope에는 Idempotency-Key를 중복 추가하지 않는다 (응답 헤더로만 반환).

검증 규칙:
- Idempotency-Key 누락·형식 오류(UUID v4 36자 아님) → 422 VALIDATION_ERROR
- 동일 key 다른 payload → 409 IDEMPOTENCY_KEY_REUSED (retryable: false)
- expired conversation + 동일 key → 410 CONVERSATION_EXPIRED (stale revision보다 우선 처리)

## 4. 모델과 계약의 정합성 원칙

- 모든 공개 모델은 API_SPEC.md 필드와 examples.json fixture와 일치해야 한다.
- 계획·후보·비교 모델은 계산 결과와 상태 분기가 계약 예제와 맞아야 한다.
- 데모 데이터 모델은 meta.is_demo=true와 demo 출처 표기를 포함해야 한다.
- 내부 계산 표현이 공개 JSON을 대체하지 않는다. 최종 응답은 계약형으로 직렬화한다.
