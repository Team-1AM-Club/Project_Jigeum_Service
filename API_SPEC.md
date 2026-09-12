# 지금 — 앱·CLI 공통 계산 API 명세 v0.1

- 작성일: 2026-09-12
- 상태: **구현을 위한 계약 초안**. 현재 서버가 구현·배포됐다는 뜻은 아니다.
- 기준: `IDEA.md`의 2인·4일 MVP. 본인은 앱, 친구는 서버·AI·교통 데이터를 담당한다. 월요일 멘토링에서 앱 서비스 또는 CLI 제출을 결정한다.
- 목적: 본인은 동일한 JSON으로 클라이언트를 먼저 만들고, 친구는 그 형식으로 실제 서버를 구현한다. CLI 선택 시 본인이 CLI 입출력·패키징을 맡는다.
- 현재 계약 범위: REST/JSON 기반 요청별 계산 API. 기존 로컬 저장·로그인 없는 계약은 CLI 및 초기 통합용 기준이며, 앱 서비스의 UserData 저장 계약을 대체하지 않는다.
- 예제 파일: [Docs/api/examples.json](Docs/api/examples.json)
- 모든 예제는 **가상 역·가상 운행 데이터**이며 `meta.is_demo=true`다. 실제 서울 운행 정보로 사용하지 않는다.

### IDEA.md 변경 반영과 조건부 개정

- 앱 서비스 선택 시 Supabase PostgreSQL에 UserData를 저장한다. 구현 전 저장 항목, 사용자 식별·인증·접근 권한·삭제, 저장·조회 API와 예제 JSON을 공동 개정해야 한다. 현재 6개 계산 API만으로 앱 서비스의 데이터 저장 요구까지 구현됐다고 간주하지 않는다.
- 본문의 앱·로컬 저장 표현은 기존 계산 흐름을 설명한다. CLI에는 해당 흐름을 명령·확인 프롬프트·로컬 기록으로 적용하며, 앱 서비스에서는 DB와 로컬 캐시의 관계를 추가로 확정한다. 모바일 전용 알림은 CLI 필수 범위가 아니다.
- 서버 내부에서 MainAgent가 SubAgent를 지휘하고, 각 SubAgent는 역할에 따라 하나 이상의 기존 Skill을 사용한다. 공개 JSON 계약과 코드 기반 시간 계산은 유지한다.
- 백엔드는 FastAPI, Docker는 컨테이너 패키징, Cloud Run은 백엔드 실행·배포 환경이다. 교통 데이터는 발급 완료된 키로 서울시 공공데이터 포털·공공데이터 포털 API를 호출한다. 개별 API 기능·실시간성·지원 범위는 실제 응답으로 검증한다.
- 앱 서비스의 PostgreSQL 5432 연결은 서버→DB 연결이다. 앱·CLI의 HTTPS API 연결 및 Cloud Run의 HTTP PORT와 구분한다. 자격증명은 서버에서만 관리한다.
- 두 개발자 모두 Spec Kit을 활용한다. 계약 변경은 함께 합의하고 본 문서·예제 JSON을 갱신한다.

## 1. 책임과 적용 범위

서버는 장소 조회, 자연어 구조화, 교통 데이터 조회, 코드 기반 시간 계산, 사용자 요청 재탐색을 수행한다. 앱은 입력·확인, 결과 표시, 계획 선택, 로컬 저장, 수동 출발·도착·취소, 선택 구현인 로컬 알림을 담당한다.

앱 실행용 AI 호출은 서버 내부 구현이다. 앱은 Solar API 키나 Timely 내부 파일 경로를 사용하지 않는다. Hermes의 개발 모델 설정은 이 HTTP 계약과 별개다. 실제 모델명·제공처·엔드포인트는 접근 권한과 대회 조건을 확인해 설정한다.

이 계산 API 초안에는 Journey CRUD와 사용자 계정 API를 정의하지 않는다. 앱 서비스 선택 시 UserData 저장·인증에 필요한 계약을 별도 개정한다. 실시간 GPS 업로드, Push 등록, Calendar 동기화, 택시비 상한선·택시 경로 최적화, 자동 재탐색은 이번 MVP에서 보류한다.

