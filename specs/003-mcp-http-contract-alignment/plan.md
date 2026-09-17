# 구현 계획: MCP HTTP 계약 정합화와 실제 백엔드 통합

**브랜치**: `feature/mcp-server-integrate` | **작성일**: 2026-09-16 | **명세**: [spec.md](spec.md)

**입력**: 003 명세와 [기존 계약 검토](contract-review.md), [상위 4건 수정안](remediation-proposal.md). 004 교통 제공처 연동은 별도 작업이다.

**상태**: 검토용 설계 제안. 공동 API 합의·구현·실제 연동 인수 전이다. `API_SPEC.md`, 공통 예제, 기존 002 문서, 004 활성 설정은 이번 작업에서 변경하지 않는다.

사용자 요청에 따라 C1·C2·U1·G1을 003 관련 문서에 반영했다. MCP 진단 필드와 `REQUEST_TIMEOUT`은 구체적인 권장안이며 T001 공동 합의 전까지 미확정이다. 문서 반영은 헌법 예외 승인이나 구현 게이트 통과가 아니다.

## 요약

공유 계약의 `text/context`, `{trip, user_confirmed}`, `data.plan.options`를 기준으로 백엔드와 MCP를 정합화한다. 서버가 초안·확인 조건·후보·선택·revision의 기준 상태를 관리한다. MCP는 Hermes의 form-mode elicitation으로 실제 사용자 응답을 받아 확인·선택 요청을 구성한다. 모델이 제출한 boolean이나 확인 증거를 신뢰하지 않는다.

MCP 도구 이름 5개를 유지하고 필요한 `action`을 추가한다. 내부 REST에는 상태 조회·조건 확인·후보 선택 경로를 제안한다. 초기 해석의 대화 생성과 멱등성 결과를 함께 커밋하며, 최초 응답 유실도 같은 키로 복구한다. 네트워크 실패·timeout 또는 계약상 허용된 일시 장애에만 500ms 뒤 최대 1회 자동 재시도한다.

검증 기준은 Hermes 대화 하나당 MCP 프로세스 하나와 로컬 FastAPI다. 원격 배포는 공유 저장소·접근 제어가 별도 합의되기 전까지 인수 대상에서 제외한다. 실제 교통 제공처 구현은 004가 담당하고 003은 공개 계약과 제공처 인터페이스를 통해 통합한다.

## 기술 배경

| 항목          | 계획 기준                                                                                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 언어·버전     | 기존 백엔드 Python 3.11 기준. MCP 구현 저장소의 Python·SDK 버전은 해당 담당자의 실제 환경에서 기록한다.                                                                  |
| 주요 의존성   | 기존 FastAPI, Pydantic 2, SQLAlchemy 2, httpx, Uvicorn. 003은 백엔드에 새 프레임워크를 추가하지 않는다. 설치 버전 고정은 공동 통합 시 기록한다.                          |
| 저장소        | 기존 SQLAlchemy/SQLite를 로컬 단일 백엔드 프로세스에서 재사용한다. 대화 및 멱등 기록의 단기 저장이며 계정·영구 이동 이력이 아니다.                                       |
| MCP·Hermes    | stdio, form-mode elicitation 필수. 미지원·거절·취소·timeout이면 확인·선택을 진행하지 않는다. 정확한 Hermes/SDK/모델 버전은 실행 인수 증거다.                             |
| 테스트        | 기존 pytest, pytest-asyncio, freezegun 및 계약/통합 테스트. MCP 쪽 가짜 HTTP 서버·stdio 테스트는 연결 문서에 보고되어 있으나 이 저장소에서 소스를 확인하지 않았다.       |
| 대상 플랫폼   | 로컬 개발 환경의 MCP→loopback FastAPI. Linux/Cloud Run은 기존 장기 배포 방향을 유지하되 이번 로컬 검증 성공과 구분한다.                                                  |
| 프로젝트 형태 | MCP 서비스 + 내부 HTTP 계산 백엔드. 독립 클라이언트 없음.                                                                                                                |
| 시간 제한     | HTTP 시도당 GET 15초/POST 30초, 자동 추가 시도 1회와 500ms 대기. 서버 조회 3초/10초, 계산 workflow 25초. 사용자 승인 대기와 호출 전체 예산은 MCP 계약에서 별도 정의한다. |
| 규모·제약     | 서울·Asia/Seoul, 후보 1~3개, 한 대화에서 상태 변경 직렬 처리. 부하 SLA나 다중 인스턴스 지원을 새로 약속하지 않는다.                                                      |

