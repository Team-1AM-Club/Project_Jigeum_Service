# Tasks: 서울 지하철·버스 공공데이터 API 연동

**입력 문서**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [연동 계약 변경안](contracts/transit-integration.md), [quickstart.md](quickstart.md)
**활성 기능**: `004-public-transit-api-integration`
**작성일**: 2026-09-16
**브랜치**: `feature/mcp-server-integrate` 유지
**상태**: 작업 목록 작성. 아래 작업은 모두 미실행이며 실제 인증·구현·테스트 성공을 뜻하지 않는다.

## 형식과 실행 규칙

`- [ ] T번호 [P 선택] [US번호] 설명과 파일 경로` 형식을 사용한다. User Story 번호는 spec.md와 동일하며, Phase는 P1인 US1 → US2 → US4, P2인 US3 → US5 순서다. 파일 경로는 저장소 루트 기준이다. 새 파일은 예정 위치이며, 구현 전에 동일 역할의 기존 구현을 확인하고 재사용한다.

- `[P]`는 명시한 선행 작업을 마친 뒤 서로 다른 파일에서 병행 가능한 작업이다. 스토리 전체가 독립적으로 병행 가능하다는 뜻은 아니다. 표시가 없는 작업과 공통 파일 변경은 순차 실행한다.
- 구현 담당 범위는 내부 FastAPI·교통 Adapter·계산·검증이다. MCP 측 계약 검증은 공동 개발자에게 전달하고 합의 결과를 기록한다. 새 MCP 도구·제품 CLI·사용자 화면은 만들지 않는다.
- 기본 6개와 추가 4개를 유지한다. 최단경로는 OA-22724/getShtrmPath이며 100178은 소개 페이지다. 15143842·15000414·보완 자료 후보를 자동 채택하지 않는다.
- API키는 백엔드 실행 프로그램만 필요한 순간 로드한다. 모델·채팅·문서·로그에 값, 부분 문자열, 길이, 해시, 전체 URL/params, 원문 예외를 출력하지 않는다. 기존 `backend/.env.transit.local`을 재생성하거나 키를 자동 교환하지 않는다.
- 실제 호출은 `--live`로 명시한 운영자 검증에서만 실행한다. 기본 테스트는 합성 응답이며 키 누락·거부·한도 초과는 실제 키 수정이나 한도 소진 없이 재현한다.
- 명세 FR-015 및 SC-003/004/007~010의 검증 요구에 따라 테스트 작업을 포함한다. 테스트를 먼저 작성하고 관련 실패를 확인한 뒤 구현한다. 현재 테스트는 실행하지 않았다.
- 공개 계약 변경은 공동 개발자 합의 → API_SPEC.md·예제 JSON → 양쪽 스키마/계약 검증 순서다. 합의 전 basis_at을 공개 응답에 추가하지 않는다.
- 사용자 허가 없이 commit하지 않는다. 자동 배포·브랜치 전환·기존 dirty 변경 되돌리기·새 패키지/인프라 추가도 이 목록에 포함하지 않는다.

## Phase 1: 준비

**목적**: 현재 코드와 공동 작업 경계를 확인하고 기존 키 파일을 안전하게 연결할 준비를 한다.

- [ ] T001 IDEA.md → API_SPEC.md → agent_specs/departure-planner-agent.md·agent_specs/recovery-agent.md → 004 문서 순서로 대조하고, 기존 dirty 변경·003 계약 정합화와 중복되는 확인/선택/revision/멱등성·Provider callers 및 재사용 위치를 specs/004-public-transit-api-integration/implementation-audit.md에 기록한다. 기존 변경을 덮어쓰지 않는다.
- [ ] T002 backend/tests/unit/test_transit_settings.py에 합성 키로 SecretStr 비표시, 서버 환경변수 우선, 로컬 파일 명시 로드, 개별 키 누락의 안전한 처리를 검증한다. 실제 키 파일은 테스트 입력으로 사용하지 않는다.
- [ ] T003 T002 후 backend/app/config.py의 기존 Settings에 credentials.md의 10개 서비스별 SecretStr 필드와 backend/.env.transit.local 명시 로드를 연결한다. 기존 .env 설정과 서버 환경변수 우선순위를 보존하고 키 누락으로 관련 없는 기능까지 중단하지 않는다.
- [ ] T004 specs/004-public-transit-api-integration/live-verification.md에 서비스/operation별 입력·실행 시각·출처·안전한 관측 필드·실제/합성·성공/실패·지원 범위·단위·한도·제약 기록 양식을 만든다. 기존 키 입력 완료 진술과 실제 인증 성공을 별도 상태로 남긴다.

**Checkpoint**: 설정 테스트와 기록 양식이 준비됐다. 키의 서비스 배정·권한은 아직 미검증이다.

## Phase 2: 공통 기반과 계약 선행조건

**목적**: 실제 키를 전송하기 전에 로그·HTTP·예산·내부 근거 모델을 보호한다. 공개 응답에 영향을 주는 스토리 연결은 계약 합의까지 완료해야 한다.

