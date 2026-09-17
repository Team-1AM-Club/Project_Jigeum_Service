# 공공 교통 연동 계약 및 기준시각 변경안

작성일: 2026-09-16. **공동 합의와 후속 배치 승인 완료**, 최종 기준은 §9다. API_SPEC.md·예제 JSON에 승인 목표를 반영했고 구현·실제 검증 상태는 별도로 기록한다. 이 문서는 API_SPEC.md를 대체하지 않는다.

## 1. 기존 공개 인터페이스 보존

| 인터페이스 | 연동 후 책임 |
|---|---|
| GET /api/v1/health | 프로세스 연결 확인. 외부 교통 제공처 전체 정상 보장이 아님 |
| GET /api/v1/capabilities | 검증된 지역·수단·날짜 및 기능 상태. 매번 모든 외부 API를 호출하지 않음 |
| GET /api/v1/places | 실제 역/정류소 후보. 이름 충돌 해소·선택 가능한 opaque place_id. 임의 주소를 몰래 역/정류소로 변환하지 않음 |
| POST /api/v1/journeys/plan | 기존 확인·revision·멱등성 검증 후 약속 또는 막차 후보 계산 |
| POST /api/v1/journeys/replan | 확인한 새 출발 기준점으로 현재 시각에 재조회; 사용자 선택 전 기존 선택 보존 |
| POST /api/v1/mobility/interpret | 기존 자연어 조건 해석/확인. 이번 API 연동이 모델/확인 규칙을 대체하지 않음 |

새 사용자용 교통 조회 HTTP endpoint나 MCP 도구를 추가하지 않는다. 개별 6+4 서비스 조회·정규화 검증은 내부 Adapter와 백엔드 운영자 검증 모듈에서 실행한다. 이 모듈은 독립 제품 클라이언트가 아니다.

공개 envelope는 status/data/error/meta, transport_modes는 subway/bus, 연결 구간은 walk/wait, 후보 기본 3개·요청 상한 5개를 유지한다. 실제 조회 실패에 is_demo=true 후보를 반환하지 않는다. 확인·선택·revision·멱등성 계약은 현재 `API_SPEC.md`의 confirm 구현 계약과 §9 승인 기준으로 영향받는 경로만 정합화한다.

## 2. Source.basis_at 변경안

현재 Source는 provider/basis/retrieved_at/service_date만 있어 제공처 기준시각과 조회시각을 구조적으로 구분할 수 없다. 아래 필드를 추가하는 안을 작성한다.

| 필드 | 타입 | 의미 |
|---|---|---|
| basis_at | Asia/Seoul aware datetime 또는 null | 제공처가 데이터의 생성/관측 기준으로 반환한 시각. null은 확인 못함 |

```json
{
  "basis_at": {
    "anyOf": [
      {"type": "string", "format": "date-time"},
      {"type": "null"}
    ],
    "description": "제공처 데이터 기준시각. 조회시각으로 대체하지 않음."
  }
}
```

이 조각은 **제안 Schema**이며 성공 호출 예제가 아니다. 기존 클라이언트와의 전환을 위해 추가 optional 필드로 제안하되, 변경 적용 후 신규 백엔드 응답은 null을 포함해 명시한다. 엄격한 MCP Schema를 포함한 양쪽 호환 검증이 선행한다. field required 여부를 포함한 최종 계약은 공동 합의로 확정한다.

- realtime 근거의 기준시각을 확인하지 못하면 null이고, 이를 검증된 현재 운행 근거로 사용하지 않는다. 일정만으로 유효한 후보는 schedule 근거와 경고로 구분한다.
- null을 retrieved_at/generated_at/server_time으로 채우지 않는다.
- schedule/static의 개정 기준이 날짜뿐이면 임의 00:00 timestamp를 생성하지 않는다. 내부 reference_date/revision 및 사용자 경고에 정확한 원본 기준을 보존한다.
- 과거 fixture는 실제 조회로 인정하지 않는다. Demo 출처가 하나라도 있으면 meta.is_demo=true다.
- refresh_after는 기존 계약의 재확인 권고이며 데이터 최신성/승차 보장이나 자동 조회 지시가 아니다.

