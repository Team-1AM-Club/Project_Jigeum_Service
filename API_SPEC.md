# 지금 — MCP 서비스용 백엔드 계산 API 명세 v0.1

- 작성일: 2026-09-12 / 제품 방향 설명 갱신: 2026-09-14
- 상태: **구현을 위한 계약 초안**. 실행·배포 완료를 의미하지 않는다.
- 제품: 지금은 MCP로 제공한다. Hermes는 개발·시연용 MCP 클라이언트이며 독립 사용자 클라이언트를 만들지 않는다.
- 담당: 본인은 MCP 도구·Hermes 연결·확인/선택 흐름·시연, 친구는 FastAPI·서비스 Agent·교통 데이터·계산·배포.
- 범위: MCP 연결 계층이 호출하는 REST/JSON 요청별 계산 API. 이 문서 자체는 MCP 프로토콜 계약이 아니다.
- 이번 정정은 제품 형태·담당·사용 흐름의 설명 변경이다. 기존 경로·필드·상태·오류·JSON 예제는 유지한다.
- 예제 파일: [Docs/api/examples.json](Docs/api/examples.json). 모든 예제는 가상 역·가상 운행 데이터이며 meta.is_demo=true다.

## 1. 책임과 적용 범위

Hermes는 사용자와 대화하고 MCP 도구를 호출한다. MCP 연결 계층은 구조화 입력 검증, REST 요청, 결과·오류 전달을 맡는다. 이 문서의 '연동 계층'은 MCP 서버와 Hermes의 입력·확인·결과 전달 흐름을 통칭하며, 양쪽의 세부 상태 소유권은 구현 전에 합의한다.

FastAPI는 장소 조회, 자연어 구조화, 교통 조회, 코드 기반 시간 계산, 사용자 요청 재탐색을 수행한다. 내부 MainAgent가 SubAgent를 지휘하고 필요한 Skill을 사용한다. Docker·Cloud Run과 기존 JSON 계산 계약을 유지한다.

Hermes의 개발·시연 모델은 Solar Pro4다. 백엔드의 AI 호출 설정은 별도 검증한다. 교통·백엔드 AI 비밀키는 백엔드 실행 환경에서 관리하며 도구 응답·설정 예제·로그에 넣지 않는다.

별도 UserData DB·회원가입·영구 이동 이력·출발/도착 버튼·자동 알림은 현재 범위에 포함하지 않는다. Journey CRUD와 사용자 계정 API도 정의하지 않는다. GPS·Push·Calendar·택시 최적화·자동 재탐색은 보류한다.

### 대화 문맥과 사용자 확인

- 기본 범위는 현재 대화의 초안·확인 조건·선택 계획이다. 서버는 과거 대화를 영구 저장하지 않는다.
- 필요한 context와 이전 계획 요약을 후속 요청에 명시적으로 전달한다. 재시작 후 자동 복원을 약속하지 않는다.
- ready_for_plan=true는 사용자 동의가 아니다. 최종 조건과 실제 사용자 확인 응답을 연결하고 조건 변경 시 재확인한다.
- user_confirmed=true를 모델이 생성하는 것만으로 동의 검증이 완성됐다고 보지 않는다. 구체적 강제 방식은 공동 설계·검증한다.
- 새 계획 조회와 적용을 구분하고 사용자가 후보를 선택한 뒤 현재 선택을 갱신한다.
- 공개 응답은 아래 JSON 구조를 유지한다. 자유 서술로 데이터·오류를 대체하지 않는다.
- MCP 스키마·오류 매핑은 별도 합의하고 REST 계약 변경이 필요하면 본 문서와 예제 JSON을 함께 갱신한다.

## 2. 연결 규칙

| 항목 | 계약 |
|---|---|
| Base URL | 배포 시 확정할 HTTPS 서버 주소 + `/api/v1` |
| MCP 연결 설정 | Base URL은 MCP 서버 실행 환경에 주입한다. localhost는 MCP 프로세스가 실행되는 호스트 기준이며 원격 백엔드 주소와 구분한다. |
| GET 요청 | `Accept: application/json` |
| POST 요청 | `Content-Type: application/json`, `Accept: application/json` |
| 문자·필드 | UTF-8, JSON 필드명은 snake_case |
| 시각 | 오프셋이 포함된 ISO 8601 문자열. 예: `2026-09-13T18:00:00+09:00` |
| 시간대 | MVP는 `Asia/Seoul`만 허용 |
| 날짜 | `YYYY-MM-DD`. 막차 운행일과 실제 승하차 날짜를 구분 |
| 시간 간격 | minutes 필드는 분 단위. 음수 허용 여부는 해당 필드 설명을 따른다. |
| 좌표 | WGS84, latitude / longitude를 별도 필드로 반환 |
| 선택값 | 문서에서 nullable로 명시한 필드만 null 허용 |
| 성공/업무 결과 | HTTP 200 + status로 분기 |
| 전송·검증·장애 | HTTP 4xx/5xx + status=error |
| 인증 | 이 초안은 사용자 계정 API를 정의하지 않는다. 공개 배포의 접근 제어·호출 제한은 별도 확인한다. 설정 예제나 사용자 대화에 고정 비밀키를 노출하지 않는다. |
| Idempotency-Key | 문자열. 상태 변경 요청에 MCP가 생성해 전달하는 UUID v4 표준 문자열(36자). 요청 헤더 `Idempotency-Key`로 전달하며, 응답 헤더에도 동일한 값을 반환한다. 응답 JSON envelope에는 중복 추가하지 않는다. 조회 전용 요청에는 불필요하며, 상태 변경 요청에서 누락되거나 형식이 잘못되면 422 VALIDATION_ERROR로 처리한다. 같은 key에 다른 요청이 이미 처리된 경우에는 409 IDEMPOTENCY_KEY_REUSED로 처리한다. |

해석의 상대 날짜는 요청의 `reference_time`을 기준으로 계산한다. 실제 경로 계획·재탐색의 현재 시각은 **서버 시각**이다. 연동 계층이 시뮬레이션 시각을 보내 실제 운행 계산을 과거로 돌리는 기능은 제공하지 않는다.

### Idempotency-Key 계약

- 생성 주체: MCP 서버가 상태 변경 MCP 도구 호출 시작 시 UUID v4로 생성한다. 모델이나 사용자에게 입력받지 않는다.
- 재사용 범위: 동일 MCP 호출 내부의 HTTP 재시도에서는 같은 키를 재사용한다. 새로운 논리적 사용자 동작에는 새 키를 생성한다.
- 전달 방식: HTTP 요청 헤더 `Idempotency-Key`로 전달한다. 조회 전용 요청에는 불필요하며, 확인·선택·재탐색 결과 적용 등 상태 변경 요청에는 필수다.
- 응답 반환: 백엔드는 응답 헤더에도 동일한 키를 반환한다. 응답 JSON envelope에는 같은 값을 중복 추가하지 않는다.
- 형식 요구: UUID v4 표준 문자열 36자를 사용한다. 필수 요청에서 누락되거나 형식이 잘못되면 기존 VALIDATION_ERROR 계약에 따라 422로 처리한다.
- 충돌 처리: 동일 key에 다른 요청이 이미 처리된 경우에는 HTTP 409, error.code `IDEMPOTENCY_KEY_REUSED`, message `Idempotency key was already used for a different request.`, retryable false로 처리한다. 클라이언트는 같은 키로 다른 요청을 재시도하지 않으며, 새 논리적 동작이면 새 키를 생성한다.

