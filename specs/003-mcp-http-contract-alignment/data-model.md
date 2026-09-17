# 데이터 모델과 상태 전이 제안

관련 문서: [명세](spec.md), [HTTP 계약](contracts/http-contract.md), [MCP 계약](contracts/mcp-contract.md).

검토용 제안이다. 아래 필드는 기존 구현 여부와 관계없이 목표 설계를 나타낸다. 실제 사용자·원문 대화 전체·영구 이동 이력은 저장하지 않는다.

## 1. Conversation

| 필드 | 타입·규칙 |
|---|---|
| conversation_id | 서버가 생성하는 UUID 문자열. MCP나 모델이 초기 값을 만들지 않는다. |
| revision | 양의 정수. 최초 초안 저장 성공은 1. 이후 domain 상태 변경 성공마다 정확히 1 증가한다. |
| created_at / updated_at | 서버 시각. updated_at은 성공한 변경에서만 갱신한다. |
| absolute_expires_at | created_at + 48시간. 변경 불가. |
| expires_at | 아래 개별 상태의 유효한 보존 deadline 중 최댓값과 absolute_expires_at 중 이른 시각. |
| draft | TripDraft, 정규화 가능한 경우의 TripRequest, draft_revision, conditions_hash, expires_at. 불완전하면 normalized_trip/hash는 null. |
| confirmed_conditions | 확인한 TripRequest, conditions_hash, confirmation_id, confirmed_at, confirmed_revision, expires_at, approval evidence. 미확인 또는 변경 후에는 null. |
| candidate_set | candidate_set_id, 생성 당시 conditions_hash/confirmation_id, Plan, generated_at, expires_at. 없으면 null. |
| candidate_marker | 가장 최근 후보의 ID·만료시각. 후보 payload를 정리한 뒤에도 같은 후보의 만료와 다른 후보 ID를 구분한다. 초안 변경·새 확인·새 후보 생성·대화 만료 때 교체하거나 제거한다. |
| active_selected_plan | 선택한 Plan의 해당 후보와 trip·출처 snapshot, candidate_set_id, option_id, selected_at, expires_at, selection evidence. 없으면 null. |
| status | active 또는 tombstone. 만료 판단은 status뿐 아니라 현재 서버 시각으로 수행한다. |
| expired_at | tombstone에서만 사용. 원래의 논리적 대화 만료시각으로 한 번 고정한다. |

conditions_hash는 normalized TripRequest 전체를 canonical JSON으로 직렬화한 SHA-256이다. 장소·종류·날짜·마감·도착 여유·이동수단을 포함한다. 직렬화는 객체 키 정렬·UTF-8·불필요한 공백 제거이며, 배열 순서와 null/필드 생략 차이를 숨기지 않는다. 공개 TripRequest의 필수 키를 먼저 검증한다. 이 hash 자체가 승인 비밀이나 권한 토큰은 아니다.

`draft_revision`은 초안을 생성·변경한 성공 revision을 가리킨다. 확인 후 conversation revision이 증가해도 그 초안의 draft_revision은 바꾸지 않는다. 계산은 현재 revision과 살아 있는 confirmation_id/hash 모두를 검증한다.

## 2. 개별 수명과 대화 수명

모든 경계는 `deadline <= server_now`이면 만료다. 날짜를 버리거나 로컬 시각 문자열만 비교하지 않는다.

| 상태 | 만료·보존 deadline |
|---|---|
| 미확인 초안 | 마지막 성공 초안 변경 + 30분 |
| 확인 조건 | 마지막 실제 조건 확인 성공 + 2시간 |
| 후보 집합 | provider valid_until이 있으면 그 시각, 없으면 generated_at + 5분. 확인 조건·대화 절대 상한을 넘기지 않는다. 여러 근거의 유효시각은 가장 이른 것을 쓴다. |
| 현재 선택 기록 | 선택한 후보의 estimated_arrival_at + 2시간 |
| 대화 전체 | 아직 유효한 초안·확인·후보·선택의 deadline 중 최댓값, 단 created_at + 48시간을 넘지 않는다. |
| tombstone | 원래 expires_at부터 24시간. 늦게 정리하거나 반복 요청해도 연장하지 않는다. |

확인 성공 시 초안의 값은 확인 조건으로 보존하고 draft는 null로 소비한다. 미확인 초안의 수명은 전체 대화 수명을 늘리는 별도 근거로 쓰지 않는다. 새로운 초안을 저장하면 이전 확인과 후보를 무효화하지만 선택 기록의 deadline은 그대로 유지한다. 새 초안이 만료돼도 선택 기록이 살아 있으면 대화는 계속 존재한다. 이때 새로운 계산에는 다시 초안 작성·확인이 필요하다.

후보 선택 성공은 **이미 받은 ETA**를 바꾸지 않는다. 후보만 만료되면 confirmed_conditions와 active_selected_plan은 남긴다. 후보의 권장 출발이 이미 지나 현재 선택 대상으로 사용할 수 없으면 선택을 거부하고 새 계산을 안내한다. `Plan.refresh_after`는 재확인 권고 시각이므로 후보 expires_at과 같은 값이라고 가정하지 않는다.