## 헌법 점검

아래 판정은 **검토용 설계**에 대한 점검이다. 구현·대회 제출 적합성·실행 성공을 뜻하지 않는다.

| 원칙                               | 연구 전        | 설계 후               | 근거·진행 조건                                                                                          |
| ---------------------------------- | -------------- | --------------------- | ------------------------------------------------------------------------------------------------------- |
| I 제품·계약 기준                   | 적합           | 적합                  | 기존 제품·도메인 구조를 유지하고 상충 문서는 공동 개정 목록으로 분리한다.                               |
| II-a MCP 제공 형태·실행 경계       | 설계 적합      | 설계 적합·실행 미검증 | 5개 도구, stdio와 HTTP 경계, 대화별 프로세스 분리.                                                      |
| II-b Hermes + Solar Pro4 실제 시연 | 미검증         | 미검증                | 설치 환경의 실제 모델·도구 호출·승인은 T062/T063 및 확장 인수로 확인한다.                               |
| III 실제 데이터·코드 검증          | 적합           | 적합                  | 시간·상태·멱등성은 코드 책임, 운영 실패의 demo 전환 금지. 004 데이터 연결은 독립 인수 조건이다.         |
| IV 확인·선택 통제                  | 적합           | 적합                  | elicitation 직접 응답, 조건 fingerprint와 revision 연결, 후보 생성과 선택 분리.                         |
| V 공동 계약                        | 제안 작성 허용 | 구현 진입 보류        | 사용자가 검토용 제안을 선택했다. 양측 합의와 공통 문서 동시 갱신 전에는 새 공개 계약을 구현하지 않는다. |
| VI 범위·증거                       | 적합           | 적합                  | 로컬 통합으로 한정, 새 계정·인프라·영구 이력 없음, 실제 수행하지 않은 검증은 미실행.                    |

공동 합의 게이트는 계획의 미결정 기술 선택을 감추는 항목이 아니다. 이 문서의 구체적인 제안을 양측이 검토한 뒤 적용할지 결정하는 절차다. 검토용 설계 작성은 완료할 수 있지만 계약 개정·구현 진입은 보류다.

**전체 헌법 게이트: 통과 아님.** II-b 미충족과 V의 공동 합의 대기가 남아 있다. T001에서 개발 도구 조건의 처리 근거를 확인하고, 예외가 필요하면 범위·만료 조건·명시적 승인 근거를 기록해야 한다. 이 문서가 예외를 승인하지 않는다. 이후 실제 시연 성공은 개발 도구 조건을 소급 충족하지 않으며, 내부 예외가 외부 제출 규칙을 바꾸지도 않는다. 제출 적합성은 별도 판단이다.

## 프로젝트 구조

### 이번 기능의 문서

```text
specs/003-mcp-http-contract-alignment/
├── spec.md
├── contract-review.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
├── remediation-proposal.md
├── contracts/
│   ├── http-contract.md
│   ├── mcp-contract.md
│   └── examples.json
└── checklists/
    ├── requirements.md
    └── plan-review.md
```

[tasks.md](tasks.md)에 기존 작업 ID를 보존한 64개 작업과 선행 조건을 관리한다. 번호가 아닌 명시된 의존성과 단계 순서로 실행한다.

### 기존 소스와 소유 경계

```text
backend/app/
├── api/{mobility,journeys,responses}.py
├── schemas/{mobility,journeys,common,errors}.py
├── services/{conversation_service,idempotency_service,interpret_service}.py
├── services/{plan_service,replan_service,last_journey_service}.py
├── models/{conversation,idempotency}.py
├── db.py
└── main.py
backend/tests/{unit,contract,integration}/
.hermes/skills/                   # 기존 Skill 원본 위치
```

