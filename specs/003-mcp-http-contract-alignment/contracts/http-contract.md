# 내부 HTTP 계약 제안

**상태**: 양측 검토 전 제안. 현재 `API_SPEC.md`를 대체하지 않는다. 공동 합의 후 기준 문서와 공통 예제를 동시 개정한다.

Base URL은 로컬 검증에서 `http://127.0.0.1:8000/api/v1`이다. 다른 포트를 사용할 경우 실제 값을 기록한다. 원격은 HTTPS·접근 제어·공유 저장소를 별도로 합의해야 한다.

## 1. 경로와 본문

| 메서드·경로 | 본문 또는 query | 성공 data |
|---|---|---|
| GET `/health` | 없음 | 기존 계약 |
| GET `/capabilities` | 없음 | 기존 계약 |
| GET `/places` | query, limit | 기존 계약 |
| POST `/mobility/interpret` | 아래 InterpretInput | 기존 draft/ready_for_plan/missing_fields/questions/applied_defaults/summary + draft_revision/conditions_hash |
| GET `/conversations/{conversation_id}` | 없음 | ConversationView |
| POST `/conversations/{conversation_id}/confirm` | ConfirmInput | confirmation_id, conditions_hash, confirmed_revision, confirmed_until |
| POST `/journeys/plan` | PlanInput | 기존 plan + candidate_set_id/candidate_expires_at |
| POST `/journeys/replan` | ReplanInput | 기존 plan/comparison + candidate_set_id/candidate_expires_at |
| POST `/conversations/{conversation_id}/select` | SelectInput | selected_plan_id, selected_option_id, candidate_set_id, selected_at, selected_until |

막차도 `/journeys/plan`의 `trip.kind=last_journey`로 보낸다. 기존 `/journeys/plan/last_journey`의 사용자용 별도 경로는 제안 계약에서 사용하지 않는다. 기존 호출처가 있다면 공동 개정 때 전환하고 회귀 테스트를 수정한다.

모든 POST는 JSON object이며 명시하지 않은 최상위 필드는 422다. query 제한과 TripDraft/TripRequest/Plan/Place/Comparison의 도메인 필드는 [공유 API](../../../API_SPEC.md)를 재사용한다. `mode`, 모델이 만든 evidence, `idempotency_key`를 도메인 본문에 섞지 않는다.

### 공통 상태 필드

- 최초 interpret만 conversation_id/revision을 **생략**한다. null과 생략을 혼용하지 않는다.
- 후속 POST는 body에 conversation_id와 revision을 필수로 보낸다. revision은 MCP가 받은 서버 버전이며 내부에서는 expected revision으로 해석한다. 서버가 임의로 최신 값으로 교정하지 않는다.
- path에도 conversation_id가 있는 confirm/select는 body와 같아야 한다. 다르면 422 VALIDATION_ERROR, details.field=`conversation_id`, reason=`PATH_BODY_MISMATCH`다.
- 모델은 backend 식별자·revision을 선택하지 않는다. MCP의 대화 binding에서 가져온다.
- 관련 성공 응답과 대화가 확인된 상태 오류에는 meta.conversation_id/revision/expires_at을 넣는다. 알 수 없는 대화에는 이 세 필드를 생략한다. tombstone은 마지막 revision과 원래 expires_at을 반환하며 payload는 반환하지 않는다.

### InterpretInput

| 필드 | 필수·규칙 |
|---|---|
| text | 공백 제거 후 비어 있지 않은 문자열. 공유 계약의 사용자 문장. |
| reference_time / timezone / context | 공유 해석 계약 그대로. timezone은 Asia/Seoul. 상대 날짜 기준은 재시도 중 고정한다. |
| conversation_id / revision | 최초에는 둘 다 생략, 후속에는 둘 다 필수. |
| request_started_at | 최초에만 필수 offset datetime. MCP가 첫 HTTP 전송 직전에 생성한다. 후속 interpret에는 넣지 않는다. |

context는 해석의 힌트·장소 선택 정보다. 서버의 확인 상태나 이전 선택을 덮어쓰는 권한이 아니다. 새 초안의 장소 ID와 최종 조건은 서버가 검증한다. 완전한 초안은 conditions_hash를 반환하고, 불완전하면 null이다. ready_for_plan은 입력 완성도이며 동의가 아니다.

최초 해석이 유효한 draft를 반환하면 status가 needs_confirmation이어도 **초안 저장 성공**이므로 revision=1과 멱등 응답을 원자 커밋한다. 모델·provider 실패면 대화 생성도 성공 처리하지 않는다.

### ConfirmInput