### 제출 형태에 따른 저장 구조

- **CLI·초기 통합: 로컬 저장 + 요청별 계산 서버.** 현재 예제와 저장 흐름의 기준이다.
- **앱 서비스: Supabase UserData 저장 + 클라이언트 로컬 캐시.** 인증·권한·DB 저장 API와 데이터 기준을 구현 전에 합의하며, 고급 계정 동기화는 보류한다.
- 모델이 자유 형식 문장만 반환하는 구조는 앱의 확인 UI와 예외 처리가 불안정하므로, 공개 응답은 아래 구조로 정규화한다.

장소 제공처의 ID를 해석하는 Adapter나 짧은 캐시는 사용할 수 있다. 다만 앱 재시작·서버 재시작 뒤에도 이전 대화를 서버가 기억한다고 가정하지 않는다.

## 2. 연결 규칙

| 항목 | 계약 |
|---|---|
| Base URL | 배포 시 확정할 HTTPS 서버 주소 + `/api/v1` |
| 앱 설정 | Base URL은 앱 환경 설정으로 주입. 실기기에서 개발 PC의 `localhost`를 사용하지 않는다. |
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
| 인증 | 현재 계산 계약은 로그인 없는 CLI·초기 통합 기준. 앱 서비스는 UserData 접근을 위한 인증 계약을 먼저 추가한다. 클라이언트에 고정 비밀 키를 넣어 인증을 대신하지 않는다. 서버 호출 제한은 적용한다. |

해석의 상대 날짜는 요청의 `reference_time`을 기준으로 계산한다. 실제 경로 계획·재탐색의 현재 시각은 **서버 시각**이다. 앱이 시뮬레이션 시각을 보내 실제 운행 계산을 과거로 돌리는 기능은 제공하지 않는다.

## 3. API 목록

아래 경로는 Base URL 뒤에 붙인다.

| Method | 경로 | 사용 시점 | 앱이 사용하는 결과 |
|---|---|---|---|
| GET | `/health` | 설치·배포 확인 | API 서버 응답 여부 |
| GET | `/capabilities` | 앱 시작·지원 여부 갱신 | 막차·장소·AI 지원 상태, 기본값, 제한 |
| GET | `/places?query=...` | 장소 확인·검색 | 선택 가능한 실제 장소 후보 |
| POST | `/mobility/interpret` | 자연어 입력·확인 답변 | 이동 조건 초안, 부족한 필드, 최대 3개 질문 |
| POST | `/journeys/plan` | 사용자가 이동 조건 확인 후 계산 | 후보 경로 1~3개, 권장 출발시각·근거 |
| POST | `/journeys/replan` | 놓침·변경 후 사용자가 재탐색 요청 | 새 계획과 이전 선택 대비 시각 변화 |

## 4. 공통 응답

모든 응답은 `status`, `data`, `error`, `meta`를 포함한다. 성공 응답에서도 error 키를 생략하지 않고 null로 둔다.

| status | HTTP | data | error | 앱 처리 |
|---|---|---|---|---|
| ok | 200 | 해당 API 결과 | null | 결과 표시 |
| needs_confirmation | 200 | 해석 초안·질문 | null | 입력 확인 UI 표시 |
| unavailable | 200 | null | 업무 사유 | 미지원·데이터 부족·경로 없음 안내 |
| error | 4xx/5xx | null | 오류 정보 | 수정 또는 재시도 UI |

`needs_confirmation`은 입력 해석 API가 반환한다. 계산 API에 잘못된 필수 필드를 보냈다면 조용히 보완하지 않고 HTTP 422를 반환한다.

### meta

| 필드 | 타입 | 의미 |
|---|---|---|
| request_id | string | 서버가 발급하는 요청 추적 ID |
| server_time | datetime | 응답 생성 시 서버 시각 |
| api_version | string | v1 |
| is_demo | boolean | 가상 데이터 사용 여부. true인 결과는 앱에 시연 데이터 표시 |

`is_demo`는 클라이언트 요청 옵션이 아니다. 별도 개발/시연 환경에서만 true 결과를 반환한다. 실제 데이터 조회 실패 시 운영 서버가 임의로 Demo 결과로 전환해서는 안 된다.

