# Quickstart: Backend MVP Implementation

**Feature**: [specs/002-backend-mvp-implementation/spec.md](../spec.md)

이 문서는 백엔드 MVP가 계약대로 동작하는지 빠르게 검증하기 위한 실행 가이드다. 전체 구현 코드나 테스트 스위트 대신, 핵심 흐름을 재현할 수 있는 최소 검증 시나리오만 담는다.

## 목표

- health/capabilities 응답 구조가 계약과 맞는지 확인한다.
- places 검색 → interpret → plan의 최소 흐름을 계약 JSON으로 확인한다.
- 데모 여부, 지원 범위, 오류 분기를 올바르게 구분하는지 확인한다.
- 아직 구현되지 않은 항목과 그 이유를 구분한다.

## 사전 준비

1. 저장소를 복제하고 기능 브랜치로 전환한다.
   ```bash
   git clone --branch develop https://github.com/Team-1AM-Club/Project_Jigeum_Service.git
   cd Project_Jigeum_Service
   git switch -c feature/backend-mvp
   ```
2. Python 환경을 준비한다(정확한 의존성/버전은 구현 시점에 확정).
3. 필요 시 환경 변수를 설정한다. 실제 키·비밀 값은 저장소에 넣지 않는다.
   ```bash
   # 예시 placeholder. 실제 값은 합의 후 설정
   export JIGEUM_BASE_URL=http://127.0.0.1:8000
   ```
4. 서버를 기킨다(명령은 구현 시점에 확정).
   ```bash
   # 예시
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   ```

## 최소 검증 시나리오

### 1. 서버 연결 확인

```bash
curl -s http://127.0.0.1:8000/api/v1/health | jq .
```

기대 결과:
- status = "ok"
- data.service = "jigeum-api"
- data.health = "ok"
- meta에 request_id, server_time, api_version, is_demo 등 포함

### 2. 기능 지원 확인

```bash
curl -s http://127.0.0.1:8000/api/v1/capabilities | jq .
```

기대 결과:
- timezone = "Asia/Seoul"
- place_search.available, interpretation.available, appointment.available, last_journey.available 포함
- transport_modes, max_options, defaults, buffer_policy, limitations 포함
- 데모 환경이면 is_demo = true

### 3. 장소 검색

```bash
curl -s "http://127.0.0.1:8000/api/v1/places?query=%ED%85%8C%EC%8A%A4%ED%8A%B8" | jq .
```

기대 결과:
- status = "ok"
- data.query, data.places, data.source, data.has_more 포함
- places는 place_id, name, address, latitude, longitude 포함

### 4. 자연어 해석(확인 필요)

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/mobility/interpret \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "natural_language": "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야.",
    "conversation_id": "conv-quickstart-001"
  }' | jq .
```

기대 결과:
- status = "needs_confirmation"
- data.draft, ready_for_plan=false, missing_fields, questions 포함
- 장소 미확정을 이유로 확인 질문을 반환

### 5. 확인 완료 후 계획 요청

해석에서 얻은 확인 조건으로 context를 채운 뒤, 사용자 확인까지 마치고 plan을 요청한다.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/plan \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "conversation_id": "conv-quickstart-001",
    "origin_place_id": "fixture:place-a",
    "destination_place_id": "fixture:place-b",
    "arrival_deadline": "2026-09-13T19:00:00+09:00",
    "arrival_preference_minutes": 10,
    "transport_mode": "subway",
    "max_options": 3,
    "user_confirmed": true
  }' | jq .
```

기대 결과:
- status = "ok"
- data.plan 포함
- plan_id, generated_at, refresh_after, trip, origin, destination, target_arrival_at, recommended_option_id, options 포함
- options는 1~3개
- buffer.total_minutes가 total_duration_minutes에 포함되어 있고 별도 재가산되지 않음

### 6. 재탐색(선택 적용 전)

재탐색은 새 계획을 줄 뿐, 기존 선택 계획을 자동 교체하지 않는다.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/replan \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "conversation_id": "conv-quickstart-001",
    "origin_place_id": "fixture:place-a",
    "destination_place_id": "fixture:place-b",
    "arrival_deadline": "2026-09-13T19:00:00+09:00",
    "arrival_preference_minutes": 10,
    "transport_mode": "subway",
    "previous_plan": {
      "plan_id": "plan-fixture-1",
      "selected_option_id": "option-a",
      "recommended_leave_at": "2026-09-13T18:10:00+09:00",
      "total_duration_minutes": 42
    },
    "current_origin_place_id": "fixture:place-a",
    "reason": "missed_connection",
    "user_confirmed": true
  }' | jq .