### payload hash 계약

- hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경에 영향을 주는 전체 JSON body를 포함한다.
- 제외: Idempotency-Key 자체, 서버 생성 request_id/server_time, tracing 헤더, 전송 시각 등 비즈니스 의미가 없는 값은 hash에서 제외한다.
- canonicalization: JSON은 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256을 사용한다.
- body 책임: MCP는 최초 요청 body와 expected revision을 보관한다. 같은 논리적 요청 재시도 시 그대로 재전송하며, 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.
- 동일성 판단: 백엔드 canonicalization은 JSON 객체 키 순서와 공백 차이만 흡수한다. 배열 순서, null과 필드 생략, 값 변경은 동일하다고 간주하지 않는다. user_confirmed 등 일부 필드만 선택적으로 hash하지 않는다.

### 동일 key 우선순위

- 유효한 conversation에서 이미 성공한 동일 key·동일 payload 재요청은 stale revision 검사보다 먼저 처리한다. 상태를 다시 변경하지 않고 저장된 응답을 반환한다.
- 단, conversation이 만료됐다면 과거 성공 응답을 복원하지 않고 410 CONVERSATION_EXPIRED로 처리한다.
- 상태 변경과 idempotency 결과 기록은 같은 DB 트랜잭션으로 커밋한다.

### 대화 상태 계약의 원칙

- 최초 요청의 conversation_id는 선택 사항이며, 없으면 백엔드가 생성한다.
- 백엔드는 관련 응답 meta에 conversation_id, revision, expires_at을 반환한다.
- 이후 확인·선택·재탐색 요청은 conversation_id와 클라이언트가 마지막으로 받은 revision을 전달한다.
- 상태 변경 성공 시 revision이 증가한다.
- 오래된 revision은 409 CONVERSATION_VERSION_CONFLICT로 처리한다.
- 없거나 만료된 대화는 410 CONVERSATION_EXPIRED로 처리한다.
- API 비밀키나 사용자 계정 정보는 이 계약에 포함하지 않는다.

### 재시도 책임

- MCP는 네트워크 연결 실패, timeout, 또는 계약상 retryable=true인 HTTP 502/503/504에 한해 최초 호출 후 최대 1회 자동 재시도할 수 있다.
- MCP 기본 재시도 정책은 자동 재시도 최대 1회, 대기 500ms로 한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.
- MCP는 같은 Idempotency-Key와 같은 body로 재시도하며, 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.
- 해석 가능한 오류 응답이 retryable=false이면 HTTP 상태만 보고 재시도하지 않는다.
- 409, 410, 검증 실패, invalid JSON/invalid response는 자동 재시도하지 않는다.
- 백엔드는 workflow 수준의 자동 재시도를 하지 않으며, provider 호출을 DB 트랜잭션 내부에 포함하지 않는다.


## 3. API 목록

아래 경로는 Base URL 뒤에 붙인다.

| Method | 경로 | 사용 시점 | 연동 계층이 사용하는 결과 |
|---|---|---|---|
| GET | `/health` | 설치·배포 확인 | API 서버 응답 여부 |
| GET | `/capabilities` | 연동 계층 시작·지원 여부 갱신 | 막차·장소·AI 지원 상태, 기본값, 제한 |
| GET | `/places?query=...` | 장소 확인·검색 | 선택 가능한 실제 장소 후보 |
| POST | `/mobility/interpret` | 자연어 입력·확인 답변 | 이동 조건 초안, 부족한 필드, 최대 3개 질문 |
| POST | `/journeys/plan` | 사용자가 이동 조건 확인 후 계산 | 후보 경로 1~3개, 권장 출발시각·근거 |
| POST | `/journeys/replan` | 놓침·변경 후 사용자가 재탐색 요청 | 새 계획과 이전 선택 대비 시각 변화 |

## 4. 공통 응답

모든 응답은 `status`, `data`, `error`, `meta`를 포함한다. 성공 응답에서도 error 키를 생략하지 않고 null로 둔다.

| status | HTTP | data | error | 연동 계층 처리 |
|---|---|---|---|---|
| ok | 200 | 해당 API 결과 | null | 결과 표시 |
| needs_confirmation | 200 | 해석 초안·질문 | null | 입력 확인 질문 전달 |
| unavailable | 200 | null | 업무 사유 | 미지원·데이터 부족·경로 없음 안내 |
| error | 4xx/5xx | null | 오류 정보 | 수정 또는 재시도 안내 |

`needs_confirmation`은 입력 해석 API가 반환한다. 계산 API에 잘못된 필수 필드를 보냈다면 조용히 보완하지 않고 HTTP 422를 반환한다.

### meta

| 필드 | 타입 | 의미 |
|---|---|---|
| request_id | string | 서버가 발급하는 요청 추적 ID |
| server_time | datetime | 응답 생성 시 서버 시각 |
| api_version | string | v1 |
| is_demo | boolean | 가상 데이터 사용 여부. true인 결과는 연동 계층에 시연 데이터 표시 |

`is_demo`는 클라이언트 요청 옵션이 아니다. 별도 개발/시연 환경에서만 true 결과를 반환한다. 실제 데이터 조회 실패 시 운영 서버가 임의로 Demo 결과로 전환해서는 안 된다.



상태 변경 응답의 응답 헤더 `Idempotency-Key`는 요청 시 전달받은 값과 동일하며, 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않는다.
### error

| 필드 | 타입 | 의미 |
|---|---|---|
| code | string | 연동 계층 분기용 안정적인 오류 코드 |
| message | string | 사용자에게 보여줄 한국어 안내 |
| retryable | boolean | 같은 입력으로 나중에 재시도할 수 있는지 |
| details | array | 필드별 오류 목록. 없으면 [] |
| details[].field | string | 예: trip.arrival_preference_minutes |
| details[].reason | string | 예: OUT_OF_RANGE |

연동 계층은 `message` 문자열 비교로 로직을 분기하지 않는다. 내부 스택·제공처 비밀 값·API 키는 응답에 포함하지 않는다.

## 5. 서버 상태와 기능 지원

### GET /health

API 프로세스가 요청에 응답하는지 확인한다. 교통 API·모델의 모든 상태가 정상이라는 보장은 아니다.

응답 예:

```json
{
  "status": "ok",
  "data": {
    "service": "jigeum-api",
    "health": "ok"
  },
  "error": null,
  "meta": {
    "request_id": "fixture-health",
    "server_time": "2026-09-13T18:00:00+09:00",
    "api_version": "v1",
    "is_demo": true
  }
}
```

### GET /capabilities

실제 서버 설정과 확인된 제공처 기능을 반환한다. `available=false`인 기능을 연동 계층이 숨기거나 제한 사유를 안내할 수 있게 한다. 막차가 true여도 모든 서울 경로 지원을 뜻하지 않으며 요청별 범위 검증은 계산 API에서 다시 수행한다.