### error

| 필드 | 타입 | 의미 |
|---|---|---|
| code | string | 앱 분기용 안정적인 오류 코드 |
| message | string | 사용자에게 보여줄 한국어 안내 |
| retryable | boolean | 같은 입력으로 나중에 재시도할 수 있는지 |
| details | array | 필드별 오류 목록. 없으면 [] |
| details[].field | string | 예: trip.arrival_preference_minutes |
| details[].reason | string | 예: OUT_OF_RANGE |

앱은 `message` 문자열 비교로 로직을 분기하지 않는다. 내부 스택·제공처 비밀 값·API 키는 응답에 포함하지 않는다.

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

실제 서버 설정과 확인된 제공처 기능을 반환한다. `available=false`인 기능을 앱이 숨기거나 제한 사유를 안내할 수 있게 한다. 막차가 true여도 모든 서울 경로 지원을 뜻하지 않으며 요청별 범위 검증은 계산 API에서 다시 수행한다.

| data 필드 | 타입 | 설명 |
|---|---|---|
| timezone | string | Asia/Seoul |
| place_search.available | boolean | 장소 검색 가능 |
| interpretation.available | boolean | 자연어 구조화 가능. false여도 수동 폼 입력 허용 |
| appointment.available | boolean | 약속 경로 계산 가능 |
| appointment.time_basis | enum | arrival_time_search / departure_time_search / unsupported |
| last_journey.available | boolean | 검증 가능한 막차 기능 유무 |
| last_journey.scope_note | string | 지원 노선·지역·제약 설명 |
| last_journey.service_date_from / to | date 또는 null | 검증 데이터의 날짜 범위. 미지원일 때 null |
| transport_modes | enum[] | 허용 대중교통 모드. subway / bus |
| max_options | integer | 이번 버전은 3 |
| defaults.arrival_preference_minutes | integer | 미지정 시 제안할 값. 초기 0, 확인 화면에 표시 |
| defaults.transport_modes | enum[] | 초기 subway, bus. 확인 화면에 표시 |
| buffer_policy.version / label | string | 실제 적용 규칙의 버전·이름 |
| limitations | string[] | 사용자에게 표시할 추가 제약 |

자연어를 해석하지 못하는 환경에서도 앱은 장소·시각 수동 입력 후 계산을 요청할 수 있다. `departure_time_search`만 가능하면 서버가 지원하는 미래 출발시각 조회를 이용해 역산·검증한다. 현재 ETA만 얻는 API를 도착시각 기반 조회라고 표시하지 않는다.

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

서버는 해당 제공처의 ID를 다시 해석할 수 있어야 한다. 임시 배열 순번을 ID로 쓰지 않는다. 앱은 ID를 분해하거나 직접 만들지 않는다.

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
| context | 예 | TripDraft 또는 null. 이전 초안과 앱에서 수정·확정한 값을 보내야 함 |

서버는 대화를 영구 저장하지 않는다. 후속 요청은 이전 `data.draft`를 context에 포함한다. 앱의 장소 선택·시각 폼 수정은 해당 필드를 갱신해 전송한다. 서버가 반환한 초안의 확인된 값을 새 문장만 보고 덮어쓰지 않는다. 사용자가 명시적으로 조건을 바꾼 경우 해당 필드만 갱신·재확인한다.

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

선호 적용 우선순위는 이번 이동에서 명시한 값 → 저장된 사용자 선호 → capabilities 기본값이다. 클라이언트는 저장된 도착 여유·이동수단을 새 TripDraft의 해당 필드에 채워 context로 보내며, 이번 이동의 명시적 값이 있으면 이를 우선한다. 앱 서비스의 선호 조회는 UserData 계약 개정 후 연결하고, CLI는 로컬 설정을 사용한다. 택시비 상한선은 수집하거나 전송하지 않는다.

장소·시각이 확정되면 여전히 미지정인 선택값은 capabilities의 기본값으로 채우고 applied_defaults와 summary에 표시한다. 예: 도착 여유 0분, 버스·지하철 허용. last_journey의 arrival_preference_minutes는 0이다. 클라이언트는 적용된 값까지 최종 확인 화면 또는 프롬프트에 보여준다.

