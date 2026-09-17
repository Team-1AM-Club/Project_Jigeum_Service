# 백엔드 배포·인증·API 연결 현황 회신

> 통합 후 안내: 아래는 원격 5caef80에 포함된 회신 원문이다. 현재 작업 트리의 confirm·revision·멱등 구현 및 검증 상태는 [통합 결과](integration-status.md)를 따른다. 배포 보류와 원격 미검증 상태는 유지된다.

확인일: 2026-09-16

요청한 항목별로 현재 확인 가능한 내용을 정리했습니다. **서울 리전 배포는 보류 상태입니다.** 월 추가 지출 목표를 0원으로 유지하기로 했고, 서울발 인터넷 응답 전송료가 이 조건과 충돌하기 때문입니다. 이번 작업에서 클라우드 자원 생성·배포·IAM 변경·Secret 등록은 하지 않았습니다. 아래의 검토안은 적용 완료된 설정이 아닙니다.

## 1. 배포 정보

| 항목 | 현재 답변 | 상태 |
|---|---|---|
| GCP 프로젝트 ID | `project-jigeum` | 사용자 제공 정보. 실제 프로젝트 조회로 검증하지 않음 |
| 프로젝트 번호 | `670549467351` | 사용자 제공 정보. ID와의 일치 미검증 |
| 리전 | 서울 `asia-northeast3` | 사용자 결정 확정 |
| 배포 서비스 종류 | GCP Cloud Run, FastAPI HTTP 백엔드 | 배포 대상 확정, 실제 배포 미실행 |
| 결제 조건 | 유료 계정, 체험 크레딧 소진. 추가 월 지출 목표 0원 | 사용자 확인. 프로젝트 결제 연결·무료 사용량 잔여분 미조회 |
| 사용 계정 | 별도로 준비한 팀용 Google 계정 | 사용자 확인. 실제 principal·권한 미조회 |
| 실제 Cloud Run 서비스 이름·revision·이미지 | 미정 | 생성·배포하지 않음 |
| 테스트 가능한 원격 API 기본 주소 | 미정 / 현재 제공할 주소 없음 | 배포 보류 |

향후 MCP에 전달할 API 기본 주소는 **`/api/v1`을 포함**해야 합니다. 주소를 발급받기 전 임의의 `run.app` 주소를 사용하지 않습니다. 로컬 서버의 경로 prefix도 `/api/v1`이지만, 이번 확인에서는 서버를 실행하거나 접속 테스트하지 않았습니다.

실행 경계는 **로컬 Hermes → 로컬 MCP → HTTPS Cloud Run 백엔드**입니다. 원격 MCP 서버 신규 배포는 이번 범위에 포함하지 않습니다.

## 2. MCP → 백엔드 인증

**확정된 정책은 팀 전용 접근입니다. 인증 방식은 검토안만 있고 실제 적용은 미정입니다.** Secret Manager의 교통 API 키 보관과 MCP의 백엔드 호출 인증은 별도입니다. 교통 API 키를 MCP 호출용 공유 비밀키로 사용하지 않습니다.

| 항목 | 검토안 또는 확인 내용 | 적용 상태 |
|---|---|---|
| 인증 방식 | Cloud Run Invoker IAM 검사 + 짧은 수명 Google ID token | 미정·미적용 |
| 인증 헤더 | 검토안: `Authorization: Bearer <ID_TOKEN>` | 토큰 발급·호출 미검증 |
| 일반 HTTP 헤더 | `Accept: application/json`, JSON 요청은 `Content-Type: application/json` | HTTP 연결 계약 기준 |
| 상태 변경 헤더 | `Idempotency-Key: <UUID v4>` | 호출 인증과 별개. 구현 상태는 4절 참조 |
| 로컬 MCP의 인증 획득 | 팀용 Google 계정으로 로컬 ADC를 구성하고 IAM Credentials `generateIdToken`으로 caller 서비스 계정의 ID token 발급 | 검토안. MCP 토큰 발급·갱신 구현 미검증 |
| token audience | 실제 Cloud Run 서비스 URL. `/api/v1`을 붙인 MCP API 기본 주소와 구분 | 실제 URL 미정 |
| 호출자 서비스 계정 이름 | 미정 | 미생성 |
| 런타임 서비스 계정 이름 | 미정 | 미생성 |

최소 IAM 권한으로 검토한 안은 다음과 같습니다. 아직 부여하지 않았으며 최종 구현 전에 확정해야 합니다.

- 팀용 Google principal: caller 서비스 계정에 한정한 `roles/iam.serviceAccountOpenIdTokenCreator`.
- Caller 서비스 계정: 해당 Cloud Run 서비스에 한정한 `roles/run.invoker`.
- 백엔드 런타임 서비스 계정: 실제 사용하는 저장소·Secret에 필요한 권한만 별도로 부여. Caller에 DB·Secret 접근 권한을 주는 안은 아닙니다.

