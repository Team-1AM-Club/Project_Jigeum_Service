# API Contract Summary: Backend MVP Implementation

**Feature**: [specs/002-backend-mvp-implementation/spec.md](../spec.md)

이 문서는 Spec Kit 계약 검증 관점에서 백엔드 MVP의 핵심 API 계약을 요약한다. API_SPEC.md를 대체하지 않으며, 실제 요청/응답 스키마와 예제는 API_SPEC.md와 Docs/api/examples.json을 기준으로 한다.

## 1. 공통 응답 봉투

모든 응답은 아래 구조를 사용한다.

```json
{
  "status": "ok" | "needs_confirmation" | "unavailable" | "error",
  "data": { ... } | null,
  "error": null | {
    "code": "string",
    "message": "string",
    "retryable": true | false,
    "details": []
  },
  "meta": {
    "request_id": "string",
    "server_time": "datetime",
    "api_version": "v1",
    "is_demo": true | false,
    ...
  }
}
```

규칙:
- 성공 응답도 error: null을 포함한다.
- 연동 계층은 message 문자열 비교로 로직을 분기하지 않는다.
- 제공자·모델 비밀값·API 키는 응답에 포함하지 않는다.
- 데모 데이터면 meta.is_demo = true다.

## 2. 상태 분기 요약

| status | HTTP | 의미 |
|---|---|---|
| ok | 200 | 계산/조회 성공 |
| needs_confirmation | 200 | 입력 해석 API가 확인 질문을 반환 |
| unavailable | 200 | 지원 범위·데이터·경로 제한으로 요청 조건을 만족 불가 |
| error | 4xx/5xx | 전송·검증·장애 |

## 3. 주요 엔드포인트 매핑

| MCP 도구 | REST 엔드포인트 | 용도 |
|---|---|---|
| get_capabilities | GET /api/v1/capabilities | 기능·지원 범위·기본값 확인 |
| search_places | GET /api/v1/places | 출발지·목적지 후보 검색 |
| interpret_trip | POST /api/v1/mobility/interpret | 자연어 이동 조건 구조화 |
| plan_journey | POST /api/v1/journeys/plan | 확인된 조건으로 계획 계산 |
| replan_journey | POST /api/v1/journeys/replan | 재탐색 대안 계산 |

health는 내부 연결 확인용이다.

## 4. 핵심 요청/응답 계약 포인트

### interpret
- 자연어를 구조화해 TripDraft, ready_for_plan, missing_fields, questions, applied_defaults, summary를 반환한다.
- ready_for_plan=true는 동의로 간주하지 않는다.
- 필수 정보가 완성돼도 사용자 최종 확인 전에는 /journeys/plan을 호출하지 않는다.

### plan
- user_confirmed=true일 때만 계산한다.
- buffer는 total_duration_minutes와 legs에 이미 반영된 값으로 제공하며, 다시 더하거나 빼지 않는다.
- meta에 conversation_id, revision, expires_at을 포함할 수 있다.

### replan
- 새 Plan과 이전 선택 대비 comparison을 반환한다.
- 사용자 선택 전에는 기존 계획을 자동 교체하지 않는다.
- 재탐색 실패·취소는 기존 기록을 삭제하지 않으며, 이전 경로가 여전히 유효하다는 보장으로 표시하지 않는다.

## 5. 주요 오류 코드

| HTTP | code | 연동 계층 동작 |
|---|---|---|
| 400 | INVALID_JSON | 요청 형식 수정 |
| 404 또는 410 | CONVERSATION_EXPIRED | 없거나 만료된 conversation_id로 요청 |
| 409 | CONVERSATION_VERSION_CONFLICT | revision 불일치, 최신 상태 재수신 후 재시도 |
| 422 | VALIDATION_ERROR | 입력 필드 오류 |
| 422 | USER_CONFIRMATION_REQUIRED | 이동 조건 확인 대화로 복귀 |
| 422 | PLACE_NOT_RESOLVABLE | 이전 장소 ID 해석 불가, 재검색·선택 |
| 429 | RATE_LIMITED | Retry-After만큼 대기 |
| 503 | ROUTING_PROVIDER_UNAVAILABLE | 교통 조회 일시 실패 |
| 503 | PLACE_PROVIDER_UNAVAILABLE | 장소 검색 일시 실패 |
| 503 | AI_UNAVAILABLE | 자연어 해석 실패 |
| 502 | UPSTREAM_RESPONSE_INVALID | 제공처/모델 결과 검증 실패 |
| 504 | UPSTREAM_TIMEOUT | 외부 요청 시간 초과 |
| 500 | INTERNAL_ERROR | 일반 오류 안내 + request_id |

