# 공공 교통 API 연동 조사

조사일: 2026-09-16. 공식 문서와 현재 소스만 조사했다. 실제 인증 호출·키 내용 확인은 수행하지 않았다. 키 발급과 서비스 이용 가능 여부는 사용자의 진술이며 실제 호출 증거와 구분한다.

## 1. 현재 구현과 재사용 경계

**결정:** 기존 FastAPI·httpx·Pydantic Settings·pytest를 재사용하고, 공식 서비스별 Adapter를 기존 제공자 인터페이스에 연결한다. 새 프레임워크·DB·인프라는 도입하지 않는다.

**이유:** `backend/app/services/provider_interfaces.py`에 `PlaceProvider`, `RoutingProvider`, `TransitProvider`, `ProviderResult`가 있다. `backend/app/integrations/`는 준비 상태다. 공개 라우터는 Mock을 직접 생성하고 있으며 `ProviderClient._execute_request`는 미구현이다. 서비스 교체를 공개 요청 구조의 변경과 분리할 수 있다.

**검토한 대안:** 기존 인터페이스와 별개인 라우팅 플랫폼, 독립 사용자 클라이언트, 요청마다 모든 제공처를 호출하는 구조는 제외했다.

**수정이 필요한 확인 사실:**

- `PlanService.plan`은 제공자 실패·빈 결과에서 Mock 후보를 생성한다. 실제 모드에서는 제거하고 실패/빈 결과를 분리해야 한다.
- `provider_client.py`는 전체 URL과 예외 메시지를 기록한다. 키가 URL path/query에 들어가는 서비스와 연결하기 전에 비밀 값 없는 로그로 교체해야 한다.
- 같은 클라이언트의 `status in RETRYABLE_STATUS_CODES or retryable` 분기는 재시도 불가 응답의 우선순위를 보장하지 않는다. 제공처 업무 오류를 먼저 해석하고 명시적 재시도 금지를 우선해야 한다.
- 현재 capabilities는 Mock, 후보 10개, taxi/bicycle/walking 등의 값을 내보내지만 `API_SPEC.md`는 대중교통 subway/bus, 후보 최대 3개를 기준으로 한다.
- 현재 `time_calculation.py`에는 목표 도착에서 이동시간을 빼는 기존 정의가 있다. 실제 연결은 헌법의 `목표 도착 = Deadline - 도착 여유`를 만족하는지 영향받는 호출부와 테스트를 대조해야 한다.
- `specs/003-mcp-http-contract-alignment/`가 별도로 존재한다. 이 작업은 그 범위 전체를 다시 구현하지 않는다. 영향을 받는 공개 경로·확인·선택·revision·멱등성 계약이 맞는지 연동 전에 확인한다.

## 2. 서비스별 공식 문서와 최초 검증

표의 명세는 문서 조사 결과다. 서비스의 현재 가동, 실제 키 권한, 응답 포맷과 범위는 최초 호출로 별도 검증한다. 요청 주소의 `{KEY}`와 `serviceKey`는 설명용 변수이며 실제 값은 기록하지 않는다.

