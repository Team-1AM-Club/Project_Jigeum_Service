# MCP 도구와 사용자 확인 흐름 제안

검토용 제안. [HTTP 계약](http-contract.md)과 [상태 모델](../data-model.md)을 함께 적용한다. 모델은 자연어와 설명을 담당하고, 요청 생성·상태·승인·시간 계산은 코드가 담당한다.

## 1. 도구 5개와 action

| 도구             | 모델 입력                                          | action·처리                                                                                                                        |
| ---------------- | -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| get_capabilities | mode (기본 demo)                                   | 지원 범위 조회. HTTP는 GET capabilities.                                                                                           |
| search_places    | query, limit, mode                                 | 장소 검색. query 정리·URL 인코딩 후 GET places.                                                                                    |
| interpret_trip   | action, text/reference_time/timezone/context, mode | `interpret`(기본): 해석·초안 갱신. `state`: bound 대화 GET. `resume`: 미수신 interpret 요청 복구. state/resume에는 해석 필드 금지. |
| plan_journey     | action, mode                                       | `calculate`(기본): 초안 확인 후 계산. `select`: 현재 후보 중 사용자 직접 선택. `resume`: 이 도구의 보류 HTTP 단계 복구.            |
| replan_journey   | action, reason, mode                               | `calculate`(기본): 현재 초안 조건·기존 선택으로 재탐색. `resume`: 보류 단계 복구. reason은 calculate에서만 필수.                   |

모든 도구는 enum·필수 필드·추가 필드를 엄격히 검증한다. action별 JSON Schema는 분기 조건을 표현한다. conversation_id, revision, confirmation_id, backend key, evidence, selected option은 모델 인자로 받지 않는다. plan/replan의 trip과 previous_plan도 서버 상태로 구성한다. 기존 모델 입력의 `user_confirmed`나 `idempotency_key`로 승인·중복 방지를 대신하는 경로는 제거한다. 이 스키마 전환은 합의 후 MCP 회귀 테스트와 함께 적용한다.

demo가 기본인 기존 이용 방식과 가상 장소·시간표 fixture를 유지한다. HTTP/demo transport를 바꿔도 상태·확인·선택 계약은 같다. demo adapter도 같은 상태 전이 인터페이스를 구현해야 하며 human approval을 생략한 실제 시연 성공으로 표시하지 않는다. 자동 테스트에서는 가짜 elicitation client의 accept/decline/cancel을 명시한다.

## 2. 대화와 mode의 분리

Hermes 대화 하나마다 MCP stdio 프로세스를 새로 시작한다. MCP는 최초 선택한 mode를 해당 프로세스에서 고정한다. 다른 mode 요청은 도구 오류 `MODE_CONFLICT`로 거부하고 새 대화·프로세스를 안내한다. mode 누락은 demo 요청이므로 HTTP 프로세스에서는 매 호출 http를 명시한다.

동일 프로세스의 state-changing action은 직렬화한다. 호스트의 병렬 설정만 신뢰하지 않고 MCP 코드에서도 확인·선택 중 경합을 막는다. 프로세스를 여러 Hermes 대화가 공유하지 않음을 실제 테스트한다. 공유되는 환경에서는 통합 인수에 실패하며, 모델의 session_id 입력으로 대체하지 않는다.

서버가 발급한 현재 conversation_id를 내부 binding으로 저장한다. 서버 상태 전체를 MCP 메모리가 대체하지 않는다. 프로세스 재시작 후 과거 ID를 모델 기억으로 복원하지 않는다. 새 대화는 새 프로세스에서 시작한다.

## 3. 계산 전에 조건 확인