실제 적용 순서: 공동 개발자 합의 → API_SPEC.md와 Docs/api/examples.json 동시 갱신 → Source/응답 스키마·fixtures·계약 테스트 → MCP JSON Schema/표시 갱신 → 합성 및 실제 응답 대조. 이번 계획에서는 이 순서를 실행하지 않았다.

## 3. 결과/오류 매핑

| 내부 원인 | 기존 공개 응답 | 자동 재시도 |
|---|---|---|
| 미확정/오래된 장소 ID | 422 error PLACE_NOT_RESOLVABLE | 없음 |
| 서울/제공처 범위 밖 | 200 unavailable OUT_OF_SERVICE_AREA | 없음 |
| 미래 약속 운행/보행 근거 부족 | 200 unavailable APPOINTMENT_TIME_UNSUPPORTED | 없음 |
| 운행일/노선/편/보행/검색 완전성으로 막차 검증 불가 | 200 unavailable LAST_JOURNEY_UNSUPPORTED | 없음 |
| 충분한 지원 자료에서 완전 탐색 후 연결 없음 | 200 unavailable NO_FEASIBLE_JOURNEY | 없음 |
| 마지막 연결 여정은 있으나 5분 정책 여유 확보 불가 | 200 unavailable BUFFER_REQUIREMENT_NOT_MET | 없음 |
| 실제 정상 빈 검색 결과 | 기존 places 정상 빈 목록; 계획은 충분한 지원 범위/완전 탐색 여부로 판정 | 없음 |
| 키/권한 설정 문제 | 503 error PLACE_PROVIDER_UNAVAILABLE 또는 ROUTING_PROVIDER_UNAVAILABLE, 안전한 안내, retryable=false | 없음 |
| 한도 초과 | 429 error RATE_LIMITED, 확인된 Retry-After만 전달 | 없음 |
| 일시 연결/제공처 장애 | 503 error 해당 PROVIDER_UNAVAILABLE | 계약상 허용 원인에만 공통 client가 500ms 후 최대 1회 |
| 외부/전체 deadline 초과 | 504 error UPSTREAM_TIMEOUT | 남은 전체 시간/횟수가 있을 때 외부 timeout에만 최대 1회; workflow retry 없음 |
| 깨진 JSON/XML/업무 응답·의미 검증 실패 | 502 error UPSTREAM_RESPONSE_INVALID | 없음 |

현재 코드에 없는 unavailable 분기 등은 영향받는 기존 공개 계약의 구현 정합화이며 새로운 오류 의미를 임의 도입하지 않는다. upstream HTTP 200의 오류도 업무 코드로 분류한다. 원문 key/URL/오류 메시지/스택은 공개 error에 포함하지 않는다. 예산 중단·자료 부족을 경로 없음으로 변환하지 않는다.

retryable은 기존 계약상 같은 입력으로 나중에 재시도 가능한지를 뜻한다. 명시적 false는 HTTP 상태보다 우선한다. provider retry 소진/예산 소진을 MCP가 동일 workflow의 반복 실행으로 증폭하지 않도록 최종 retryable을 정합화한다. 최종 오류·한도·deadline 매핑은 contract tests로 검증한다.

## 4. 내부 제공처 경계

기존 `ProviderResult`의 성공/실패 의미를 유지한다. 내부 데이터는 [data-model.md](../data-model.md)의 근거 모델로 만들고 공개 결과로 변환하기 전에 스키마/의미를 검증한다. `ok=false`를 성공 빈 목록이나 Mock으로 바꾸지 않는다. `ok=true`여도 요청에 필요한 날짜·좌표·편·연결 근거가 없으면 계산 미지원이다.

PlaceProvider는 역/정류소 ID 대응을 보존한다. RoutingProvider는 검증된 구간·시간·출처만 반환한다. TransitProvider는 관측과 시간표를 구분한다. 기존 인터페이스를 수정해야 한다면 모든 callers/Mock/서비스/tests를 함께 영향 분석하며 역할이 같은 별도 인터페이스를 중복 생성하지 않는다.

