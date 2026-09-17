# Implementation Plan: Backend MVP Implementation

**Branch**: `002-backend-mvp-implementation` | **Date**: 2026-09-14 | **Spec**: [specs/002-backend-mvp-implementation/spec.md](../spec.md)

**Input**: Feature specification from `/specs/002-backend-mvp-implementation/spec.md`

**Note**: This plan is created manually because the Spec Kit PowerShell setup script is not available in this environment. The template structure from `.specify/templates/plan-template.md` is followed.

## Summary

백엔드 MVP는 Hermes → MCP → FastAPI 연결을 Contract 기반으로 구현하고, 장소 검색·자연어 해석·약속 출발시각 계산의 최소 흐름을 먼저 종단 간 연결한 뒤, 재탐색·막차로 확장한다. 핵심은 공개 JSON 계약(API_SPEC.md + examples.json)을 먼저 고정하고, 데모/live 어댑터를 분리해 운영 조회 실패를 데모 결과로 자동 대체하지 않는 것이다.

**기술적 접근 요약**:
- FastAPI + Pydantic 기반 HTTP 서비스, `{status, data, error, meta}` 공통 봉투 중앙화
- 데모/실제 어댑터 분리, 실제 제공처 장애 시 자동 대체 금지
- MCP 도구 5개(get_capabilities, search_places, interpret_trip, plan_journey, replan_journey)와 REST 엔드포인트 1:1 매핑
- UserStory 1(health/capabilities) → UserStory 2(interpret → plan 최소 흐름) → UserStory 3(데모/live 분리, 재탐색·막차 확장 준비) 순서

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI + Uvicorn 기준, 정확한 버전은 구현 시점 확인)

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic. 필요시(http 클라이언트, 시간대 처리 등) 표준 라이브러리 또는 경량 패키지 사용.

**Storage**: MVP 단계에선 영구 저장을 필수 구조로 보지 않음. 대화 문맥·선택 상태 보관은 구현 전에 두 개발자가 별도 합의(장소·교통·Solar 키처럼 미확정 운영 값).

**Testing**: pytest 기반 단위/통합 테스트. 계약 검증은 examples.json fixture와 대조.

**Target Platform**: Linux 컨테이너(GCP Cloud Run 배포 기준). 로컬 개발은 127.0.0.1 + 선택 포트.

**Project Type**: HTTP API 서비스 (MCP 서버의 백엔드 계산 계층)

**Performance Goals**: MVP에서는 엄격한 SLA 수치보다 계약 응답 구조·상태 분기 정확성과 연결 재현성을 우선한다.

**Constraints**:
- 대상 지역: 서울 (검증된 데이터 범위로 제한)
- 시간대: Asia/Seoul만 허용
- 목표 도착시각 = arrival_deadline − arrival_preference_minutes
- Buffer는 이미 총 이동시간에 포함, 중복 가산 금지
- Mock 날짜와 서버 시각을 실제 운행 계산에 주입 금지
- 운영 조회 실패를 Demo 결과로 자동 대체 금지
- taxi 등 미지원 모드, 범위 밖 조건, 미확인 계산은 검증 오류로 처리
- user_confirmed=true 없이 계산 금지, ready_for_plan=true를 동의로 간주 금지

**Scale/Scope**: 2명·4일 MVP. 막차·재탐색은 검증된 지원 범위 안에서 확장. 대규모 동시성·다중 사용자 계정·장기 보존은 범위 밖.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

### Gate 1 — 제품 방향과 문서 기준 (헌법 I)
- [x] 모든 작업은 IDEA.md를 최신 제품 방향의 최우선으로 사용한다.
- [x] IDEA.md → API_SPEC.md → agent_specs → specs 순서로 읽는다.
- [x] API_SPEC.md를 공개 요청·응답 계약 기준으로 사용한다.
- [x] IDEA.md·API_SPEC.md와 충돌하는 제안은 구현하지 않는다.

### Gate 2 — MCP 제공 형태와 실행 경계 (헌법 II)
- [x] 서비스는 MCP로 제공한다. MCP는 임시 포장이 아니다.
- [x] 독립 사용자 클라이언트를 개발하지 않는다.
- [x] Hermes + Upstage Solar Pro4를 개발·시연에 사용한다.
- [x] MCP 서버(도구 계층)와 FastAPI 백엔드(계산 계층)의 실행 경계를 구분한다.
- [x] 로컬 stdio와 원격 백엔드 주소를 혼동하지 않는다.