조회·replay·충돌·거절·취소·provider 실패는 revision, updated_at, TTL을 갱신하지 않는다. 후보 생성 성공도 확인 유효기간을 새로 2시간 연장하지 않는다. 같은 조건을 새 사용자 승인으로 다시 확인하면 확인 deadline을 갱신하는 별도 성공 변경이다.

시간 경과로 개별 payload를 제거하는 정리는 사용자 상태 변경 revision을 증가시키지 않는다. 요청 검증에서는 정리 실행 여부와 관계없이 deadline을 확인한다. 대화 전체 만료는 payload와 replay 응답을 원자 제거하고 최소 tombstone만 남긴다. 정리는 시작 시·주기적·요청 시 실행하며, 주기 간격은 로컬 구현의 관리 값이고 만료 의미에 영향을 주지 않는다.

## 3. ApprovalEvidence와 SelectionEvidence

| 필드 | 규칙 |
|---|---|
| source | 고정값 `mcp_elicitation` |
| interaction_id | MCP 코드가 생성하는 UUID. 같은 승인 결과의 HTTP 재전송에서 유지한다. |
| accepted_at | MCP가 실제 accept 응답을 받은 offset datetime. 재전송 때 갱신하지 않는다. |
| 승인 대상 | 확인 요청의 draft_revision/conditions_hash 또는 선택 요청의 candidate_set_id/option_id와 함께 저장한다. |

MCP 도구의 모델 입력 스키마에는 evidence, confirmation_id, backend revision, Idempotency-Key를 노출하지 않는다. 서버는 증거의 형식·대상·현재 상태·revision·중복 사용을 검사한다. 최초 적용 시 accepted_at이 서버보다 30초 넘게 미래이거나 5분보다 오래되면 거부한다. 이미 성공한 동일 요청 replay는 증거 나이 검사보다 먼저 판정한다.

interaction_id는 한 사용자 승인 행위에만 귀속된다. 다른 키·다른 대상의 승인으로 재사용할 수 없도록 기록 또는 UNIQUE 제약으로 막는다. 거절·취소·대기 종료의 증거는 승인 레코드가 아니다. 서버는 HTTP로 받은 evidence만으로 실제 사람 신원을 인증할 수 없다. 신뢰된 로컬 MCP를 거친다는 실행 경계와 실제 Hermes 인수 테스트가 함께 필요하다.

## 4. 상태 전이

| 동작 | 선행 조건 | 성공 변화 | 유지할 것 |
|---|---|---|---|
| 최초 interpret | 유효한 초기 키·시작시각, 검증된 해석 응답 | 대화 UUID 발급, draft 저장, revision=1 | 아직 확인·후보·선택 없음 |
| 후속 interpret | 기존 대화 유효, 기대 revision 일치 | draft 교체, 확인·후보 무효화, revision+1 | 이전 선택 snapshot·deadline |
| confirm | 완전한 살아 있는 draft, hash·draft_revision 일치, 실제 승인 evidence | confirmed_conditions·confirmation_id 저장, draft 소비, 후보 무효화, revision+1 | 이전 선택 snapshot |
| plan/replan | 유효한 확인 조건, 일치하는 effective trip, 기대 revision | 새 candidate_set, revision+1 | 확인 조건의 기존 deadline·이전 선택 |
| select | 최신 candidate_set 소속 option, 유효한 후보·조건, 실제 선택 evidence | active_selected_plan 교체, revision+1 | 확인 조건, 후보의 원래 deadline |
| GET state | 대화 유효 | 상태 조회만 | revision·TTL |
| 실패·승인 전 취소 | 서버의 실패가 확인됐거나 아직 HTTP를 보내지 않음 | 성공 domain 변화 없음 | 이전 상태·수명 |
| 대화 만료 | now >= expires_at | payload 제거, tombstone 전환 | ID·마지막 revision·expired_at, 최소 멱등 매핑 |

반복 select는 같은 키이면 replay다. 다른 키로 동일 후보를 다시 선택하는 것은 새 승인 행위가 있을 때만 성공하며, 기존 selected deadline을 연장하지 않는다. 조건이 달라진 후 과거 후보를 선택할 수 없다.

이미 HTTP를 전송한 뒤 MCP가 취소되거나 timeout이 발생하거나 첫 응답의 JSON/schema/key/status가 깨진 경우에는 서버 미적용을 단정하지 않는다. 서버가 commit했을 수 있으므로 결과 미수신 상태로 남기고 같은 키로 확인한다. 사용자 취소나 자동 재시도 금지를 서버 rollback으로 표현하지 않는다.

확인 성공 뒤 계산이 실패했다면 **확인 트랜잭션의 성공은 유지**된다. 계산 실패가 확인까지 되돌리지 않는다. 계산 재요청 시 확인 조건이 그대로 유효하면 불필요하게 같은 조건을 다시 질문하지 않는다. 사용자 재탐색 요청 자체는 elicitation에서 확인한다.

## 5. IdempotencyRecord와 초기 생성

