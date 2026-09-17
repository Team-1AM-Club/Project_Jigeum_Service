# 조사와 설계 결정

작성일: 2026-09-16. [계획](plan.md)의 검토용 근거이며 공통 계약 확정본이 아니다.

## 사용자가 정한 범위

| 결정             | 답변                                                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------------------------------- |
| 대상·적용 범위   | 003 MCP HTTP 통합, 검토용 제안. 공통 API 문서 개정은 공동 검토 후.                                                  |
| 상태·재시도      | 서버 SSOT, 확인·선택·revision 포함. 제한된 오류에 500ms 뒤 최대 1회, 같은 키·본문.                                  |
| 사용자 확인      | Hermes form-mode elicitation 필수. 미지원이면 계산·선택 차단.                                                       |
| 인터페이스       | MCP 도구 5개 유지 + action. 내부 REST 상태 경로 추가.                                                               |
| 실행 경계        | 로컬 통합 우선. 원격 상태 공유·접근 제어는 별도 게이트.                                                             |
| 수명             | 초안 30분, 확인 후 2시간, 선택 ETA 후 2시간, 전체 최대 48시간. 후보는 provider 유효시각 또는 5분. tombstone 24시간. |
| 대화 분리        | Hermes 대화마다 MCP 프로세스 분리. 한 프로세스의 여러 대화 지원은 이번 범위 밖.                                     |
| 상위 4건 수정안  | C1·C2·U1·G1을 003 관련 문서까지 동기화한다. 공통 API/예제는 공동 합의 작업으로 남긴다.                              |
| 미확정 계약 표현 | MCP 진단 필드·REQUEST_TIMEOUT의 구체적인 권장안을 기록하되 T001 공동 합의 전까지 미확정으로 유지한다.               |

## 기존 구현 조사

현재 작업 트리에는 별도 작업의 백엔드 변경이 있다. 다음은 파일을 읽은 결과이며 실행 테스트 결과가 아니다. 기준 HEAD는 `44f61169c050255268ba855c6074a15bb8000a6f`지만 수정된 파일은 그 커밋 그대로가 아니다.