### Gate 3 — 검증 가능한 코드와 실제 데이터 (헌법 III)
- [x] 경로 유효성·시간 계산·상태 전이·횟수 제한·권한 검증은 테스트 가능한 코드로 처리한다.
- [x] AI는 자연어 구조화·확인 질문·검증된 결과 설명에만 사용한다.
- [x] 실시간 교통편·막차·경로·요금·이동시간을 생성/추측하지 않는다.
- [x] 교통 결과는 실제 확인 데이터의 출처·기준시각을 포함한다.
- [x] Demo/fixture는 실제 데이터와 명확히 표시·분리한다.
- [x] 운영 조회 실패를 Demo로 자동 대체하지 않는다.
- [x] 실행하지 않은 테스트·조회·저장·배포를 성공으로 보고하지 않는다.

### Gate 4 — 사용자 확인과 계획 통제 (헌법 IV)
- [x] 경로 계산 전 해석된 장소·시각·도착 여유·이동수단을 표시하고 명시적 확인을 받는다.
- [x] 넓은 지역명·학교·“집”을 임의 장소로 확정하지 않는다.
- [x] 이미 확정된 명확한 조건을 불필요하게 다시 질문하지 않는다.
- [x] ready_for_plan=true를 사용자 동의로 간주하지 않는다.
- [x] 모델이 user_confirmed=true를 생성했다는 사실만으로 사람의 확인을 검증했다고 간주하지 않는다.
- [x] 재탐색은 사용자 요청으로 시작하며, 새 결과는 사용자가 선택하기 전까지 기존 계획에 적용하지 않는다.
- [x] 재탐색 실패·취소는 기존 기록을 삭제하지 않으며, 이전 경로가 여전히 유효하다는 보장으로 표시하지 않는다.

### Gate 5 — 계약 우선 통합과 실행 구조 (헌법 V)
- [x] 두 개발자는 Spec Kit으로 명세·계획·작업을 관리한다.
- [x] 공개 API 경로·필드·상태·오류 의미 변경은 먼저 합의하고 API_SPEC.md + examples.json을 함께 갱신한다.
- [x] 클라이언트와 서버는 동일한 구조화 JSON 계약을 사용한다.
- [x] 제공처 교체는 공개 계약을 보존하는 Adapter로 격리한다.
- [x] MainAgent → SubAgent 실행 순서·결과 취합 구조를 유지한다.
- [x] `.hermes/skills`를 Skill 원본의 단일 저장 위치로 사용한다.

### Gate 6 — MVP 범위, 보안, 증거 기반 완료 (헌법 VI)
- [x] 2명·4일 MVP 범위 안에서 수행한다.
- [x] 택시비 상한선·택시 최적화·GPS 상시 추적·자동 재탐색·Calendar 자동 동기화·백그라운드 알림 등 보류 기능을 승인 없이 포함하지 않는다.
- [x] UserData DB·회원가입·영구 이동 이력·출발/도착 상태 버튼은 현재 필수 범위가 아니다.
- [x] 실제 키·비밀 값을 저장소·설정 예제·도구 응답·로그·시연 영상에 포함하지 않는다.
- [x] 완료 주장은 재현 가능한 실행 증거에 근거한다.

**사전 게이트 판정**: 통과. Phase 0 연구 없이도 spec과 IDEA.md, 헌법 기준으로 방향성·배제 조건이 명확하다. 다만 실제 제공처·키·Solar 모델 ID·배포 환경 값은 미확정이므로, 구현 과정에서 사용자에게 질의해 확정한다.

## Project Structure

### Documentation (this feature)

```text
specs/002-backend-mvp-implementation/
├── plan.md              # This file
├── research.md          # Phase 0 output (already exists)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created here)
```

### Source Code (repository root)

백엔드 MVP는 기존 저장소 구조 위에서 `backend/` 경로를 주 구현 위치로 사용한다. 이 계획에서는 새 소스 레이아웃을 발명하지 않고, 기존 백엔드 준비 구조와 BACKEND_HANDOFF.md의 작업 경로 지도를 따른다.

```text
backend/
├── app/
│   ├── main.py          # FastAPI 진입점
│   ├── api/             # 라우트·공통 응답·오류 처리
│   ├── schemas/         # 요청·응답·외부 데이터 검증
│   ├── domain/          # 시간 계산·Buffer·조건 확인 정책
│   ├── integrations/    # 장소·교통·Solar 어댑터, demo/live 분리
│   └── agents/          # MainAgent·SubAgent 실행 조율
├── tests/
│   ├── unit/
│   ├── contract/
│   └── integration/
└── README.md            # 설치·실행·환경 변수 예시
```

**Structure Decision**: 기존 `backend/` 준비 구조를 그대로 사용하고, 새 프로젝트 레이아웃을 만들지 않는다. 소스 트리 세부 구성은 구현 시점에 BACKEND_HANDOFF.md의 경로 지도를 따라 채운다.

## Complexity Tracking