- [ ] T005 공식 활용가이드와 무키 연결 점검으로 10개 서비스의 host/path/port/scheme·method·인증 위치·허용 응답 형식·계정 한도 확인 방법을 specs/004-public-transit-api-integration/credentials.md에 확정한다. HTTP 예시를 HTTPS 주소로 추정하지 않고 미확정 전송 방식에는 키를 보내지 않는다. 평문 전송만 가능하면 위험과 필요한 사용자 결정을 기록하고 인증 호출을 보류한다.
- [ ] T006 backend/tests/unit/test_provider_client.py에 HTTP 200 업무 오류, 명시적 retryable=false 우선, 허용 오류 500ms 후 최대 1회/금지 오류 0회, 시도·전체 deadline, pagination 포함 시도 예산, 동시성·취소·redirect 차단·응답 크기 제한을 합성 전송으로 검증한다.
- [ ] T007 T006 후 backend/app/services/provider_client.py의 전체 URL·params·응답 원문·예외 로그를 service alias/operation/시도/안전한 상태로 교체하고, 상위 예외/HTTP debug 로그에도 비밀 값이 흘러가지 않도록 처리한다. 키가 포함된 다른 host redirect는 허용하지 않는다.
- [ ] T008 T007 후 backend/app/services/provider_client.py의 미구현 HTTP 전송을 httpx.AsyncClient로 연결하고 backend/app/main.py의 기존 lifespan에서 생성/종료를 관리한다. 서비스별 JSON/XML 업무 오류를 해석할 수 있도록 기존 호출 경계를 최소 수정한다. XML은 DTD/외부 entity를 처리하지 않고 크기/구조를 제한하며, 기존 의존성으로 불가능하면 추가 의존성을 먼저 제안한다.
- [ ] T009 T008 후 backend/app/services/provider_client.py에 요청별 공유 deadline·시도 수·semaphore·동일 요청 중복 조회 제거를 구현한다. health/capabilities 3초·외부 0회, places 10초·4회·동시 2, plan/replan 25초·12회·동시 4, 운영자 단일 검증 60.5초·2회·동시 1을 적용한다. 각 시도는 min(30초, 남은 전체 시간)이며 대기·retry·page도 예산에 포함한다. 공통 client만 retry하고 다른 요청에 실시간 값을 재사용하지 않는다.
- [ ] T010 backend/tests/unit/test_transit_domain.py에 ID namespace/선행 0·순환 노선 occurrence·좌표계·단위·aware 시각·기준/조회시각·정상 빈 결과/실패 구분을 검증한다. 누락 좌표 0 채움, 이름만의 매핑, 조회시각의 basis_at 대체를 거부한다.
- [ ] T011 T010 후 backend/app/domain/transit.py에 Evidence·TransitPlace/ProviderIdentifier·RoutePattern/StopOccurrence·ScheduledCall/TransitObservation·TransferLink·JourneyCandidate·CoverageEvidence의 필요한 필드와 검증을 구현하고 backend/app/services/provider_interfaces.py의 기존 ProviderResult 경계에 연결한다. 새 DB/중복 인터페이스를 만들지 않고 모든 callers·Mock을 영향 분석한다.
- [ ] T012 T005 및 T007~T011 후 backend/app/integrations/verify_transit.py에 10개 service alias의 명시적 --live 최소 probe를 구현한다. 키는 로컬 설정에서 로드하고 alias별 확정 endpoint만 호출한다. 승인된 관측 필드·응답 구조/업무 상태·단위 확인 결과만 출력하며 URL/원문 body를 저장하지 않는다. OA-101/OA-110/OA-22724 인증 실패 시 자동 키 교환/조합 없이 중단하고 사용자에게 서비스 배정 확인을 요청한다.
- [ ] T013 Source.basis_at 필드의 optional/required·null·시간대·호환 방식과 transit-initial-5m-v1 정책 표현에 대한 공동 개발자 합의를 specs/004-public-transit-api-integration/contracts/transit-integration.md에 기록한다. 합의가 없으면 대기 상태를 유지하고 공개 계약 변경을 진행하지 않는다.
- [ ] T014 T013 합의 후 API_SPEC.md와 Docs/api/examples.json을 함께 갱신해 basis_at과 기준시각 미확인·정적 기준일의 정확한 의미를 확정한다. 기존 envelope·도구/경로·후보 3개·subway/bus·확인/선택 의미를 보존한다.
- [ ] T015 T014 후 backend/tests/contract/test_transit_source_contract.py에 basis_at=datetime/null·제공처/조회시각 분리·정적 날짜의 임의 자정 변환 금지·Demo 표시·기존 응답 호환 사례를 추가한다. MCP 개발자의 엄격한 JSON Schema/표시 검증 결과는 specs/004-public-transit-api-integration/contracts/transit-integration.md에 기록하고 양쪽 불일치가 있으면 반영을 중단한다.
- [ ] T016 T015 후 backend/app/schemas/journeys.py·backend/app/schemas/common.py의 실제 Source 정의 위치와 모든 응답 변환/fixture를 합의 계약에 맞춘다. 기준시각 미확인 실시간 관측을 현재 운행 근거에서 제외하고 정적 기준일/개정 정보는 정확한 경고로 전달한다.

**Checkpoint**: T005~T012가 끝나면 안전한 내부 probe가 가능하다. 공개 스토리 인수는 T013~T016 공동 계약 게이트까지 통과해야 한다. 실제 응답·단위가 아직 확인되지 않았다면 parser를 확정하지 않는다.

## Phase 3: US1 — 실제 교통 데이터 조회 (P1, 최초 검증 범위)

**목표**: 기본 6개와 추가 4개의 합의 operation을 조회·정규화하고 실제 제공처 응답의 의미와 대조한다.

**독립 검증**: 아래 operation별 실제 성공 최소 1건, 기본 6개 각각 정규화 대조, ID·단위·시각·출처·실제 표시 일치. 빈 결과는 가상 교통편 없이 빈 결과로 유지한다. 날짜·단위가 미확정인 필드는 계산 근거로 인정하지 않는다.

### 테스트