unavailable 응답 예시 코드:
- OUT_OF_SERVICE_AREA
- APPOINTMENT_TIME_UNSUPPORTED
- LAST_JOURNEY_UNSUPPORTED
- NO_FEASIBLE_JOURNEY
- BUFFER_REQUIREMENT_NOT_MET


## 6. Idempotency-Key 계약

상태 변경 요청(POST /api/v1/mobility/interpret, POST /api/v1/journeys/plan, POST /api/v1/journeys/replan)의 멱등성을 보장하기 위한 계약.

### Idempotency-Key 형식과 전달
- MCP 서버가 상태 변경 MCP 도구 호출 시작 시 UUID v4 표준 문자열 36자로 Idempotency-Key를 생성한다.
- MCP는 HTTP 요청 헤더 `Idempotency-Key`로 백엔드에 전달한다.
- 백엔드 응답 시 응답 헤더 `Idempotency-Key`로 동일한 키를 반환한다.
- 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않는다 (SC-013, SC-014).
- Idempotency-Key 누락·형식 오류(UUID v4 36자 아님)는 422 VALIDATION_ERROR로 처리한다.

### payload hash
- 각 상태 변경 요청마다 payload hash를 계산해 저장한다.
- hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body.
- body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256으로 hash한다.
- MCP는 최초 요청 body와 expected revision을 보관하며, 같은 논리적 요청 재시도 시 그대로 재전송한다.
- 백엔드 canonicalization은 JSON 객체 키 순서와 공백 차이만 흡수한다. 배열 순서, null과 필드 생략, 값 변경은 동일하다고 간주하지 않는다.

### 동일 key 처리
- 같은 Idempotency-Key + 같은 payload hash 재시도는 최초 저장 응답을 반환한다 (effectively-once).
- 유효한 conversation에서 이미 성공한 동일 key·동일 payload 재요청은 stale revision 검사보다 먼저 처리한다.
- 같은 Idempotency-Key로 다른 요청이 이미 처리됐으면 409 IDEMPOTENCY_KEY_REUSED로 처리한다 (retryable: false).
- 만료된 conversation에서 동일 key로 요청하면 410 CONVERSATION_EXPIRED를 반환한다 (stale revision보다 우선).

### 백엔드 저장
- conversation_id + idempotency_key에 UNIQUE 제약을 둔다.
- 상태 변화와 idempotency 기록은 같은 DB 트랜잭션으로 커밋한다.

## 7. 상태 오류 5종

| HTTP | code | 의미 | retryable |
|---|---|---|---|
| 404 | CONVERSATION_NOT_FOUND | 존재한 적 없는 conversation_id로 요청함 | false |
| 409 | CONVERSATION_VERSION_CONFLICT | 이전 revision으로 상태 변경 시도 (현재 revision보다 낮음) | false |
| 409 | IDEMPOTENCY_KEY_REUSED | 같은 Idempotency-Key로 다른 payload 요청이 이미 처리됨 | false |
| 410 | CONVERSATION_EXPIRED | 없거나 만료된 conversation_id로 요청함 | false |
| 410 | CANDIDATE_SET_EXPIRED | conversation은 유효하나 후보 집합만 만료됨 | false |

규칙:
- 없거나 만료된 conversation은 404 또는 410 중 하나로 통일 → **410 CONVERSATION_EXPIRED**로 최종 확정.
- hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리한다.
- 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.
- 409, 410은 자동 재시도하지 않는다.

## 8. Provider 호출 순서 5단계

provider가 필요한 상태 변경 요청 시 다음 5단계 순서를 따른다.

1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
3. provider 성공 결과를 검증한다.
4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

규칙:
- provider 호출은 DB 트랜잭션 외부에서 수행한다.
- provider 성공 후에만 짧은 트랜잭션에서 재확인 후 원자 커밋한다.
- provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다.
- provider 실패는 domain 상태·revision·updated_at·TTL을 갱신하지 않는다.
- 백엔드는 workflow 수준의 자동 재시도를 하지 않으며, provider 호출을 DB 트랜잭션 내부에 포함하지 않는다.

## 9. 재시도 정책

MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 확정한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.

적용 대상:
- 네트워크 연결 실패
- timeout
- 계약상 retryable=true인 HTTP 502/503/504

적용 제외:
- 4xx 응답
- 409 CONVERSATION_VERSION_CONFLICT
- 409 IDEMPOTENCY_KEY_REUSED
- 410 CONVERSATION_EXPIRED
- 410 CANDIDATE_SET_EXPIRED
- 검증 실패
- invalid response (무효한 JSON 등)

재시도 방식:
- 같은 Idempotency-Key와 같은 body로 재시도한다.
- MCP는 최초 요청 body와 expected revision을 보관하고, 같은 논리적 요청 재시도 시 그대로 재전송한다.
- 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.