서비스별 ID/인증 방식과 host/path는 공식 활용명세에 근거해 확정한다. 최단경로는 사용자 정정으로 OA-22724/getShtrmPath이며 KEY path 인증과 역명·검색일시 입력을 동적 명세에서 확인했다. 허브 100178은 소개이고 15143842로 자동 대체하지 않는다. OA-22724의 XML header/body 구조·시간 단위·운행편/날짜 대응·pagination 완전성을 실제 검증한다. 날짜/역명은 path segment로 정확히 escaping하며 요청 전 검색에서 선택한 역코드/호선과 반환 역을 대조한다. 키 배정 혼동 가능성은 실제 인증 전 미검증 상태다. 추가 후보 15000414는 채택되지 않았다.

## 5. 상태 변경 및 수용 범위

입력·확인·conversation/revision/idempotency 검증 → DB 쓰기 트랜잭션 밖 provider 호출 → 결과 검증 → 짧은 트랜잭션에서 만료/revision/멱등성 재검증 → 기존 상태 적용 순서를 보존한다. 실패·취소·상태 충돌은 이전 선택과 TTL/revision을 변경하지 않는다. 성공 재생은 외부 조회 0회다.

각 API 조회 성공, 실제 약속 성공, 실제 막차 성공은 별도의 증거다. 현재 전부 미실행이며 버스 미래 운행/보행 자료 확보 전에는 관련 SC-007~009를 통과로 표시하지 않는다.

## 6. 데이터 기준 수용과 실제 통합 게이트

SC-002는 모든 기록에서 출처/근거 유형/실제·Demo/기준 확인 여부를 보존하고 계산에 사용한 근거가 유형별 사용 조건을 충족하는지를 검증한다. realtime basis_at=null은 기준 미확인으로 기록할 수 있지만 현재 운행 계산의 근거로 인정하지 않는다. static/schedule 기준일만 제공되면 내부 reference_date/revision/validity/service_date와 정확한 공개 경고를 유지하고 basis_at에 임의 자정 시각을 채우지 않는다. basis_at의 공개 계약 반영은 여전히 공동 합의 대기다.

최초 실제 키 호출 전 공통 전송과 운영자 출력의 합성 sentinel 보호 검증을 통과한다. Source/Buffer 등 공개 출력 경로를 연결하면 해당 경로도 합성 보호 테스트를 통과해야 한다. 공동 개발자는 초기 최소 약속과 최종 인수 시 다른 환경의 Hermes + Solar Pro4에서 도구 발견/호출/응답 수신/표시를 확인하고 Schema 검사와 별도의 실행 증거를 남긴다. 기존 배포 연결 상태도 검증/미검증으로 기록하며 새 배포를 수행하는 계약은 아니다.

## 7. 공동 개발자 전달용 합의 요청

2026-09-16 사용자 확인: **공동 합의 전**. 아래 내용은 검토할 제안이며 승인 기록이 아니다. 이 문서가 합의 내용의 단일 기준이며, 별도 문서에 같은 계약을 복제하지 않는다.

### 변경 목적과 범위

현재 Source의 retrieved_at은 조회시각이다. 제공처 데이터의 생성·관측 시각을 표현하기 위해 basis_at을 추가한다. 기존 API 경로·MCP 도구·응답 envelope·후보 상한·사용자 확인/선택 규칙은 유지한다. 공개 계약 변경 전 양쪽 개발자가 아래 항목을 확정해야 한다.