- [ ] T017 [P] [US1] backend/tests/unit/test_seoul_subway.py에 OA-15442/12764/12601/101/110/22724의 합성 성공·빈 결과·업무 오류·깨진 응답 및 실제 포맷과 다른 구조 거부를 검증한다. STATION_CD/FR_CODE/TOPIS ID, 방향 코드, recptnDt 지연, 시간표/예측/위치 구분과 OA-22724 header/body·path escaping·응답 역 대조를 포함한다.
- [ ] T018 [P] [US1] backend/tests/unit/test_seoul_bus.py에 15000303/15000193/15000332/15000314의 합성 응답을 검증한다. stId/arsId/busRouteId·seq/section/ordinal·동일 정류소 재방문·GRS80/WGS84·dataTm/mkTm·ETA와 위치·금일 첫/막차를 구분하고 Decoding 키가 query serializer에서 한 번만 encoding되는지 합성 키로 확인한다.

### 구현과 실제 대조

- [ ] T019 [US1] T017 후 backend/app/integrations/seoul_subway.py에 OA-15442 SearchSTNBySubwayLineInfo 역 검색/코드 조회를 구현한다. STATION_CD/FR_CODE/호선과 1~8호선·9호선 2~3단계 범위를 보존하고 TOPIS ID/좌표는 검증 없이 연결하지 않는다.
- [ ] T020 [US1] T019 후 backend/app/integrations/seoul_subway.py에 realtimeStationArrival 및 realtimePosition 조회를 구현한다. 열차·역·호선·방향·생성시각·원본 ETA/상태를 보존하며 위치에서 ETA를 생성하거나 지난 예측을 도착으로 clamp하지 않는다.
- [ ] T021 [US1] T020 후 backend/app/integrations/seoul_subway.py에 OA-101 SearchSTNTimeTableByIDService와 OA-110 SearchSTNTimeTableByFRCodeService를 별도 입력 코드로 구현한다. WEEK_TAG/INOUT_TAG·ARRIVETIME/LEFTTIME·기종점·급행/분기·FL_FLAG·운행일과 실제 날짜를 보존하고 미검증 코드/시각은 사용하지 않는다.
- [ ] T022 [US1] T021 후 backend/app/integrations/seoul_subway.py에 OA-22724/getShtrmPath를 구현한다. 출발/도착역명·검색일시 path segment를 escaping하고 시간표 포함 Y 및 검증된 옵션만 사용한다. header/resultCode/body·열차 시각/방향/종착지·reqHr/wtngHr/totalReqHr·거리 단위·페이지 경로 완전성을 검증하며 선택한 역코드/호선과 반환 역을 대조한다.
- [ ] T023 [US1] T018 후 backend/app/integrations/seoul_bus.py에 getStationByName·getRouteByStation·getBustimeByStation 및 getBusRouteList·getStaionByRoute를 구현한다. 공식 operation 철자, 정류소/노선 ID·방향·기종점·occurrence·검증된 좌표를 유지한다. 금일 첫/막차를 미래 시간표로 확장하지 않는다.
- [ ] T024 [US1] T023 후 backend/app/integrations/seoul_bus.py에 getBusPosByRouteSt와 getArrInfoByRouteAll을 구현한다. 차량/구간 위치와 ETA·mkTm·isLast를 구분하고 출발/도착 정류소의 동일 운행편 대응을 검증 전 계산에 사용하지 않는다.
- [ ] T025 [US1] T019~T024 후 backend/app/domain/transit.py에 서비스 간 역·정류소·노선·방향·occurrence 대응 검증을 연결한다. 장소 응답의 필수 좌표를 충족하는 공식 보완 자료와 코드 교차표도 조사·확보해 specs/004-public-transit-api-integration/data-model.md에 근거를 기록한다. 추가 키/서비스 채택이 필요하면 사용자와 먼저 합의한다. 동일 이름/차량 번호만의 결합을 거부하고 page 누락·미확인 좌표/단위·기준시각·시간표 적용일을 미검증 상태로 유지한다. 좌표가 확보되지 않으면 관련 장소 응답 인수를 보류하며 US4까지 기다려 값을 추정하지 않는다.
- [ ] T026 [US1] T012 및 T019~T025 후 backend/app/integrations/verify_transit.py로 10개 서비스의 아래 최소 operation을 실제 호출하고 specs/004-public-transit-api-integration/live-verification.md에 안전한 관측과 성공/실패를 기록한다. OA-101/OA-110/OA-22724 배정 혼동은 개별 지정 키로만 확인하며 실패한 기능을 완료 처리하지 않는다.
- [ ] T027 [US1] T026 관측 후 backend/app/integrations/seoul_subway.py·backend/app/integrations/seoul_bus.py와 backend/tests/unit/test_seoul_subway.py·backend/tests/unit/test_seoul_bus.py의 parser/합성 fixture를 실제 구조·단위·시각·pagination 결과에 맞춰 확정한다. 관측된 업무 코드·sentinel·자정 표현과 문서 차이를 기록하고 확인하지 못한 의미는 보류한다.
- [ ] T028 [US1] T027 후 backend/app/services/transit_providers.py에서 기존 PlaceProvider/RoutingProvider/TransitProvider를 구현·조립한다. Adapter 정규화/근거/실패를 보존하고 지원 자료가 부족한 Routing 결과를 성공 빈 후보나 Mock으로 바꾸지 않는다.
- [ ] T029 [US1] T028 후 backend/tests/contract/test_transit_places.py에 실제 Provider를 합성 주입한 장소 검색·동명 역/정류소 구분·opaque place_id 재확인·정상 빈 목록·주소/건물의 역/정류소 선택 필요·좌표 미검증 거부를 검증한다.
- [ ] T030 [US1] T029 후 backend/app/api/places.py와 backend/app/schemas/places.py에 실제 PlaceProvider를 연결한다. 선택 가능한 역/정류소와 검증된 좌표만 기존 계약으로 반환하고 공개 교통 조회 endpoint를 추가하지 않는다.