1. bound 대화가 없으면 interpret를 안내한다. state를 GET해 최신 draft와 확인 상태를 받는다. 조회 성공은 TTL을 늘리지 않는다.
2. 유효한 confirmation/confirmed_trip이 있으면 그 값을 사용한다. 확인 상태가 없다면 draft를 확인하고 불완전하거나 만료됐으면 부족 정보만 안내하고 종료한다. 조건 준비 완료만으로 provider를 호출하지 않는다.
3. 이번 trip에 유효한 서버 확인이 이미 있으면 그 조건을 다시 묻지 않는다. 새 조건이면 서버가 반환한 normalized trip으로 날짜·장소·마감·여유·교통수단과 적용 기본값을 표시한다. 모델이 바꾼 요약으로 대체하지 않는다.
4. elicitation form의 boolean `approve`를 사용자에게 받는다. 기본값 true를 두지 않는다. 응답 action=accept **그리고** approve=true인 경우만 다음 단계로 간다. decline/cancel/timeout/미지원은 계산하지 않는다.
5. 그 응답을 받은 MCP 코드가 interaction_id/accepted_at을 생성한다. 표시한 draft_revision/hash와 함께 confirm POST를 보낸다. 승인 대기 중 서버 상태가 바뀌면 409로 종료하고 최신 조건부터 다시 확인한다.
6. confirm 결과의 revision/confirmation_id로 해당 action의 plan 또는 replan POST를 만든다. 확인과 계산의 키는 다르다. 확인 성공 후 계산 실패는 확인 성공 상태를 되돌리지 않는다.

폼 예: message에 전체 조건 요약, requestedSchema에 `{ "type": "object", "properties": { "approve": { "type": "boolean", "title": "표시된 조건으로 계산" } }, "required": ["approve"] }`. 사용자가 조건 수정을 원하면 approve=false 또는 cancel 후 interpret로 돌아간다. 한 폼에서 자유 텍스트 조건을 받아 승인된 초안을 몰래 변경하지 않는다.

evidence는 Hermes 클라이언트의 직접 응답에 대한 기록이다. 악의적인 클라이언트나 loopback에 직접 접속하는 임의 프로그램까지 인증하는 수단은 아니다. 이 로컬 신뢰 경계 밖의 지원은 별도 설계한다.

## 4. 후보 선택과 재탐색

`plan_journey(action=select)`는 GET state에서 현재 후보를 읽는다. candidate_set_id·revision·유효시각을 고정해 보여주고, option_id enum 중 하나를 elicitation으로 직접 선택하게 한다. 추천을 기본 선택으로 자동 전송하지 않는다. accept와 유효 option_id가 함께 와야 select POST를 구성한다. 선택 전 만료·조건 변경·후보 교체는 서버가 거부한다.

재탐색은 `replan_journey(action=calculate, reason=...)`로 시작하며 다음 두 경로를 구별한다.

- **출발점 변경 또는 새 초안이 있는 경우**: 먼저 별도 interpret 호출로 현재 출발점을 반영한다. 새 초안은 이전 확인을 무효화하므로 replan action 안의 elicitation 승인 뒤 **새 confirm POST가 반드시 성공해야** replan POST를 보낸다. 과거 confirmation_id를 재사용하지 않는다.
- **조건이 그대로이고 서버 확인이 아직 유효한 경우**: 불필요한 interpret를 실행하지 않는다. confirmed_trip과 현재 선택을 읽고 이번 재탐색 실행 의사만 elicitation으로 확인한 뒤 replan POST를 보낸다. 이 경우에만 confirm POST를 생략한다.

서버의 이전 선택 trip/요약과 effective trip을 비교하고 목적지·마감 등 유지 조건이 바뀌었다면 새 plan 흐름을 안내한다. elicitation에는 현재 출발점과 유지 조건, 재탐색 의사를 함께 표시한다. 승인 결과로 REST body의 user_confirmed=true를 구성한다. 새 confirm이 필요한 경로에서는 하나의 form 응답을 조건 확인과 이번 재탐색 의사에 함께 결부한다.

새 후보가 오면 기존 선택은 유지한다. 실제 선택은 별도 select action이다. 취소·실패는 기존 기록을 보존하지만 그 경로의 현재 이용 가능성을 보장하지 않는다. 권장 후보 외의 선택에는 권장 후보 전용 comparison을 그대로 붙이지 않는다.

## 5. 키·응답 유실·replay