| data 필드 | 타입 | 설명 |
|---|---|---|
| timezone | string | Asia/Seoul |
| place_search.available | boolean | 장소 검색 가능 |
| interpretation.available | boolean | 자연어 구조화 가능. false여도 명시적 조건 입력 허용 |
| appointment.available | boolean | 약속 경로 계산 가능 |
| appointment.time_basis | enum | arrival_time_search / departure_time_search / unsupported |
| last_journey.available | boolean | 검증 가능한 막차 기능 유무 |
| last_journey.scope_note | string | 지원 노선·지역·제약 설명 |
| last_journey.service_date_from / to | date 또는 null | 검증 데이터의 날짜 범위. 미지원일 때 null |
| transport_modes | enum[] | 허용 대중교통 모드. subway / bus |
| max_options | integer | 이번 버전은 3 |
| defaults.arrival_preference_minutes | integer | 미지정 시 제안할 값. 초기 0, 확인 대화에 표시 |
| defaults.transport_modes | enum[] | 초기 subway, bus. 확인 대화에 표시 |
| buffer_policy.version / label | string | 실제 적용 규칙의 버전·이름 |
| limitations | string[] | 사용자에게 표시할 추가 제약 |

자연어를 해석하지 못하는 환경에서도 연동 계층은 장소·시각 수동 입력 후 계산을 요청할 수 있다. `departure_time_search`만 가능하면 서버가 지원하는 미래 출발시각 조회를 이용해 역산·검증한다. 현재 ETA만 얻는 API를 도착시각 기반 조회라고 표시하지 않는다.

전체 예제: `capabilities`.

## 6. 장소 검색

### GET /places

| Query | 필수 | 제한 |
|---|---|---|
| query | 예 | 앞뒤 공백 제거 후 1~100자. URL 인코딩 |
| limit | 아니오 | 1~10 정수, 기본 5 |

장소 검색 결과는 대중교통 경로 계산에 사용할 출발·도착 기준점이다. 집 동·호수는 요구하지 않는다.

| data 필드 | 타입 | 설명 |
|---|---|---|
| query | string | 적용한 검색어 |
| places | Place[] | 검색된 후보. 0~limit개 |
| source.provider | string | 실제 장소 제공처 이름 |
| source.retrieved_at | datetime | 조회 시각 |
| has_more | boolean | 추가 후보가 있음. MVP는 검색어 구체화로 좁힘 |

검색 성공 후 결과가 없으면 HTTP 200, status=ok, places=[]다. 제공처 장애와 구분한다. 페이지네이션은 이번 버전에 포함하지 않는다.

### Place

| 필드 | 타입 | 설명 |
|---|---|---|
| place_id | string | 서버가 해석할 수 있는 제공처 기반 불투명 ID |
| name | string | 표시할 장소명 |
| address | string 또는 null | 제공처의 주소. 주거 상세 호수 불필요 |
| latitude | number | 위도 -90~90 |
| longitude | number | 경도 -180~180 |

서버는 해당 제공처의 ID를 다시 해석할 수 있어야 한다. 임시 배열 순번을 ID로 쓰지 않는다. 연동 계층은 ID를 분해하거나 직접 만들지 않는다.

서버가 검색 결과를 반환해도 사용자 선택 전에는 장소가 확정되지 않는다. 이미 사용자가 선택한 장소를 이유 없이 다시 선택하게 하지 않는다. 제공처가 모호한 지역 중심점만 반환했다면 출입구·POI 확인을 요청한다.

계산 요청에는 **place_id만** 보내고, 서버는 장소 제공처나 검증된 캐시에서 좌표를 해석한다. 클라이언트가 임의 수정한 좌표로 교통 계산을 수행하지 않는다. 좌표 직접 입력·GPS 기반 검색 API는 후속 범위다.

전체 예제: `places_found`.

## 7. 자연어 입력 해석

### POST /mobility/interpret

요청:

```json
{
  "text": "오늘 오후 7시까지 테스트 B역 2번 출구에 도착해야 해. 집에서 출발할 거야.",
  "reference_time": "2026-09-13T18:00:00+09:00",
  "timezone": "Asia/Seoul",
  "context": null
}
```

| 필드 | 필수 | 타입·규칙 |
|---|---|---|
| text | 예 | string, 1~2000자. 새 요청 또는 확인 질문에 대한 답 |
| reference_time | 예 | datetime. “오늘/내일” 해석 기준 |
| timezone | 예 | Asia/Seoul |
| context | 예 | TripDraft 또는 null. 이전 초안과 연동 계층에서 수정·확정한 값을 보내야 함 |

서버는 대화를 영구 저장하지 않는다. 후속 요청은 이전 `data.draft`를 context에 포함한다. 대화에서 확인한 장소·시각 수정은 해당 필드를 갱신해 전송한다. 서버가 반환한 초안의 확인된 값을 새 문장만 보고 덮어쓰지 않는다. 사용자가 명시적으로 조건을 바꾼 경우 해당 필드만 갱신·재확인한다.

### TripDraft

아래 키를 모두 포함한다. 미확정 값은 null 또는 표에 정의된 미확정 상태로 표현한다.

| 필드 | 타입 | 규칙 |
|---|---|---|
| kind | appointment / last_journey / null | 약속 도착 또는 막차 귀가 |
| origin / destination | PlaceSlot | 원문 표현과 확정 장소를 분리 |
| arrival_deadline | datetime 또는 null | appointment의 도착 마감 |
| arrival_preference_minutes | integer 또는 null | 0~120분. null은 미지정, 0은 정시 선호 |
| service_date | date 또는 null | last_journey의 운행일 |
| transport_modes | enum[] 또는 null | subway / bus, 중복 금지, 지정 시 1개 이상 |
| ambiguities | string[] | 모호한 필드 경로. 예: arrival_deadline, destination.place_id |

PlaceSlot은 다음 세 필드다.

| 필드 | 타입 | 규칙 |
|---|---|---|
| query | string 또는 null | “집”, “잠실” 등 사용자 표현 |
| place | Place 또는 null | 검색·선택한 장소 |
| confirmed | boolean | 사용자가 장소를 선택·확인했으면 true. true이면 place가 필요 |

context의 Place도 서버에서 ID와 정보를 검증한다. confirmed 플래그만 보고 가짜 장소를 허용하지 않는다. 명확한 장소 이름을 다시 묻는 대신, 필요하다면 검색 결과 선택 단계로 연결한다.

### 해석 응답 data

| 필드 | 타입 | 규칙 |
|---|---|---|
| draft | TripDraft | 누적 입력을 반영한 새 초안 |
| ready_for_plan | boolean | 계획 요청에 필요한 정보가 채워졌는지 |
| missing_fields | string[] | 필수 미확정/모호한 필드 경로. 최대 3개로 자르지 않음 |
| questions | Question[] | 이번 응답에서 물을 질문 0~3개 |
| applied_defaults | array | 적용한 기본값 {field, value, reason}. 적용 안 했으면 [] |
| summary | string | 확인용 요약. 계산되지 않은 시각·경로를 만들지 않음 |

Question은 `field`, `type`, `prompt`, `options`를 포함한다.

- field: 한 개의 미확정 필드 경로.
- type: place_search / datetime / select / number.
- prompt: 사용자 질문.
- options: select 선택지 배열. 각 원소는 {label: string, value: string}. 나머지 type은 [].