### 실제 검증 대상 operation

| 서비스 alias | 최초 operation/입력 |
|---|---|
| subway-stations | SearchSTNBySubwayLineInfo: 역명/역코드/호선 |
| subway-arrivals | realtimeStationArrival: 검증한 공식 역명 |
| subway-positions | realtimePosition: 공식 호선명 |
| subway-timetable | SearchSTNTimeTableByIDService: STATION_CD/day/direction tag |
| subway-last-train | SearchSTNTimeTableByFRCodeService: FR_CODE/day/direction tag |
| subway-path | getShtrmPath: 선택한 출발·도착역과 검색일시, 시간표 포함 Y |
| bus-stations | getStationByName → getRouteByStation 및 getBustimeByStation: 확인한 arsId/busRouteId |
| bus-routes | getBusRouteList → getStaionByRoute: 확인한 busRouteId |
| bus-positions | getBusPosByRouteSt: 확인한 노선/구간 ordinal |
| bus-arrivals | getArrInfoByRouteAll: 확인한 busRouteId |

한 행에 여러 operation이 있으면 모두 실제 대조한다. 실제 계정 한도가 우선하며 전체 수집이나 한도 회피는 하지 않는다. 서울역 등 quickstart의 입력은 후보일 뿐, 지원되는 것으로 미리 판정하지 않는다.

**Checkpoint**: 조회 성공과 계획 성공은 별도다. US1만으로 미래 약속·막차·혼합 환승 지원을 표시하지 않는다.

## Phase 4: US2 — 실패와 미지원 구분 (P1)

**목표**: 제공처 실패·데이터 부족·지원 범위 밖 요청을 정확히 종료하고 Mock 성공을 방지한다.

**독립 검증**: 인증, 한도, 지연, 잘못된 응답, 정상 빈 결과, 미지원의 6분류에서 잘못된 성공 0건. 허용 retry 1회/500ms, 금지 retry 0회이며 로그/응답 secret sentinel 노출 0건이다.

- [ ] T031 [P] [US2] backend/tests/contract/test_transit_failures.py에 6분류와 HTTP 200 업무 오류의 공개 status/error/unavailable 매핑을 검증한다. NO_FEASIBLE_JOURNEY는 충분한 지원 자료로 완전 탐색한 경우에만 허용하고 인증 retryable=false·한도 Retry-After 의미를 확인한다.
- [ ] T032 [P] [US2] backend/tests/unit/test_transit_secret_redaction.py에 path/query 키·encoding된 합성 키·제공처 오류·httpx 예외·debug 로그·운영자 출력·공개 응답의 secret sentinel 유출 0건을 검증한다. 실제 키 값·길이·해시는 확인하지 않는다.
- [ ] T033 [US2] T031~T032 후 backend/app/services/provider_client.py·backend/app/schemas/errors.py·backend/app/api/responses.py에서 내부 원인을 기존 공개 오류로 매핑한다. 인증/권한은 해당 PROVIDER_UNAVAILABLE nonretryable, 한도는 RATE_LIMITED, timeout은 UPSTREAM_TIMEOUT, 의미/구조 오류는 UPSTREAM_RESPONSE_INVALID로 전달하고 업무 원문은 노출하지 않는다.
- [ ] T034 [US2] T033 후 backend/app/services/plan_service.py·backend/app/services/last_journey_service.py·backend/app/services/replan_service.py의 실제 모드 Mock fallback을 제거한다. 명시적 Demo 선택은 보존하며 실패·부분 결과·정상 빈 결과를 구분하고 기존 선택/TTL/revision을 변경하지 않는다.
- [ ] T035 [US2] T034 후 backend/app/services/transit_providers.py와 backend/app/domain/transit.py에 지역/노선/방향/운행일·기능별 CoverageEvidence 게이트를 적용한다. 키 존재·health 정상·실시간 도착/막차 flag만으로 미래/전체 경로를 지원하지 않으며, 기준시각 미확인·오래된 예측·page 누락도 성공 근거에서 제외한다.
- [ ] T036 [US2] T035 후 backend/tests/integration/test_transit_retry_budget.py에 전체 deadline/시도 수/동시성·취소·page·중복 조회와 provider retry 소진 뒤 workflow 반복 금지를 검증한다. 성공 멱등성 재생 외부 0회, 진행 중 동일 키/본문 조정, 네트워크 응답 유실로 두 실행이 시작될 때 places 최대 8/plan 최대 24의 구분을 확인한다. MCP 기존 최대 1회 정책과의 양쪽 대조 결과는 specs/004-public-transit-api-integration/contracts/transit-integration.md에 기록한다.
- [ ] T037 [US2] T036 후 backend/tests/integration/test_transit_unavailable.py에 범위 밖·시각/단위/좌표/편/보행 근거 부족·탐색 예산 중단을 재현한다. 외부 호출 중 만료/revision 충돌·취소·실패에서 기존 선택·TTL·revision이 유지되고 경로 없음/Mock 성공으로 바뀌지 않는지 확인한다.

**Checkpoint**: US1의 실제 조회와 US2의 실패 처리가 함께 검증되어야 단계 1을 인수할 수 있다.

## Phase 5: US4 — 실제 약속 출발 계획 (P1)