상태 REST 라우터와 스키마는 기존 `api/`, `schemas/` 아래에 구현한다. MCP 소스 경로를 이 저장소에 임의로 만들지 않는다. MCP 담당자는 자신의 실제 저장소·진입점·버전을 인수 자료에 연결한다. 구조 조사에는 graph 도구가 제공되지 않아 제한된 파일 읽기를 사용했다. 기존 `services/idempotency.py`와 `idempotency_service.py`의 중복은 호출처 확인 후 상태 workflow에 쓰는 구현을 하나로 통일하며, 확인 없이 파일을 삭제하지 않는다.

## 복잡성 추적

헌법 예외를 적용한 설계는 없다. 새 메시지 브로커·캐시 서버·DB 제품·사용자 계정·별도 승인 웹 화면을 추가하지 않는다. 원격 인증 설계와 프로세스 간 상태 공유는 별도 게이트다.

## Phase 0 — 조사와 결정

[research.md](research.md)에 사용자 결정, 현재 구현 근거, 제안 선택과 대안을 기록했다. 첫 요청 중복 방지, replay와 최신 revision의 차이, 승인 근거의 신뢰 경계, 단계별 TTL, 응답 오류 및 전체 시간 예산을 구체화한다.

## Phase 1 — 설계 산출물

- [데이터 모델](data-model.md): 상태·수명·동시성·원자 커밋·초기 요청 보존.
- [HTTP 계약 제안](contracts/http-contract.md): 필드·신규 내부 경로·오류·초기 응답 유실·재시도 규칙.
- [MCP 계약 제안](contracts/mcp-contract.md): 5개 도구 action, elicitation, 대화 분리, 보류 요청 복구.
- [예제](contracts/examples.json): 헤더와 본문을 분리한 요청, 상태 응답, 거부·재생 검사 사례.
- [검증 안내](quickstart.md): 재현 명령, 모의/실제 검증 경계 및 인수 순서.

## 구현 순서와 담당

1. **공동 계약·개발 도구 게이트** — T001에서 II-b 처리 근거, MCP 오류 진단 표현, REQUEST_TIMEOUT 도입 여부와 변경 영향표·예제를 검토한다. 합의된 계약을 T002에서 `API_SPEC.md`, `Docs/api/examples.json`, 002 계약/상태 문서, HTTP 연결 안내에 함께 반영한다.
2. **백엔드 상태 기반** — 초안 저장, TTL, 초기 요청 멱등성, 조건부 revision 갱신, 상태와 성공 응답의 원자 저장을 구현한다. DB migration은 기존 데이터 보존 방안을 검토한 뒤 적용한다.
3. **약속 정합화·경계 검증** — US1→US2→US3 순으로 해석·약속·상태 경로와 MCP 승인·복구를 연결한다. T064의 서버 제한 검증을 T041 전에 완료한다. provider 호출 중 쓰기 트랜잭션을 유지하지 않는다.
4. **확장 전 실제 약속 인수** — T041·T003·T005 후 T062에서 실제 Hermes 승인·선택·프로세스 분리·복구를 확인한다. T063에서 같은 로컬 Hermes→MCP→FastAPI 흐름에 004의 검증된 약속 provider를 연결해 실제 약속 1건 이상을 인수한다. 막차 provider 준비를 기다리는 작업과 분리한다.
5. **재탐색·막차 확장과 회귀** — T063 통과 후 US4→US5를 수행한다. T055/T056은 확장 기능 인수와 약속 회귀를 맡는다. Hermes나 약속 데이터가 미준비면 약속 모의·장애 검증은 계속하되 T063과 US4/US5 확장은 보류한다.

### 응답 불명과 서버 처리 제한