필수 필드가 남으면 status=needs_confirmation, ready_for_plan=false다. 시간 의미·목적지·출발지 순으로 막힌 항목을 우선 확인하되 명확한 값을 재질문하지 않는다.

선호 적용 우선순위는 이번 이동의 명시 값 → 현재 문맥에서 사용자가 확인한 선호 → capabilities 기본값이다. 확인된 선호는 TripDraft에 채워 context로 보내되 이번 이동의 명시 값을 우선한다. 저장된 집 주소·선호나 UserData DB가 있다고 임의 가정하지 않는다. 택시비 상한선은 수집하거나 전송하지 않는다.

장소·시각이 확정되면 여전히 미지정인 선택값은 capabilities의 기본값으로 채우고 applied_defaults와 summary에 표시한다. 예: 도착 여유 0분, 버스·지하철 허용. last_journey의 arrival_preference_minutes는 0이다. 클라이언트는 적용된 값까지 최종 확인 대화에 보여준다.

필수 정보가 완성되면 status=ok, ready_for_plan=true, missing_fields=[], questions=[]를 반환한다. 이 상태도 사용자의 최종 확인 응답을 대체하지 않는다. 사용자가 확인한 뒤에만 /journeys/plan을 호출한다.

응답 예:

```json
{
  "status": "needs_confirmation",
  "data": {
    "draft": {
      "kind": "appointment",
      "origin": {
        "query": "집",
        "place": null,
        "confirmed": false
      },
      "destination": {
        "query": "테스트 B역 2번 출구",
        "place": null,
        "confirmed": false
      },
      "arrival_deadline": "2026-09-13T19:00:00+09:00",
      "arrival_preference_minutes": null,
      "service_date": null,
      "transport_modes": null,
      "ambiguities": []
    },
    "ready_for_plan": false,
    "missing_fields": [
      "origin.place_id",
      "destination.place_id"
    ],
    "questions": [
      {
        "field": "origin.place_id",
        "type": "place_search",
        "prompt": "출발 기준으로 사용할 가까운 역·정류장이나 건물 출입구를 선택해 주세요.",
        "options": []
      },
      {
        "field": "destination.place_id",
        "type": "place_search",
        "prompt": "테스트 B역 2번 출구의 검색 결과를 선택해 주세요.",
        "options": []
      }
    ],
    "applied_defaults": [],
    "summary": "도착 마감은 오늘 19:00입니다. 출발지와 목적지의 위치 선택이 필요합니다."
  },
  "error": null,
  "meta": {
    "request_id": "fixture-interpret_needs_confirmation",
    "server_time": "2026-09-13T18:00:00+09:00",
    "api_version": "v1",
    "is_demo": true
  }
}
```

전체 준비 완료 예제: `interpret_ready`.

### 재사용할 해석 원칙

- “오후 7시까지 도착”은 arrival_deadline 19:00으로 확정한다.
- 도착 여유가 미지정이라고 Deadline을 다시 묻지 않는다.
- “잠실”, “집”을 임의 좌표로 확정하지 않는다.
- “내일”은 reference_time과 timezone을 이용해 절대 날짜로 변환한다.
- 상대 시각·운행일이 명확하지 않으면 확인을 요청한다. 자정 이후라고 무조건 새 운행일로 간주하지 않는다.
- LLM 원문 JSON을 그대로 반환하지 않고 서버가 스키마·값을 검증한다.

## 8. 이동 계획 계산

### POST /journeys/plan

요청 예:

```json
{
  "trip": {
    "kind": "appointment",
    "origin_place_id": "fixture:place-a",
    "destination_place_id": "fixture:place-b",
    "arrival_deadline": "2026-09-13T19:00:00+09:00",
    "arrival_preference_minutes": 10,
    "service_date": null,
    "transport_modes": [
      "subway",
      "bus"
    ]
  },
  "user_confirmed": true
}
```

| 필드 | 필수 | 설명 |
|---|---|---|
| trip | 예 | 아래 TripRequest |
| user_confirmed | 예 | true. 연동 계층의 이동 조건 확인 후 요청 |

user_confirmed는 연동 계층 흐름을 확인하는 값이며 인증이나 위·변조 방지 수단이 아니다.

### TripRequest

모든 키를 포함한다.

| 필드 | 타입 | 규칙 |
|---|---|---|
| kind | enum | appointment / last_journey |
| origin_place_id | string | 선택·확정한 출발지 ID |
| destination_place_id | string | 선택·확정한 목적지 ID |
| arrival_deadline | datetime 또는 null | appointment는 필수, last_journey는 null |
| arrival_preference_minutes | integer | 0~120, last_journey는 0 |
| service_date | date 또는 null | last_journey는 필수, appointment는 null |
| transport_modes | enum[] | subway / bus, 1~2개, 중복 금지 |

도보는 연결 구간으로 기본 허용한다. transport_modes는 사용할 수 있는 대중교통 종류다. taxi는 지원하지 않으며 입력 시 검증 오류를 반환한다.

### 계산 동작

1. 필수 필드·사용자 확인·지원 지역·제공처 기능을 검증한다.
2. place_id를 실제 장소로 해석하고 서버 시각을 기준으로 유효한 경로를 조회한다.
3. appointment의 목표 도착시각을 Deadline에서 도착 여유만큼 빼서 계산한다.
4. 시간표·조회 결과와 코드 기반 Buffer 규칙을 함께 적용해 이용 가능한 경로를 구한다.
5. 후보 1~3개와 권장 후보 ID를 반환한다. 데이터 기준시각과 계산 방법을 포함한다.

appointment에서 목표 도착이 가능하면 그 조건을 만족하는 후보 중 늦게 출발할 수 있는 경로를 우선한다. 목표 도착이 이미 어려우면 현재 이후 출발하는 경로 중 빨리 도착하는 대안을 우선한다. 동률은 환승 횟수, 도보시간이 적은 순으로 비교한다.

Deadline이 과거라고 요청 자체를 잘못된 JSON으로 처리하지 않는다. 실제 이용 가능한 경로가 있으면 late 상태로 반환한다. 확인된 경로가 없을 때만 unavailable로 처리한다.

last_journey는 요청한 운행일의 연결 가능한 마지막 여정을 계산한다. 운행일과 실제 날짜가 다를 수 있으며, 각 교통편 방향·종착역·환승·도보를 검증한다. 지원 데이터가 없으면 LAST_JOURNEY_UNSUPPORTED, 지원 범위에서 검색한 결과 경로가 없으면 NO_FEASIBLE_JOURNEY다. 두 상태를 혼동하지 않는다.

계산된 recommended_leave_at이 이미 과거라면 그 경로를 현재 이용 가능한 권장안으로 반환하지 않는다. 현재 출발 가능한 안으로 다시 평가한다. 막차에서 Hard Deadline은 남았지만 권장 여유를 확보할 수 없는 경우 이번 MVP는 가능한 경로로 강행 추천하지 않고 unavailable + BUFFER_REQUIREMENT_NOT_MET로 안내한다.

### 성공 응답 data

`{ "plan": Plan }`

### Plan

