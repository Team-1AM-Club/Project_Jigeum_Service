# MCP → 백엔드 연동 인수인계 확인표

> 통합 후 안내: 아래 소스 점검은 원격 5caef80 시점 기록이다. 현재 로컬 confirm·revision·멱등 처리 검증은 [통합 결과](../../Docs/integration-status.md)에 기록했다. 클라우드 배포·인증·공유 저장소는 여전히 미검증이다.

확인일: 2026-09-16. 근거: [명세](spec.md), [배포 계획](plan.md), [API 계약](../../API_SPEC.md), [공동 예제](../../Docs/api/examples.json).

**현재 상태: 월 추가 지출 0원 유지, 서울 배포 보류(BLOCK-COST-001).** 이 세션에서 배포하거나 GCP 자원·IAM·Secret을 조회하지 않았다. 따라서 테스트 가능한 원격 주소와 원격 성공 기록을 제공할 수 없다. 아래 소스 확인은 작업 중인 로컬 파일 기준이며, 배포 버전의 지원 보장이 아니다. 팀원의 정보 요청을 기록한 문서로 Phase 1 설계·구현 재개를 의미하지 않는다.

## 1. 배포 정보

| 요청 항목 | 현재 답변 | 재개 후 확인할 사항 |
|---|---|---|
| GCP 프로젝트 | 사용자 제공 ID `project-jigeum`, 번호 `670549467351` | 실제 ID·번호·결제 연결과 권한 일치 |
| 리전 | 서울 `asia-northeast3` | 승인된 배포 대상의 실제 리전 |
| 서비스 종류 | Cloud Run의 FastAPI 백엔드; MCP는 로컬 실행 | 서비스 이름, 실행 서비스 계정, Cloud Run revision, 소스 버전·이미지 digest |
| API 기본 주소 | 미확인·미제공. 배포 보류 | 실제 서비스 origin에 `/api/v1`을 붙인 전체 URL과 호출 검증 결과 |
| OpenAPI 주소 | 배포본 없음. 로컬 코드의 경로는 `/openapi.json`, Swagger UI는 `/docs` | 배포 origin 기준 전체 URL, 해당 버전 schema, 인증 후 접근 확인 |

`/api/v1/openapi.json`로 추정하지 않는다. 현재 [main.py](../../backend/app/main.py)는 업무 라우터에만 `/api/v1`을 적용한다. 프로젝트 ID로 `run.app` 주소를 추측하지 않는다.

## 2. MCP → 백엔드 인증

팀 전용 인증은 확정 요구사항이다. 아래는 기존 계획의 **미확정 후보**이며 실제 로그인·권한 부여·토큰 발급·호출은 수행하지 않았다.

| 구분 | 검토 중인 방식 | 검증 조건 |
|---|---|---|
| HTTP 호출 | `Authorization: Bearer <OIDC ID token>` | Cloud Run IAM 인증, 대상 서비스 URL을 audience로 사용(`/api/v1` 제외), 익명·만료·다른 audience·권한 없는 호출 거부 |
| 로컬 MCP | 팀용 Google 계정으로 로컬 사용자 ADC를 준비한 뒤 IAM Credentials `generateIdToken` 직접 호출 | 호출용 서비스 계정의 ID token 발급(`includeEmail=true`), 만료 전 갱신, ADC와 토큰을 채팅·저장소·로그에 남기지 않음 |
| 토큰 발급 권한 | 팀 계정에 호출용 서비스 계정 범위의 `roles/iam.serviceAccountOpenIdTokenCreator` | 실제 principal, IAM Credentials API와 조직 정책, 사용자 ADC quota project에 필요한 권한 확인 |
| 서비스 호출 권한 | 호출용 서비스 계정에 대상 Cloud Run 서비스 범위의 `roles/run.invoker` | 실제 IAM 바인딩 및 허용/거부 테스트 |
| 업무 헤더 | JSON 요청은 `Content-Type: application/json`; 상태 변경은 `Idempotency-Key: <UUID v4>` | 인증 헤더와 별도 책임. 재시도는 동일 key·동일 body 유지 |

