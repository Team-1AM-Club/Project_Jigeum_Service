# 친구용 백엔드 인수인계 — 공통 시작점

## 이번 공유 범위

이 인수인계 커밋은 공통 문서·API 계약·폴더 골격만 제공한다. 제품은 **MCP 서비스**이며 별도 사용자 화면은 개발하지 않는다.

- 포함: 제품 방향, 분업, REST 계약과 예제 JSON, Agent 역할, Spec Kit 명세, 백엔드 준비 폴더, 대화 상태 저장·검증·전이 설계, Idempotency-Key 계약.
- 미포함: 작성자의 작업 중 백엔드 코드와 테스트, MCP 구현, Skill ZIP, 개인 Hermes 설정, 디버그 파일, 비밀키.
- backend/app/main.py와 backend/Dockerfile은 자리표시자다. 실행 가능한 서버·이미지가 아니다.
- .hermes/skills/는 준비 폴더다. 실제 원본 반입·검토·연결·실행 검증은 별도 작업이다.
- 이 문서는 실행·테스트·배포 완료를 뜻하지 않는다.

## 작업 경로와 시작 방법

저장소: https://github.com/Team-1AM-Club/Project_Jigeum_Service
공통 기준 브랜치: develop

처음 받는 경우:

~~~sh
git clone --branch develop https://github.com/Team-1AM-Club/Project_Jigeum_Service.git
cd Project_Jigeum_Service
git switch -c feature/backend-mvp
~~~

이미 복제한 저장소가 있으면 새로 복제하거나 초기화하지 않는다. 먼저 git status로 자신의 미커밋 작업을 확인하고 보존한 후 develop의 최신 변경을 반영한다.