```json
{
  "conversation_id": "11111111-1111-4111-8111-111111111111",
  "revision": 1,
  "draft_revision": 1,
  "conditions_hash": "서버에서 받은 SHA-256 hex 64자",
  "evidence": {
    "source": "mcp_elicitation",
    "interaction_id": "22222222-2222-4222-8222-222222222222",
    "accepted_at": "2026-09-13T18:01:00+09:00"
  }
}
```

위 hash 설명 문자열은 문서 표기다. 실제 전송은 서버가 반환한 64자 값이어야 한다. 서버는 draft의 완전성·유효기간·hash·draft_revision·기대 revision과 evidence를 확인한다. 새 확인은 confirmation_id를 서버에서 만들고 이전 후보를 무효화한다. 현재 선택 기록은 유지한다. 조건을 요청 본문에 새로 적어 승인 대상으로 바꾸지 않는다.

### PlanInput

`conversation_id`, `revision`, `confirmation_id`, `trip`, `user_confirmed`를 모두 보낸다. trip은 확인된 TripRequest와 완전히 같아야 하고 user_confirmed는 엄격한 boolean true만 허용한다. 이 flag만으로는 계산할 수 없다.

서버는 살아 있는 confirmed_conditions와 confirmation_id/hash를 검사한 뒤 경로 provider를 호출한다. 성공 Plan은 `data.plan` 아래에 두며 options는 1~3개다. candidate_set_id와 candidate_expires_at은 Plan 밖의 data 필드로 반환해 기존 `Plan.refresh_after` 의미를 바꾸지 않는다.

### ReplanInput

`conversation_id`, `revision`, `confirmation_id`, `trip`, `previous_plan`, `current_origin_place_id`, `reason`, `user_confirmed`를 모두 보낸다. reason은 missed_connection/route_changed/manual이다.

- trip과 previous_plan은 서버 active_selected_plan snapshot에 대응해야 한다. previous_plan은 기존 네 필드 요약이다. 선택이 없거나 값이 다르면 409 SELECTION_MISMATCH다.
- 계산용 effective trip은 기존 trip의 origin_place_id만 current_origin_place_id로 대체한다. 나머지 목적지·종류·날짜·마감·여유·이동수단을 유지한다. effective trip은 이번에 확인한 조건과 정확히 같아야 한다.
- 다른 조건까지 바꾸려는 요청은 새 interpret→confirm→plan 흐름으로 처리한다. 이전 선택은 새 선택 전까지 보존한다.
- 현재 출발점 변경은 interpret에서 초안에 반영한 후 확인한다. replan 안에서 몰래 해석·수정하지 않는다.
- 서버는 previous_plan 시각을 임의의 비교 사실로 받지 않고 자신의 선택 snapshot과 대조한다. 이 부분은 기존 stateless 설명의 개정 제안이다.
- 성공은 새 후보와 기존 선택 대비 comparison만 생성한다. 추천과 다른 후보를 선택하면 추천 전용 비교 문구를 숨기거나 서버의 해당 후보 값으로 별도 설명한다.

### SelectInput

`conversation_id`, `revision`, `candidate_set_id`, `option_id`, `evidence`가 필수다. evidence 구조는 ConfirmInput과 같다. MCP는 elicitation으로 실제 선택된 option_id를 받으며 모델의 추천을 선택 결과로 변환하지 않는다.

서버는 후보가 현재 대화의 최신 집합인지, 현재 확인 조건에 속하는지, 유효한 option인지 검사한다. 만료나 조건 변경 후에는 선택하지 않는다. 성공은 selected snapshot과 revision만 갱신하며 경로를 재계산하지 않는다.

### ConversationView

data는 다음 키를 모두 포함하고 없는 상태는 null로 표시한다.

- `draft`: trip_draft(TripDraft), normalized_trip 또는 null, draft_revision, conditions_hash 또는 null, expires_at. 확인 성공 뒤에는 draft 전체가 null이다.
- `confirmation`: confirmation_id, conditions_hash, confirmed_revision, expires_at. 확인 조건의 TripRequest는 `confirmed_trip`에 둔다.
- `confirmed_trip`: TripRequest 또는 null.
- `candidate_set`: candidate_set_id, plan, conditions_hash, expires_at 또는 null.
- `active_selected_plan`: plan_id, option_id, trip, 선택 후보 snapshot `option`, candidate_set_id, selected_at, expires_at 또는 null.

approval evidence 원문, 원문 대화, 키·request hash·DB 내부 컬럼은 조회 응답에 노출하지 않는다. 만료된 하위 상태는 null로 반환한다. 후보가 없다는 이유만으로 active_selected_plan을 지우지 않는다. GET은 수명을 늘리지 않는다.

## 2. 멱등성·초기 요청

