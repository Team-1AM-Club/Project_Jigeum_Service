# Research: Backend MVP Implementation

**Feature**: [specs/002-backend-mvp-implementation/spec.md](../spec.md)
**Date**: 2026-09-14

## 1. 실제 장소·교통 제공처, 키, 한도, 호출 가이드

### Decision
MVP에서는 서울시 공공데이터 포털·공공데이터 포털의 발급된 키를 사용하되, 구체적인 서비스·엔드포인트·한도는 **사용자가 키·한도·호출 가이드를 양식으로 제출한 뒤 확정**한다. 양식 제출 전까지는 데모/예시 데이터로 최소 흐름을 먼저 구현한다.

### Rationale
IDEA.md·BACKEND_HANDOFF.md·API_SPEC.md 모두 실제 제공처의 서비스명·엔드포인트·권한·응답·지원 범위를 "실제 검증"해야 한다고 명시한다. 지금 당장 어떤 API가 어떤 범위로 가능한지는 문서만으로는 확정할 수 없다.

### Alternatives considered
- 모든 가능한 교통 API를 지금부터 조사·정리: 범위 과다, 키·한도 확인 전에는 구현 판단에 연결하기 어려움.
- 특정 API를 지금 단정: 지원 범위·막차 검증 가능 여부가 틀릴 위험이 있음.

### Deferred
- 실제 사용할 장소·교통 API의 서비스명·엔드포인트·권한·응답·지원 범위
- 키의 호출 한도·최신성·실패 시 재시도 정책
- 막차 검증 가능 여부
- 위 항목은 사용자 양식 제출 후 확정한다.

## 2. 백엔드 내부 AI 호출 설정

### Decision
백엔드 내부 Agent/Skill 런타임에서 Solar 계열 모델을 사용할 수 있다고 가정하되, **정확한 모델 ID·호출 경로·접근 권한은 사용자 양식 제출 후 확정**한다. MVP 구현에서는 필요한 지점을 스텁/데모 기준으로 먼저 처리할 수 있게 한다.

### Rationale
IDEA.md·API_SPEC.md·BACKEND_HANDOFF.md 모두 백엔드 AI 설정은 "별도 검증/확정" 대상으로 남겨둔다. 지금 확정 없이 특정 모델 ID나 호출 경로를 단정하는 것은 금지된다.

### Alternatives considered
- 지금 특정 모델/엔드포인트를 단정: 미확정 값을 지원 기능처럼 하드코딩하는 위험이 있음.
- 백엔드 AI를 이번 MVP에서 제외: 가능하지만, 해석·Agent 실행 구조를 전혀 안 쓰는 방향으로 고정하기 전이라 유보.

### Deferred
- Solar 모델 ID·제공처·호출 경로·접근 권한
- 호출 횟수·시간 제한 정책
- 위 항목은 사용자 양식 제출 후 확정한다.

## 3. Buffer 정책 버전과 세부 항목

### Decision
MVP에서는 Buffer 정책 이름만 두고(예: `demo-v1`), 세부 항목·분은 실제 정책이 확정되기 전까지 세부 보장값처럼 주장하지 않는다. API 응답에는 `policy_version`, `total_minutes`, `items`, `warnings`를 남길 수 있도록 구조를 준비한다.

### Rationale
API_SPEC.md는 Buffer 시간이 이미 총 이동시간에 포함되어 있다고 명시하고, 중복 가산을 금지한다. 정책 확정 전에 세부 수치를 확정값으로 주장하면 SC-004 검증과 충돌할 수 있다.

### Alternatives considered
- Buffer를 아예 안 씀: MVP 후기 확장에서 Buffer 관련 경고·설명 요구를 놓칠 수 있음.
- 세부 분과 항목을 지금 확정: 미확정 정책을 검증 가능한 사실처럼 만드는 위험.

### Deferred
- 실제 Buffer 정책 버전·라벨·항목·분
- Buffer 관련 warning code의 세부 정의 확장

## 4. Cloud Run/배포 Base URL·포트·환경변수·접근 제어

### Decision
로컬 개발 우선 시작: FastAPI는 로컬에서 `127.0.0.1` + 선택한 포트로 실행한다. Cloud Run 배포 시에는 플랫폼의 `PORT` 환경변수와 `0.0.0.0` 바인딩을 사용한다. 환경변수명은 구현 시점에 정리하되, Base URL·포트·접근 제어는 아직 미확정으로 남긴다.