| 필드 | 타입 | 의미 |
|---|---|---|
| plan_id | string | 이번 계산 결과 ID. 서버 저장 리소스 주소가 아님 |
| generated_at | datetime | 계산 완료 시각 |
| refresh_after | datetime | 데이터 재확인을 권할 시각. 운행 보장/만료 시각이 아님 |
| trip | TripRequest | 검증한 요청 조건 |
| origin / destination | Place | 검증한 출발·도착 장소 |
| target_arrival_at | datetime 또는 null | appointment의 목표 도착. last_journey는 null |
| recommended_option_id | string | options 안의 한 option_id |
| options | RouteOption[] | 성공이면 1~3개. 빈 배열 성공 금지 |

refresh_after는 제공처의 최신성 조건을 반영한다. 확정 정책이 없을 때 서버 기본값은 generated_at + 5분으로 설정하고 추후 조정 가능하게 한다. 연동 계층은 이를 지나면 데이터 재확인을 안내하며, 유효성이 보장된 최신 정보라고 표시하지 않는다. 이 값만으로 백그라운드 자동 호출을 시작하지 않는다.

### RouteOption

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
| late_by_minutes | integer ≥ 0 또는 null | Deadline 초과 분. 양수 차이를 올림. last_journey는 null |
| target_margin_minutes | integer 또는 null | 목표 도착 - 예상 도착의 분 차이를 내림. 양수=여유, 음수=부족 |
| legs | Leg[] | 실제 순서의 이동·대기 구간 |
| calculation_method | enum | schedule_search / departure_search |
| sources | Source[] | 데이터 출처, 최소 1개 |
| warnings | Warning[] | 없으면 [] |
| navigation_url | string 또는 null | 지원되는 외부 지도 HTTPS/딥링크. 미확인 URL은 null |

appointment 판정은 원래 datetime 차이로 수행한다. 반올림된 숫자로 상태를 바꾸지 않는다.

- on_time: estimated_arrival_at ≤ target_arrival_at.
- preference_missed: target_arrival_at < estimated_arrival_at ≤ arrival_deadline.
- late: estimated_arrival_at > arrival_deadline.
- last_journey: not_applicable, late_by_minutes=null, target_margin_minutes=null.
- on_time / preference_missed의 late_by_minutes는 0.

Buffer는 `policy_version: string`, `total_minutes: number`, `items: array`다.
각 item은 `code: string`, `minutes: number ≥ 0`, `leg_id: string`, `reason: string`이다.

**Buffer의 시간은 legs와 total_duration_minutes에 이미 반영되어 있다. 연동 계층에서 다시 더하거나 권장 출발시각에서 다시 빼지 않는다.** items는 해당 대기·이동 구간에 포함된 추가 여유의 설명이며 합계는 total_minutes와 일치해야 한다. 같은 시간에 여러 여유 항목을 중복 배정하지 않는다.

### Leg

| 필드 | 타입 | 설명 |
|---|---|---|
| leg_id | string | 해당 후보 안의 구간 ID |
| mode | enum | walk / wait / subway / bus |
| from / to | Point | 구간 시작·끝 |
| departure_at / arrival_at | datetime | 해당 구간 시작·끝 |
| duration_minutes | number ≥ 0 | 구간 시간 |
| transit | Transit 또는 null | subway/bus에 필수, walk/wait는 null |
| wait_reason | enum 또는 null | wait이면 scheduled_wait / safety_buffer / mixed, 그 외 null |

Point는 `name: string`, `latitude: number`, `longitude: number`다.

Transit은 `line_name: string`, `direction: string 또는 null`, `headsign: string 또는 null`, `service_id: string 또는 null`이다. 막차 계산에는 방향·종착역·해당 편 식별을 검증할 수 있어야 하며, 그 핵심 정보가 없어 검증할 수 없는 경우 성공 막차를 반환하지 않는다.

Source는 `provider: string`, `basis: schedule / realtime / demo`, `retrieved_at: datetime`, `service_date: date`다. demo 출처가 하나라도 있으면 meta.is_demo=true여야 한다.

Warning은 `code: string`, `message: string`이다. 초기 코드는 DEMO_DATA, SCHEDULE_ONLY, DATA_REFRESH_RECOMMENDED로 정한다. 클라이언트는 모르는 warning code도 message를 표시할 수 있어야 한다.

### 시간 불변 조건

- 첫 leg.departure_at = recommended_leave_at.
- 마지막 leg.arrival_at = estimated_arrival_at.
- 시간순으로 연결하며 구간 사이 대기는 wait leg로 명시한다.
- 구간 duration_minutes는 datetime 차이의 분 값이다. 소수 허용. 연동 계층 표시는 올림할 수 있다.
- total_duration_minutes는 전체 datetime 차이로 구하고, 반올림 전 구간 합과 일치한다.
- 막차는 recommended_leave_at ≤ hard_leave_at. 출발을 앞당기는 것만으로 환승 안전이 확보된다고 가정하지 않고 각 연결을 재검증한다.
- 현재 시각만을 기반으로 받은 ETA를 미래 경로 또는 막차의 증거로 쓰지 않는다.

### 약속 계획 전체 응답 예