**목표**: 확인된 사용자 조건을 실제 운행·보행 근거와 연결해 후보 1~3개를 계산한다.

**독립 검증**: 지하철, 버스, 지하철→버스, 버스→지하철 각각 실제 약속 최소 1건. Deadline 19:00/도착 여유 10분의 목표는 18:50이고, 첫 승차 전 5분 Buffer는 여정당 한 번이다. 모든 구간·승하차·보행·대기 근거를 대조하고 자료 부족은 성공으로 반환하지 않는다.

- [ ] T038 [P] [US4] specs/004-public-transit-api-integration/research.md에서 버스 운행일별 trips/stop_times·방향/종착지·정류소 occurrence·구간 시각/각 편 대응·현재성·적용 기간을 충족하는 공식 보완 자료를 추가 조사하고 후보별 충족/결손을 기록한다. 선정안과 필요 권한/비용을 구체화하고 새 API키·유료 제공처·인프라는 사용자 합의 전 채택하지 않는다. 자료가 확보되지 않으면 이 작업을 완료 표시하지 않는다.
- [ ] T039 [P] [US4] specs/004-public-transit-api-integration/data-model.md에 검증된 역 좌표/코드 교차표, 공휴일/특별 운행을 포함한 ServiceCalendar, 동일 수단 및 양방향 혼합 TransferLink의 실제 경로/최소시간/제약/적용 기준을 확정한다. 과거 집계·직선거리/임의 속도를 대체 근거로 삼지 않고 필요한 추가 제공처는 사용자에게 질의한다. 충분한 근거가 없으면 완료 표시하지 않는다.
- [ ] T040 [US4] T038~T039 자료 확보 및 필요한 채택 합의 후 backend/app/domain/transit.py·backend/app/services/transit_providers.py에 승인된 보완 자료의 최소 읽기/검증을 연결한다. 공식 ID↔편/운행일/좌표/보행 대응과 유효 기간을 확인하고 새 DB·주기 전체 수집을 추가하지 않는다. 후보 서비스가 실제 API 추가라면 구현 전 plan.md·credentials.md·계약 변경안을 먼저 합의 갱신한다.
- [ ] T041 [US4] T040 후 backend/tests/unit/test_transit_appointment.py에 목표 도착, 구간 합/권장 출발→도착 차이, 첫 승차 전 5분 한 번, 실제 보행/대기 분리, 동일 편/방향/운행일·종착지, 불가능한 혼합 연결 거부를 검증한다. 반올림 전 datetime으로 승차 가능성을 판정한다.
- [ ] T042 [US4] T041 후 backend/app/services/transit_providers.py에서 검증된 scheduled/현재 관측의 동일 운행편 대응과 TransferLink로 약속 경로를 조립한다. 범위 내 모든 구간의 시간 흐름·승하차·대기·방향·목적지 도달을 확인하고 현재 ETA를 임의 미래 시간표로 사용하지 않는다.
- [ ] T043 [US4] T042 후 backend/app/services/time_calculation.py·backend/app/services/calculation_service.py·backend/app/schemas/buffer.py의 영향받는 callers를 함께 맞춘다. target_arrival_at=arrival_deadline-arrival_preference_minutes, transit-initial-5m-v1의 첫 승차 전 wait/item 5분 한 번, 구간 합과 total_duration 일치 및 표시 단계 재차감 금지를 구현한다.
- [ ] T044 [US4] T043 후 backend/app/services/plan_service.py에 실제 검증된 후보를 연결해 기존 계약의 1~3개 후보·출처·basis_at·운행일·경고·예상 도착/권장 출발을 생성한다. 자료 부족/불완전 탐색은 APPOINTMENT_TIME_UNSUPPORTED 등 기존 사유로 구분하고 서울 전체 지원으로 확대하지 않는다.
- [ ] T045 [US4] T044 후 backend/app/api/journeys.py에서 Mock 직접 생성을 실제 Provider 주입으로 교체한다. 조건/장소 확인·conversation/revision/idempotency를 외부 호출 전에 검증하고 DB 쓰기 트랜잭션 밖 조회 뒤 적용 직전 만료/revision/멱등성을 재검증한다. 기존 003의 영향받는 계약만 정합화한다.
- [ ] T046 [US4] T045 후 backend/app/services/replan_service.py와 backend/app/api/journeys.py에 확인된 현재 역/정류소 기준 재조회·기존 목적지/Deadline 보존을 연결한다. 새 후보는 선택 전 기존 선택에 적용하지 않고 실패/취소/충돌은 이전 계획·TTL/revision을 보존한다.
- [ ] T047 [US4] T046 후 backend/tests/contract/test_journeys_plan.py·backend/tests/contract/test_journeys_replan.py·backend/tests/integration/test_transit_appointment_e2e.py에서 합성 실제 Provider로 확인→계산→선택 및 재탐색을 검증한다. 미확인 요청은 외부 0회, 후보 최대 3·Source/Leg/Buffer 계약, 동일 성공 재생 0회, 충돌/만료·주소 입력·자료 부족·기존 선택 보호를 확인한다.
- [ ] T048 [US4] T047, T049 및 T026~T027의 실제 조회 게이트 후 지하철/버스/두 방향 혼합 약속 각각 최소 1건을 backend/app/integrations/verify_transit.py의 안전한 검증 흐름으로 재현하고 specs/004-public-transit-api-integration/live-verification.md에 사용자 확인·각 구간 운행/보행·시간·출처와 계산 대조를 기록한다. 근거가 부족한 유형은 미완료로 남긴다.