MCP는 각 논리 HTTP POST 직전에 UUIDv4 키를 만들고 원본 body와 관련 revision을 보관한다. HTTP 재시도는 같은 직렬화 body와 키다. reference_time·request_started_at·accepted_at을 재생성하지 않는다. 인증과 무관한 키이지만 모델에게 생성·관리를 맡기지 않는다.

POST 전송 후 서버 적용 여부를 확정할 수 없고 더 이상의 자동 시도가 허용되지 않으면, 시도 횟수와 관계없이 해당 단계는 `OUTCOME_UNKNOWN`으로 보류한다. JSON/schema/헤더 키/status 조합이 깨졌다면 첫 응답에서도 자동 추가 시도 0회로 즉시 보류한다. 자동 재시도 금지는 미적용의 증거가 아니다. 원래 단계·키·직렬화 body·revision·시각 값과 남은 자동 재시도 예산을 유지한다.

진행 중 요청을 새 키로 반복하지 않는다. `resume`은 명시적 재수신 의사를 직접 elicitation으로 받은 뒤 원래 POST를 1회 전송한다. 자동 재시도 예산을 초기화하지 않으며 다시 깨진 응답이면 보류를 유지한다. GET의 revision 변화만으로 해당 요청의 성공·실패를 확정하지 않는다.

confirm 응답이 유실됐으면 confirm만 복구한 뒤 계산으로 진행할 수 있다. plan/replan/select 응답이 유실됐으면 그 단계만 복구한다. replay에서 최초 응답보다 최신 revision을 알고 있으면 GET state로 확인하며 MCP가 최신 상태를 과거 응답으로 덮어쓰지 않는다. 이미 만료된 후보를 새 결과처럼 안내하지 않는다.

보류 단계가 있는 동안 새로운 상태 변경은 `REQUEST_PENDING`으로 거부하고 GET 조회만 허용한다. 유효하고 요청 대응이 확인된 성공 replay, 미적용이 보장된 최종 오류, 계약상 대화 만료 등 종료 사유를 구별한다. 대화 만료는 과거 미적용의 증거가 아니며 과거 결과를 복원하지 않는다. 프로세스가 종료되면 이 복구 메모리는 사라지므로 자동 복원·exactly-once provider 실행·재시작 후 선택 복원을 약속하지 않는다.

| 관측 결과                               | 자동 재시도·보류 판단                                                                      |
| --------------------------------------- | ------------------------------------------------------------------------------------------ |
| 유효하고 요청에 대응하는 성공           | 성공/replay를 처리하되 관측 최대 revision을 낮추지 않는다.                                 |
| 유효하고 미적용이 보장된 최종 오류      | 허용 오류만 500ms 뒤 최대 1회 자동 재시도한다. 최종 실패가 확인되면 보류를 해제한다.       |
| 전송 후 연결 실패·timeout으로 적용 불명 | 허용된 남은 자동 재시도 뒤에도 불명이면 보류한다.                                          |
| POST 응답의 JSON/schema/key/status 파손 | 자동 재시도 0회, 첫 응답부터 OUTCOME_UNKNOWN. 원인은 UPSTREAM_RESPONSE_INVALID로 구분한다. |
| GET 응답 파손                           | UPSTREAM_RESPONSE_INVALID. 새 변경 보류를 만들지 않으며 기존 보류도 해제하지 않는다.       |

## 6. 응답 전달과 오류

유효한 백엔드 envelope는 structured result로 그대로 전달하고 설명 텍스트는 그 필드에서만 만든다. 업무상 unavailable과 유효 error는 정상 도구 결과로 전달하되 성공 계획으로 표현하지 않는다. MCP 호출 자체의 잘못된 인자·연결 장애·invalid response는 도구 실행 오류로 구분한다. 가능하면 `isError=true`와 안정된 도구 오류 code를 사용한다.

도구 오류: `ELICITATION_UNSUPPORTED`, `USER_CONFIRMATION_REQUIRED`, `USER_CANCELLED`, `CONFIRMATION_TIMEOUT`, `UPSTREAM_RESPONSE_INVALID`, `OUTCOME_UNKNOWN`, `REQUEST_PENDING`, `MODE_CONFLICT`. 서버 오류와 혼동하지 않도록 별도 분류하며 서버의 error.code를 바꾸지 않는다.