```json
{
  "status": "ok",
  "data": {
    "plan": {
      "plan_id": "plan-fixture-1",
      "generated_at": "2026-09-13T18:00:00+09:00",
      "refresh_after": "2026-09-13T18:05:00+09:00",
      "trip": {
        "kind": "appointment",
        "origin_place_id": "fixture:place-a",
        "destination_place_id": "fixture:place-b",
        "arrival_deadline": "2026-09-13T19:00:00+09:00",
        "arrival_preference_minutes": 10,
        "service_date": null,
        "transport_modes": [
          "subway",
          "bus"
        ]
      },
      "origin": {
        "place_id": "fixture:place-a",
        "name": "테스트 A역 1번 출구",
        "address": "서울 내 가상 출발 지점",
        "latitude": 37.5,
        "longitude": 126.95
      },
      "destination": {
        "place_id": "fixture:place-b",
        "name": "테스트 B역 2번 출구",
        "address": "서울 내 가상 도착 지점",
        "latitude": 37.51,
        "longitude": 127.02
      },
      "target_arrival_at": "2026-09-13T18:50:00+09:00",
      "recommended_option_id": "option-a",
      "options": [
        {
          "option_id": "option-a",
          "summary": "가상 노선 A 이용 · 도보 10분",
          "recommended_leave_at": "2026-09-13T18:10:00+09:00",
          "hard_leave_at": null,
          "estimated_arrival_at": "2026-09-13T18:50:00+09:00",
          "total_duration_minutes": 40,
          "buffer": {
            "policy_version": "demo-v1",
            "total_minutes": 5,
            "items": [
              {
                "code": "BOARDING_MARGIN",
                "minutes": 5,
                "leg_id": "option-a-leg-2",
                "reason": "시연용 탑승 여유 5분"
              }
            ]
          },
          "arrival_status": "on_time",
          "late_by_minutes": 0,
          "target_margin_minutes": 0,
          "legs": [
            {
              "leg_id": "option-a-leg-1",
              "mode": "walk",
              "from": {
                "name": "테스트 A역 1번 출구",
                "latitude": 37.5,
                "longitude": 126.95
              },
              "to": {
                "name": "테スト A역 승강장",
                "latitude": 37.5001,
                "longitude": 126.9501
              },
              "departure_at": "2026-09-13T18:10:00+09:00",
              "arrival_at": "2026-09-13T18:15:00+09:00",
              "duration_minutes": 5,
              "transit": null,
              "wait_reason": null
            },
            {
              "leg_id": "option-a-leg-2",
              "mode": "wait",
              "from": {
                "name": "테スト A역 승강장",
                "latitude": 37.5001,
                "longitude": 126.9501
              },
              "to": {
                "name": "테スト A역 승강장",
                "latitude": 37.5001,
                "longitude": 126.9501
              },
              "departure_at": "2026-09-13T18:15:00+09:00",
              "arrival_at": "2026-09-13T18:20:00+09:00",
              "duration_minutes": 5,
              "transit": null,
              "wait_reason": "safety_buffer"
            },
            {
              "leg_id": "option-a-leg-3",
              "mode": "subway",
              "from": {
                "name": "테スト A역 승강장",
                "latitude": 37.5001,
                "longitude": 126.9501
              },
              "to": {
                "name": "테스트 B역 승강장",
                "latitude": 37.5101,
                "longitude": 127.0201
              },
              "departure_at": "2026-09-13T18:20:00+09:00",
              "arrival_at": "2026-09-13T18:45:00+09:00",
              "duration_minutes": 25,
              "transit": {
                "line_name": "가상 노선 A",
                "direction": "테스트 B역 방향",
                "headsign": "테스트 B역",
                "service_id": "fixture-service-a"
              },
              "wait_reason": null
            },
            {
              "leg_id": "option-a-leg-4",
              "mode": "walk",
              "from": {
                "name": "테스트 B역 승강장",
                "latitude": 37.5101,
                "longitude": 127.0201
              },
              "to": {
                "name": "테스트 B역 2번 출구",
                "latitude": 37.51,
                "longitude": 127.02
              },
              "departure_at": "2026-09-13T18:45:00+09:00",
              "arrival_at": "2026-09-13T18:50:00+09:00",
              "duration_minutes": 5,
              "transit": null,
              "wait_reason": null
            }
          ],
          "calculation_method": "schedule_search",
          "sources": [
            {
              "provider": "fixture",
              "basis": "demo",
              "retrieved_at": "2026-09-13T18:00:00+09:00",
              "service_date": "2026-09-13"
            }
          ],
          "warnings": [
            {
              "code": "DEMO_DATA",
              "message": "가상 시연 데이터이며 실제 운행 정보가 아닙니다."
            }
          ],
          "navigation_url": null
        }
      ]
    }
  },
  "error": null,
  "meta": {
    "request_id": "fixture-plan_appointment",
    "server_time": "2026-09-13T18:00:00+09:00",
    "api_version": "v1",
    "is_demo": true
  }
}
```

예시 계산: 목표 도착 18:50, 권장 출발 18:10, 전체 40분 = 도보 10분 + 탑승 여유 대기 5분 + 지하철 25분. 추가 여유 5분은 40분 안에 들어 있으며 별도로 재가산하지 않는다.

막차 예제는 `plan_last_journey`를 참조한다. service_date는 2026-09-12이고 예상 도착은 다음 날 00:15다. 권장 출발은 23:35, 검증된 Hard Deadline은 23:40인 **가상 시간표**다.

## 9. 사용자 요청 재탐색

### POST /journeys/replan

요청 예:

```json
{
  "trip": {
    "kind": "appointment",
    "origin_place_id": "fixture:place-a",
    "destination_place_id": "fixture:place-b",
    "arrival_deadline": "2026-09-13T19:00:00+09:00",
    "arrival_preference_minutes": 10,
    "service_date": null,
    "transport_modes": [
      "subway",
      "bus"
    ]
  },
  "previous_plan": {
    "plan_id": "plan-fixture-1",
    "selected_option_id": "option-a",
    "recommended_leave_at": "2026-09-13T18:10:00+09:00",
    "estimated_arrival_at": "2026-09-13T18:50:00+09:00"
  },
  "current_origin_place_id": "fixture:place-a",
  "reason": "missed_connection",
  "user_confirmed": true
}
```

| 필드 | 필수 | 설명 |
|---|---|---|
| trip | 예 | 유지할 기존 TripRequest. 목적지·Deadline·선호를 포함 |
| previous_plan | 예 | 이전 선택 비교용 PlanSummary |
| current_origin_place_id | 예 | 사용자가 현재 출발 기준점으로 확인한 장소 ID |
| reason | 예 | missed_connection / route_changed / manual |
| user_confirmed | 예 | true. 재탐색 요청 확인 |

PlanSummary는 `plan_id`, `selected_option_id`, `recommended_leave_at`, `estimated_arrival_at` 네 필드다. 앞 두 값은 string, 뒤 두 값은 datetime이다.

서버는 이전 plan_id로 DB 조회하지 않는다. trip과 current_origin_place_id를 다시 검증해 현재 서버 시각 기준으로 새 경로를 계산한다. 응답 plan.trip.origin_place_id와 plan.origin은 **새 출발지**를 반영한다.

previous_plan의 시각은 연동 계층이 보낸 과거 비교 기준으로만 사용한다. 현재 경로의 운행·정확성 근거로 사용하지 않는다. 위조 여부를 보장하는 서버 저장 기록이 아니므로 추후 보안·공유 기능이 필요하면 별도 저장 모델을 도입한다.

거절·취소 상태에서는 연동 계층이 요청하지 않는다. reason=route_changed도 user_confirmed=true가 필요하다. 서버는 새 결과를 반환할 뿐 기존 로컬 계획을 자동 교체하지 않는다.

### 성공 응답 data

| 필드 | 타입 | 설명 |
|---|---|---|
| plan | Plan | 새로 계산된 후보 |
| comparison | Comparison | 이전 선택과 새 권장 후보 비교 |

Comparison은 다음 필드다.

- previous_plan_id: string.
- previous_selected_option_id: string.
- compared_option_id: 새 plan.recommended_option_id.
- arrival_change_minutes: 새 권장 ETA - 이전 선택 ETA의 분 차이. 양수=더 늦게 도착.
- leave_change_minutes: 새 권장 출발 - 이전 선택 권장 출발의 분 차이. 양수=더 늦은 시각.
- summary: 확인된 차이를 설명하는 한국어 문장.

변화량 두 필드는 소수 분을 허용한다. 연동 계층이 표시를 반올림하더라도 도착 상태 판정은 서버 값에 따른다. 사용자가 다른 후보를 선택하면 comparison은 그 후보의 비교가 아니므로 연동 계층이 시각을 다시 비교하거나 해당 비교 문구를 숨긴다.

전체 예제 `replan_late`: 이전 도착 18:50 → 새 도착 19:10으로 20분 늦어지고, Deadline 19:00을 10분 초과한다.

### 사용자 선택 후 적용

새 결과를 사용자가 선택하면 현재 대화의 선택 계획을 갱신한다. 이 API는 기존 계획을 자동 교체하지 않는다. 재탐색 실패·취소는 이전 선택을 삭제하지 않으며, 이전 경로가 여전히 유효하다는 뜻으로 표시하지 않는다.