| 근거 파일                                                              | 확인한 사실·설계 영향                                                                                                                                       |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/api/mobility.py`                                          | natural_language 입력과 trip_draft 출력. meta의 revision=1과 1일 만료를 직접 구성한다. 서버의 실제 상태에서 메타를 읽도록 바꿔야 한다.                      |
| `backend/app/api/journeys.py`, `schemas/journeys.py`                   | 평탄한 TripRequest/Plan, 별도 last_journey 경로, replan의 user_confirmed 기본 True가 남아 있다. 공유 구조 및 서버 확인 게이트와 다르다.                     |
| `backend/app/services/conversation_service.py`                         | UUID 발급·기본 24시간·개별 commit, 조회 후 revision 비교 방식. 조건부 UPDATE와 외부 workflow 트랜잭션 경계가 필요하다.                                      |
| `backend/app/models/conversation.py`                                   | confirmed_conditions/candidate_set/active_selected_plan JSON은 있으나 독립 미확인 초안과 단계별 만료를 담을 확장이 필요하다.                                |
| `backend/app/services/idempotency_service.py`, `models/idempotency.py` | SHA-256 canonical hash, 대화+키 UNIQUE, flush 기반 저장이 있다. 최초 대화 생성의 전역 키 매핑·HTTP status 보존·정리 정책·동시 충돌 후 재생을 보강해야 한다. |
| `backend/app/services/idempotency.py`                                  | 같은 이름의 테이블을 별도 정의하는 구현이 있다. 실제 호출처 확인 후 하나의 경로를 사용한다. 이번 조사에서 제거 여부는 판단하지 않았다.                      |
| `backend/app/db.py`, `config.py`, `requirements.txt`                   | SQLAlchemy SessionLocal, SQLite 기본값, Python 3.11 대상 도구 설정, FastAPI/Pydantic 2/httpx/pytest 의존성을 확인했다.                                      |
| `backend/tests/contract`, `backend/tests/integration`                  | conversation/plan/last_journey/replan 테스트 파일이 있다. 파일 존재를 현재 계약 통과로 간주하지 않는다.                                                     |

Graph 도구는 이번 세션에 제공되지 않았다. 범위를 제한한 파일 읽기로 조사했으며 전체 호출 관계나 코드 전체의 결함 부재는 주장하지 않는다. MCP 서버 소스와 설치 Hermes 런타임은 이 조사 범위에서 확인되지 않았다.

## R1. 실제 확인과 모델 입력의 분리

**결정**: MCP가 서버 초안으로 요약을 만들고 `elicitation/create` form 요청을 보낸다. `accept`와 명시적 승인 값이 함께 온 경우에만 MCP 코드가 evidence를 만들어 확인 REST를 호출한다. 선택도 같은 방식으로 후보 ID를 직접 받는다.

**근거**: Hermes 공식 문서는 form-mode elicitation을 CLI/TUI와 승인 표면으로 전달한다고 명시한다. MCP 명세는 capability 협상과 accept/decline/cancel을 정의한다. 설치 버전의 지원 여부와 실제 사람 입력 경로는 별도 실행 검증한다. [Hermes 문서](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp#mcp-elicitation-support), [MCP elicitation 명세](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)

**대안**: 모델 boolean 또는 인용된 사용자 문장을 증거로 받는 방식은 조건 결부와 출처를 강제하지 못하므로 제외한다. 별도 승인 웹 화면은 제품 범위와 복잡성 때문에 제외한다.

**신뢰 경계**: 이 evidence는 MCP가 직접 받은 클라이언트 응답의 기록이지 사람 신원 인증이나 암호학적 증명은 아니다. 로컬의 신뢰된 Hermes/MCP/백엔드 경계를 전제로 한다. 원격 공개 백엔드에 그대로 적용하지 않는다.

## R2. 내부 상태 경로와 기존 도메인 JSON

**결정**: GET 상태 조회, POST 조건 확인, POST 후보 선택을 내부 REST로 분리한다. 도구 5개 안의 action에서 호출한다. 요청 본문의 `conversation_id`, `revision`을 명시하고 응답은 `meta.conversation_id/revision/expires_at`으로 통일한다. 도메인 `TripRequest`, `Plan`, `Comparison`은 공유 API 구조를 재사용한다.

**이유**: 조회·확인·계산·선택의 실패와 commit 단위를 분명하게 테스트할 수 있다. plan/replan을 자동 선택과 결합하지 않는다.

**대안**: 모든 REST를 action union으로 만드는 방식은 기존 계산 경로를 과도하게 확장한다. MCP 도구를 추가하는 방식은 사용자가 선택한 5개 범위와 다르다.

## R3. 초기 응답 유실과 유한한 멱등성 보존

**결정**: 최초 interpret는 conversation_id/revision 없이 받고 서버가 생성한다. MCP는 최초 전송 직전에 `request_started_at`을 UTC offset datetime으로 만들고 키·본문과 함께 고정한다. 백엔드는 키를 전역 UNIQUE로 식별하며 초기 생성·초안·성공 envelope를 원자 저장한다.

**이유**: 대화 ID를 받기 전에도 같은 요청을 찾을 수 있어야 한다. 기록을 영구 보관하지 않으면서 아주 오래된 최초 요청이 새 대화를 만드는 것을 막으려면 요청의 시작 시각도 필요하다.

**제안한 경계값**: 기록이 없는 최초 요청만 시작 후 5분 이내, 서버보다 최대 30초 앞선 시각을 허용한다. 기존 기록이 있으면 이 나이 검사 대신 연결된 대화의 생존·재생 규칙을 적용한다. 만료 후에는 응답 payload를 제거하고 최소 키 매핑만 tombstone 종료까지 유지한다. 제거 후 오래된 최초 본문은 `410 INITIAL_REQUEST_EXPIRED`로 거부한다. 시각을 바꾸는 것은 같은 요청 재시도가 아니다.

**대안**: 새 UUID를 매번 발급하면 첫 응답 유실에서 중복 생성된다. 키를 영구 저장하면 단기 보존 원칙과 맞지 않는다. MCP가 conversation_id를 만드는 방식은 서버 발급 결정과 다르다. 기존 대화+키 복합 UNIQUE보다 전역 UUID 키 UNIQUE가 새 대화/다른 경로의 잘못된 키 재사용도 단순하게 검출한다.

## R4. 저장과 원자성

**결정**: 기존 SQLite와 SQLAlchemy를 로컬 단일 백엔드 프로세스에서 사용한다. provider 호출은 쓰기 트랜잭션 밖에서 수행한다. 성공 적용 시 revision 조건부 UPDATE, domain 갱신, idempotency 결과 저장을 같은 짧은 트랜잭션에 묶는다.

**이유**: 현재 자산으로 필요한 상태 정합성을 검증할 수 있다. 다중 프로세스·인스턴스 공유를 로컬 DB로 해결했다고 주장하지 않는다. 같은 키의 동시 요청은 한 상태 변경만 commit하며 loser는 winner 기록을 재조회한다. provider 호출 자체가 한 번만 발생함을 보장하는 계약은 아니다.

**대안**: process mutex만으로 DB 원자성을 대신하지 않는다. 새 Redis/PostgreSQL 도입은 원격 인수 범위가 결정된 뒤 별도 검토한다.

## R5. 수명과 이전 선택 보존

**결정**: 사용자 답변의 단계별 수명을 적용한다. 세부 deadline과 대화 전체 수명의 관계는 [데이터 모델](data-model.md)에 정의한다. 조회·replay·실패는 수명을 연장하지 않는다. 새 초안으로 확인과 후보를 무효화해도 이전 선택 기록은 보존한다.

**대안**: 코드의 고정 24시간은 사용자 선택과 달라 채택하지 않는다. 후보 만료와 대화 만료를 같은 오류로 처리하면 이전 선택 보존을 검증할 수 없다.

## R6. 재시도·응답·대기

**결정**: 자동 재시도는 MCP의 HTTP 경계 한 곳에서만 수행한다. 502/503/504는 유효한 계약 오류의 retryable=true일 때만 허용한다. 잘못된 JSON/스키마·키·상태 조합은 재시도하지 않는다. POST 전송 후 적용 불명은 첫 응답부터 보류하고 원본 요청을 보존한다. 유효한 미적용 오류와 응답 파손을 구별한다. 사용자 승인 대기는 HTTP timeout 밖에 둔다. 전체 호출 상한과 각 단계 수는 [MCP 계약](contracts/mcp-contract.md)에 명시한다.

**대안**: HTTP 상태만 보고 재시도하거나 Hermes·MCP·backend workflow가 각각 재시도하는 방식은 호출 수를 예측하기 어려워 제외한다. 응답 유실 후 새 키로 자동 재실행하는 것도 제외한다.

## R7. 공동 적용과 환경 정보

**결정**: 이 디렉터리의 제안을 검토한 뒤 공통 기준을 한 번에 개정한다. 사용자 범위 결정은 답변으로 정리했으며 MCP 진단 필드와 REQUEST_TIMEOUT은 사용자가 선택한 대로 T001 공동 합의 전까지 미확정 권장안으로 남긴다. 아직 실제 실행하지 않은 환경은 미검증 조건으로 기록한다.

실행에 필요한 MCP 저장소 경로·진입점, 설치 Hermes/SDK, 실제 Solar Pro4 ID, Base URL, 제공처 범위는 [검증 안내](quickstart.md)의 사전 조건이다. 임의 값으로 대체하거나 지금 연결됐다고 보고하지 않는다. 별도 004 작업의 provider 설계·구현을 변경하지 않는다.

## R8. 수정안의 근거와 대안

- **C1 결정**: MCP 설계 적합, 개발 도구 조건 미충족, 실제 시연 미검증을 분리한다. 문서 반영 요청은 헌법 예외 승인이 아니다.
- **C2 결정**: T062/T063을 확장 전 실제 약속 인수로 분리하고 US4/US5 앞에 둔다. 막차 데이터까지 기다리는 일괄 인수 대신 약속 제공처 준비만을 T063의 외부 선행 조건으로 둔다. 실제 약속을 검증하지 않은 확장은 채택하지 않는다.
- **U1 결정**: 재시도 허용 여부와 서버 적용 확정 여부를 독립적으로 판정한다. 첫 파손 응답도 OUTCOME_UNKNOWN으로 보류한다. 대표 오류와 원인을 분리하는 `diagnostics.cause_code`를 제안하며 T001에서 기존 MCP schema와 맞춰 확정한다. 새 키 자동 실행·GET revision만으로 성공 판단·취소를 rollback으로 간주하는 대안은 제외한다.
- **G1 결정**: 서버 핸들러 진입부터 원자 확정까지 단조 경과시간 3/10/25초를 검증한다. 기존 timeout 처리를 우선 재사용하고 새 상태 경로의 SLA는 추가하지 않는다. 기존 UPSTREAM_TIMEOUT을 서버 전체 예산 소진에 확대 해석하는 대신 REQUEST_TIMEOUT을 제안하되 공동 합의 전 도입하지 않는다. 단순 task 취소만으로 늦은 commit 방지를 주장하는 대안은 제외한다.

이번 수정은 기존 문서와 사용자 답변에 근거한 설계 보완이다. 새 외부 기술 조사나 설치 환경·제공처 실행 검증을 했다는 뜻이 아니다.