> **채우기 조건**: Constitution Check에 위반 사항이 있어 정당화가 필요한 경우에만 작성한다.

이 계획 단계에서는 헌법 위반이 없으므로 비워 둔다.

## Phase 0: Research Status

research.md는 이미 작성되어 있다. 주요 미확정 항목은 다음과 같이 정리되어 있다.

- 실제 장소·교통 API 서비스명·엔드포인트·권한·한도·호출 가이드 → 사용자 양식 제출 후 확정
- Solar 모델 ID·호출 경로·접근 권한 → 사용자 양식 제출 후 확정
- 실제 Buffer 정책 버전·항목·분 → 정책 확정 후 반영
- 배포 Base URL·포트·환경변수 이름·접근 제어 → 구현 시점 확정

따라서 Phase 0에서 새로 해결할 NEEDS CLARIFICATION은 없으며, 연구 결과를 확정 전까지 데모/스텁으로 우회할 수 있는 구조로 진행한다.

## Phase 1: Design Direction

### data-model.md 방향

이번 MVP에서 중심 데이터 모델은 다음 세 층으로 정리한다.

1. **공개 요청/응답 모델**
   - TripDraft, TripRequest, Plan, RouteOption, Place, PlanSummary, Comparison 등
   - API_SPEC.md 및 examples.json과 1:1로 맞춰야 하는 계약형 모델

2. **내부 계산/도메인 모델**
   - 목표 도착시각, 권장 출발시각, Buffer, leg·total_duration_minutes 관계
   - 시간대·자정 경계·운행일 구분을 다루는 계산용 표현

3. **대화 문맥·선택 상태 모델(합의 후 확정)**
   - 현재 대화 이동 조건, 확인 상태, 선택 계획
   - 저장 위치·수명·소유권은 BACKEND_HANDOFF.md/헌법 범위 안에서 두 개발자가 구현 전에 합의

data-model.md에는 위 구분과 각 모델의 필수 필드·검증 규칙·상태/계산 불변식을 정리한다. 저장 스키마나 ORM 확정은 범위 밖이면 보류한다.

### contracts/api-contract.md 방향

API 계약 문서는 API_SPEC.md를 대체하지 않고, Spec Kit 계약 체크리스트/검증 관점에서 핵심 계약을 요약·링크한다.

포함 내용:
- 공통 응답 봉투와 상태 분기(ok/needs_confirmation/unavailable/error)
- 메타 필드 계약(conversation_id, revision, expires_at 등)
- 주요 오류 코드와 연동 계층 동작
- 예제를 대체하지 않고 examples.json fixture ID를 참조
- MCP 도구 ↔ REST 엔드포인트 매핑

### quickstart.md 방향

빠른 검증 시나리오 중심으로 작성한다.

포함 내용:
- 사전 준비(저장소 복제, 브랜치, Python 환경, 필요 시 키/환경 변수 placeholder)
- 서버 기동 명령
- curl 기준 최소 검증 시나리오:
  - health/capabilities
  - places 검색
  - interpret → needs_confirmation
  - interpret → ready → plan
  - plan 응답의 buffer/시간대/상태 분기 확인
- 데모 여부·실제 데이터 여부 구분 확인 방법
- 아직 구현되지 않은 항목과 그 이유

전체 구현 코드나 테스트 스위트는 넣지 않고, 실행 가능한 검증 가이드로 한정한다.

### Provider 호출 순서 요약

이전 확정 규칙에 포함된 Provider 호출 순서 5단계는 다음과 같다.

1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
3. provider 성공 결과를 검증한다.
4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다. provider 호출은 DB 트랜잭션 외부에서 수행하며, provider 성공 후에만 짧은 트랜잭션에서 재확인 후 원자 커밋한다. provider 실패는 domain 상태·revision·updated_at·TTL을 갱신하지 않는다.

자세한 내용과 예외 처리(tombstone 충돌, expired_at 재설정 금지, hard delete 후 404 등)는 contracts/api-contract.md와 BACKEND_HANDOFF.md를 참조한다.

## 확정 규칙 보강 (2026-09-15)

이전 speckit-plan 실행 이후 확정된 규칙이 있다. 이 규칙들은 API_SPEC.md, BACKEND_HANDOFF.md, spec.md, contracts/api-contract.md에 반영됐으며, plan.md에서는 요약만 남긴다. 상세는 원문 계약을 따른다.

### Idempotency-Key

- MCP가 각 상태 변경 요청에 Idempotency-Key를 생성해 HTTP 헤더 `Idempotency-Key`로 전달한다. 형식은 UUID v4 표준 문자열(36자)이다.
- 백엔드는 응답 시 응답 헤더 `Idempotency-Key`로 동일한 키를 돌려준다. 응답 JSON envelope에는 Idempotency-Key를 중복 추가하지 않는다.
- Idempotency-Key 누락·형식 오류는 422로 처리한다.
- 같은 Idempotency-Key로 다른 요청이 이미 처리됐으면 409 IDEMPOTENCY_KEY_REUSED로 처리한다. retryable은 false다.
- 백엔드는 conversation_id + idempotency_key에 UNIQUE 제약을 둔다.