재탐색은 매번 사용자가 요청한다. 자동 재제시 3회 정책을 수동 요청 횟수 제한으로 적용하지 않는다. 영구 저장·출발/도착 상태 관리·알림 발송은 현재 MCP 계약에 포함하지 않는다.

## 10. 오류·불가 사유와 연동 계층 동작

| HTTP | status | code | 연동 계층 동작 |
|---|---|---|---|
| 400 | error | INVALID_JSON | 요청 형식 수정. 사용자 입력 재시도 반복 금지 |
| 422 | error | VALIDATION_ERROR | details.field에 맞는 입력 오류 표시 |
| 422 | error | USER_CONFIRMATION_REQUIRED | 이동 조건 확인 대화로 돌아감 |
| 422 | error | PLACE_NOT_RESOLVABLE | 이전 장소 ID를 해석할 수 없으므로 다시 검색·선택 |
| 200 | unavailable | OUT_OF_SERVICE_AREA | 서울 또는 제공처 지원 범위 밖 안내 |
| 200 | unavailable | APPOINTMENT_TIME_UNSUPPORTED | 요청한 시각 조건의 경로를 검증할 수 없음을 안내 |
| 200 | unavailable | LAST_JOURNEY_UNSUPPORTED | 막차 데이터·운행일·노선 지원 부족 안내 |
| 200 | unavailable | NO_FEASIBLE_JOURNEY | 지원 데이터에서 조건에 맞는 경로가 없음을 안내 |
| 200 | unavailable | BUFFER_REQUIREMENT_NOT_MET | 요구한 여유를 확보한 막차 경로가 없음. 안전한 탑승을 단정하지 않음 |
| 429 | error | RATE_LIMITED | Retry-After 헤더의 초만큼 재요청 대기 |
| 503 | error | ROUTING_PROVIDER_UNAVAILABLE | 교통 조회 일시 실패. 재시도 안내 |
| 503 | error | PLACE_PROVIDER_UNAVAILABLE | 장소 검색 일시 실패. 재시도 안내 |
| 503 | error | AI_UNAVAILABLE | 자연어 해석 실패. 명시적 조건 입력 안내 |
| 502 | error | UPSTREAM_RESPONSE_INVALID | 제공처·모델 결과 검증 실패. 잘못된 경로·시간을 표시하지 않음 |
| 504 | error | UPSTREAM_TIMEOUT | 외부 요청 시간 초과. 재시도 안내 |
| 500 | error | INTERNAL_ERROR | 일반 오류 안내와 request_id 제공 |
| 404 | error | CONVERSATION_NOT_FOUND | 존재한 적 없는 conversation_id로 요청함. 새 대화로 다시 시작한다. |
| 409 | error | CONVERSATION_VERSION_CONFLICT | 전달한 revision이 서버의 현재 revision과 다르다. 최신 상태를 다시 받아 재시도해야 한다. |
| 409 | error | IDEMPOTENCY_KEY_REUSED | 같은 Idempotency-Key로 다른 요청이 이미 처리됐다. 같은 키로 다른 요청을 재시도하지 않는다. |
| 410 | error | CONVERSATION_EXPIRED | conversation이 만료됐다. 새 대화로 다시 시작한다. |
| 410 | error | CANDIDATE_SET_EXPIRED | conversation은 유효하지만 후보 집합이 만료됐다. 기존 확인 조건으로 새 계획을 요청한다. |

상태 관련 오류는 CONVERSATION_NOT_FOUND, CONVERSATION_EXPIRED, CANDIDATE_SET_EXPIRED, CONVERSATION_VERSION_CONFLICT, IDEMPOTENCY_KEY_REUSED로 구분한다.


최소 서버에서 위 오류 코드가 발생하는 지점을 명시적으로 매핑한다. 존재하지 않는 경로·메서드도 JSON envelope를 유지하며 각각 404 NOT_FOUND, 405 METHOD_NOT_ALLOWED를 반환한다.