친구의 주 작업 경로는 **<저장소 루트>/backend/**다. 작성자 PC의 예시는 E:/MABC/backend/이며 친구 PC에서 같은 절대 경로를 만들 필요는 없다.

| 경로 | 친구가 구현할 내용 |
|---|---|
| backend/app/main.py | FastAPI 진입점과 라우터 연결 |
| backend/app/api/ | API 라우트와 공통 응답·오류 처리 |
| backend/app/schemas/ | 요청·응답·외부 데이터 검증 |
| backend/app/domain/ | 시간 계산·Buffer·조건 확인 정책 |
| backend/app/integrations/ | 장소·교통·Solar 어댑터, demo/live 분리 |
| backend/app/agents/ | MainAgent·SubAgent 실행 조율 |
| backend/tests/unit/ | 계산·시간대·경계 조건 테스트 |
| backend/tests/contract/ | API 계약·예제 JSON 검증 |
| backend/tests/integration/ | 최소 흐름과 제공처 연동 검증 |

.gitkeep은 빈 폴더를 Git으로 공유하기 위한 파일이며 구현 완료 표시가 아니다.
## 먼저 읽을 문서

1. [IDEA.md](../IDEA.md): 최신 제품 범위와 역할.
2. [API_SPEC.md](../API_SPEC.md), [예제 JSON](api/examples.json): 공동 통합 기준. 예제는 가상 데이터다.
3. [Agent 역할](../agent_specs/README.md): 해당 MainAgent·SubAgent 명세.
4. [기능 명세](../specs/001-trip-intake-and-planning/spec.md), [계획](../specs/001-trip-intake-and-planning/plan.md), [작업 목록](../specs/001-trip-intake-and-planning/tasks.md).

이전 Skill 예시는 현재 MVP의 필수 구현 목록이 아니다. 충돌 시 IDEA.md와 API_SPEC.md를 우선하고, 관련 명세를 함께 정정한다.

## 분업 경계와 연결 계약

본인은 MCP 도구·HTTP 연결·Hermes 확인/선택 흐름·시연을 담당한다. 친구는 FastAPI·Agent·Skill·교통 데이터·계산·테스트·배포를 담당한다. Hermes + Upstage Solar Pro4를 개발·시연에 사용한다.

| 본인 MCP 도구 | 친구 백엔드 HTTP API |
|---|---|
| get_capabilities | GET /api/v1/capabilities |
| search_places | GET /api/v1/places |
| interpret_trip | POST /api/v1/mobility/interpret |
| plan_journey | POST /api/v1/journeys/plan |
| replan_journey | POST /api/v1/journeys/replan |

health는 내부 연결 확인용이다. 정확한 경로·필드·상태·오류 의미는 API_SPEC.md를 따른다. MCP 도구 스키마와 결과/오류 매핑은 아직 별도 합의·검증이 필요하다.
## 대화 상태 저장·검증·전이 설계

이 절은 대화 상태 저장·검증·전이 설계의 공통 규칙을 기술한다. 규칙의 목적은 다음 세 가지다.

- **효과적 once(effectively-once)**: 네트워크·외부 provider의 exactly-once 보장이 아니라, 백엔드 상태 반영의 effectively-once를 보장한다.
- **재시도 안전**: 동일 대화·동일 요청의 재시도에서 상태가 두 번 바뀌지 않도록, idempotency 기록과 상태 변경을 같은 트랜잭션으로 묶는다.
- **만료 처리 일관성**: 없거나 만료된 conversation은 410 CONVERSATION_EXPIRED로 통일한다. (404/410 중 하나로 통일하되, 이번 약정은 410으로 한다. 과거 존재 여부 구분을 위한 별도 이력은 보관하지 않는다.)

### 상태 단일 진실 원천

상태 단일 진실 원천은 백엔드다. Hermes 세션·MCP 메모리는 권위 있는 저장소로 사용하지 않는다.

### DB 저장 방식

대화 상태는 SQLite에 TTL 방식으로 저장한다. conversation_id 기준으로 관리하며, 만료 시각(expires_at)이 지나면 즉시 만료 처리한다.

- 백엔드는 conversation_id로 조회하되, expires_at <= now이면 만료 판단을 우선한다.
- TTL은 제공 계약에 따른다(별도 지정 없으면 기본값 사용).
- 만료 판단은 매 요청 시 확인하며, 별도 정리 주기와 독립적으로 동작한다.

### 대화 수명 주기

1. conversation 생성: 첫 상태 변경 요청이 수신되면 백엔드가 conversation_id를 생성할 수도 있고, MCP가 생성한 것을 받아 저장할 수도 있다(구현 시점에 결정).
2. 정상 상태 유지: 확인 조건·후보·선택 계획이 유지된다.
3. 만료: expires_at까지 활성화되지 않거나, 계약이 정한 다른 만료 조건에 도달하면 만료 처리한다.
4. tombstone → hard delete: 만료 후 24시간 동안 최소 메타데이터만 보관하고, 이후 완전 삭제한다.
5. 대화당 상태 변경 요청 횟수 제한은 별도 규칙이 없는 한 무제한으로 둔다.

### 상태 저장·갱신 흐름의 기본 원칙

- 어떤 요청이 대화 상태를 변경하면, 그 변경과 idempotency 기록은 같은 트랜잭션으로 커밋한다.
- 제공자 실패는 상태 변경을 일으키지 않는다. domain 상태·revision·updated_at은 바뀌지 않는다.
- 만료된 conversation을 재사용하지 않는다.
- 동일 key의 재시도는 상태 변경을 일으키지 않고 저장된 응답을 반환한다. 단, body가 다르면 충돌 처리한다.

### 상태 저장의 검증 책임

검증은 코드로 처리한다. AI는 구조화·질문·설명만 한다.

- time·duration·이동 시간 계산은 코드.
- 상태 전이 조건은 코드.
- 횟수 제한·권한 검증은 코드.
- AI는 확인된 입력 구조화, 조건 해석 확인 질문, 오류·모호함 설명을 담당한다.



### Idempotency-Key 계약

- MCP가 각 상태 변경 요청에 Idempotency-Key를 생성해 전달한다. 형식은 UUID v4 표준 문자열(36자)이다.
- MCP는 Idempotency-Key를 HTTP 헤더 `Idempotency-Key`로 전달한다.
- 백엔드는 응답 시 응답 헤더 `Idempotency-Key`로 동일한 키를 돌려준다.
- 백엔드 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않는다.
- Idempotency-Key가 누락되거나 형식이 맞지 않으면 422 VALIDATION_ERROR로 처리한다.
- 같은 Idempotency-Key로 다른 요청이 이미 처리됐으면 409 IDEMPOTENCY_KEY_REUSED로 처리한다. 이 오류는 retryable이 아니며, 같은 키로 다른 요청을 재시도하지 않는다.

### Idempotency-Key의 저장과 매칭

- 백엔드는 conversation_id + idempotency_key에 UNIQUE 제약을 둔다.
- 상태 변경 요청 처리 시 해당 키가 이미 존재하면, 저장된 응답을 찾아 그대로 반환한다.
- 같은 key + 같은 payload 재시도는 최초 응답을 반환한다. 이 동작이 백엔드 상태 반영의 effectively-once를 구현한다.
- 같은 key + 다른 payload는 409 IDEMPOTENCY_KEY_REUSED로 처리한다. retryable은 false다.
- idempotency 기록은 상태 변경과 같은 DB 트랜잭션으로 커밋한다.

### payload hash 계약

- 각 상태 변경 요청마다 payload hash를 계산해 storage에 record한다.
- payload hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 그리고 상태 변경 전체 JSON body.
- body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256을 hash한다.
- hash에 MCP가 생성한 Idempotency-Key 자체, 서버가 생성한 request_id/server_time, tracing 헤더, 전송 시각 등 비즈니스 의미가 없는 값은 넣지 않는다.
- 백엔드 canonicalization은 JSON 객체 키 순서와 공백 차이만 흡수한다.
- 배열 순서, null과 필드 생략, 값 변경은 동일하다고 간주하지 않는다.
- 일부 필드만 선택적으로 hash하지 않는다. 전체 body를 canonicalize 대상에 포함한다.

### body 책임

- MCP는 최초 요청 body와 expected revision을 보관한다.
- 같은 논리적 요청 재시도 시 그대로 재전송하며, 재시도 과정에서 현재 시각이나 revision을 새 값으로 바꾸지 않는다.
- 백엔드는 body를 canonicalize하여 hash를 비교할 뿐, body를 해석하거나 재구성하지 않는다.

### 동일 key 우선순위

- 유효한 conversation에서 이미 성공한 동일 key·동일 payload 재요청은 stale revision 검사보다 먼저 처리한다.
- 이 경우 상태를 다시 변경하지 않고 저장된 응답을 반환한다.
- 단, conversation이 만료됐다면 과거 성공 응답을 복원하지 않고 410 CONVERSATION_EXPIRED로 처리한다.
- 상태 변경과 idempotency 결과 기록은 같은 DB 트랜잭션으로 커밋한다.

### provider 호출 순서

provider가 필요한 상태 변경은 다음 5단계 순서로 처리한다.

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

### 만료된 conversation과 tombstone

- expires_at <= 서버 현재 시각이면 즉시 만료로 판단한다.
- 해당 요청은 상태 변경과 revision 증가 없이 410 CONVERSATION_EXPIRED로 반환한다.
- 만료 시 확인 조건·후보·선택 계획 payload를 제거하고, conversation_id·마지막 revision·expired_at만 tombstone으로 보관한다.
- tombstone은 24시간 유지 후 hard delete한다. hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리한다.
- 정리는 백엔드 시작 시 한 번, 실행 중 주기적으로 수행한다. 요청 시 만료가 발견되면 cleanup 주기를 기다리지 않고 즉시 tombstone 처리한다.
- tombstone 전환으로 사용자 revision은 증가시키지 않고 마지막 revision을 유지한다.

### tombstone 생성 충돌 처리

- 동일 conversation_id의 만료 처리는 멱등하게 수행한다.
- 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환한다.
- 별도 테이블을 사용하는 경우 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다.
- 충돌 후 해당 tombstone이 존재함을 확인하면 동일하게 410 CONVERSATION_EXPIRED로 응답한다.
- 기존 expired_at을 재설정하거나 tombstone 보존 기간을 연장하지 않는다.
- 중복 키 이외의 DB 오류는 무시하거나 410으로 감추지 않는다.
- hard delete 이후에는 404 CONVERSATION_NOT_FOUND를 반환하고, 과거 존재 여부를 구분하기 위한 별도 이력은 보관하지 않는다.

### 후보만 만료된 경우

- conversation과 confirmed_conditions는 유지한다.
- active_selected_plan도 유지한다.
- 만료된 candidate_set은 선택할 수 없다.
- 해당 candidate 선택 요청은 410 CANDIDATE_SET_EXPIRED로 처리한다.
- revision은 변경하지 않는다.
- 사용자는 기존 확인 조건으로 새 후보 생성을 요청할 수 있다.
- 새 후보가 생성돼도 active_selected_plan은 자동 교체하지 않는다. 새 후보 중 하나를 명시적으로 선택했을 때만 active_selected_plan을 변경한다.

### 재시도 정책

- MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 확정한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.
- 네트워크 연결 실패·timeout 또는 계약상 retryable=true인 502/503/504에만 적용한다.
- 같은 Idempotency-Key와 같은 body로 재시도한다.
- 4xx·409·410·검증 실패·invalid response는 자동 재시도하지 않는다.
- 해석 가능한 오류 응답이 retryable=false이면 HTTP 상태만 보고 재시도하지 않는다.
- 백엔드는 workflow 수준의 자동 재시도를 하지 않으며, provider 호출을 DB 트랜잭션 내부에 포함하지 않는다.
- retryable 오류 여부는 기존 error envelope에 표시한다.



## 첫 작업 순서

이 문서와 다음 두 문서를 함께 보면서 결정 가능한 것부터 닫는다.

1. [IDEA.md](../IDEA.md) — 제품 방향, MVP 범위, 분업.
2. [API_SPEC.md](../API_SPEC.md) — REST/JSON 계산 API 계약. 필드·상태 코드·오류 매핑을 여기서 닫는다.
3. [Docs/api/examples.json](../Docs/api/examples.json) — 계약 fixture. 예시 JSON의 요청·응답 쌍을 그대로 사용할 수 있는지 확인한다.

그다음 아래 순서로 작업한다.

1. 스키마(Pydantic)와 모델(SQLAlchemy)을 먼저 정한다.
2. 가능성은 없지만 오류 표·경로·헤더 계약을 먼저 맞춘다.
3. 저장 대화 상태·idempotency·만료 처리의 코드를 먼저 넣는다. 외부 호출은 그 뒤에 붙인다.
4. 외부 호출이 필요한 흐름은provider 호출 순서를 지킨다. DB 쓰기 트랜잭션 안에서 외부 호출을 하지 않는다.

## 구현 전에 함께 확정할 것

- API 키·호출 한도·호출 가이드. 소유자는 친구다. MCP 호출 성공에 필요하므로 백엔드 착수 전에 양식을 받아 채워야 한다. 아직 받지 않았으면 아직 시작하지 않는다.
- 백엔드가 대화 상태를 owner로 갖고 SQLite/TTL로 저장하는 설계. 이 설계의 세부(conversation_id 기준, 만료 시점, tombstone 24시간 후 삭제, POST 요청은 외부 호출 전 fast failure)는 아래 "대화 상태 저장·검증·전이 설계"에 적어뒀다.
- 서비스 호스트·포트·접근 제어. 로컬 우선(127.0.0.1:8000)으로 시작하고, 클라우드 배포 시 환경변수/포트 매핑만 바꾼다.
- Provider 호출 실패 시 재시도 여부·재시도 횟수·대기 시간. MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 잡았다(제한된 재시도 문단 참조). 변경하려면 두 사람이 함께 바꾼다.

## 첫 인수인계 결과물

이 커밋이 주는 것:

- 이 문서.
- [API_SPEC.md](../API_SPEC.md).
- [Docs/api/examples.json](../Docs/api/examples.json).
- 역할 명세: `agent_specs/` 아래 읽기.
- Spec 명세: `specs/002-backend-mvp-implementation/`.



