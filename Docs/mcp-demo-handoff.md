# MCP 데모 구현 상태 및 백엔드 인수인계

**기준 커밋**: `75d64c2` (feature/mcp-demo-tools)
**목적**: 현재 MCP 데모 구현 범위, 검증 결과, Hermes 연결·시연 방법, 안전 규칙, 데모/실제 경계, 백엔드 담당자에게 필요한 후속 연동 사항을 한 곳에 정리한다.
**범위**: 이 문서는 데모 구현 상태와 인수인계 메모다. 실제 서버·배포·실제 교통 연동 완료를 뜻하지 않는다.
**공유 방식**: 개인 PC 절대 경로, 비밀키, 실제 환경값이 필요한 설정은 넣지 않는다. 실제 값이 필요한 항목은 “별도 합의/별도 환경”으로 남긴다.

---

## 1. 구현 완료 범위

구현 대상은 `mcp-jigeum-demo` 서버의 MCP 데모 도구 5개이며, 모두 `Docs/api/examples.json`의 fixture 기반 응답을 사용한다.

- `get_capabilities`: 지원 기능·기본값·제한 확인
- `interpret_trip`: 이동 조건 구조화, 부족한 항목과 확인 질문 반환
- `search_places`: 장소 검색 후보 반환
- `plan_journey`: 확인된 조건으로 약속 출발시각 또는 막차 계획 계산
- `replan_journey`: 사용자 요청에 따라 대안과 기존 계획 대비 변화 계산

이 5개 도구는 현재 **데모 모드**로 동작하며, 실제 FastAPI나 실제 교통·장소 제공자에 연결하지 않는다. 응답의 `meta.is_demo`는 모두 `true`다.

---

## 2. 검증 결과

아래 결과는 `75d64c2` 기준의 기존 검증 결과다.

- 전체 unittest discover: 75 tests OK, skipped=1, exit 0
  - skip 1건은 `user_confirmed` 누락 시 MCP 스키마가 호출 전에 거부하는 기존 예상 동작 관련 테스트다. 이는 서버 측 예외 처리보다 스키마 단계에서 먼저 막히는 동작으로 이해한다.
- `mcp-server/verify_mcp.py`: 통과
- `mcp-server/verify_http.py`: 통과
- `git diff --check`: 통과
- Hermes에서 5개 도구 실제 호출 및 전체 흐름 통과
  - 호출 순서: `get_capabilities` → `interpret_trip`(확인 필요) → `interpret_trip`(계획 가능) → `search_places`(정상) → `search_places`(빈 결과) → `plan_journey`(확인 거부) → `plan_journey`(정상 계획) → `replan_journey`(정상 재탐색) → `get_capabilities`(재확인)
  - `plan_journey`에서 `user_confirmed=false`일 때 `USER_CONFIRMATION_REQUIRED`가 반환되고 계획이 계산·적용되지 않음을 확인함
  - `replan_journey`는 `comparison`과 새 `plan`만 반환하며, 사용자 선택 없이 기존 계획이 자동 적용됐다는 표현은 없음을 확인함

이 검증 결과는 데모 도구 기준이며, 실제 백엔드 연결·배포·실제 데이터 검증이 별도로 필요하다.

---

## 3. Hermes 연결 및 시연 방법

### 3.1 서버 실행 파일과 저장소 상대 경로

- MCP 서버 구현 파일: `mcp-server/jigeum_mcp_server.py`
- 검증 스크립트: `mcp-server/verify_mcp.py`, `mcp-server/verify_http.py`
- 예제는 저장소 루트 기준 상대 경로 `Docs/api/examples.json`을 사용한다.

공유 문서에는 개인 PC의 절대 경로(예: `E:\...`)를 하드코딩하지 않는다. 실제 설치·실행 경로는 각 환경 기준으로 맞춘다.

### 3.2 MCP 설정 후 재로드

Hermes 설정에 MCP 서버를 등록한 뒤에는 MCP 도구가 현재 세션에 노출되도록 재로드가 필요할 수 있다. 실습·시연 환경에서 도구 목록이 보이지 않으면 먼저 MCP 설정 반영 여부와 재로드 상태를 확인한다. 필요하면 `/reload-mcp` 또는 세션을 다시 시작한다.

### 3.3 정상 시연 순서

시연은 아래 순서로 진행한다.

1. `get_capabilities`
2. `interpret_trip`
3. `search_places`
4. 사용자 조건 확인
5. `plan_journey`
6. `replan_journey`

계산은 사용자 조건 확인 이후의 `plan_journey` 단계에서만 수행한다. `interpret_trip`의 `ready_for_plan=true`는 입력 준비 완료이지 사용자 동의가 아니다.

---

## 4. 안전 규칙

- `user_confirmed=true`가 전달되기 전에는 계획 계산을 수행하지 않는다.
- `user_confirmed=false`로 계획 호출을 시도하면 `USER_CONFIRMATION_REQUIRED`로 거부된다.
- `replan_journey`는 새 대안 `plan`과 `comparison`만 반환한다.
- 재탐색 결과는 사용자가 선택한 뒤에만 현재 대화의 선택 계획에 적용한다. 사용자 선택 없이 기존 계획을 자동 적용하지 않는다.
- 실제 경로·막차·시간은 모델이 생성하지 않는다. 시뮬레이션·데모 데이터라도 실제 교통 정보로 소개하지 않는다.

