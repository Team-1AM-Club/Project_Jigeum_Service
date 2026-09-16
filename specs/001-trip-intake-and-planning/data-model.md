# 데이터 모델: 이동 입력·조건 확인·출발 시각 계산

> 2026-09-14: 서비스 제공 형태는 MCP로 확정됐다. Hermes는 개발·시연용 클라이언트다. 기존 REST 스키마는 유지하며, 제품 전제의 정정은 구현·테스트 완료를 의미하지 않는다.


**생성일**: 2026-09-13
**관련 명세**: [spec.md](../spec.md), [API_SPEC.md](../../../API_SPEC.md)

이 문서는 기능 명세에서 추출한 엔티티와 검증 규칙, 상태 전이를 정리한다. 구현 상세 언어·프레임워크는 기재하지 않는다.

## 1. TripDraft (이동 조건 초안)

자연어 입력과 사용자 확인을 누적해 저장하는 구조화 중간 상태이다.

- **kind**: `appointment` | `last_journey` | `null`
- **origin**: PlaceSlot
- **destination**: PlaceSlot
- **arrival_deadline**: datetime 또는 null
- **arrival_preference_minutes**: integer(0~120) 또는 null
- **service_date**: date 또는 null
- **transport_modes**: `["subway","bus"]` 중 중복 없는 1~2개 또는 null
- **ambiguities**: string[]

규칙:

- `kind=appointment`이면 arrival_deadline이 필수 방향성이다.
- `kind=last_journey`이면 service_date가 필수 방향성이고 arrival_deadline은 null이다.
- arrival_preference_minutes는 0~120 범위이며, `last_journey`일 때 0으로 본다.
- transport_modes에 `taxi`는 허용하지 않는다.
- PlaceSlot은 `query`, `place`, `confirmed`로 구성된다. `confirmed=true`이면 `place`가 있어야 한다.

## 2. PlaceSlot (장소 슬롯)

사용자 표현과 확정된 장소를 분리한다.

- **query**: string 또는 null (예: "집", "잠실", "강남역 2번 출구")
- **place**: Place 또는 null
- **confirmed**: boolean

규칙:

- `confirmed=false`이면 `place`는 null일 수 있다.
- "집", "잠실" 같은 표현을 임의 좌표로 확정하지 않는다. 필요 시 장소 검색·선택 단계로 연결한다.

## 3. Place (장소)

경로 계산에 사용하는 출발·도착 기준점이다.

- **place_id**: string (서버가 해석할 수 있는 제공처 기반 불투명 ID)
- **name**: string
- **address**: string 또는 null
- **latitude**: number(-90~90)
- **longitude**: number(-180~180)

규칙:

- 클라이언트는 place_id만 계산 요청으로 보내고, 좌표 직접 입력·수정으로 교통 계산을 수행하지 않는다.
- 서버는 place_id를 실제 장소로 해석할 수 있어야 한다.

## 4. TripRequest (계획 계산 요청)

사용자가 확인한 뒤 `/journeys/plan`으로 전송하는 확정 조건이다.

- **kind**: `appointment` | `last_journey`
- **origin_place_id**: string
- **destination_place_id**: string
- **arrival_deadline**: datetime 또는 null
- **arrival_preference_minutes**: integer(0~120)
- **service_date**: date 또는 null
- **transport_modes**: `["subway","bus"]` 중 1~2개, 중복 없음

규칙:

- `appointment`는 arrival_deadline이 필수, service_date는 null.
- `last_journey`는 service_date가 필수, arrival_deadline은 null, arrival_preference_minutes는 0.
- 도보는 연결 구간으로 기본 허용한다.
- 택시(taxi)는 지원하지 않으며 입력 시 검증 오류를 반환한다.

## 5. Plan (계획 계산 결과)

계산 완료된 계획 전체이다.

- **plan_id**: string (이번 계산 결과 ID, 서버 저장 리소스 주소 아님)
- **generated_at**: datetime
- **refresh_after**: datetime
- **trip**: TripRequest
- **origin**: Place
- **destination**: Place
- **target_arrival_at**: datetime 또는 null (`appointment`에서만 존재)
- **recommended_option_id**: string
- **options**: RouteOption[] (성공이면 1~3개, 빈 배열 금지)

규칙:

- 첫 leg.departure_at = recommended_leave_at.
- 마지막 leg.arrival_at = estimated_arrival_at.
- refresh_after는 데이터 재확인을 권할 시각이며, 운행 보장 시각이 아니다.

## 6. RouteOption (후보 경로)

하나의 경로 후보이다.

- **option_id**: string
- **summary**: string
- **recommended_leave_at**: datetime
- **hard_leave_at**: datetime 또는 null (`last_journey`에서만 존재)
- **estimated_arrival_at**: datetime
- **total_duration_minutes**: number ≥ 0
- **buffer**: Buffer
- **arrival_status**: `on_time` | `preference_missed` | `late` | `not_applicable`
- **late_by_minutes**: integer ≥ 0 또는 null
- **target_margin_minutes**: integer 또는 null
- **legs**: Leg[]
- **calculation_method**: `schedule_search` | `departure_search`
- **sources**: Source[]
- **warnings**: Warning[]
- **navigation_url**: string 또는 null

규칙:

- appointment 판정:
  - on_time: estimated_arrival_at ≤ target_arrival_at
  - preference_missed: target_arrival_at < estimated_arrival_at ≤ arrival_deadline
  - late: estimated_arrival_at > arrival_deadline
  - on_time/preference_missed일 때 late_by_minutes = 0
- last_journey는 not_applicable, late_by_minutes=null, target_margin_minutes=null.
- recommended_leave_at이 이미 과거면 현재 이용 가능한 권장안으로 반환하지 않고, 현재 출발 가능한 안으로 다시 평가한다.

## 7. Leg (이동·대기 구간)

- **leg_id**: string
- **mode**: `walk` | `wait` | `subway` | `bus`
- **from**: Point
- **to**: Point
- **departure_at**: datetime
- **arrival_at**: datetime
- **duration_minutes**: number ≥ 0
- **transit**: Transit 또는 null (subway/bus에 필수)
- **wait_reason**: `scheduled_wait` | `safety_buffer` | `mixed` 또는 null

규칙:

- 시간순으로 연결하며 구간 사이 대기는 wait leg로 명시한다.
- transit은 subway/bus에만 존재하고 walk/wait에는 null이다.

## 8. Point

- **name**: string
- **latitude**: number
- **longitude**: number

## 9. Transit

- **line_name**: string
- **direction**: string 또는 null
- **headsign**: string 또는 null
- **service_id**: string 또는 null

규칙:

- 막차 계산에는 방향·종착역·해당 편 식별을 검증할 수 있어야 하며, 핵심 정보가 없어 검증할 수 없으면 성공 막차를 반환하지 않는다.

## 10. Buffer (Safety Buffer)

- **policy_version**: string
- **total_minutes**: number
- **items**: BufferItem[]

### BufferItem

- **code**: string
- **minutes**: number ≥ 0
- **leg_id**: string
- **reason**: string

규칙:

- Buffer 시간은 legs와 total_duration_minutes에 이미 반영되어 있으며, 연동 계층에서 다시 더하거나 권장 출발시각에서 다시 빼지 않는다.
- items의 합계는 total_minutes와 일치해야 한다.
- 같은 시간에 여러 여유 항목을 중복 배정하지 않는다.

## 11. Source (데이터 출처)

- **provider**: string
- **basis**: `schedule` | `realtime` | `demo`
- **retrieved_at**: datetime
- **service_date**: date

규칙:

- demo 출처가 하나라도 있으면 meta.is_demo=true여야 한다.

## 12. Warning (경고)

- **code**: string
- **message**: string

초기 코드 예시: `DEMO_DATA`, `SCHEDULE_ONLY`, `DATA_REFRESH_RECOMMENDED`.

## 13. 현재 대화의 선택 계획

기존 Local Journey 영구 저장·진행 상태·알림 모델은 현재 MCP 필수 모델이 아니다. 기존 구현 파일은 삭제하지 않으며 필요 시 후속 명세에서 재검토한다.

현재 범위에서는 Plan과 사용자가 선택한 option_id를 관리하고, 재탐색 시 아래 PlanSummary와 trip을 전달한다. 대화 간 격리·확인 조건의 수명·저장 위치는 구현 전에 합의한다. 모델의 자유 서술을 영구 저장이나 사용자 선택의 증거로 보지 않는다.

계획 조회와 적용은 구분한다. 사용자 선택 전 후보를 적용하지 않으며 재탐색 실패·취소가 기존 선택을 삭제해서는 안 된다. 재시작 후 자동 복원이나 알림 발송을 약속하지 않는다.

## 14. PlanSummary (이전 계획 비교용)

- **plan_id**: string
- **selected_option_id**: string
- **recommended_leave_at**: datetime
- **estimated_arrival_at**: datetime

## 15. Comparison (재탐색 비교)

- **previous_plan_id**: string
- **previous_selected_option_id**: string
- **compared_option_id**: string
- **arrival_change_minutes**: number (새 권장 ETA − 이전 선택 ETA, 양수=더 늦게 도착)
- **leave_change_minutes**: number (새 권장 출발 − 이전 선택 권장 출발, 양수=더 늦은 시각)
- **summary**: string

규칙:

- 사용자가 다른 후보를 선택하면 comparison은 그 후보의 비교가 아니므로, 연동 계층은 해당 비교 문구를 숨기거나 다시 비교한다.
- 변화량 두 필드는 소수 분을 허용한다. 상태 판정은 서버 값에 따른다.

## 16. 검증 규칙 요약

- `appointment`: arrival_deadline 필수, service_date null, arrival_preference_minutes 0~120, transport_modes 1~2개 중복 없음
- `last_journey`: service_date 필수, arrival_deadline null, arrival_preference_minutes 0, transport_modes 1~2개 중복 없음
- taxi 입력 시 검증 오류
- place_id는 서버에서 실제 장소로 해석 가능해야 함
- user_confirmed=false로 계획 요청 시 USER_CONFIRMATION_REQUIRED 처리
- Demo 출처가 하나라도 있으면 meta.is_demo=true
- 운영 조회 실패를 Demo 결과로 자동 대체하지 않음
- 실패·취소된 재탐색이 기존 로컬 기록을 삭제하지 않음
- 재탐색 결과는 사용자 선택 전까지 기존 계획에 적용하지 않음