**Checkpoint**: T038~T040은 현재 미충족 외부 자료 게이트다. 공개 자료 조사 결과만으로 완료할 수 없으며, 지하철만 성공해도 US4 전체를 완료로 축소하지 않는다.

## Phase 6: US3 — 연결 범위와 검증 증거 (P2)

**목표**: 운영자·공동 개발자가 실제/합성 검증과 조회/계획 지원 수준을 재현 가능한 기록으로 구분한다.

**독립 검증**: 모든 합의 서비스/operation에 조건·시각·관측·제약·성공/실패/미검증 기록이 있고, health 정상이나 키 보유가 계획 지원으로 해석되지 않는다.

- [ ] T049 [P] [US3] T026~T027 후 backend/app/integrations/verify_transit.py의 최소 probe를 정규화 대조·명시적 실패·기존 서비스 주입을 통한 계획 검증 실행으로 확장하고 backend/tests/unit/test_verify_transit.py에 --live opt-in·안전한 입력/출력·종료 상태를 검증한다. 계획 계산 로직을 검증 모듈에 중복 구현하지 않으며, 합성 서비스 주입으로 모듈을 먼저 검증하고 실제 계획 호출은 US4/US5 구현 후 실행한다. 과거 fixture와 명시적 Demo를 실제 호출 성공으로 분류하지 않고 단일 검증 60.5초를 넘는 묶음 실행은 단계별로 결과를 보고한다.
- [ ] T050 [P] [US3] T035 후 backend/tests/contract/test_transit_capabilities.py에 documented/configured/real_call_verified/normalized/planning_verified의 공개 지원 매핑, 부분 지원·현재 제공처 장애·is_demo·지역/수단·후보 상한을 검증한다. health/capabilities 요청마다 외부 호출이 없음을 확인한다.
- [ ] T051 [US3] T050 후 backend/app/api/capabilities.py·backend/app/api/health.py에서 검증 상태를 기존 계약의 capabilities/limitations에 연결한다. subway/bus·후보 최대 3과 요청 범위별 지원을 반영하고 이전 성공 기록과 현재 상태를 구분한다. 전체 제공처 건강을 프로세스 health로 보장하지 않는다.
- [ ] T052 [US3] T049~T051 후 specs/004-public-transit-api-integration/live-verification.md의 모든 서비스/operation 기록을 실제 관측·정규화·공개 지원 표시와 대조한다. 조회 성공/약속 성공/막차 성공을 분리하고 실패·미검증·자료 결손·실제 계정 한도를 빠짐없이 기록한다.
- [ ] T053 [US3] T052 후 specs/004-public-transit-api-integration/quickstart.md·credentials.md에 구현된 명령/설정·실제 검증 재현 조건·안전한 실패 확인·미지원 범위를 맞춘다. 운영자가 키를 채팅/명령 인자로 전달하지 않고 같은 절차를 실행할 수 있게 한다.

**Checkpoint**: US3 기록 작업은 필요한 선행 작업 이후 US4보다 먼저 실행할 수 있다. US4/US5의 실제 수용 증거는 해당 스토리에서 추가하며, 아직 미실행인 단계는 그 상태를 유지한다.

## Phase 7: US5 — 마지막 연결 여정과 막차 계획 (P2)

**목표**: 요청 운행일에 목적지까지 연결되는 마지막 여정의 hard_leave_at와 recommended_leave_at를 구분한다.

**독립 검증**: 지하철/버스/두 방향 혼합 막차 각각 실제 최소 1건. 자정 이후 날짜, 연결 불가, 운행일 미지원, Buffer 부족을 구분한다. 일부 경로/후보 3개/검색 예산 중단은 전체 마지막 여정이나 경로 없음으로 판정하지 않는다.

- [ ] T054 [P] [US5] backend/tests/unit/test_transit_service_day.py에 실제 검증한 day/direction 코드·시간표 개정/적용일·00시/24시 이상/sentinel·공휴일/특별 운행·운행일과 실제 날짜 분리를 검증한다. 확인되지 않은 자정/휴일 규칙은 지원하지 않는다.
- [ ] T055 [P] [US5] backend/tests/unit/test_transit_last_journey.py에 마지막 연결 탐색·기종점/급행/분기·두 방향 혼합 보행/대기·hard/recommended 출발·최후 출발 경과·5분 부족·검색 완전성을 검증한다. 후보 상한과 전체 탐색을 분리하고 last flag만으로 성공하지 않는다.
- [ ] T056 [US5] T054~T055 후 backend/app/domain/transit.py·backend/app/integrations/seoul_subway.py·backend/app/integrations/seoul_bus.py에 실제 관측한 운행일/시각 표기·예외일·적용일과 운행편 대응을 확정한다. OA-110 한 역의 마지막 row와 전체 마지막 연결을 구분하며 승인된 버스 자료와도 일관되게 적용한다.
- [ ] T057 [US5] T056 후 backend/app/services/transit_providers.py에 검증된 운행 범위의 마지막 연결 여정 탐색을 구현한다. 모든 필요한 운행편/방향/종착지/TransferLink·페이지·탐색 범위의 완전성을 확인하고, API가 최단경로만 제공하거나 예산 내 완전 탐색이 불가능하면 LAST_JOURNEY_UNSUPPORTED/기존 실패로 종료한다.
- [ ] T058 [US5] T057 후 backend/app/services/last_journey_service.py·backend/app/services/time_calculation.py에 hard_leave_at와 첫 승차 전 5분을 확보한 recommended_leave_at를 연결한다. 이미 경과한 최후 출발, 완전 탐색 후 연결 없음, 데이터/운행일 미지원, BUFFER_REQUIREMENT_NOT_MET를 기존 계약으로 구분하고 총 소요/Buffer를 중복 계산하지 않는다.
- [ ] T059 [US5] T058 후 backend/app/api/journeys.py·backend/app/schemas/journeys.py에서 기존 plan last_journey와 replan 분기에 실제 막차 결과를 연결한다. 확인·선택·revision·멱등성·상태 보호와 후보 상한 3을 유지하고 합의하지 않은 공개 필드를 추가하지 않는다.
- [ ] T060 [US5] T059 후 backend/tests/contract/test_journeys_plan_last_journey.py·backend/tests/integration/test_transit_last_journey_e2e.py에 자정 이후 도착/혼합 연결 불가/미지원일/권장 여유 부족의 4경계와 검색 중단·부분 page·최후 출발 경과를 검증한다. 상태 보호·실제/Demo/Source/Buffer 계약도 함께 대조한다.
- [ ] T061 [US5] T060 후 backend/app/integrations/verify_transit.py의 안전한 검증 흐름으로 지하철/버스/두 방향 혼합 막차 각각 최소 1건을 실제 재현하고 specs/004-public-transit-api-integration/live-verification.md에 각 운행편·보행·날짜·최종 연결·검색 완전성·hard/recommended 출발을 기록한다. 4경계는 합성/실제 구분을 남기고 실제 성공이 없는 유형은 미완료로 유지한다.