| 서비스 | 문서에서 확인한 기능/요청 | 핵심 검증 |
|---|---|---|
| OA-12764 실시간 도착 | `realtimeStationArrival`, 역명, 페이지 구간, JSON/XML | 생성시각 `recptnDt`, 도착예측 필드·단위·역명 표기, 서울 밖 미제공 구간, 역/호선별 식별자 |
| OA-12601 실시간 위치 | `realtimePosition`, 호선명, 페이지 구간, JSON/XML | `subwayId/statnId/trainNo`, `updnLine`, `trainSttus`, `recptnDt/lastRecptnDt`, `lstcarAt`; 위치를 ETA로 바꾸지 않음 |
| OA-15442 역 정보 | 주어진 S 페이지는 Sheet. A 페이지의 `SearchSTNBySubwayLineInfo`는 역코드·역명·호선 검색 | `STATION_CD/STATION_NM/LINE_NUM/FR_CODE`; 1~8호선 및 9호선 2~3단계만 공식 범위. TOPIS ID와 동일하다고 가정하지 않음 |
| 15000303 정류소 | `stationinfo/getStationByName`의 이름 검색; `getBustimeByStation`의 `arsId + busRouteId` | `stId`와 `arsId` 구분, WGS84 좌표, 금일 첫·막차 시각을 다른 운행일에 재사용하지 않음 |
| 15000193 노선 | `busRouteInfo/getBusRouteList`, `getStaionByRoute` | 공식 철자는 `getStaionByRoute`; `busRouteId`, 정류소 순번·방향·기종점·구간 정보; 순환/동일 정류소 재방문 |
| 15000332 버스 위치 | `buspos/getBusPosByRouteSt` 등 필요한 상세 기능 | 노선·구간·차량 ID, 차량 위치/정류소 도착 여부, 위치를 도착예정으로 만들지 않음 |
| OA-101 열차 시간표 | `SearchSTNTimeTableByIDService`, `STATION_CD/WEEK_TAG/INOUT_TAG` | 평일/토/일·공휴일 코드, 상하행 코드, `ARRIVETIME/LEFTTIME`, 기종점·급행·분기·열차 대응, 자정 이후 표기 |
| OA-110 막차 시간표 | `SearchSTNTimeTableByFRCodeService`, 요청은 외부역코드 `FR_CODE` | 제목과 요청 코드 체계 차이, `FL_FLAG` 의미, 실제 막차 row 여부, 현재 endpoint 이용 가능 여부 |
| OA-22724 최단경로 (허브 100178 소개) | `getShtrmPath`, 출발역명·도착역명·검색일시 필수, 시간표 포함 기본 Y | 열차 출발/도착·방향·종착지·환승/대기 필드, 시간·거리 단위, 자정 넘김 및 범위 실제 검증 |
| 15000314 버스 도착 | `arrive/getArrInfoByRouteAll`, `busRouteId` | 정류소별 첫·둘째 ETA, 제공시각 `mkTm`, `isLast1/2`, 차량 ID; 출발/도착 row의 동일 차량 대응을 실응답으로 검증 |

**서울 API 주소 계열:** 정적 정보·시간표는 `openapi.seoul.go.kr:8088`, 실시간은 해당 서비스의 공식 지하철 API 주소를 사용한다. 실제 host/port/scheme은 활용가이드와 최소 연결 검증을 통해 서비스 목록에 확정한다. 소개 페이지 주소를 API 주소로 사용하지 않는다.

**버스 주소 계열:** 공식 명세의 `ws.bus.go.kr/api/rest/...`를 사용하며 query parameter로 Decoding 인증키를 전달한다. JSON/XML 지원 여부는 기능별 명세 및 실제 Content-Type/응답으로 결정한다. 포털의 다른 기능이 JSON을 지원한다는 이유로 모두 JSON이라 가정하지 않는다.

### 확인한 불일치와 제한

**결정:** 문서 간 범위 충돌이나 접근 오류를 실제 종료·지원으로 확정하지 않는다. 개별 노선·방향·날짜·기능의 성공 관측으로 지원 근거를 만든다.

**이유:** OA-101/110의 열린데이터 설명과 공공데이터포털 설명에서 9호선 지원 문구가 일치하지 않는다. 열린데이터 페이지의 정적 HTML에는 일반 종료/URL 오류 안내 템플릿도 포함된다. 브라우저에서 OA-22724의 실제 동적 API 명세가 표시되는 것을 확인했으므로 숨겨진 안내 문구만으로 종료를 판정하지 않는다. 원래 제시한 버스 서비스 목록 페이지의 접근 오류도 개별 버스 API 장애의 증거가 아니다.

**검토한 대안:** 동일 제목의 다른 API로 자동 전환하거나 지원 노선을 문서 중 넓은 쪽으로 채택하는 방식은 제외했다.

서울 실시간 API의 공식 이용가이드는 일 최대 1,000 요청과 한 번에 최대 1,000건을 안내한다. 이를 정적 서비스 전체나 사용자의 승인 계정에 일괄 적용하지 않는다. 버스 포털의 개발 트래픽 1,000 표시는 실제 계정의 한도/측정 기간과 별도로 확인한다. 한도를 확인하기 위해 대량 호출하지 않는다.

## 3. 최단경로 API 식별 — OA-22724로 해소