ADC는 로컬 자격 증명을 찾는 방식이며 ADC 파일이나 OAuth access token을 그대로 Cloud Run 호출 헤더에 넣는다는 뜻이 아니다. 직접 ID token 발급과 일반 서비스 계정 impersonation의 권한 요구를 혼동하지 않는다. 호출 계정 이메일·서비스 계정 이름은 미확정이며 임의로 생성하지 않았다. [공식 ID token 발급 절차](https://docs.cloud.google.com/iam/docs/create-short-lived-credentials-direct).

## 3. Secret Manager 설정

Secret Manager는 백엔드가 외부 제공자의 키를 사용하는 경로다. Secret 저장만으로 MCP 호출 인증이 설정되지는 않는다. MCP에 교통 API 키나 백엔드 Secret 접근 권한을 전달하지 않는다.

| 기록할 항목 | 현재 상태 / 재개 후 기록 기준 |
|---|---|
| Secret 이름·버전·용도 | 실제 목록 미조회. 사용할 provider 확정 후 필요한 항목만 기록. 목록이 없다는 뜻이 아니며 이름이나 버전 `1`을 가정하지 않음 |
| Secret 읽는 계정 | Cloud Run 실행 서비스 계정 미확정. 호출용 서비스 계정과 구분 |
| 접근 권한 | 사용할 각 Secret 범위의 `roles/secretmanager.secretAccessor` 검토. 실제 부여 여부 미확인 |
| 백엔드 사용 방식 | 미확정. 기존 환경 설정으로 연결할 수 있으면 Cloud Run Secret 참조로 환경변수에 주입하는 안을 재개 후 검토. 환경변수 방식은 숫자 버전을 고정해 revision과 대응시키고 사용 필드·갱신/재배포 방법을 기록 |
| 비용 | 필요한 Secret 버전 수·접근 횟수·무료 잔여량을 비용 검토에 추가. Secret Manager도 자동으로 무료라고 간주하지 않음 |

최종 목록은 `Secret 이름 / 숫자 버전 / 용도 / backend 설정 필드 또는 mount 경로 / 실행 SA / 접근 범위 / 검증 상태`로 작성한다. 현재 [config.py](../../backend/app/config.py)의 `model_provider_api_key` 등 필드 존재만으로 live provider 연동이나 Secret 사용을 입증할 수 없다. 필요한 키의 종류는 해당 연동 작업에서 확정한다. 비밀값·ADC 내용·서비스 계정 JSON 키를 이 표에 기록하지 않는다. [Cloud Run Secret 설정 공식 문서](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

## 4. API 계약과 현재 구현 간 차이

계약의 기준은 `API_SPEC.md`와 `Docs/api/examples.json`이다. 아래 차이는 **배포하면서 승인한 계약 변경이 아니라 현재 소스에서 발견한 선행 확인 항목**이다. 배포본이 없으므로 로컬과 배포본의 차이는 아직 비교할 수 없다.

| 항목 | 계약상 요구 | 현재 소스 확인 / 배포 상태 |
|---|---|---|
| confirm | 계산 전 사용자 조건 확인 및 확인된 상태 검증 | 팀원이 말한 confirm은 확인 흐름 요구로 기록. 별도 `/confirm` endpoint로 임의 해석하지 않음. 현재 `TripRequest`에 `user_confirmed`가 없고 재탐색 요청에는 해당 필드가 있으나 기본값이 true여서 전체 확인 강제를 입증하지 못함. 구체적 확인/선택 API는 공동 계약 확인 필요 |
| conversation_id | 최초 미지정 시 생성, 이후 같은 대화 유지 | `/mobility/interpret`는 미지정 시 빈 문자열을 사용. 모델·서비스 파일 존재와 별개로 HTTP 경로의 실제 생성·저장 연동 확인 필요 |
| revision | 마지막 revision 전달, 상태 변경 시 증가, stale 요청 409 | interpret 응답은 `revision=1` 고정. HTTP 상태 변경 경로의 원자적 버전 검증·영속 저장을 완료로 볼 수 없음 |
| Idempotency-Key | UUID v4 요청/응답 헤더, 동일 요청 replay, 다른 payload 409, 상태와 원자적 저장 | 입력 검사와 interpret 응답 헤더 설정은 보이지만 journeys 경로의 응답 헤더 반환·저장 replay는 확인되지 않음. 헤더 정의에 `include_in_schema=False`가 있어 생성 OpenAPI의 계약 누락도 검증 필요 |
| 만료 오류 | 사용자 선택: tombstone 잔존 시 410, 삭제 또는 최초부터 없으면 404 | API_SPEC 내부와 초기 인수인계의 410 통일 문구가 충돌. 공동 합의 후 문서·예제·구현을 함께 정합화해야 함 |

소스 근거: [mobility.py](../../backend/app/api/mobility.py), [journeys.py](../../backend/app/api/journeys.py), [요청 스키마](../../backend/app/schemas/journeys.py). 기존 [백엔드 초기 인수인계](../../Docs/BACKEND_HANDOFF.md)는 골격 공유 시점 문서이며 현재 배포 지원표로 사용하지 않는다. 이번 작업에서 API 계약이나 코드를 수정하지 않았다.

재개 시 배포할 버전의 OpenAPI와 공동 예제를 대조하고, 요청·응답·오류·헤더 차이를 항목별로 기록한다. 생성 OpenAPI에 필드가 보인다는 사실만으로 상태 보존이나 중복 요청 처리 성공을 판정하지 않는다.

## 5. 연결 테스트 준비와 오류 확인

| 항목 | 현재 확인 및 후속 기준 |
|---|---|
| 실제 교통 API | 현재 HTTP 라우터는 `MockRoutingProvider`를 직접 생성한다. 별도 교통 연동 명세나 자격 증명 보유만으로 live 연결 완료라 하지 않음 |
| 아직 mock인 기능 | 장소 검색 `MockPlaceProvider`, 자연어 해석 `MockModelProvider`, 계획·막차·재탐색 `MockRoutingProvider`. 원격 실행 검증 없음 |
| 테스트 후보 | 로컬 mock에 있는 서울역 `place_seoul_station` → 강남역 `place_gangnam_station`. 시간은 테스트 당일 미래의 도착 시각을 `+09:00`으로 사용. 예: `2026-09-17T19:00:00+09:00`는 그 시각 이전 실행에만 유효한 후보이며 성공 검증된 입력이 아님 |
| 실행 전 입력 확정 | 배포 provider의 장소 검색 결과로 ID를 다시 얻고 지원 지역·교통수단·운행일 확인. 정상 대화 생성·사용자 확인 후 받은 ID와 revision을 사용. 실제 교통 테스트와 mock 테스트 결과를 분리 |
| 검증할 흐름 | 인증 후 health/capabilities → 장소 검색 → 해석·조건 확인 → 계획·선택 → 동일 요청 재전송·revision 충돌 → 재시작 후 상태 유지. 현 단계 미실행 |
| 오류 공유 정보 | 발생 시각(Asia/Seoul), method/path, HTTP status, 안전하게 가린 error.code/message, request_id 또는 trace 식별자(있는 경우), Cloud Run revision, 재현 단계. Authorization·토큰·키·전체 환경변수·민감한 대화 원문 제외 |
| 오류 확인 방법 | Cloud Run 인증 계층의 401/403과 backend envelope 오류를 구분. IAM 단계에서 거부된 응답은 backend JSON 형식이나 request_id가 없을 수 있음. 배포 담당이 시간·서비스·revision으로 Cloud Logging을 확인하고 필요한 결과만 공유 |
| 담당 역할 | MCP 담당: 토큰 갱신·HTTP 헤더·재시도·Hermes 확인/선택 흐름. 백엔드/배포 담당: IAM·Secret 주입·컨테이너·API 상태 계약·교통 provider·서버 로그. 실명/연락 채널과 로그 열람 권한은 재개 시 팀에서 지정 |

실제 호출을 수행한 뒤에만 `대상 URL / 배포 revision / 수행 시각 / 입력 조건 / 예상 결과 / 실제 결과 / 담당 / 미검증 사유`를 채운다. 원격 연결 성공과 실제 교통 데이터 연결 성공은 별도로 판정한다.

## 재개 시 필요한 비밀이 아닌 정보

- 비용 게이트를 해소할 승인된 조건과 재개 결정.
- 실제 서비스 이름·URL·revision·실행 SA, 허용할 Google principal·호출 SA.
- 필요한 Secret의 이름·버전·용도와 provider별 live/mock 상태.
- 공동 합의한 확인/선택 흐름과 계약 정합성 결과, 테스트 입력·실행 결과, 담당자와 오류 확인 경로.

현재는 배포 보류로 확보할 수 없는 항목이므로 답변 대기 때문에 문서 반영을 중단하지 않는다. 배포 재개 전에는 미확정 상태로 실행하지 않는다.