## 10. 계약 예제 참조

이 계약의 예제 fixture는 Docs/api/examples.json을 사용한다.

주요 case id:
- health
- capabilities
- places_found
- interpret_needs_confirmation
- interpret_ready
- plan_appointment
- plan_last_journey
- replan_late
- last_journey_unsupported
- no_feasible_journey
- invalid_arrival_preference
- provider_unavailable
- confirmation_required
- conversation_version_conflict
- conversation_expired

연동 계층은 Mock 모드에서 case.response와 case.http_status를 사용한다. 실제 호출로 전환할 때는 JSON 구조와 결과 분기 코드를 유지하고 Base URL/데이터 연결만 바꾼다.



## 5. Idempotency-Key와 대화 상태 계약

### Idempotency-Key

- MCP가 각 상태 변경 요청에 Idempotency-Key를 생성해 HTTP 헤더 `Idempotency-Key`로 전달한다. 형식은 UUID v4 표준 문자열(36자)이다.
- 백엔드는 응답 시 응답 헤더 `Idempotency-Key`로 동일한 키를 돌려준다. 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않는다.
- Idempotency-Key 누락·형식 오류는 422로 처리한다.
- 같은 Idempotency-Key로 다른 요청이 이미 처리됐으면 409 IDEMPOTENCY_KEY_REUSED로 처리한다. retryable은 false다.

### 상태 오류 5종

| HTTP | code | 의미 |
|---|---|---|
| 404 | CONVERSATION_NOT_FOUND | 존재한 적 없는 conversation_id로 요청함. 새 대화로 다시 시작한다. |
| 409 | CONVERSATION_VERSION_CONFLICT | 전달한 revision이 서버의 현재 revision과 다르다. 최신 상태를 다시 받아 재시도해야 한다. |
| 409 | IDEMPOTENCY_KEY_REUSED | 같은 Idempotency-Key로 다른 요청이 이미 처리됐다. 같은 키로 다른 요청을 재시도하지 않는다. |
| 410 | CONVERSATION_EXPIRED | conversation이 만료됐다. 새 대화로 다시 시작한다. |
| 410 | CANDIDATE_SET_EXPIRED | conversation은 유효하지만 후보 집합이 만료됐다. 기존 확인 조건으로 새 계획을 요청한다. |

상태 관련 오류는 CONVERSATION_NOT_FOUND, CONVERSATION_EXPIRED, CANDIDATE_SET_EXPIRED, CONVERSATION_VERSION_CONFLICT, IDEMPOTENCY_KEY_REUSED로 구분한다. hard delete 이후에는 404 CONVERSATION_NOT_FOUND를 반환하고, 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.

### payload hash와 동일 key 우선순위

- 각 상태 변경 요청마다 payload hash를 계산해 저장한다. hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body. body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256을 hash한다.
- 같은 key + 같은 payload 재시도는 최초 응답을 반환한다(effectively-once).
- 같은 key + 다른 payload는 409 IDEMPOTENCY_KEY_REUSED로 처리한다.
- 유효한 conversation에서 이미 성공한 동일 key·동일 payload 재요청은 stale revision 검사보다 먼저 처리한다.

### provider 호출 순서 5단계

1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
3. provider 성공 결과를 검증한다.
4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다.

### tombstone 계약

- expires_at <= 서버 현재 시각이면 즉시 만료로 판단한다.
- 만료 시 확인 조건·후보·선택 계획 payload를 제거하고, conversation_id·마지막 revision·expired_at만 tombstone으로 보관한다.
- tombstone은 24시간 유지 후 hard delete한다. hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리한다.
- 동일 conversation_id의 만료 처리는 멱등하게 수행한다. 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환하거나, 별도 테이블 사용 시 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다.
- tombstone 전환으로 사용자 revision은 증가시키지 않고 마지막 revision을 유지한다.

### 재시도 정책

- MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 확정한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.
- 네트워크 연결 실패·timeout 또는 계약상 retryable=true인 502/503/504에만 적용한다.
- 같은 Idempotency-Key와 같은 body로 재시도한다.
- 4xx·409·410·검증 실패·invalid response는 자동 재시도하지 않는다.
## 7. 계약 변경 규칙

- 공개 API의 경로·필드·상태·오류 의미를 변경하려면 먼저 합의하고 API_SPEC.md와 Docs/api/examples.json을 함께 갱신한 뒤 구현한다.
- MCP 도구 스키마·오류 매핑은 백엔드 API 계약과 별개로 두 개발자가 구현 전에 합의한다.
- 계약서 예제는 실제 데이터가 아니라 개발용 fixture이며, meta.is_demo=true로 표시한다.