오류 예:

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "도착 여유시간은 0~120분의 정수여야 합니다.",
    "retryable": false,
    "details": [
      {
        "field": "trip.arrival_preference_minutes",
        "reason": "OUT_OF_RANGE"
      }
    ]
  },
  "meta": {
    "request_id": "fixture-invalid_arrival_preference",
    "server_time": "2026-09-13T18:00:00+09:00",
    "api_version": "v1",
    "is_demo": true
  }
}
```

unavailable는 서버 장애와 달리 요청 조건 또는 데이터 지원 한계다. 자동 재시도로 해결된다고 표시하지 않는다. `NO_FEASIBLE_JOURNEY`는 제공처가 검증한 범위에서의 결과이며 서울 전체의 모든 대안이 없다는 보장이 아니다.

## 11. MCP 호출 순서와 대화 상태

1. get_capabilities로 /capabilities의 기능·기본값·지원 범위를 확인한다.
2. interpret_trip으로 /mobility/interpret를 호출한다.
3. search_places로 /places 후보를 받고 사용자에게 선택을 요청한다.
4. 확인한 값으로 context를 갱신한다. 명확히 입력된 값은 임의 변경하지 않는다.
5. Hermes 대화에서 최종 조건을 요약하고 사용자 동의를 받은 뒤 plan_journey로 /journeys/plan을 호출한다.
6. 사용자가 선택한 Plan과 option_id를 현재 대화의 선택 계획으로 관리한다.
7. replan_journey로 /journeys/replan을 호출하고 새 후보에 대한 사용자 선택 후에만 계획을 갱신한다.

필수 조건을 직접 입력해 검증할 수 있다면 /interpret를 생략할 수 있다. /plan의 필수 조건과 사용자 확인 요구는 동일하다.

문맥·확인·선택 상태의 실제 저장 위치와 수명은 구현 전에 공동 합의한다. 서버가 plan_id로 DB 복원을 수행한다고 가정하지 않는다. 과거의 Local Journey 영구 저장·상태 버튼·notification_id 모델은 현재 MCP 필수 계약이 아니다.



### tombstone 생성 충돌 처리

tombstone은 24시간 유지 후 hard delete한다. 정리는 백엔드 시작 시 한 번, 실행 중 주기적으로 수행하며, 요청 시 만료가 발견되면 cleanup 주기를 기다리지 않고 즉시 tombstone 처리한다. tombstone 전환으로 사용자 revision은 증가시키지 않고 마지막 revision을 유지한다.

- 동일 conversation_id의 만료 처리는 멱등하게 수행한다.
- 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환한다.
- 별도 테이블을 사용하는 경우 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다.
- 충돌 후 해당 tombstone이 존재함을 확인하면 동일하게 410 CONVERSATION_EXPIRED로 응답한다.
- 기존 expired_at을 재설정하거나 tombstone 보존 기간을 연장하지 않는다.
- 중복 키 이외의 DB 오류는 무시하거나 410으로 감추지 않는다.
- hard delete 이후에는 404 CONVERSATION_NOT_FOUND를 반환하고, 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.

존재한 적 없는 conversation과 hard delete된 conversation은 모두 404 CONVERSATION_NOT_FOUND로 처리한다.
과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.

이 문단은 provider 호출 순서의 5단계 절차를 정의한다.

### provider 호출 순서와 상태 변경 경계

provider가 필요한 상태 변경은 다음 순서를 따른다.

1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
3. provider 성공 결과를 검증한다.
4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

동시 요청이 먼저 같은 key로 완료했다면 저장된 응답을 반환한다.
다른 요청 때문에 revision이 바뀌었다면 409 CONVERSATION_VERSION_CONFLICT를 반환하고 provider 결과는 적용하지 않는다.
그 사이 conversation이 만료됐다면 410 CONVERSATION_EXPIRED로 처리한다.

provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다.

provider 실패는 domain 상태·revision·updated_at·TTL을 갱신하지 않는다. 백엔드는 workflow 수준의 자동 재시도를 하지 않으며, provider 호출을 DB 트랜잭션 내부에 포함하지 않는다.
## 12. 시간 초과·재시도·중복 요청

- 서버 처리 제한 초안: health/capabilities 3초, places 10초, interpret/plan/replan 25초.
- 연동 계층 대기 제한: GET 15초, POST 30초. 실제 제공처 제약으로 바꿔야 하면 두 담당자가 함께 수정한다.
- rate limit의 Retry-After는 정수 초로 반환한다.
- 연동 계층은 중복 계산 요청을 막고 진행 상태를 전달한다.
- 입력이 바뀐 뒤 이전 요청이 늦게 도착하면 새 상태를 덮어쓰지 않는다. 연동 계층에서 요청 순번 또는 취소로 처리한다.
- POST는 자동 반복 호출하지 않고 사용자 재시도를 제공한다. 계산 요청은 서버 리소스를 생성하지 않지만 모델·교통 호출 비용이 발생할 수 있다.
- 같은 계산을 다시 요청해도 현재 시각·교통 상태가 달라 결과가 바뀔 수 있다. plan_id 재사용이나 동일 응답을 보장하지 않는다.
- 계산 중 네트워크가 끊기면 현재 선택 계획은 유지하고 결과 미수신으로 표시한다.

## 13. MCP 연동 Mock 예제 사용

[examples.json](Docs/api/examples.json)은 요청, HTTP 상태, 완전한 응답을 case별로 묶었다. 실행 서버나 테스트 완료 결과가 아니라 **이 계약에 맞춰 연동 계층을 개발하기 위한 fixture**다.

| case id | 확인할 도구 결과 |
|---|---|
| health | 서버 연결 |
| capabilities | 기능 지원·기본값 |
| places_found | 장소 후보 선택 |
| interpret_needs_confirmation | 장소 확인 질문 |
| interpret_ready | 최종 조건 확인 |
| plan_appointment | 약속 출발시각·경로 |
| plan_last_journey | 자정 이후 도착하는 막차 |
| replan_late | 재탐색 후 지각 |
| last_journey_unsupported | 막차 데이터 미지원 |
| no_feasible_journey | 지원 범위에서 연결 경로 없음 |
| invalid_arrival_preference | 필드 검증 오류 |
| provider_unavailable | 서버 제공처 장애·재시도 |
| confirmation_required | 확인 없이 계산을 요청한 오류 |

연동 계층은 Mock 모드에서 case.response와 case.http_status를 사용한다. 실제 호출로 전환할 때 JSON 구조와 결과 분기 코드는 유지하고 Base URL/데이터 연결 부분만 바꾼다. 예제의 날짜는 고정이므로 Mock 시간도 해당 meta.server_time으로 맞춘다. 실제 서버 계산의 현재 시각을 예제 날짜로 바꾸지 않는다.

## 14. 두 사람의 구현·검증 순서

### 첫날 합의할 사항

- 이 명세의 공개 경로와 응답 키를 두 사람이 함께 고정한다.
- 본인은 examples.json으로 MCP 도구 결과·오류 매핑과 Hermes 확인·선택 흐름을 검증한다.
- 친구는 /health, /capabilities와 장소·교통 데이터 검증부터 진행한다.
- 자연어 모델이 아직 연결되지 않아도 본인은 수동 입력으로 /journeys/plan 통합을 준비할 수 있다.
- 첫날 Hermes → MCP → FastAPI 호출을 검증하고 배포 서버의 실제 연결 여부를 별도로 기록한다.
- MCP 스키마·오류 전달·사용자 확인·대화 상태의 소유권을 합의한다. REST 계약 변경은 본 문서와 fixture를 함께 갱신한다.

### 의미 있는 계약 검증

1. 명확한 19:00 도착 표현이 확인 질문 없이 유지된다.
2. origin/destination 확정 없이 계획 계산을 요청하면 422로 처리된다.
3. 19:00 Deadline, 10분 전 선호의 target_arrival_at은 18:50이다.
4. 예상 도착이 18:55이면 preference_missed, late_by_minutes=0이다.
5. 도보·대기·추가 Buffer가 이미 포함된 전체 이동시간에 다시 Buffer를 더하지 않는다.
6. 막차 운행일과 다음 날 도착시각을 올바르게 처리한다.
7. 미지원 데이터와 실제 검색 결과 경로 없음이 다른 코드다.
8. 재탐색의 양수 arrival_change_minutes는 더 늦은 도착이다.
9. 실패한 재탐색이 기존 선택 계획을 지우지 않는다.
10. 실제 제공처 장애 시 Demo 경로로 자동 대체하지 않는다.

변경이 필요하면 명세와 fixture를 함께 수정한다. 실제 데이터 제공처가 바뀌어도 연동 계층 공개 계약을 유지하는 Adapter를 구현한다.

## 15. 구현 전에 확정할 환경 값

공개 JSON 계약은 위 내용으로 작업할 수 있다. 아래 운영 값은 실제 접근 가능한 환경에서 결정한다.

- 배포 Base URL.
- 장소·교통 제공처와 사용 가능한 키·한도.
- 지원 지역·노선·운행일 범위.
- 미래 시각 검색 방식과 막차 검증 가능 여부.
- 실제 Buffer 정책 버전과 수치.
- 백엔드 실행용 AI 모델 ID·호출 경로.
- 호출 제한과 제공처별 최신성 기준.

미확정 값을 실제 지원 기능처럼 하드코딩하지 않는다. capabilities에서 검증된 상태를 반환하고 불가능한 요청은 정의한 불가 사유로 응답한다.


### tombstone 충돌 처리

- tombstone은 24시간 유지 후 hard delete한다. 정리는 백엔드 시작 시 한 번, 실행 중 주기적으로 수행하며, 요청 시 만료가 발견되면 cleanup 주기를 기다리지 않고 즉시 tombstone 처리한다.
- tombstone 전환으로 사용자 revision은 증가시키지 않고 마지막 revision을 유지한다.
- 동일 conversation_id의 만료 처리는 멱등하게 수행한다.
- 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환한다.
- 별도 테이블을 사용하는 경우 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다.
- 충돌 후 해당 tombstone이 존재함을 확인하면 동일하게 410 CONVERSATION_EXPIRED로 응답한다.
- 기존 expired_at을 재설정하거나 tombstone 보존 기간을 연장하지 않는다.
- 중복 키 이외의 DB 오류는 무시하거나 410으로 감추지 않는다.
- hard delete 이후에는 404 CONVERSATION_NOT_FOUND를 반환하고, 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.

존재한 적 없는 conversation과 hard delete된 conversation은 모두 404 CONVERSATION_NOT_FOUND로 처리한다.
과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.