| 결정 항목 | 검토 제안 | 합의 상태 |
|---|---|---|
| 필드 필수 여부 | 전환 중 수신 스키마는 optional. 변경된 백엔드의 신규 응답은 null을 포함해 항상 출력. 최종 required 전환은 별도 합의 | 대기 |
| null 및 누락 | null은 제공처 기준시각 미확인. 전환 중 누락도 미확인으로 처리하며 조회시각으로 대체하지 않음 | 대기 |
| 시간대·직렬화 | 유효한 값은 Asia/Seoul aware datetime, JSON은 ISO 8601의 +09:00 offset. 날짜만 있으면 timestamp로 만들지 않음 | 대기 |
| 실시간 계산 사용 | 기준시각/예측 의미/사용 제한을 검증한 관측만 사용. null·해석 불가·설명되지 않는 미래 시각·지난 예측·규칙 미확정은 제외 | 대기 |
| 정적·시간표 근거 | 원문 기준일·개정·적용 범위·운행일을 내부 보존하고 정확한 공개 warnings로 전달. basis_at에 임의 자정 금지 | 대기 |
| 이전 응답 수신 | basis_at 없는 기존 fixture/서버 응답을 전환 중 수신 가능하게 하되 기준시각 미확인으로 표시 | 대기 |
| 새 응답 수신 | MCP의 엄격한 JSON Schema가 새 필드를 허용하도록 조정하고 양쪽 계약 테스트에서 null/유효시각을 검증 | 대기 |
| Safety Buffer 표현 | 기존 Buffer 구조 사용. policy_version은 transit-initial-5m-v1 제안. 첫 승차 전 wait에 5분을 여정당 한 번 포함하고 item의 code는 initial_boarding_margin 제안, leg_id는 해당 wait를 참조 | 대기 |
| Buffer 합계·표시 | total_minutes=5, item 합=5, legs/total_duration에 이미 포함. 실제 보행·scheduled wait와 구분하고 표시에서 재차감 금지 | 대기 |

### 양쪽에서 확인할 사례

- 제공처 기준시각이 확인된 실시간 Source와 basis_at=null인 Source를 각각 수신·표시한다. 후자는 현재 운행 계산에 사용하지 않는다.
- 기존 응답에서 basis_at이 누락된 사례를 수신하고 미확인으로 처리한다.
- 정적 기준일만 있는 시간표는 정확한 기준일/적용 경고를 표시하며 임의 timestamp를 생성하지 않는다.
- 19:00 Deadline/도착 여유 10분의 목표 도착은 18:50이다. 첫 승차 전 Buffer 5분은 구간과 총 소요에 한 번만 반영한다.
- 합성 자격증명이 응답·로그·오류·Hermes 표시로 노출되지 않는지 확인한다.

### 합의 기록과 적용 순서

현재 백엔드 담당·MCP 담당의 승인과 합의 시각은 **미확인**이다. 수정 의견이 있으면 이 표의 제안을 갱신하고 최종 항목별 결정, 양쪽 승인, 합의 날짜를 기록한다. 문서를 전달하거나 검토했다는 사실만으로 승인으로 간주하지 않는다.

합의 완료 후 T016을 완료 처리하고 T017의 API_SPEC.md·Docs/api/examples.json 갱신, T018~T019의 양쪽 스키마/계약 검증 및 구현을 진행한다. 합의 전에는 공개 Source·MCP Schema·계산 정책 계약을 변경하지 않는다. T029/T077의 다른 환경 Hermes 실제 검증은 별도 실행 증거가 필요하다.

## 9. 최종 승인 및 통합 소스 수령 — 2026-09-16

사용자는 후보 기본 3개·요청 상한 5개 보존과 flat-plan-proposal.json의 후보별 상세 배치를 승인했다. §7~8의 대기 기록은 이전 검토 이력이며 이 절이 현재 합의 기준이다. basis_at은 전환 입력 optional, 신규 출력은 null 포함 항상 제공한다. 유효한 시각은 ISO 8601 +09:00이며 null/누락을 retrieved_at으로 대체하지 않는다. 정적 기준일에 시각을 만들지 않으며 기준시각 미검증 실시간 자료는 현재 운행 계산에서 제외한다.

data는 flat Plan을 유지한다. sources·buffer·legs·warnings·estimated_arrival_at·hard_leave_at은 data.comparison.options[]에 배치한다. data.recommended_option_id는 상위 요약에 대응하는 후보이며 사용자 선택과 다르다. selected_option_id는 사용자 선택 전 null이다. buffer_applied는 추천 후보의 buffer.total_minutes와 같아야 한다.

transit-initial-5m-v1의 initial_boarding_margin은 첫 승차 전 safety_buffer wait에 여정당 한 번 5분 배정하며 구간 합과 total_duration_minutes에 포함한다. 별도 추가 5분 차감은 제거한다. 이동·대기 40분 + Buffer 5분이면 총 45분, 목표 도착 18:50이면 출발 18:05다.