```

기대 결과:
- status = "ok"
- data.plan과 data.comparison 포함
- arrival_change_minutes, leave_change_minutes, summary 포함
- 사용자가 새 후보를 선택하기 전까지 기존 계획이 자동 교체되지 않음

## 데모/실제 구분 확인

- 응답이 데모 데이터면 meta.is_demo = true여야 한다.
- 데모 출처가 포함되면 sources에 basis = "demo"가 표시되어야 한다.
- 실제 데이터 조회 실패를 데모 결과로 자동 대체하지 않는지 확인한다.

## 오류/불가 케이스 확인

- 미확인 상태/필수 필드 누락 시 422 USER_CONFIRMATION_REQUIRED 또는 VALIDATION_ERROR
- 지원 범위 밖/경로 없음은 200 unavailable로 구분
- 서버 장애/시간 초과는 5xx 계열 오류 코드와 retryable 표시로 구분

검증은 API_SPEC.md의 오류 표와 examples.json의 해당 case id를 함께 본다.

## 확인 포인트

- [ ] health/capabilities가 계약 envelope과 상태 분기를 따른다.
- [ ] places 응답이 ID·출처·기준시각을 포함한다.
- [ ] interpret가 needs_confirmation을 올바르게 반환한다.
- [ ] plan이 user_confirmed=true일 때만 계산되고 buffer 중복 가산이 없다.
- [ ] replan이 비교 정보를 주되 기존 선택을 자동 교체하지 않는다.
- [ ] 데모/실제, 지원 가능/불가, 오류/불가해가 구분되게 응답한다.

## 아직 구현/확정되지 않은 항목



## 추가 검증 시나리오: 대화 상태·Idempotency-Key (contract 검증)

아래 시나리오는 contracts/api-contract.md의 Idempotency-Key·상태 오류 5종·Provider 호출 순서 5단계 계약을 검증한다. 완전한 통합 테스트가 아니라 contract 준수 여부를 빠르게 확인하는 용도다.

### 대화 상태 생성·revision 증가 확인

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/mobility/interpret \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "text": "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해.",
    "reference_time": "2026-09-14T18:00:00+09:00",
    "timezone": "Asia/Seoul"
  }' | jq '{conversation_id: .meta.conversation_id, revision: .meta.revision, expires_at: .meta.expires_at}'
```

기대 결과:
- meta.conversation_id: 유효한 conversation 식별자
- meta.revision: 1 이상 (최초 생성 시 1)
- meta.expires_at: 미래 시각의 만료 시각
- 응답 헤더 `Idempotency-Key`: 요청 시 전달한 UUID와 동일

### Idempotency-Key 중복 요청 idempotency 확인

```bash
IDEM_KEY="<이전 요청에서 받은 key 또는 새 UUID>"
curl -s -X POST http://127.0.0.1:8000/api/v1/mobility/interpret \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{동일한 요청 body}' | jq '{status, data, meta}'
```

기대 결과:
- 상태 변경 없이 최초 요청과 동일한 응답 반환 (effectively-once)
- response_body는 최초 요청과 동일
- 동일 key + 다른 body → 409 IDEMPOTENCY_KEY_REUSED

### 만료 conversation 요청 시 410 확인

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/plan \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "conversation_id": "<만료된 conversation_id>",
    "user_confirmed": true,
    "trip": {...}
  }' | jq '{status, error}'
```

기대 결과:
- status = "error"
- error.code = "CONVERSATION_EXPIRED"
- HTTP 410

### 이전 revision 요청 시 409 확인

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/plan \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "conversation_id": "<유효한 conversation_id>",
    "user_confirmed": true,
    "trip": {...}
  }' | jq '{status, error}'
```

기대 결과 ( conversation 현재 revision이 3 이상일 때 ):
- status = "error"
- error.code = "CONVERSATION_VERSION_CONFLICT"
- HTTP 409

### 후보만 만료된 경우 410 CANDIDATE_SET_EXPIRED 확인

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/plan \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "conversation_id": "<후보만 만료된 conversation_id>",
    "user_confirmed": true,
    "trip": {...}
  }' | jq '{status, error}'
```

기대 결과:
- status = "error"
- error.code = "CANDIDATE_SET_EXPIRED"
- HTTP 410
- conversation과 confirmed_conditions, active_selected_plan은 유지됨 (상태 변경 없음)


아래는 이 quickstart만으로 검증할 수 없으며, 구현 전에 합의/확정이 필요하다.

- 실제 장소·교통 API 서비스명·엔드포인트·키·한도·호출 가이드
- Solar 모델 ID·호출 경로·접근 권한
- 실제 Buffer 정책 버전·항목·분
- 배포 Base URL·포트·환경변수 이름·접근 제어
- 대화 문맥·선택 상태의 저장 위치·수명·소유권

이 항목들은 임의 가정으로 고정하지 않고, 사용자에게 질의해 확정한다.