---

## 5. 데모와 실제 연동 경계

현재는 다음과 같이 데모 경계 안에서만 동작한다.

- `Docs/api/examples.json` fixture 기반 응답만 사용한다.
- 실제 FastAPI 호출은 하지 않는다.
- 실제 교통·장소 제공자 연동은 없다.
- 실제 경로·시간·막차 계산을 수행하지 않는다.
- UserData DB, 회원가입, 영구 이동 이력은 현재 범위에 포함하지 않는다.
- 문서에는 비밀키, 실제 API 키, 개인 PC 절대 경로를 포함하지 않는다.

데모 데이터와 실제 데이터는 구분해서 다룬다. 운영 조회 실패를 데모 결과로 자동 대체하지 않는다.

---

## 6. 백엔드 담당자에게 필요한 후속 연동 사항

데모 도구를 실제 서비스로 전환하려면 아래 항목의 연결 지점과 합의를 정리해야 한다.

### 6.1 fixture 응답을 실제 FastAPI 응답으로 교체할 연결 지점

- `get_capabilities` → GET `/api/v1/capabilities`
- `search_places` → GET `/api/v1/places`
- `interpret_trip` → POST `/api/v1/mobility/interpret`
- `plan_journey` → POST `/api/v1/journeys/plan`
- `replan_journey` → POST `/api/v1/journeys/replan`

데모 모드에서는 현재 fixture 응답을 그대로 반환하지만, 실제 연동 모드에서는 위 API를 호출하고 응답 봉투(`status`, `data`, `error`, `meta`)를 그대로 전달해야 한다.

### 6.2 장소 검색, 계획 생성, 재탐색의 API 계약 확인

- 요청·응답 필드, 필수/선택 여부, 상태 분기, 오류 코드를 `API_SPEC.md` 기준으로 맞춘다.
- `plan_journey`와 `replan_journey`의 `user_confirmed`와 확인 상태를 백엔드와 어떻게 결부할지 합의한다.
- `replan_journey`의 `previous_plan`, `current_origin_place_id`, `reason` 처리 방식도 함께 확인한다.

### 6.3 conversation_id / revision / idempotency 및 상태 소유권 합의

- 대화별 문맥, 확인 조건, 선택 계획의 저장 위치·수명을 누가 담당하는지 정한다.
- 중복·지연 계산이 현재 상태를 덮어쓰지 않도록 요청 식별 또는 취소/순번 처리 방식을 합의한다.
- 서버가 `plan_id`로 과거 계획을 복원한다고 가정하지 않는다.

### 6.4 provider 상태에 따른 오류 응답 매핑 합의

- 동일한 요청이라도 제공처 상태에 따라 `ROUTING_PROVIDER_UNAVAILABLE`, `PLACE_PROVIDER_UNAVAILABLE`, `unavailable` 계열 등으로 결과가 달라질 수 있다.
- MCP 계층이 이 차이를 어떻게 구분하고 사용자에게 안내할지 매핑을 합의한다.

### 6.5 demo와 real 실행 모드 분리 방식 합의

- 현재는 demo 모드만 동작한다. 실제 연동 시 demo/real을 어떻게 전환할지, 환경변수나 모드 플래그로 분리할지 합의한다.
- demo 모드에서도 실제 계약 구조와 결과 분기는 유지하고, 연결 방식만 바꾸는 방향을 권장한다.

### 6.6 계약 변경 시 문서 공동 갱신

- API 계약 변경이 필요하면 `API_SPEC.md`와 `Docs/api/examples.json`을 두 개발자가 함께 갱신한다.
- MCP 도구 스키마·오류 매핑·확인/상태 소유권도 함께 정리한다.

---

## 7. 현재 계약 모호성

아래 항목은 현재 합의된 범위가 부족하거나 확인되지 않은 부분이다. 데모 동작과는 별개로 이후 협의가 필요하다.

- 동일한 계획 요청에서 provider 상태별 오류를 구분할 입력이 현재 요청 스키마만으로는 부족할 수 있다. 어떤 경우에 어떤 오류 코드로 매핑할지는 공동 합의가 필요하다.
- `Docs/api/examples.json`에는 replan 전용 실패 fixture가 없다. 따라서 데모에서 replan 실패 사례를 임의로 생성하지 않았다.
- replan 실패 사례, provider 상태별 오류, demo/real 모드 전환 방식은 현재 문서가 단정하지 않는다. 향후 오류 fixture 또는 백엔드 상태 계약에 대한 공동 합의가 필요하다.

---

## 문서 유지 원칙

- 실제 기능 완료 여부는 실행 결과로만 판단한다. 데모 동작을 실제 서비스 완료로 소개하지 않는다.
- 데모 데이터와 실제 데이터를 구분해서 말한다.
- 코드·API 계약·예제 JSON을 수정하지 않는 한 이 문서의 내용도 그에 맞춰 갱신하지 않는다.
- 비밀키, 실제 환경값, 개인 경로는 문서에 넣지 않는다.