### Rationale
헌법과 BACKEND_HANDOFF.md는 Cloud Run 컨테이너가 `PORT` 환경변수와 `0.0.0.0`을 사용해야 한다고 명시한다. 반면 실제 배포 Base URL·접근 제어는 아직 합의 전이다.

### Alternatives considered
- 로컬/배포를 하나의 환경변수로 일찍 고정: 미확정 값이 있어 지금은 보류.
- 접근 제어를 지금 설계: 공개 배포 검토 전이라 범위를 넘김.

### Deferred
- 배포 Base URL, 포트, 접근 제어, 환경변수 이름

## 5. 대화 상태 SQLite TTL 구현 범위

### Decision
대화 상태는 SQLite 기반 TTL 저장소에 `conversation_id` 기준으로 저장한다. 보관 대상은 최신 미확인 초안, 확인한 조건, 현재 후보 계획(만료 시각 포함), 최종 선택 계획, `revision`, `created_at`, `updated_at`, `expires_at`으로 한정한다. 원문 대화 전체·과거 계획 이력은 저장하지 않는다.

### Rationale
사용자 승인에서 확정된 저장 설계와 수명을 그대로 반영한다. 단일 진실 원천은 백엔드이며, 앱은 `conversation_id`만 기기 로컬에 저장한다.

### Alternatives considered
- 과거 계획 이력까지 저장: 사용자 승인에서 명시적 제외.
- 인메모리 상태만 사용: 백엔드 재시작 이후 복구 불가 → SQLite 유지.

### Notes
- 수명: 미확인 초안 30분, 확인된 조건 2시간, 후보 계획 provider valid_until까지(없으면 5분), 선택 계획 estimated_arrival_at 이후 2시간, 전체 상한 48시간.
- 상태 전이: 새 입력이 기존 미확인 초안·후보를 무효화, 선택 계획은 새 후보 생성 시 유지, 사용자 명시적 선택 시에만 교체.
- 충돌 처리: 이전 revision로 상태 변경 시 409, 없거나 만료된 conversation_id는 410.

## 6. FastAPI + Uvicorn + Pydantic 구조화 패턴

### Decision
공통 응답 봉투 `{status, data, error, meta}`를 중앙에서 다루는 응답/오류 처리 구조를 둔다. 요청 검증은 Pydantic 스키마로 처리하고, HTTP 422/상태 분기(ok/needs_confirmation/unavailable/error)는 계약대로 매핑한다.

### Rationale
API_SPEC.md의 공통 응답·오류 구조는 반복 구현이 될 가능성이 높아, router/service/store와 분리해 두는 편이 계약 유지에 유리하다.

### Alternatives considered
- 라우터마다 개별 envelope 작성: 누락·불일치 위험.
- 오류 메시지를 연동 계층 분기에 사용: API_SPEC.md에서 금지.

### Notes
- `message` 문자열 비교로 로직을 분기하지 않는다.
- 제공자·모델 비밀값·API 키는 응답에 포함하지 않는다.

## 7. MCP-백엔드 연결 패턴

### Decision
MCP 서버는 실행 환경에 주입된 Base URL로 FastAPI를 호출한다. 로컬 개발과 원격 백엔드는 주소를 구분한다. 타임아웃·에러 매핑은 API_SPEC.md의 대기 제한·연산 제한 초안을 따른다.

### Rationale
헌법과 API_SPEC.md는 MCP와 백엔드 실행 경계를 구분하고, GET 15초/POST 30초 수준의 연동 계층 대기 제한을 제시한다.

### Alternatives considered
- MCP가 직접 DB나 내부 계층을 건너뜀: 백엔드 권위 유지 원칙에 위배.
- 타임아웃/재시도를 임의로 확대: 순서·비용·중복 요청 제한 원칙과 충돌 가능.

### Notes
- 동일 계산 재요청 시 현재 시각·교통 상태 차이로 결과가 바뀔 수 있음.
- 입력이 바뀐 뒤 이전 요청이 늦게 도착하면 새 상태를 덮어쓰지 않음.


## Clarifications Resolved (2026-09-15)

speckit-clarify 워크플로우에서 해소된 5가지 명확화 항목의 기록과 결정 근거.