**결정:** 사용자가 실제 최단경로 페이지를 [OA-22724](https://data.seoul.go.kr/dataList/OA-22724/A/1/datasetView.do)로 정정했다. 100178은 소개 경로로 유지하고 실제 Adapter 대상은 OA-22724로 확정한다. 공공데이터포털 15143842는 자동 대체하지 않는다. 기존 `SEOUL_SUBWAY_PATH_API_KEY` 칸을 그대로 사용한다.

**이유:** 브라우저에서 해당 페이지의 동적 Open API 화면을 직접 확인했다. 서비스는 `getShtrmPath`, 공식 샘플 주소 계열은 `http://openapi.seoul.go.kr:8088/{KEY}/{TYPE}/getShtrmPath/{START_INDEX}/{END_INDEX}/{dptreStnNm}/{arvlStnNm}/{searchDt}`다. 이 표는 문서 증거이며 사용자 키로 호출한 결과가 아니다.

필수 입력은 KEY/TYPE/SERVICE/START_INDEX/END_INDEX와 출발역명·도착역명·검색일시다. 선택 입력은 `searchType`(duration/distance/transfer), `exclTrfstnNms`, `thrghStnNms`, `schInclYn`(기본 Y)다. 역 목록은 콤마 구분이다. 검색일시 표기는 문서상 yyyy-MM-dd hh:mm:ss이며 실제 시간 해석과 path escaping은 최초 호출로 확인한다. 이름 입력이지만 같은 이름/호선/역코드 대응은 먼저 검증한다.

출력에는 경로/역코드·역번호·호선, 총 거리/시간, `reqHr/wtngHr`, `trainDptreTm/trainArvlTm/trainno`, 종착역·상하행, 환승·급행·무정차가 있다. 상세 시간/거리 단위와 운행일·자정 경계, 환승 소요의 포함 범위는 샘플 숫자만으로 확정하지 않는다. 페이지의 예제 XML은 header/resultCode/body 구조를 보여주므로 일반 서울 표 형식과 동일한 파서로 가정하지 않는다. 실제 JSON/XML 성공과 업무 오류를 별도 검증한다.

**검토한 대안:** 소개 페이지를 endpoint로 사용하거나 유사 제목의 다른 제공처로 key를 전달하는 방식은 제외했다. 정적 HTML의 종료 안내 템플릿으로 현행 API 종료를 확정하는 판단도 제외했다.

사용자는 OA-101/OA-110/100178 키 혼동 가능성을 알렸다. 명세 식별은 해소됐지만 실제 키 배정/권한/인증은 미검증이다. 입력 파일의 값은 읽거나 교환하지 않았다. 해당 칸의 설명 주석만 OA-22724로 정정했다.

## 4. 버스 미래 운행과 혼합 환승

**결정:** 도착정보·금일 막차·최단경로 후보만으로 미래 날짜의 연결 여정을 확정하지 않는다. 필요한 운행/연결 자료를 실제로 확보하기 전에는 해당 조건을 미검증/미지원으로 처리한다. 전체 기능 완료를 선언하지 않는다.

**이유:** `getBustimeByStation`은 금일 첫·막차, 노선 목록/경유 정류소 정보는 운행 기준과 순서, 도착정보는 실시간 예측을 제공한다. 날짜별 모든 운행편의 승하차 시각이나 미래 구간 도착시각의 충분한 근거는 현재 확인한 명세에서 얻지 못했다.

별도 [15000414 대중교통환승경로 조회](https://www.data.go.kr/data/15000414/openapi.do)의 `pathinfo/getPathInfoByBusNSub`는 `startX/startY/endX/endY`를 받고 총 거리·시간·승하차 위치·노선 등의 경로 후보 정보를 제공한다. 공식 요청 목록에 미래 날짜·시각이 없고 구간별 실제 보행 경로/시간도 확인되지 않았다. **추가 권한을 확보하더라도 이 서비스 하나가 시간표·막차·보행 문제를 모두 해결한다고 판단하지 않는다.** 현재 연동 대상에 자동 추가하지 않았다.

**필요한 근거:**

1. 버스: 운행일·노선·방향·정류소 순번·각 편/차량 대응, 검증 가능한 승차와 목적 정류소 도착시각. 금일 예측과 미래 예정 운행을 구분한다.
2. 환승: 지하철 승하차 지점과 버스 승하차 지점 사이 통행 가능한 실제 보행 연결, 기준과 최소 소요시간, 적용 기간. 직선거리와 임의 보행속도는 대체 근거가 아니다.
3. 막차: 필요한 모든 편의 연결과 검색 완전성을 검증할 수 있는 범위. 단순히 후보 3개를 찾은 것을 전체 범위의 마지막 연결 여정이라고 부르지 않는다.

**검토한 대안:** 위치로 ETA 생성, 배차간격으로 미래 편 생성, 거리/속도로 보행시간 생성, 모델 추정, 운영 실패의 Mock 대체, 근거 없이 유료 제공처 추가는 제외했다.

**사용자 답변:** 별도 운행·보행 자료는 없으며 추가 자료 조사가 필요하다. 공개 자료를 우선 조사하고 필요한 보완 제공처는 별도로 제안한다. 검증 전 성공으로 표시하지 않으며 유료 제공처·새 키·인프라 도입은 추가 합의 사항이다.

### 보완 공개 자료 조사 결과

사용자 답변 후 다음 공식 자료를 추가 조사했다. 어느 것도 새 연동 대상으로 채택하거나 인증 요청하지 않았다.

| 후보 | 제공 내용 | 현재 요구사항의 결손 |
|---|---|---|
| [KTDB 2025 GTFS 기반정보](https://www.ktdb.go.kr/www/selectBbsNttView.do?bbsNo=2&key=45&nttNo=3825) | 시내/마을버스·도시철도의 trips/stop_times | 2025년 3월 평일 하루, 자료신청 및 비표준 파일럿. 현재/미래 날짜 운행표·실제 혼합 보행을 보장하지 않음 |
| [서울 도보 네트워크 OA-21208](https://data.seoul.go.kr/dataList/OA-21208/A/1/datasetView.do) | WGS84 노드·링크 WKT, 시작/종료 노드·길이·통행시설, 버스정류장/지하철 출입구 포함 안내 | 2020 공간 기준, KEY 필요. 역코드/정류소↔노드 교차표와 보행시간 미확인. 링크 길이를 임의 속도로 나눠 시간을 확정하지 않음 |
| [환승 승객수·환승시간 OA-21221](https://data.seoul.go.kr/dataList/OA-21221/F/1/datasetView.do) | 일별·정류장별·사용자 유형별 과거 집계, 적재 5일 지연 | 특정 역↔정류소/수단/보행 경로 대응 미확인. 집계 환승시간은 특정 미래 연결 보행시간이 아님 |

좌표 보완 후보 [역사마스터 OA-21232](https://data.seoul.go.kr/dataList/OA-21232/A/1/datasetView.do)는 역사 ID/명칭/호선/좌표를 제공하지만 OA-15442 코드와의 공식 매핑은 미검증이다. 좌표 확보와 보행 연결/시간 확보는 별개다. [OA-21217](https://data.seoul.go.kr/dataList/OA-21217/S/1/datasetView.do)의 1시간 단위 평균 버스 운행시간도 5일 지연된 과거 집계이며 미래 회차별 시간표를 대체하지 않는다.

현재 조사 범위에서는 미래 운행편·구간 시각과 실제 혼합 보행시간을 모두 충족하는 무료·무추가승인 자료를 확인하지 못했다. 자료가 존재하지 않는다고 단정하지 않으며, 최신 서비스 캘린더/예외일/각 편 stop_times와 역·정류소↔출입구/보행 노드의 대응 및 시간 비용을 향후 데이터 확보 요건으로 남긴다.

## 5. 시간·식별자·출처

**결정:** 제공처 ID와 정규 ID의 대응 근거를 보존하고 운행일, 실제 날짜, 기준시각, 조회시각을 각각 관리한다. 시각 없는 실시간 관측은 현재 운행을 검증하는 근거에서 제외한다.

**이유:** `STATION_CD`, 외부코드 `FR_CODE`, TOPIS `statnId`, 버스 `stId/arsId`, 차량·노선 ID는 서로 다르다. OA-101의 방향 1/2와 실시간 위치의 방향 0/1도 그대로 비교할 수 없다. 역명·동일 차량 번호만으로 서로 다른 제공처/운행일의 편을 연결하지 않는다.

**검토한 대안:** 이름을 주키로 삼기, 24시 넘는 시각을 임의 다음 운행일로 처리하기, 일반 주말/공휴일 추정, 시간표를 실제 도착으로 표기하기는 제외했다. 날짜를 지정할 수 없는 API는 요청 날짜의 운행 증거가 되지 않는다.

사용자는 `Source.basis_at: datetime | null` 계약 변경안 작성을 승인했다. 실제 반영은 공동 개발자 합의 후 `API_SPEC.md`와 예제 JSON을 함께 갱신한다. 기준일만 있는 정적 자료는 임의의 자정 timestamp로 변환하지 않고 원본 기준/개정일을 보존한다. 조회시각을 기준시각 대신 채우지 않는다.

## 6. HTTP·설정·조회 예산

**결정:** 기존 공통 클라이언트의 실제 전송을 httpx로 구현하고 재시도는 그 계층에서만 수행한다. 외부 시도 상한 30초와 API 서버의 더 짧은 전체 제한을 함께 적용한다.

**이유:** [HTTPX timeout](https://www.python-httpx.org/advanced/timeouts/)은 connect/read/write/pool 각각을 제한하며 read timeout은 전체 작업의 경과시간과 다르다. [Python 3.11 asyncio timeout](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.timeout)을 이용한 전체 deadline이 필요하다. [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)의 dotenv와 환경변수 우선순위를 활용할 수 있다. 설치 버전은 구현 시작 시 확인하며 이번 계획에서 패키지를 업그레이드하지 않는다.

**검토한 대안:** 외부 요청별 30초만 설정해 여러 호출이 누적되도록 하는 방식, Adapter·서비스·HTTP 라이브러리의 중복 retry, 자동 한도 회피 키 전환, 무제한 페이지 수집은 제외했다.

예산은 `plan.md`에서 요청별로 정의한다. 정상 빈 결과·인증·권한·한도·잘못된 입력/응답·명시적 nonretryable에는 자동 retry가 없다. 500ms와 남은 시간/횟수를 확보할 때만 허용 오류에 최대 한 번 재시도한다. HTTP 200의 제공처 업무 오류도 먼저 해석한다.

키 파일은 사용자 요청으로 `backend/.env.transit.local`에 만들었고 실제 값은 확인하지 않았다. 현재 앱은 이 파일을 읽지 않는다. 구현 시 기존 Settings에 서비스별 SecretStr 필드와 로컬 파일 명시 로드를 연결하며 서버 환경변수가 우선한다. 키는 HTTP 요청 직전에만 필요한 형식으로 사용한다. 로그에는 서비스 alias·비밀 값 없는 작업명·시도·상태만 남긴다.

## 7. 정책 확인과 상태

사용자는 키 입력 완료를 알렸다. 키 내용은 읽지 않았고 배정/인증은 미검증이다. OA-101/OA-110/100178 혼동 가능성을 기록했다. 키를 자동 교환하거나 다른 제공처에 무차별 시도하지 않는다.

Safety Buffer는 사용자 답변으로 첫 승차 전 5분·여정당 한 번으로 확정했다. 최소 환승 보행/대기시간은 Buffer로 대체하지 않는다. 정책 식별자는 transit-initial-5m-v1로 제안하며 기존 공개 buffer_policy와 공동 정합화한다.

현재 상태는 **사용자 정책/실제 서비스 OA-22724/보완자료 확보 여부 확정, 실제 인증·응답 검증과 보완 데이터 확보 필요**다. 최단경로 명세 식별 질의는 해소됐다. 자료가 필요한 항목은 구현 선행조건으로 남기며 실제 호출·약속·막차 수용 기준은 미실행이다.

## 공식 근거

- [OA-12764 실시간 도착 API](https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do), 원래 제공된 F 페이지와 API 상세를 구분한다.
- [OA-12601 실시간 위치](https://data.seoul.go.kr/dataList/OA-12601/A/1/datasetView.do)
- [OA-15442 역 정보 API](https://data.seoul.go.kr/dataList/OA-15442/A/1/datasetView.do), 원래 제공된 S 페이지는 Sheet다.
- [15000303 정류소](https://www.data.go.kr/data/15000303/openapi.do)
- [15000193 노선](https://www.data.go.kr/data/15000193/openapi.do)
- [15000332 버스 위치](https://www.data.go.kr/data/15000332/openapi.do)
- [OA-101 열차 시간표](https://data.seoul.go.kr/dataList/OA-101/A/1/datasetView.do), [공공데이터포털 시간표 설명](https://www.data.go.kr/data/15057982/openapi.do)
- [OA-110 막차 시간표](https://data.seoul.go.kr/dataList/OA-110/A/1/datasetView.do), [공공데이터포털 관련 시간표 설명](https://www.data.go.kr/dataset/15003143/openapi.do?lang=en)
- [OA-22724 최단경로 API](https://data.seoul.go.kr/dataList/OA-22724/A/1/datasetView.do), [100178 소개](https://data.seoul.go.kr/bsp/wgs/dataView/data300View/100178.do). [15143842](https://www.data.go.kr/data/15143842/openapi.do)는 유사 제목의 미채택 후보다.
- [15000314 버스 도착](https://www.data.go.kr/data/15000314/openapi.do)
- [15000414 대중교통환승경로 후보](https://www.data.go.kr/data/15000414/openapi.do)
- [서울 OpenAPI 이용가이드](https://data.seoul.go.kr/together/guide/useGuide.do)
- [버스 서비스 목록](http://api.bus.go.kr/contents/sub02/svcList.html): 앞선 접근 오류 때문에 목록 내용 확인은 보류되었으며 별도 dataset으로 취급하지 않는다.