필수 정보가 완성되면 status=ok, ready_for_plan=true, missing_fields=[], questions=[]를 반환한다. 이 상태도 사용자의 최종 확인 버튼을 대체하지 않는다. 사용자가 확인한 뒤에만 /journeys/plan을 호출한다.

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
| user_confirmed | 예 | true. 앱의 이동 조건 확인 후 요청 |

user_confirmed는 앱 흐름을 확인하는 값이며 인증이나 위·변조 방지 수단이 아니다.

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

refresh_after는 제공처의 최신성 조건을 반영한다. 확정 정책이 없을 때 서버 기본값은 generated_at + 5분으로 설정하고 추후 조정 가능하게 한다. 앱은 이를 지나면 데이터 재확인을 안내하며, 유효성이 보장된 최신 정보라고 표시하지 않는다. 이 값만으로 백그라운드 자동 호출을 시작하지 않는다.

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

**Buffer의 시간은 legs와 total_duration_minutes에 이미 반영되어 있다. 앱에서 다시 더하거나 권장 출발시각에서 다시 빼지 않는다.** items는 해당 대기·이동 구간에 포함된 추가 여유의 설명이며 합계는 total_minutes와 일치해야 한다. 같은 시간에 여러 여유 항목을 중복 배정하지 않는다.

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
- 구간 duration_minutes는 datetime 차이의 분 값이다. 소수 허용. 앱 표시는 올림할 수 있다.
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

previous_plan의 시각은 앱이 보낸 과거 비교 기준으로만 사용한다. 현재 경로의 운행·정확성 근거로 사용하지 않는다. 위조 여부를 보장하는 서버 저장 기록이 아니므로 추후 보안·공유 기능이 필요하면 별도 저장 모델을 도입한다.

거절·취소 상태에서는 앱이 요청하지 않는다. reason=route_changed도 user_confirmed=true가 필요하다. 서버는 새 결과를 반환할 뿐 기존 로컬 계획을 자동 교체하지 않는다.

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

변화량 두 필드는 소수 분을 허용한다. 앱이 표시를 반올림하더라도 도착 상태 판정은 서버 값에 따른다. 사용자가 다른 후보를 선택하면 comparison은 그 후보의 비교가 아니므로 앱이 시각을 다시 비교하거나 해당 비교 문구를 숨긴다.

전체 예제 `replan_late`: 이전 도착 18:50 → 새 도착 19:10으로 20분 늦어지고, Deadline 19:00을 10분 초과한다.

### 앱 로컬 적용

새 결과를 사용자가 선택하면 앱이 같은 local_journey_id의 선택 계획을 교체한다. 재탐색이 실패·취소되면 이전 기록을 삭제하지 않는다. 단, 이전 경로가 여전히 유효하다는 의미로 표시하지 않는다.

이 버전의 재탐색은 매번 사용자가 요청한다. 자동 재제시 3회 정책을 수동 클릭 횟수 제한으로 잘못 적용하지 않는다. 향후 자동 재탐색을 추가할 때 주기·횟수·중복 사건 관리 API를 별도 설계한다.

## 10. 오류·불가 사유와 앱 동작