로컬 MCP는 토큰 만료 전에 갱신해야 합니다. 비밀번호·ADC 파일·서비스 계정 키 파일·토큰 원문은 채팅이나 저장소로 전달하지 않습니다. 현재 FastAPI 소스에 Cloud Run 인증 완료를 입증하는 설정은 없으며, 로컬 HTTP 호출 성공이 원격 팀 인증 성공을 의미하지 않습니다.

## 3. Secret Manager 설정

**현재 확정된 Secret Manager 설정은 없습니다.** 필요한 키 종류와 제공처 연결이 확정되지 않았으므로 Secret 이름을 임의로 정하지 않았습니다.

| 항목 | 현재 답변 |
|---|---|
| 사용할 Secret 이름 | 미정 |
| 사용할 Secret 버전 | 미정. 생성·등록하지 않음 |
| Secret별 용도 | 미정. 실제 교통·장소·백엔드 AI 제공처가 요구하는 자격증명을 확인한 후 결정 |
| Secret을 읽는 서비스 계정 | 미정. 백엔드 런타임 서비스 계정에 부여하는 방향으로 검토 |
| Secret 접근 권한 | 사용 시 필요한 개별 Secret에 `roles/secretmanager.secretAccessor`를 부여하는 안 검토. 실제 부여 없음 |
| 백엔드 사용 방식 | 미정. Cloud Run 환경변수 주입 또는 파일 마운트 중 필요한 방식을 확정해야 함 |

백엔드에는 환경변수를 읽는 Settings 구조가 있지만 **Secret Manager 연동 완료를 의미하지 않습니다.** Secret 이름·버전·환경변수 매핑과 비용을 함께 확정해야 합니다. 비밀키 원문은 이 문서에 포함하지 않았습니다. Hermes 모델 자격증명은 Hermes 실행 환경에서 관리하며 백엔드 Secret과 구분합니다.

## 4. API 계약

### OpenAPI 및 배포 버전

- 배포 버전: **없음 / 미정**. 원격 배포와 배포 버전의 계약 검증은 하지 않았습니다.
- 배포 OpenAPI 주소: **미정**.
- 현재 FastAPI 소스의 OpenAPI 경로는 **`/openapi.json`**, Swagger UI 경로는 **`/docs`**입니다. 이 두 경로에는 `/api/v1` prefix가 붙지 않습니다. 실제 배포 후 해당 호스트의 주소를 제공해야 합니다.
- 합의 기준: 저장소 루트 `API_SPEC.md`와 `Docs/api/examples.json`. 로컬 구현과의 차이를 해결한 뒤 원격 통합해야 합니다.

### 합의한 의미와 현재 로컬 구현

| 항목 | 합의된 요구사항 | 현재 확인한 구현 / 검증 상태 |
|---|---|---|
| confirm / 사용자 확인 | 계산 전 사람의 조건 확인, 새 계획 적용 전 선택 필요. `user_confirmed=true`만으로 사람의 동의를 증명하지 않음 | 확인 질문·`next_action="confirm"`은 존재. 별도 confirm HTTP 라우트는 등록된 라우터에서 확인되지 않음. plan 요청 스키마에는 `user_confirmed`가 없고 replan에는 검사 코드가 있음. 전체 서버 확인 게이트 지원 완료로 답할 수 없음 |
| `conversation_id` | 최초 미지정이면 서버 생성, 이후 같은 대화 ID로 상태 유지 | interpret는 전달된 ID 또는 빈 값을 응답 meta에 사용. plan/replan은 ID 필수. HTTP 경로의 실제 대화 생성·영속 저장 연동은 미완성 |
| `revision` | 상태 변경 성공 시 증가, 오래된 값은 `409 CONVERSATION_VERSION_CONFLICT` | interpret 응답은 고정 `revision=1`. 현재 라우터의 저장소 기반 버전 검사·원자 갱신 지원 완료를 확인하지 못함 |
| `Idempotency-Key` | UUID v4, 같은 논리 요청 재시도는 같은 key/body/revision 유지. 동일 결과 재생, 다른 payload는 409. 상태와 성공 결과를 함께 커밋 | 라우터의 헤더 형식 검증 및 응답 헤더 반환 코드 존재. 실제 저장 연동에 의한 중복 처리 방지·재생·충돌 지원은 미완성·미검증 |
| 재시작·재배포 후 상태 | 유효기간 내 조건·후보·선택·revision·중복 처리 기록 유지 | 요구사항 확정. 원격 영속 저장 미구현·미검증. SQLite 설정·모델만으로 보존을 보장하지 않음 |
| 만료와 삭제 | 만료 기록이 남아 있으면 410, 삭제됐거나 처음부터 없으면 404. 물리 정리는 다음 시작·요청 시 허용 | 사용자 선택 확정. 기존 API 문서의 충돌 문구·예제를 공동 정합화한 후 구현해야 함 |

### 공개 계약과 로컬 구현의 주요 차이

**배포하면서 바뀐 요청·응답은 없습니다.** 배포 자체가 없으며, 아래는 현재 소스가 공유 계약과 다른 부분입니다. 배포 승인된 계약 변경으로 간주하지 않습니다.