- POST 전송 후 적용 여부가 불명확하면 첫 응답부터 `OUTCOME_UNKNOWN`으로 보류한다. invalid JSON/schema/key/status는 자동 재시도하지 않지만 미적용의 증거도 아니다. 원본 요청을 보존하고 GET만 허용하며 사용자 승인 resume으로 복구한다. 유효한 확정 실패와 깨진 응답의 구분·진단 표현은 [MCP 계약 §5~6](contracts/mcp-contract.md)을 따른다.
- 서버 처리 예산은 health/capabilities 3초, places 10초, interpret/plan/replan 25초다. 핸들러 진입부터 결과 검증·원자적 상태 확정까지 단조 경과시간으로 측정하며 네트워크 전달·elicitation은 제외한다. 중첩 provider는 남은 예산을 공유한다.
- T064는 기존 timeout 위치를 T004에서 조사한 뒤 부족한 부분만 보강한다. 확정 지점의 경과시간이 제한 이상이면 새 상태 적용을 거부하고 늦은 작업의 commit을 차단한다. 이미 제한 안에 확정된 성공은 지연 전달돼도 보존한다. 새 상태/confirm/select 경로의 별도 SLA는 추가하지 않는다.
- 서버 전체 예산 소진의 `504 / REQUEST_TIMEOUT / retryable=true`는 미적용 보장이 있는 경우의 권장안이다. 기존 외부 요청 `UPSTREAM_TIMEOUT`과 구별하며 T001/T002 전에는 공통 API나 코드에 도입하지 않는다.

## 변경 영향과 동기화 대상

| 변경                                         | 구현 영향                                            | 함께 갱신할 기준·검증                                                                                           |
| -------------------------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| text/context, draft/ready_for_plan/questions | mobility 라우터·스키마·interpret 서비스·MCP 직렬화   | API_SPEC §7, interpret 예제, 해석 계약 테스트                                                                   |
| nested trip, data.plan.options, trip.kind    | journeys 라우터·계산 응답 매핑·막차 분기             | API_SPEC §8, 약속/막차 예제·기존 flat 입력 테스트                                                               |
| conversation/revision, 확인·선택·상태 조회   | 신규 내부 상태 경로·상태 서비스·MCP action           | API_SPEC §2/3/4/11, 002 spec/plan/data-model/contracts, 상태 테스트                                             |
| 실제 사용자 승인                             | Hermes elicitation·MCP evidence 생성·서버 검증       | MCP 도구 스키마·가짜 호스트/실제 Hermes 거부 테스트                                                             |
| 멱등성·초기 생성·TTL                         | 상태/멱등 모델·트랜잭션·정리·재전송 처리             | 공통 예제 헤더 6건 수정, 최초 유실/동시 요청/만료 테스트                                                        |
| 재탐색 기준 상태                             | replan 서비스·selected snapshot 검증                 | previous_plan 예제, candidate 만료를 select 거부 사례로 정정                                                    |
| 오류·재시도·전체 제한                        | 응답 builder·MCP HTTP client·원자 확정·provider 예산 | API_SPEC §10/12, MCP 적용 불명 진단, HTTP 연결 안내, T035/T038/T041/T048/T064의 오류·늦은 commit·호출 횟수 검증 |
| demo/live 및 출처                            | 기존 mock과 004 provider 경계                        | fixture, capabilities, 실제 교통 인수 자료                                                                      |

기존 `IDEA.md`의 상태 소유권 미합의·서버 저장을 가정하지 않는다는 과거 설명도 합의 단계에서 서버 SSOT 결정과 맞춘다. 제품 범위는 확대하지 않는다.

## 검증 전략과 종료 조건

명세 FR-001~021와 SC-001~008을 [검증 안내](quickstart.md)의 V01~V12에 대응한다. 계약/상태 단위 테스트, 실제 HTTP 통합, 가짜 MCP 호스트, 실제 Hermes, 실제 데이터 인수를 분리한다. 동시성 테스트는 독립 DB 세션을 사용해 순차 mock으로 통과시키지 않는다.

계획 단계의 완료는 문서 구조·참조·예제 일관성 검증까지다. 실제 기능 완료는 공동 합의, 코드 구현, 실행 증거가 모두 필요하다. 현재 실행 주소·모델 ID·MCP 경로·실제 제공처는 값을 추측하지 않고 실행 시 확인할 입력으로 남긴다.

C1은 판정 분리와 출처 보존, C2는 T062/T063 선행 인수, U1은 첫 깨진 응답 보류와 명시적 복구, G1은 T064의 3/10/25초 직전·경계·초과 검증으로 추적한다. 상세 문서 점검과 남은 구현 게이트는 [검토 기록](checklists/plan-review.md)에 둔다.