| HTTP | status | code | 앱 동작 |
|---|---|---|---|
| 400 | error | INVALID_JSON | 요청 형식 수정. 사용자 입력 재시도 반복 금지 |
| 422 | error | VALIDATION_ERROR | details.field에 맞는 입력 오류 표시 |
| 422 | error | USER_CONFIRMATION_REQUIRED | 이동 조건 확인 화면으로 이동 |
| 422 | error | PLACE_NOT_RESOLVABLE | 이전 장소 ID를 해석할 수 없으므로 다시 검색·선택 |
| 200 | unavailable | OUT_OF_SERVICE_AREA | 서울 또는 제공처 지원 범위 밖 안내 |
| 200 | unavailable | APPOINTMENT_TIME_UNSUPPORTED | 요청한 시각 조건의 경로를 검증할 수 없음을 안내 |
| 200 | unavailable | LAST_JOURNEY_UNSUPPORTED | 막차 데이터·운행일·노선 지원 부족 안내 |
| 200 | unavailable | NO_FEASIBLE_JOURNEY | 지원 데이터에서 조건에 맞는 경로가 없음을 안내 |
| 200 | unavailable | BUFFER_REQUIREMENT_NOT_MET | 요구한 여유를 확보한 막차 경로가 없음. 안전한 탑승을 단정하지 않음 |
| 429 | error | RATE_LIMITED | Retry-After 헤더의 초만큼 재요청 대기 |
| 503 | error | ROUTING_PROVIDER_UNAVAILABLE | 교통 조회 일시 실패. 재시도 버튼 |
| 503 | error | PLACE_PROVIDER_UNAVAILABLE | 장소 검색 일시 실패. 재시도 버튼 |
| 503 | error | AI_UNAVAILABLE | 자연어 해석 실패. 수동 입력 제공 |
| 502 | error | UPSTREAM_RESPONSE_INVALID | 제공처·모델 결과 검증 실패. 잘못된 경로·시간을 표시하지 않음 |
| 504 | error | UPSTREAM_TIMEOUT | 외부 요청 시간 초과. 재시도 버튼 |
| 500 | error | INTERNAL_ERROR | 일반 오류 안내와 request_id 제공 |

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

## 11. 호출 순서와 앱 상태

1. 앱 시작 시 /capabilities를 읽어 기능·기본값·지원 범위를 확인한다.
2. 사용자가 자연어를 입력하면 /mobility/interpret를 호출한다.
3. 장소 질문은 /places 검색 결과 선택 UI로 처리한다.
4. 앱이 context를 갱신해 /mobility/interpret를 다시 호출하거나, 완성된 수동 폼을 직접 검증한다.
5. 최종 확인 화면에서 사용자 동의를 받은 뒤 /journeys/plan을 호출한다.
6. 후보를 선택해 앱 로컬에 Plan 전체와 선택한 option_id를 저장한다.
7. 출발·도착 버튼은 로컬 상태를 변경한다.
8. 재탐색은 /journeys/replan 호출 후 결과 확인·선택을 거쳐 로컬 계획을 갱신한다.

수동 폼 사용 시 /interpret는 필수가 아니다. 서버는 /plan의 필수 조건을 동일하게 검증한다.

### 로컬 저장 모델 예시

이 모델은 서버 API가 아니라 앱 내부 합의다.

| 필드 | 설명 |
|---|---|
| local_journey_id | 앱 생성 UUID |
| selected_plan | Plan 전체 |
| selected_option_id | 선택한 경로 후보 |
| state | scheduled / departed / arrived / cancelled |
| created_at / updated_at | 날짜·시간대 포함 시각 |
| last_calculation_request_id | 문제 추적용 서버 request_id |
| notification_id | 로컬 알림을 구현했다면 기기 알림 ID, 아니면 null |

최초 저장은 scheduled, 출발 버튼은 departed, 도착 버튼은 arrived, 취소는 cancelled로 처리한다. 미출발 상태에서 사용자가 직접 도착을 확인할 수도 있다. arrived/cancelled는 종료 상태이며 자동 재탐색·출발 알림을 하지 않는다. 종료 기록을 다시 사용하려면 새 이동으로 등록한다. 재탐색 성공만으로 departed를 scheduled로 되돌리지 않는다.

선택 계획이 수정·취소·종료되면 기존 로컬 알림을 취소하거나 갱신한다. 서버가 알림을 발송한 것으로 표시하지 않는다. 앱 밖의 교통 변화를 감지하는 기능은 이번 API에 없다.

## 12. 시간 초과·재시도·중복 요청

- 서버 처리 제한 초안: health/capabilities 3초, places 10초, interpret/plan/replan 25초.
- 앱 대기 제한: GET 15초, POST 30초. 실제 제공처 제약으로 바꿔야 하면 두 담당자가 함께 수정한다.
- rate limit의 Retry-After는 정수 초로 반환한다.
- 앱은 버튼 중복 클릭을 막고 로딩 상태를 표시한다.
- 입력이 바뀐 뒤 이전 요청이 늦게 도착하면 새 상태를 덮어쓰지 않는다. 앱에서 요청 순번 또는 취소로 처리한다.
- POST는 자동 반복 호출하지 않고 사용자 재시도를 제공한다. 계산 요청은 서버 리소스를 생성하지 않지만 모델·교통 호출 비용이 발생할 수 있다.
- 같은 계산을 다시 요청해도 현재 시각·교통 상태가 달라 결과가 바뀔 수 있다. plan_id 재사용이나 동일 응답을 보장하지 않는다.
- 계산 중 네트워크가 끊기면 로컬 이동 기록은 유지하고 결과 미수신으로 표시한다.