### C1: T014 'AI 제공자' 용어 명확화
- **문제**: tasks.md T014의 'AI 제공자' 용어가 모호함. AI의 역할 범위가 불분명.
- **결정**: '모델 제공자 (자연어 해석)'로 명확화.
- **근거**: AI는 자연어 입력 구조화·확인 질문 생성 역할만 담당하며, 실제 경로 계산·교통 데이터 제공은 별도 제공자(라우팅·대중교통·장소 제공자)가 담당. 헌장 III조(AI 사용 범위)와 일치.
- **적용**: tasks.md T014 수정, T037 'AI 제공자 호출' → '모델 제공자(자연어 해석) 호출'로 변경.

### C2: T028 Provider 호출 순서 5단계 명시
- **문제**: tasks.md T028에 Provider 호출 순서 5단계가 명시되지 않고 '흐름 조정'만 기술됨.
- **결정**: Provider 호출 순서 5단계(① conversation 유효성·입력·Idempotency-Key 기록·revision 확인 → ② DB 쓰기 트랜잭션 밖에서 provider 호출 → ③ provider 성공 결과 검증 → ④ 짧은 DB 트랜잭션에서 만료 여부·Idempotency-Key·revision 재확인 → ⑤ domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자적 커밋)를 명시하고, provider 호출 필요 없는 경우 DB 트랜잭션 안에서 검증·커밋하도록 명확화.
- **근거**: API_SPEC.md, BACKEND_HANDOFF.md, contracts/api-contract.md에 이미 반영된 규칙과 일치. FR-034에 명시된 5단계 순서와 정합.
- **적용**: tasks.md T028에 5단계 명시.

### C3: Idempotency-Key 신뢰 모델
- **문제**: Idempotency-Key 고유성 신뢰 모델이 불명확. 백엔드가 키 고유성을 재검증해야 하는지, MCP가 보장한 것으로 신뢰해도 되는지 모호.
- **결정**: MCP가 생성 시 UUID v4 고유성을 보장하고, 백엔드는 형식 검증(UUID v4 36자)과 conversation_id + Idempotency-Key UNIQUE 제약으로 멱등성 처리. 백엔드가 키 고유성을 재검증하거나 새 키를 요구하지 않음.
- **근거**: 헌법의 "효과적 once" 원칙, FR-016(Idempotency-Key 생성 주체), FR-038(UUID v4 형식), FR-018(동일 key 다른 요청 → 409)에 부합. 백엔드가 키 충돌 처리를 추가하면 불필요한 복잡성 증가.
- **적용**: spec.md Assumptions에 신뢰 모델 명시, tasks.md T021/T022 설계에 반영.

### C4: T040/T063 역할 경계 명확화
- **문제**: tasks.md T040(확인 조건 충족 전 plan 요청 차단)과 T063(일반 상태 변경 검증)의 역할 경계가 중복되는 것처럼 보임.
- **결정**: T040은 US1 특유 검증(확인 조건 충족 전 plan 요청 차단)으로 한정, 일반 상태 변경 검증(conversation 유효성·입력·Idempotency-Key·revision 확인)은 T063에 위임.
- **근거**: T040은 User Story 1(약속 이동)에 특화된 사전 조건 검증, T063은 User Story 4(대화 상태)의 공통 인프라 검증으로 역할 분리. US2(막차), US3(재탐색)도 T063의 일반 검증을 공유.
- **적용**: tasks.md T040 설명에 'US1 특유 검증' 명시, T063 설명에 '일반 상태 변경 검증' 명시.

### C5: SC-013/SC-014 커버리지 (T021)
- **문제**: tasks.md T021에 SC-013(응답 헤더 Idempotency-Key 반환)과 SC-014(응답 envelope 중복 추가 금지) 태스크가 없음.
- **결정**: T021a(응답 헤더 Idempotency-Key 반환), T021b(응답 envelope Idempotency-Key 중복 추가 금지)을 T021에 추가.
- **근거**: API_SPEC.md 4장 meta 섹션과 BACKEND_HANDOFF.md에 이미 반영된 계약. SC-013/SC-014는 Success Criteria에 포함되므로 구현 태스크 필요.
- **적용**: tasks.md T021 → T021a, T021b로 확장.


## Clarifications Resolved (2026-09-15)

speckit-clarify 워크플로우에서 해소된 5가지 명확화 항목과 결정 근거.