통합 소스는 Docs/confirm-mcp-integration/confirm-mcp-integration.patch로 수령했다. 전체 git apply --check는 main.py만 충돌했고 해당 파일 제외 검사는 통과했다. 47개 파일을 적용하고 main.py의 HTTP·DB lifespan과 오류 계약을 수동 병합했다. confirm과 기존 last_journey 라우트, HTTP MCP 6개 도구를 보존한다. 003의 다른 제안 계약은 자동 적용하지 않는다.

제공처 retry는 백엔드만 담당한다. MCP는 반환된 429·502·503·504를 재시도하지 않는다. 응답 유실 재시도는 같은 멱등 키·본문·revision을 사용하며 완료 재생뿐 아니라 진행 중 재요청의 외부 조회 0회도 별도 검증한다. 현재 합성 전송의 중복 제거는 단일 RequestBudget 범위이며 HTTP 멱등성의 프로세스/인스턴스 보장 증거를 대신하지 않는다.

현재 검증: 백엔드 287 passed, 13 warnings. verify_backend_stdio.py 종료 0, 6개 도구와 확인·계획·재탐색·막차 흐름 통과. 모두 Mock/합성 기반이며 실제 제공처·Hermes·배포는 미검증이다. 내부 도메인과 Source 클래스/기본 계약 테스트를 추가했다. 공개 후보 상세 변환과 Buffer 기존 계산 변경·양쪽 엄격한 수신/표시·진행 중 HTTP 멱등성의 외부 중복 방지는 후속 작업이다.

## 8. 사용자 전달 공동 합의와 통합본 차이 — 2026-09-16

사용자가 공동 합의 내용을 전달했다. §7의 미합의 기록은 전달 전 시점의 기록이며, 아래 내용이 현재 판단 기준이다. **basis_at의 의미와 Buffer 정책은 합의됐지만 응답 배치·후보 상한·confirm 라우트의 통합본 대응은 추가 확인 중**이다. T016 전체 완료 및 T017의 공개 계약 갱신으로 자동 전환하지 않는다.

| 항목 | 전달된 합의 | 구현 상태 |
|---|---|---|
| basis_at | 전환 수신 optional, 새 백엔드 응답은 null 포함 항상 출력. 누락/null은 미확인, 조회시각 대체 금지 | 공개 응답 배치 확인 대기 |
| 시각 | 유효값은 ISO 8601 +09:00. 날짜만 있으면 임의 시각 금지. 기준 미검증 실시간은 현재 계산 제외 | 내부/공개 후속 검증 필요 |
| Buffer | transit-initial-5m-v1 및 initial_boarding_margin 사용 가능. 총 소요에 포함하면 기존 별도 5분 차감 제거. wait·합계·표시·계산 공동 검증 | 40+5=45분, 목표 18:50→출발 18:05. 계산 구현 전 |
| HTTP MCP·라우트 | confirm_trip을 포함한 6개 도구, confirm 및 기존 막차 전용 라우트 보존 | 이 체크아웃에서 confirm 라우트/HTTP MCP 코드는 발견되지 않음. 통합본 경로·요청/응답 대응 확인 필요 |
| 후보 수 | 현재 기본 3·요청 상한 5. 상한 3은 기존 보존이 아니라 변경 | 기존 상한 5 보존 또는 명시적 3 변경 확인 대기 |
| 응답 | 현재 HTTP data는 flat Plan. Source/Buffer/legs/warnings 전체 JSON 예시 필요 | 아래 합성 예시 제공. 배치 승인 전 공개 schema 변경 금지 |
| 003 | 현재 구현과 003 제안 차이를 구분하고 자동 적용 금지 | 003은 승인된 통합 계약으로 간주하지 않음 |
| 제공처 retry | 백엔드에서 담당. MCP는 반환된 429·502·503·504를 자동 재시도하지 않음 | 기존 계획의 상태 오류 MCP retry 유지 문구는 이 합의로 대체. 오류 코드·뜻을 임의 변경하지 않음 |
| 응답 유실 | MCP–백엔드 응답 유실은 별도이며 같은 멱등 키로 외부 조회 중복 방지 검증 | 성공 재생 및 진행 중 같은 키/본문은 외부 추가 조회 0회. 공유 저장/조정 범위에서 보장 여부 검증 필요 |