### payload hash와 동일 key 우선순위

- 각 상태 변경 요청마다 payload hash를 계산해 저장한다. hash 범위: HTTP method, 정규화된 API path, conversation_id, expected revision, 상태 변경 전체 JSON body.
- body는 UTF-8, key 정렬, 불필요한 공백 제거 방식으로 canonicalize한 뒤 SHA-256을 hash한다.
- 같은 key + 같은 payload 재시도는 최초 응답을 반환한다(effectively-once).
- 유효한 conversation에서 이미 성공한 동일 key·동일 payload 재요청은 stale revision 검사보다 먼저 처리한다.

### provider 호출 순서 5단계

1. conversation 유효성, 입력, idempotency 기록, revision을 확인한다.
2. DB 쓰기 트랜잭션 밖에서 provider를 호출한다.
3. provider 성공 결과를 검증한다.
4. 짧은 DB 트랜잭션에서 만료 여부, idempotency 기록, revision을 다시 확인한다.
5. domain 상태 변경 + revision 증가 + idempotency 성공 결과를 원자적으로 커밋한다.

provider 호출이 필요 없는 상태 변경은 DB 트랜잭션 안에서 검증과 커밋을 수행한다.

### 만료와 tombstone

- 없거나 만료된 conversation은 410 CONVERSATION_EXPIRED로 통일한다.
- candidate만 만료된 경우는 410 CANDIDATE_SET_EXPIRED로 처리한다. 이 경우 conversation과 confirmed_conditions, active_selected_plan은 유지한다.
- expires_at <= 서버 현재 시각이면 즉시 만료로 판단한다.
- 만료 시 payload를 제거하고 conversation_id·마지막 revision·expired_at만 tombstone으로 보관한다.
- tombstone은 24시간 유지 후 hard delete한다. hard delete 이후 동일 ID 요청은 404 CONVERSATION_NOT_FOUND로 처리한다.
- tombstone 생성은 멱등하게 처리한다. 가능하면 기존 conversation 행을 조건부 UPDATE하여 tombstone으로 전환하거나, 별도 테이블 사용 시 UNIQUE 제약과 ON CONFLICT DO NOTHING을 사용한다.
- 원본 payload 제거와 tombstone 기록은 같은 DB 트랜잭션으로 처리한다.

### 재시도 정책

- MVP 기본값은 자동 재시도 최대 1회, 대기 500ms로 확정한다. 새 인프라나 사용자 설정 기능을 추가하지 않는다.
- 네트워크 연결 실패·timeout 또는 계약상 retryable=true인 502/503/504에만 적용한다.
- 같은 Idempotency-Key와 같은 body로 재시도한다.
- 4xx·409·410·검증 실패·invalid response는 자동 재시도하지 않는다.
- provider 실패는 domain 상태·revision·updated_at·TTL을 갱신하지 않는다.

### 상태 오류 5종

| HTTP | code | 의미 |
|---|---|---|
| 404 | CONVERSATION_NOT_FOUND | 존재한 적 없는 conversation_id로 요청함 |
| 409 | CONVERSATION_VERSION_CONFLICT | revision 불일치 |
| 409 | IDEMPOTENCY_KEY_REUSED | 같은 key로 다른 요청 이미 처리 |
| 410 | CONVERSATION_EXPIRED | conversation 만료 |
| 410 | CANDIDATE_SET_EXPIRED | conversation 유효하나 후보만 만료 |

## Post-Design Constitution Re-Check

Phase 1 설계 후에도 아래 항목은 유지되어야 한다.

- [x] 공개 계약은 API_SPEC.md + examples.json 기준
- [x] 데모/live 분리, 운영 실패 자동 대체 금지
- [x] Buffer 중복 가산 금지
- [x] ready_for_plan ≠ 동의, user_confirmed 필요
- [x] 재탐색 결과 자동 적용 금지
- [x] 실제 키·비밀 값 비노출

## Deferred to Implementation

- 실제 장소·교통 API 연결 세부(서비스명·엔드포인트·키·한도)
- Solar 모델 ID·호출 경로·접근 권한
- 실제 Buffer 정책 수치
- 배포 Base URL·포트·환경변수 이름·접근 제어
- 대화 문맥·선택 상태 저장 위치·수명·소유권(합의 필요)

이 항목들은 구현 중 사용자에게 질의해 확정한다. 임의 가정으로 고정하지 않는다.