### C1: T014 'AI 제공자' 용어 명확화
- **문제**: tasks.md T014의 'AI 제공자' 용어가 모호함. AI의 역할 범위가 불분명.
- **결정**: '모델 제공자 (자연어 해석)'로 명확화.
- **근거**: AI는 자연어 입력 구조화·확인 질문 생성 역할만 담당하며, 실제 경로 계산·교통 데이터 제공은 별도 제공자(라우팅·대중교통·장소 제공자)가 담당. 헌장 III조(AI 사용 범위)와 일치.
- **적용**: tasks.md T014 수정, T037 'AI 제공자 호출' → '모델 제공자(자연어 해석) 호출'로 변경.

### C2: T028 Provider 호출 순서 5단계 명시
- **문제**: tasks.md T028에 Provider 호출 순서 5단계가 명시되지 않고 '흐름 조정'만 기술됨.
- **결정**: Provider 호출 순서 5단계(① conversation 유효성·입력·Idempotency-Key 기록·revision 확인 → ② DB 쓰기 트랜잭션 밖에서 provider 호출 → ③ provider 성공 결과 검증 → ④ 짧은 DB 트랜잭션에서 만료 여부·Idempotency-Key·revision 재확인 → ⑤ domain 상태 변경 + revision 증가 + Idempotency-Key 성공 결과 원자적 커밋)를 명시하고, provider 호출 필요 없는 경우 DB 트랜잭션 안에서 검증·커밋하도록 명확화.
- **근거**: API_SPEC.md, BACKEND_HANDOFF.md, contracts/api-contract.md에 이미 반영된 규칙과 일치. FR-034에 명시된 5단계 순서와 정합.
- **적용**: tasks.md T028에 5단계 명시.

### C3: Idempotency-Key 신뢰 모델
- **문제**: Idempotency-Key 고유성 신뢰 모델이 불명확. 백엔드가 키 고유성을 재검증해야 하는지, MCP가 보장한 것으로 신뢰해도 되는지 모호.
- **결정**: MCP가 생성 시 UUID v4 고유성을 보장하고, 백엔드는 형식 검증(UUID v4 36자)과 conversation_id + Idempotency-Key UNIQUE 제약으로 멱등성 처리. 백엔드가 키 고유성을 재검증하거나 새 키를 요구하지 않음.
- **근거**: 헌법의 "효과적 once" 원칙, FR-016(Idempotency-Key 생성 주체), FR-038(UUID v4 형식), FR-018(동일 key 다른 요청 → 409)에 부합. 백엔드가 키 충돌 처리를 추가하면 불필요한 복잡성 증가.
- **적용**: spec.md Assumptions에 신뢰 모델 명시, tasks.md T021/T022 설계에 반영.

### C4: T040/T063 역할 경계 명확화
- **문제**: tasks.md T040(확인 조건 충족 전 plan 요청 차단)과 T063(일반 상태 변경 검증)의 역할 경계가 중복되는 것처럼 보임.
- **결정**: T040은 US1 특유 검증(확인 조건 충족 전 plan 요청 차단)으로 한정, 일반 상태 변경 검증(conversation 유효성·입력·Idempotency-Key·revision 확인)은 T063에 위임.
- **근거**: T040은 User Story 1(약속 이동)에 특화된 사전 조건 검증, T063은 User Story 4(대화 상태)의 공통 인프라 검증으로 역할 분리. US2(막차), US3(재탐색)도 T063의 일반 검증을 공유.
- **적용**: tasks.md T040 설명에 'US1 특유 검증' 명시, T063 설명에 '일반 상태 변경 검증' 명시.

### C5: SC-013/SC-014 커버리지 (T021)
- **문제**: tasks.md T021에 SC-013(응답 헤더 Idempotency-Key 반환)과 SC-014(응답 envelope 중복 추가 금지) 태스크가 없음.
- **결정**: T021a(응답 헤더 Idempotency-Key 반환), T021b(응답 envelope Idempotency-Key 중복 추가 금지)을 T021에 추가.
- **근거**: API_SPEC.md 4장 meta 섹션과 BACKEND_HANDOFF.md에 이미 반영된 계약. SC-013/SC-014는 Success Criteria에 포함되므로 구현 태스크 필요.
- **적용**: tasks.md T021 → T021a, T021b로 확장.

## Unresolved / Deferred

- 실제 장소·교통 API 서비스명·엔드포인트·권한·한도·호출 가이드
- Solar 모델 ID·호출 경로·접근 권한
- 실제 Buffer 정책 버전·항목·분
- 배포 Base URL·포트·환경변수 이름·접근 제어
- 위 항목은 사용자 양식 제출 후 확정한다.