### flat Plan 전체 JSON 제안

[flat-plan-proposal.json](flat-plan-proposal.json)은 **합성 계약 검토용 전체 envelope**다. `data.plan` wrapper를 만들지 않고 현재 flat `data`를 유지한다. 실제 장소/좌표/운행편의 증거 또는 실행 완료 예시가 아니다.

| 위치 | 제안·현재 구분 |
|---|---|
| data의 기존 plan_id/conversation_id/장소 ID/시각/total_duration/transport_mode/comparison/buffer_applied/notes/막차 필드 | 기존 flat 필드 보존. total_duration 의미만 합의대로 Buffer 포함 변경 |
| data.recommended_option_id | 추가 제안. 상위 요약이 어느 후보인지 표시하며 사용자 선택과 구분. 승인 대기 |
| data.comparison.options[]의 기존 PlanSummary 필드 | 기존 위치 유지. 후보의 total_duration도 Buffer 포함 |
| data.comparison.options[].sources[].basis_at | 의미 합의된 필드. sources의 위치는 추가 승인 대기 |
| data.comparison.options[].buffer/legs/warnings | 새 후보별 상세 필드 제안. Buffer는 해당 leg_id의 5분 wait를 참조. 위치/구간/경고 schema 승인 대기 |
| data.comparison.options[].estimated_arrival_at/hard_leave_at | 후보별 추가 시각 제안. appointment의 hard_leave_at은 null. 승인 대기 |
| data.comparison.selected_option_id | 사용자 선택 전 null. 추천만으로 사용자 선택으로 표시하지 않음 |

상위 fields는 recommended_option_id 후보의 요약이며, 상세는 comparison.options[] 안에만 배치해 동일 Source/Buffer/legs/warnings의 중복을 피한다. 기존 Leg·RouteLeg와 제안의 상세 Leg 구조가 다르므로 전체 schema 합의 및 양쪽 검증을 먼저 한다. 기존 buffer_applied는 전환 중 buffer.total_minutes와 같은 값을 출력하는 호환용 필드로 제안한다.

후보 상한과 flat 배치 결정이 확정되면 spec·plan·tasks의 기존 '후보 3 유지/기존 계약 유지' 문구, MCP 도구 개수, retry 및 중복 실행 검증 기준도 함께 정합화한다. 현재 문서의 이전 문구를 통합본에 자동 적용하지 않는다.

## 10. Source 전달의 로컬 합성 검증 — 2026-09-16

§9의 승인 중 Source/warnings 전달을 구현했다. 이 절은 추가 공동 승인이나 Hermes 실행 기록이 아니다.

- `PlanSummary.sources/warnings`를 약속·막차와 두 종류 재탐색에 보존한다. 기존 제공처 옵션에 출처가 없으면 빈 목록을 반환하며 출처나 기준시각을 만들지 않는다.
- Source의 미지정 `basis_at`은 출력에서 `null`이다. aware 시각은 +09:00으로 직렬화하고 날짜만 있는 입력·시간대 없는 시각은 거부한다. 신규 Source/경고 모델의 추가 필드는 금지한다.
- 실시간 Source는 provider·basis_at·retrieved_at·service_date가 일치하는 내부 Evidence가 필요하다. 사용 규칙 확인, normalized/planning_verified, 기준시각 존재 및 조회시각 이전 조건을 모두 만족하지 못하면 해당 후보를 제외한다. 남은 후보가 없으면 기존 경로 없음 오류를 반환한다. 실제 operation별 현재성/ETA 규칙(T015/T040)과 요청 범위 CoverageEvidence(T047)의 대체 검증은 아니다.
- 기준시각 없는 시간표에는 `SOURCE_BASIS_UNKNOWN` 경고와 전달된 적용 운행일을 표시한다. 원문 개정일/적용 범위를 임의 생성하지 않으며 실제 제공처의 정적 근거 변환은 후속 작업이다. 제공처 입력 객체를 변경하지 않는다.
- Source 계약 26건, HTTP 확인 후 계획/동일 키 완료 응답 재생의 출처 보존을 검증했다. MCP `test_approved_source_fixture_reaches_mcp_without_loss`는 승인 예시의 null·demo·경고를 포함한 전체 JSON 전달을 확인한다. Plan JSON Schema의 Source 참조·추가 필드 금지·nullable 정의도 검사했다.