| 항목 | 공유 API 계약 | 현재 로컬 구현 |
|---|---|---|
| interpret 요청 | `text`, `reference_time`, `timezone`, `context` 등 | `natural_language`, `conversation_id` |
| interpret 응답 | `data.draft`, `ready_for_plan`, `questions` | `trip_draft`, `requires_confirmation`, `confirmation_questions` |
| plan 요청 | `{trip, user_confirmed}` | 평탄한 `TripRequest`, `conversation_id` 필수 |
| plan 응답 | `data.plan.options` 구조 | data에 평탄한 Plan 반환 |
| 막차 요청 | `/journeys/plan`에서 `trip.kind`로 구분 | 별도 `/journeys/plan/last_journey` 라우트 |

`health`·`capabilities`도 현재 mock 구현의 필드·지원 범위가 예제와 완전히 같지 않습니다. OpenAPI 생성만으로 공유 계약 일치나 기능 지원을 입증하지 않습니다. 차이는 `API_SPEC.md`와 예제 JSON을 함께 맞추고 실행 검증한 후 전달하겠습니다.

## 5. 연결 테스트 준비

| 항목 | 현재 답변 |
|---|---|
| 실제 교통 API 연결 여부 | 현재 HTTP 라우터는 MockRoutingProvider 사용. 실제 연결 완료 아님 |
| 장소 검색 | MockPlaceProvider 사용 |
| 자연어 해석 | MockModelProvider 사용. Hermes의 Solar Pro4 설정과 백엔드 모델 연결은 별개 |
| 약속 경로·막차·재탐색 | 현재 라우터는 mock 제공처를 사용. 실제 노선·운행일·막차 검증 완료로 전달하지 않음 |
| 응답 구분 | 현재 health/capabilities 및 주요 라우터는 `meta.is_demo=true`로 응답 |
| 원격 연결 테스트 | 배포 보류로 미실행. 실제 연결 가능한 URL·검증된 운행 시간 예시 없음 |

로컬 mock 입력 후보는 **서울역 `place_seoul_station` → 강남역 `place_gangnam_station`**, 도착시각 예시 **`2026-09-17T10:00:00+09:00`**입니다. 이는 코드에 있는 mock 장소를 사용하는 형식 예시이며, 이 날짜로 실제 HTTP 성공을 검증하지 않았습니다. mock 경로·시각은 실제 운행 정보를 보장하지 않고, 일부 fixture 시각은 고정되어 있어 시간의 일관성도 확인해야 합니다. 실제 교통 테스트용 출발지·도착지·날짜는 제공처 연결과 지원 범위 확정 후 별도로 전달하겠습니다.

초기 연결 확인 경로는 `GET /api/v1/health`, `GET /api/v1/capabilities`입니다. 실제 서버 주소와 인증이 준비된 후 호출해야 합니다. 이동 계획 테스트는 위 계약 차이를 먼저 해결해야 합니다.

### 오류 확인 및 담당

- 연결 오류는 HTTP 상태와 `status/data/error/meta` envelope로 확인합니다. `200 unavailable`은 성공 계획이 아닙니다.
- 상태 관련 합의 코드는 `CONVERSATION_VERSION_CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `CONVERSATION_EXPIRED`, `CONVERSATION_NOT_FOUND`, `CANDIDATE_SET_EXPIRED`입니다. 현재 실제 발생·응답 검증은 완료하지 않았습니다.
- Cloud Run IAM에서 차단한 인증 오류는 백엔드 JSON envelope와 다를 수 있으므로 HTTP 상태를 먼저 구분해야 합니다. HTML·원문 예외를 사용자에게 그대로 노출하지 않습니다.
- 문의 시 호출 시각·경로·HTTP 상태·오류 코드·반환된 request_id(있는 경우)를 공유하면 됩니다. Authorization 토큰, Secret 원문, 사용자 자연어·장소 등 민감한 payload는 제거합니다.
- 백엔드 코드·계산·제공처·배포·서버 로그: **백엔드 담당자(본 회신 작성 측)**. MCP 헤더 전달·토큰 갱신·Hermes 도구 호출: **MCP/Hermes 담당 팀원**. 구체적인 담당자 이름과 연락 경로는 미정입니다.
- 이번 회신은 문서·소스 확인 결과입니다. 서버 실행, 새 테스트, 실제 교통 조회, 저장 성공, 원격 인증·배포 성공을 보고하는 문서가 아닙니다.

## 참고 자료

- [배포 명세](../specs/005-cloud-run-deployment/spec.md)
- [배포 계획 및 차단 사유](../specs/005-cloud-run-deployment/plan.md)
- [배포 조사 결과](../specs/005-cloud-run-deployment/research.md)
- [공유 API 계약](../API_SPEC.md)
- [API 예제](api/examples.json)
- [기존 MCP HTTP 연결 문서](mcp-http-integration.md) — 이 문서에 적힌 과거 테스트 결과는 이번 회신 작성 중 재실행한 결과가 아닙니다.