## 13. 프론트엔드 Mock 예제 사용

[examples.json](Docs/api/examples.json)은 요청, HTTP 상태, 완전한 응답을 case별로 묶었다. 실행 서버나 테스트 완료 결과가 아니라 **이 계약에 맞춰 앱을 개발하기 위한 fixture**다.

| case id | 확인할 화면 |
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

앱은 Mock 모드에서 case.response와 case.http_status를 사용한다. 실제 호출로 전환할 때 JSON 구조와 화면 분기 코드는 유지하고 Base URL/데이터 연결 부분만 바꾼다. 예제의 날짜는 고정이므로 Mock 시간도 해당 meta.server_time으로 맞춘다. 실제 서버 계산의 현재 시각을 예제 날짜로 바꾸지 않는다.

## 14. 두 사람의 구현·검증 순서

### 첫날 합의할 사항

- 이 명세의 공개 경로와 응답 키를 두 사람이 함께 고정한다.
- 본인은 examples.json으로 확인·결과·오류 화면을 만든다. CLI 선택 시 동일한 입력·출력을 명령과 프롬프트로 제공한다.
- 친구는 /health, /capabilities와 장소·교통 데이터 검증부터 진행한다.
- 자연어 모델이 아직 연결되지 않아도 본인은 수동 입력으로 /journeys/plan 통합을 준비할 수 있다.
- 첫날 끝에 클라이언트에서 배포 서버를 호출한다. 앱 형태로 확정되면 설치 앱, CLI 형태로 확정되면 CLI에서 검증한다.
- 앱 서비스로 확정하면 UserData·인증·권한·저장 계약을 공동 개정한 뒤 서버와 클라이언트에 연결한다.

### 의미 있는 계약 검증

1. 명확한 19:00 도착 표현이 확인 질문 없이 유지된다.
2. origin/destination 확정 없이 계획 계산을 요청하면 422로 처리된다.
3. 19:00 Deadline, 10분 전 선호의 target_arrival_at은 18:50이다.
4. 예상 도착이 18:55이면 preference_missed, late_by_minutes=0이다.
5. 도보·대기·추가 Buffer가 이미 포함된 전체 이동시간에 다시 Buffer를 더하지 않는다.
6. 막차 운행일과 다음 날 도착시각을 올바르게 처리한다.
7. 미지원 데이터와 실제 검색 결과 경로 없음이 다른 코드다.
8. 재탐색의 양수 arrival_change_minutes는 더 늦은 도착이다.
9. 실패한 재탐색이 기존 로컬 기록을 지우지 않는다.
10. 실제 제공처 장애 시 Demo 경로로 자동 대체하지 않는다.

변경이 필요하면 명세와 fixture를 함께 수정한다. 실제 데이터 제공처가 바뀌어도 앱 공개 계약을 유지하는 Adapter를 구현한다.

## 15. 구현 전에 확정할 환경 값

공개 JSON 계약은 위 내용으로 작업할 수 있다. 아래 운영 값은 실제 접근 가능한 환경에서 결정한다.

- 배포 Base URL.
- 장소·교통 제공처와 사용 가능한 키·한도.
- 지원 지역·노선·운행일 범위.
- 미래 시각 검색 방식과 막차 검증 가능 여부.
- 실제 Buffer 정책 버전과 수치.
- 앱 실행용 AI 모델 ID·호출 경로.
- 호출 제한과 제공처별 최신성 기준.

미확정 값을 실제 지원 기능처럼 하드코딩하지 않는다. capabilities에서 검증된 상태를 반환하고 불가능한 요청은 정의한 불가 사유로 응답한다.