**Checkpoint**: 각 수단과 양방향 혼합의 실제 약속·막차 검증이 모두 충족되어야 전체 요청을 인수한다. 부족한 자료/탐색 완전성을 미지원 표시만으로 전체 완료 처리하지 않는다.

## Phase 8: 최종 검증과 인수인계

- [ ] T062 backend/tests/unit·backend/tests/contract·backend/tests/integration에서 관련 신규 검증과 기존 확인/만료/충돌/멱등성/선택 보호 회귀를 실행한다. backend/pyproject.toml의 기존 사용 가능한 lint/format 규칙도 확인하고 실행한 명령·결과/차단 원인을 specs/004-public-transit-api-integration/live-verification.md에 기록한다. 실제 호출은 기본 pytest에 포함하지 않는다.
- [ ] T063 .dockerignore·backend/.dockerignore·backend/.env.transit.local의 Git 제외/미추적 상태와 공개 출력 보호를 재확인한다. backend/tests/unit/test_transit_secret_redaction.py의 합성 sentinel 결과 및 변경된 추적 파일을 대조하고 실제 키 파일 내용·키 fingerprint를 출력하지 않는다.
- [ ] T064 specs/004-public-transit-api-integration/spec.md·plan.md·research.md·data-model.md·contracts/transit-integration.md·checklists/requirements.md를 실제 결과와 대조하고 아래 FR/SC 추적표의 누락을 확인한다. 모든 미충족 자료/합의/인증/수용 조건과 단계별 완료 상태를 명시한다.
- [ ] T065 specs/004-public-transit-api-integration/quickstart.md의 구현 후 재현 절차를 검증하고 live-verification.md의 실제/합성·조회/약속/막차 결과로 공동 개발자 인수인계를 작성한다. 코드 수정·검증·문서 완결성과 전체 범위를 대조한 뒤 보고하며 commit/배포는 실행하지 않는다.

## 의존성과 실행 순서

### 단계와 외부 게이트

| 구간 | 시작 조건 | 다음 단계의 차단 조건 |
|---|---|---|
| 준비 T001~T004 | 현재 문서/코드 확인 | 설정 보호와 기록 양식 미완료 |
| 내부 기반 T005~T012 | 준비 완료 | 전송 방식·로그 보호·공유 예산 미확정 시 실제 키 호출 금지 |
| 공동 계약 T013~T016 | 변경안을 검토할 수 있음 | 합의 없으면 공개 basis_at 변경/그 결과의 인수 금지 |
| US1 T017~T030 | 공통 기반 완료 | 합의 operation 실제 성공·정규화 대조 미완료 |
| US2 T031~T037 | US1 Adapter/Provider 준비 | 실패 처리·Mock 대체 제거·예산/상태 보호 미검증 |
| US4 T038~T048 | US1·US2 완료 | T038~T040 보완 자료 확보/채택 합의 미완료 시 해당 계산/실제 인수 금지 |
| US3 T049~T053 | 각 작업에 적힌 US1/US2 선행 작업 완료 | 기록/지원 표시가 실제 근거와 불일치 |
| US5 T054~T061 | US4의 운행/보행/계산 기반, US3 검증 흐름 완료 | 각 편/운행일/검색 완전성·실제 막차 사례 미검증 |
| 최종 T062~T065 | 전체 스토리 검증 결과 확보 | SC 미충족이면 전체 완료 금지 |

T038~T039의 공개 자료 조사는 T001 이후 다른 파일 편집과 충돌하지 않는 범위에서 앞당길 수 있다. 외부 자료를 확보하지 못해도 독립적인 기반/Adapter/오류/기록 작업은 계속할 수 있다. API 실제 응답을 확인하기 위한 T012 probe는 공개 스토리 완료와 별도로 T005~T011 통과 후 실행 가능하다.

스토리 의존 그래프:

```text
준비 → 내부 기반 + 공동 계약 → US1 → US2 ─────────→ US4 → US5 → 최종
                                  └────→ US3 ────────────┘
T038/T039 보완 자료 확보 + 필요한 채택 합의 ────────→ US4/US5
```