**T001 합의 전 미확정 권장안**: MCP 도구 오류의 대표 code는 `OUTCOME_UNKNOWN`, 안전한 진단 필드는 `diagnostics.cause_code="UPSTREAM_RESPONSE_INVALID"`로 둔다. `diagnostics.cause_code`는 이 제안의 표현 후보이며 실제 MCP 저장소의 기존 오류 schema 확인 후 양측이 필드명·위치를 확정한다. 서버 envelope의 `error.code`나 모델 입력 schema에 진단 값을 삽입하지 않는다. 원문 응답은 담지 않는다.

서버가 유효한 envelope로 반환한 `UPSTREAM_RESPONSE_INVALID`는 해당 요청의 미적용이 보장될 때만 확정 실패다. MCP가 깨진 HTTP 응답을 보고 만든 같은 이름의 원인 진단은 적용 불명이다. 이 둘을 같은 실패 처리로 합치지 않는다.

HTTP 연결이라는 이유로 meta.is_demo=false를 설정하지 않는다. 출처·기준시각·데모 표시를 유지하고 실제 실패 시 fixture로 대체하지 않는다. 원문 HTML·스택·비밀키는 결과에 포함하지 않는다. 확인·선택 로그에는 결과 상태와 익명화한 대상 관계만 남기며 원문 대화나 불필요한 주소는 남기지 않는다.

## 7. 시간 예산

| 범위                       | 상한 제안                                                                                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| GET 단계                   | 15초 × 최대 2회 + 500ms = 30.5초                                                                                   |
| POST 단계                  | 30초 × 최대 2회 + 500ms = 60.5초                                                                                   |
| 사용자 elicitation         | 한 action에 최대 1회, 300초. HTTP 연결·DB 트랜잭션을 잡은 채 기다리지 않는다.                                      |
| calculate/replan 최대 순서 | GET 1단계 + elicitation 1회 + confirm POST 최대 1단계 + 계산 POST 1단계 = 최대 451.5초                             |
| select                     | GET 1단계 + elicitation + select POST = 최대 391초                                                                 |
| resume                     | elicitation + 기존 POST 1회 + 필요 시 GET 1단계. confirm 복구 후 남은 계산까지 포함해도 480초 이내에서만 진행한다. |
| MCP 전체 호출              | 480초. 각 단계는 남은 예산 안에서만 시작하며 예산 부족이면 추가 HTTP를 보내지 않는다.                              |
| Hermes host 호출 timeout   | 500초 제안. 실제 설정이 유효한지 설치 환경에서 검증한다.                                                           |

지연을 인위적으로 이 수치만큼 채우지 않는다. 사용자 응답이 빨리 오면 즉시 진행한다. API_SPEC의 POST 30초는 **HTTP 한 시도**이며 사용자 입력 대기까지 포함한 전체 MCP 호출 제한이 아니다. 취소 후 이미 보낸 HTTP가 성공했을 수 있으므로 취소를 rollback으로 표현하지 않는다. 성공 여부가 불명확하면 동일 키 복구 절차를 사용한다.

## 8. 실제 Hermes 인수

공식 문서의 capability 지원과 설치 환경의 지원을 구분한다. 초기 MCP handshake에서 form elicitation 지원을 확인하고 실제 사용자 승인·거절·취소·대기 종료·두 대화 분리를 검사한다. [Hermes 공식 MCP 문서](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp), [MCP 명세](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)

Solar Pro4 모델 식별자는 실행 환경에서 확인한 값을 기록한다. 샘플 이름을 실제 모델 ID로 기입하지 않는다. 개발 도구·작성 도구·시연 모델을 각각 사실대로 구분한다.

T062는 약속 흐름의 실제 accept/decline/cancel/timeout·직접 선택·대화 분리·동일 키 resume을 인수한다. T063은 같은 환경의 실제 약속 데이터를 인수한다. 두 단계는 재탐색·막차 확장 전에 완료하며, 이후 T055/T056에서 확장 인수와 약속 회귀를 수행한다.