상태 변경 POST는 요청 헤더 `Idempotency-Key`의 UUIDv4 표준 36자가 필수다. 서버가 형식 검증한 키는 성공·상태 오류 응답 헤더에 동일하게 반환한다. 누락·형식 오류에는 안전하게 반향할 유효 키가 없으므로 반환하지 않는다. JSON envelope에는 키를 추가하지 않는다.

키는 전역 UNIQUE로 제안한다. 같은 키의 다른 method/path/body/대화/revision은 409 IDEMPOTENCY_KEY_REUSED다. 객체 키 순서와 공백만 canonicalization으로 흡수한다. 최초 request_started_at, evidence 시각, 배열 순서도 원본에서 유지한다.

초기 키를 조회할 때 요청에 conversation_id가 없더라도 이미 저장된 성공 대화를 찾아 같은 UUID를 반환한다. 처음 보는 초기 키는 request_started_at이 서버보다 30초 넘게 미래이면 422, 5분 넘게 과거이면 410 INITIAL_REQUEST_EXPIRED로 거부한다. 이미 성공한 키는 먼저 연결된 대화 생존을 확인하므로 유효한 대화의 replay가 5분 제한 때문에 거부되지 않는다.

동일 키 재생은 stale revision보다 우선한다. 대화 만료는 replay보다 우선한다. 존재한 적 없거나 tombstone까지 삭제된 명시적 ID는 404다. 초기 키 매핑 제거 후의 예전 최초 요청은 시작시각 규칙으로 차단한다. 자세한 커밋·정리 순서는 [데이터 모델](../data-model.md)을 따른다.

replay는 최초 HTTP status·body를 그대로 반환한다. request_id/server_time/revision을 최신값으로 다시 쓰지 않는다. 응답 헤더의 키도 그대로다. 따라서 replay 응답은 최신 상태 조회 결과와 다를 수 있다.

## 3. 응답과 오류

기존 `status/data/error/meta` envelope와 meta.request_id/server_time/api_version/is_demo를 유지한다. 정상 업무 결과는 HTTP 200이며, unavailable의 data는 null이다. 잘못된 요청과 서버 장애는 error다. MIME·JSON·필수 키·status/HTTP/data 조합을 MCP에서 검증한다.

| HTTP | code | 동작 |
|---|---|---|
| 422 | VALIDATION_ERROR | 잘못된 구조·키·path/body·시각 입력. 자동 재시도 없음. |
| 422 | USER_CONFIRMATION_REQUIRED | 확인 없음/만료/조건 불일치, false 또는 누락된 flag, 승인 증거 없음. provider 호출 없음. |
| 409 | CONVERSATION_VERSION_CONFLICT | 새로운 요청의 오래된 revision. GET state 후 사용자 의도 재확인. |
| 409 | IDEMPOTENCY_KEY_REUSED | 같은 키의 다른 요청. 원래 요청으로만 복구하거나 새 사용자 동작으로 새 키 사용. |
| 409 | SELECTION_MISMATCH | 다른 대화/교체된 후보/없는 option 또는 이전 선택 요약 불일치. 최신 상태를 확인한다. |
| 409 | APPROVAL_REUSED | 이전 interaction_id를 새 키·새 승인에 재사용. 다시 실제 승인 필요. |
| 404 | CONVERSATION_NOT_FOUND | 미존재 또는 hard delete 후 ID. 과거 상태 복원 금지. |
| 410 | CONVERSATION_EXPIRED | tombstone 보존 중인 대화. 과거 성공 replay 금지. |
| 410 | CANDIDATE_SET_EXPIRED | 대상이 현재 후보와 일치하지만 deadline/현재 출발 가능성이 만료됨. 기존 선택 보존. |
| 410 | INITIAL_REQUEST_EXPIRED | 보존 기록 없는 오래된 초기 요청. 자동으로 새 대화 생성 금지. |
| 502 | UPSTREAM_RESPONSE_INVALID | 서버가 provider 형식 불량을 유효 envelope로 알리는 오류. retryable=false이며 해당 요청의 미적용을 보장한다. MCP에서 HTTP 응답 자체의 파손을 감지한 적용 불명과 구별한다. 원문 HTML·stack 노출 금지. |
| 503/504 | 기존 provider unavailable/timeout 코드 | 유효 envelope에서 retryable=true인 경우만 제한적 재시도. |
| 504 | REQUEST_TIMEOUT (T001 미확정 권장안) | 서버 전체 처리 예산 소진. 미적용이 보장된 경우만 error, retryable=true로 반환한다. 기존 외부 요청 UPSTREAM_TIMEOUT과 구별한다. |