US3를 Phase 6에 배치한 이유는 명세 우선순위이며, 런타임 의존 때문에 US4 이후에만 실행하라는 뜻은 아니다. 각 스토리는 자신의 입력/근거를 합성 주입해 독립 검증하되 실제 인수는 위 의존 게이트를 통과해야 한다.

### 스토리 내부 순서

테스트/안전한 probe → 모델·Adapter 의미 확정 → Provider/계산 → 기존 route 연결 → 공개 계약 검증 → 실제 관측 대조 순서다. 실제 응답에서 차이가 발견되면 관련 합성 fixture와 parser를 수정하고 해당 검증을 다시 실행한다. 공통 client/domain/시간 계산/Source를 변경할 때 모든 영향받는 callers·Mock·계약 테스트를 함께 확인한다.

## 스토리별 병행 예시

아래는 작업 가능성 설명이며 자동 subagent 실행 명령이 아니다. 병행할 때 담당 파일을 분리하고 같은 파일을 건드리는 작업은 순서대로 진행한다.

| 스토리 | 병행 가능한 예시 | 순차 통합 |
|---|---|---|
| US1 | T017 지하철 테스트 ↔ T018 버스 테스트 | 각각 테스트 후 T019~T022와 T023~T024 Adapter 개발은 파일 소유를 분리하면 병행 가능; 둘 다 끝난 뒤 T025 |
| US2 | T031 공개 실패 계약 테스트 ↔ T032 secret sentinel 테스트 | 둘 다 끝난 뒤 T033 공통 오류 매핑 |
| US4 | T038 버스 근거 조사(research.md) ↔ T039 좌표/운행일/보행 근거 확정(data-model.md) | 둘 다 확보·필요 합의 후 T040 공통 모델/Provider |
| US3 | T049 검증 모듈/테스트 ↔ T050 capabilities 계약 테스트 | T050 후 T051, T049/T051 후 T052 기록 대조 |
| US5 | T054 운행일/시각 테스트 ↔ T055 마지막 연결 테스트 | 둘 다 끝난 뒤 T056 공통 날짜/편 대응 |

이 표의 Adapter 병행은 T019~T024 자체의 선행 테스트와 파일별 순서를 지킨다는 조건이다. 이후 Provider·domain·journeys 공통 통합은 병행하지 않는다.

## 요구사항 추적

| 명세 요구사항 | 주요 작업 |
|---|---|
| FR-001~004, FR-017, FR-024 | T005, T019~T027, T049~T053 |
| FR-005, FR-020 | T010~T011, T017~T028, T035, T040~T042 |
| FR-006, FR-016 | T013~T016, T020~T022, T025~T027, T035 |
| FR-007 | T028, T031, T034, T037, T044 |
| FR-008 | T002~T003, T005~T008, T012, T032, T063 |
| FR-009 | T031, T033~T037, T044, T058~T060 |
| FR-010 | T006, T009, T036 |
| FR-011 | T010~T011, T017~T019, T023~T025, T029~T030, T040 |
| FR-012, FR-019, FR-023 | T021~T027, T038~T042, T054~T056 |
| FR-013 | T035, T050~T052, T057 |
| FR-014 | T001, T013~T016, T029~T030, T045~T047, T059 |
| FR-015 | T026~T027, T031~T032, T036~T037, T047~T048, T052, T060~T062 |
| FR-018 | T018, T024~T027 |
| FR-021 | T041~T044, T047~T048 |
| FR-022 | T054~T061 |
| FR-025 | T029~T030, T038~T042, T047~T048, T055~T061 |
| FR-026 | T001, T009, T051, T064~T065 |

| 성공 기준 | 인수 증거 |
|---|---|
| SC-001, SC-005, SC-006 | T026~T027 실제 operation별 성공/정규화, T052~T053 범위·재현 기록 |
| SC-002 | T015~T016, T017~T018, T026~T027, T048, T061 출처/시각/실제 표시 |
| SC-003 | T031, T034~T037 6분류 및 잘못된 성공 0건 |
| SC-004 | T002, T032, T063 비밀 노출 0건 |
| SC-007 | T041, T047~T048 각 수단 약속/목표 도착·여유 대조 |
| SC-008 | T054~T061 각 수단 막차/4경계·검색 완전성 |
| SC-009 | T038~T040, T047~T048, T055, T060~T061 양방향 혼합 약속·막차와 주소 제한 |
| SC-010 | T006, T009, T036 30초·전체 예산·retry 1/500ms·금지 0 |

## 구현 전략과 완료 판정

1. 최초 검증 범위는 준비/공통 기반 + US1 + US2 + US3의 조회 기록이다. 기본 6개와 추가 4개 operation을 모두 검증하고 실패를 정확히 전달한다. 이는 조회 단계의 MVP이며 전체 요청 완료가 아니다.
2. 보완 자료 T038~T040을 확보·검증한 뒤 US4를 완성한다. 지하철·버스·양방향 혼합 실제 약속 4종의 증거를 각각 남긴다.
3. 마지막 연결 탐색의 충분성을 확보한 뒤 US5를 완성한다. 실제 막차 4종과 경계 4분류를 검증하고 US3의 지원/기록을 다시 맞춘다.
4. T062~T065에서 회귀·계약·보안·재현 절차를 대조한다. 합의/자료/인증/검증이 막히면 작업 ID와 원인을 기록하고 미완료 상태를 유지한다. 일부 성공을 전체 완료로 바꾸지 않는다.

작업 완료 표시는 구현 및 해당 작업에 명시된 검증 증거가 있을 때만 변경한다. 이 문서 생성 시점에는 65개 작업 모두 미실행이다.