| 필드 | 규칙 |
|---|---|
| idempotency_key | UUIDv4 표준 36자, 전역 UNIQUE 제안. 요청·응답 헤더 전용. |
| request_hash | HTTP method + 정규화된 `/api/v1/...` path + 요청 conversation_id/없음 + 기대 revision/없음 + canonical body의 SHA-256. 최초 body의 request_started_at도 포함. |
| conversation_id | 최초 성공 때 해석되는 서버 UUID. 최초 요청 fingerprint의 conversation_id 없음 값을 사후 UUID로 바꾸지 않는다. |
| http_status / response_body | 성공한 domain 변경의 최초 HTTP status와 envelope. `ok`와 초안 저장 성공인 `needs_confirmation`을 보관한다. |
| created_at | 최초 commit 시각. replay에서 바꾸지 않는다. |
| expired_at | 대화 만료 후 최소 매핑에 남기는 시각. 응답 payload는 제거한다. |

요청 처리 순서:

1. JSON/키 형식과 요청 대상의 기본 구조를 검증한다. 최초가 아닌 요청은 대화 존재·만료를 확인한다.
2. 기존 키의 fingerprint가 다르면 409. 같은 키의 성공 대화가 만료됐으면 410이며 과거 성공을 반환하지 않는다.
3. 유효한 대화의 같은 키·본문이면 최초 응답을 재생한다. 현재 revision과의 불일치보다 우선한다.
4. 새로운 키이면 기대 revision, 확인·후보·선택 조건과 수명을 검증한다. 최초 요청은 request_started_at의 5분/미래 30초 규칙도 검사한다.
5. provider가 필요하면 DB 쓰기 트랜잭션 밖에서 호출하고 결과를 검증한다.
6. 짧은 쓰기 트랜잭션에서 1~4의 상태를 다시 검사한다. 처리 예산이 적용되는 요청은 원자 확정 지점에서 남은 단조 시간도 검사한다. 제한 이상이면 새 결과를 적용하지 않으며 timeout 뒤 늦은 commit을 차단한다. 새 domain 상태 + revision 조건부 갱신 + 최초 결과를 함께 commit한다. 하나라도 실패하면 전부 rollback한다. 제한 안에 이미 확정한 성공은 응답 전달이 늦어도 지우지 않는다.

기존 대화의 갱신은 `WHERE conversation_id = id AND revision = expected AND status = active` 및 만료 확인을 포함하고 갱신 행 수가 1일 때만 성공한다. provider 호출 전의 읽기 결과를 commit 시점의 근거로 재사용하지 않는다. SQLite의 write 경쟁·UNIQUE 충돌은 제한된 시간 안에서 winner를 재조회하고 replay 또는 명시적 충돌/일시 장애로 처리한다. 일반 DB 오류를 만료로 감추지 않는다.

동시 최초 요청은 동일 키 UNIQUE 경쟁에서 한 대화만 commit한다. 패배한 트랜잭션의 임시 대화 행은 rollback하고 winner의 UUID·응답을 반환한다. 업무상 unavailable·검증 실패·provider 실패는 domain 성공으로 저장하지 않는다. provider 요청 비용이 exactly-once라는 보장은 없으며 검증 기준은 **상태 적용 1회**다.

대화 만료 시 초기 키→대화 ID의 최소 매핑을 tombstone의 24시간 종료까지 유지한다. 이후 mapping도 제거한다. 예전 초기 요청이 더 늦게 도착하면 보존 기록이 없어도 request_started_at 제한으로 새 대화를 생성하지 않는다. 이를 피하려고 시간·본문을 바꾸는 것은 같은 논리 요청이 아니며 MCP는 허용하지 않는다.

## 6. MCP의 비권위 상태

MCP 프로세스는 현재 mode, 서버 conversation_id, 관측한 최대 revision, 진행 중 요청의 키·원본 직렬화 body·HTTP 단계·고정 시각·남은 retry 예산·적용 불명 상태와 안전한 원인 분류를 유지한다. 이 값은 서버 상태의 대체 저장소가 아니다. 사용자 선택을 MCP 메모리에서 독자 확정하지 않는다.

POST 응답 파손은 첫 응답부터 보류하며 새로운 변경을 차단한다. GET은 허용하지만 revision 변화만으로 해당 요청의 결과를 확정하지 않는다. 유효한 성공 replay, 미적용이 보장된 최종 오류, 만료 종료를 구별한다. 만료 종료는 과거 미적용의 증거가 아니다. 명시적 resume은 원래 POST 1회이며 자동 retry 예산을 초기화하지 않는다.

하나의 Hermes 대화가 하나의 프로세스를 소유한다. 모델이 다른 conversation_id를 인자로 지정할 수 없다. 다른 mode·새 Hermes 대화에는 새 프로세스가 필요하다. 프로세스가 재시작되면 자동 복원을 약속하지 않으며 조건을 새로 확인한다.

오래된 성공 replay의 meta.revision은 최초 응답 그대로다. MCP는 이미 관측한 더 높은 revision을 낮추지 않고 필요한 경우 GET state로 동기화한다. 재생된 후보가 현재도 선택 가능하다고 설명하지 않는다.