신규 오류 코드는 이 제안의 일부다. 구현 전 API_SPEC 오류표와 관련 예제를 함께 갱신한다. 확인·선택의 순서는 대화 생존→동일 키 replay→새 요청 revision→대상/수명/evidence다. 새 revision을 가진 만료 후보는 410, 오래된 revision부터 보내면 409이므로 테스트에서 상태를 구분한다.

오류 message는 한국어이고 분기는 code로 한다. details는 없으면 []다. 형식이 유효한 백엔드 업무 오류를 MCP protocol 오류로 바꾸지 않는다. HTTP 200 unavailable은 성공 계획이 아니다. 비200 unavailable 등 계약에 없는 조합은 MCP의 UPSTREAM_RESPONSE_INVALID 진단 대상이다. POST 전송 뒤 적용 여부가 불명확하면 대표 오류 OUTCOME_UNKNOWN으로 보류하며 성공 또는 미적용으로 단정하지 않는다.

## 4. 재시도와 제한시간

- HTTP 시도당 GET 15초, POST 30초. 재시도 사이 500ms. 같은 논리 HTTP 요청당 자동 추가 시도는 최대 1회다.
- 허용: 연결 실패·timeout, 또는 **유효한** error envelope에 retryable=true인 502/503/504.
- 금지: 모든 4xx, 409/410/422, retryable=false, 잘못된 JSON·schema·응답 헤더 키 불일치, status 조합 불일치, 업무상 unavailable.
- HTTP client의 숨겨진 transport retry를 끄고 MCP가 한 곳에서 관리한다. backend workflow는 자동 재시도하지 않는다. provider 내부 호출은 해당 요청의 남은 서버 예산 안에서 관리하고 004와 중첩되지 않게 합의한다.
- GET 한 단계의 최대 HTTP 대기는 30.5초, POST는 60.5초다. 확인·계산은 별도 논리 HTTP 요청으로 키가 서로 다르다.
- 적용 여부를 확정할 수 없고 더 이상의 자동 시도가 허용되지 않으면 시도 횟수와 관계없이 결과 미수신으로 보류한다. 잘못된 POST 응답은 첫 시도부터 보류한다. 서버 성공 여부를 모른다는 이유로 새 키를 만들어 자동 계산하지 않는다. 세부 복구는 [MCP 계약 §5](mcp-contract.md)를 따른다.

### 서버 처리 예산과 원자 확정

| 대상 | 예산 | 책임 |
|---|---|---|
| health/capabilities | 3초 | 백엔드 담당 |
| places | 10초 | 백엔드 담당 |
| interpret/plan/replan | 25초 | 백엔드 담당, 중첩 provider 예산은 004와 조율 |

측정 범위는 해당 핸들러 진입부터 결과 검증·상태 확정까지의 단조 경과시간이다. 네트워크 전달과 사용자 elicitation 대기는 제외한다. provider별 호출에 전체 예산을 새로 부여하지 않는다. 상태 GET·confirm·select의 별도 SLA를 이번 수정에서 추가하지 않는다.

원자적 확정 지점의 경과시간이 제한 이상이면 새로운 domain 상태·revision·updated_at·TTL·성공 replay 기록을 적용하지 않는다. timeout 응답 후 작업이 늦게 commit하지 못하게 해야 하며 취소 요청만으로 이를 보장했다고 보지 않는다. 제한 안에 이미 commit한 성공은 응답 전달이 늦어도 보존하고 동일 키 replay로 회수한다. confirm 성공 뒤 plan timeout은 plan 직전 상태와 비교하며 confirm을 되돌리지 않는다. 독립적인 자연 만료 처리는 실패에 의한 변경과 구별한다.

T064에서 각 예산의 직전·정확한 경계·초과, provider 지연·늦은 성공·이미 commit한 응답 지연을 시간 제어 가능한 검증으로 확인한다. 기존 timeout 처리와 테스트를 T004에서 먼저 조사해 재사용하고 실제 경로를 quickstart에 기록한다. 새 REQUEST_TIMEOUT은 T001 합의 및 T002 공통 오류표·예제 동시 반영 후에만 구현한다.

## 5. 합의 후 변경할 문서와 코드

API_SPEC의 필드·상태 메타·새 경로·stateless 설명·retry 중복 문구·404/410 규칙을 한 번에 맞춘다. 공통 examples의 request 안에 들어간 Idempotency-Key는 headers로 옮기고, candidate 만료는 select 오류 사례로 만든다. 002 상태·계약 문서와 HTTP 연결 안내도 같은 결정으로 동기화한다.

현재 형식과 제안 형식을 동시에 추측해서 수용하는 숨은 adapter를 MCP에 두지 않는다. 양측 버전과 fixture를 같은 계약으로 전환한 뒤 통합하며, 전환 전후 테스트 결과를 별도로 남긴다.