**남은 인수**: 실제 공동 MCP 환경의 엄격한 응답 schema 수신·표시, 실제 제공처 변환, 나머지 후보 상세/Buffer 계산 및 사용자 선택 계약. 로컬 adapter 보존 테스트를 Hermes + Solar Pro4 표시 검증으로 보고하지 않는다. T018/T019는 미완료를 유지한다.

## 11. 공유 Schema 수신 검증 승인 및 구현

사용자는 2026-09-16 질의에서 ‘공유 Source Schema와 MCP 수신 검증 구현’을 선택했다. `Docs/api/source-envelope.schema.json`을 추가하고 Source/DataWarning 정의의 백엔드 모델 일치 검사를 연결했다. MCP는 후보별 Source/warnings의 구조·날짜/aware 시각을 검사하고 실패 시 기존 UPSTREAM_RESPONSE_INVALID를 재시도 없이 반환한다. 원문이나 schema 예외는 공개하지 않는다. 전환 입력의 필드 누락/null 허용과 정상 응답 보존은 유지한다. API_SPEC.md와 Docs/api/examples.json에 같은 수신 계약을 기록했다.

정적 Source와 일치하는 Evidence의 기준일·개정·적용 범위는 SOURCE_REFERENCE 경고로 전달한다. 입력에 없는 정보나 기준시각을 만들지 않는다. 상세 정의와 실제 Hermes 연결 결과는 [MCP 수신·배포 검증](../mcp-source-deployment-verification.md)을 따른다.

현재 Hermes에서는 capabilities·장소 검색의 실제 호출을 확인했으며 응답은 demo다. 실제 Source 후보를 표시한 검증은 아직 없으므로 §10의 관련 인수 게이트를 완료 처리하지 않는다. SDK outputSchema는 기존 일반 object이며 공유 상세 Schema 검사는 HTTP 수신 경계에서 실행된다.
## 팀원 회신에 따른 공동 인수 현황

2026-09-16 team-handoff-reply.md 수령: 현재 MCP의 반환 타입은 일반 dict이며 Source 전용 엄격한 응답 모델은 없다. 기본 envelope 검사 후 내용을 그대로 반환하고 basis_at을 생성·대체하지 않는다는 코드 확인을 받았다. 승인 예시와 최신 Source 변경은 아직 수령하지 않아 누락/null/+09:00 및 후보별 출처/경고의 공동 adapter·stdio·Hermes 표시 검증은 미실행이다. 엄격한 모델을 새로 도입하거나 SDK의 일반 객체 Schema를 Source 인수 통과로 간주하지 않는다. T018/T019의 공동 인수는 미완료다.

후속 변경은 Docs/transit-source-integration의 통합본 이후 delta patch·manifest·승인 예시로 전달하며 팀원이 MCP 수신·보존 및 실제 표시 결과를 회신한다. 백엔드는 provider·정규화·Source/계산과 진행 중 동일 요청의 외부 조회/상태 검증을 맡고, MCP는 응답 유실·같은 key/body/revision 재전송과 사용자 안내를 맡는다. worker/인스턴스 수는 미정이며 완료 응답 재생만으로 진행 중 중복 조회 0회를 보장하지 않는다. 새 공개 오류/도구는 도입하지 않는다.

사용자 제공 API 주소에서 Hermes/Solar Pro4의 실제 get_capabilities 호출과 Demo 표시를 확인했다. 이는 Source 후보·실제 계획 검증이 아니며 세부 실행 증거는 live-verification.md를 따른다. 공개 후보 수 승인(기본 3/상한 5)을 변경하지 않는다.
