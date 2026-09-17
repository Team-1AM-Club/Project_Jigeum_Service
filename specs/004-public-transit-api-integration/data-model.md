# 공공 교통 데이터 모델 설계

작성일: 2026-09-16. 내부 모델의 설계이며 새 DB 테이블·마이그레이션·영구 이동 이력을 요구하지 않는다. 아래 필드가 제공처 원문에 없으면 임의 생성하지 않는다. 공개 응답은 `API_SPEC.md`를 따른다.

## 1. 출처 근거 — Evidence

| 필드 | 의미/검증 |
|---|---|
| provider/service/operation | 제공처·서비스 식별자·비밀 값 없는 작업명 |
| basis | static / schedule / realtime / demo 내부 분류; 공개 Source는 기존 schedule/realtime/demo 분류로 의미를 검증해 매핑 |
| basis_at | 제공처가 생성/관측한 aware datetime 또는 null. 조회시각으로 대체 금지 |
| retrieved_at | 서비스가 응답을 받은 aware datetime |
| revision/reference_date/validity | 확인한 원본 개정·기준일·적용 범위; 미제공은 null |
| service_date/day_type | 운행일과 확인된 평일/토/일·공휴일 유형. 날짜를 받지 않는 API에 미래 운행일을 붙여 예정값으로 만들지 않음 |
| raw_time/units/id_namespace | 검증에 필요한 원문 시각 표현·단위·식별자 체계. 키/전체 요청 URL은 보관하지 않음 |
| verification_state | 문서 확인 / 실제 호출 / 정규화 확인 / 계획 근거 확인을 구분 |

정적 자료의 기준일만 알면 그 날짜를 임의 자정 시각으로 변환하지 않는다. 기준일·개정 설명을 내부에 보존하고 필요한 공개 경고에 표시한다. 실시간 기준시각 미확인은 현재 운행 검증 근거로 사용하지 않는다. `generated_at`, `refresh_after`, `retrieved_at`는 운행 보장 또는 제공처 기준시각이 아니다.

## 2. 역·정류소 — TransitPlace / ProviderIdentifier

| 필드 | 의미/검증 |
|---|---|
| place_id | 기존 장소 검색과 계획에서 사용하는 opaque ID. 제공처의 이름만 주키로 사용하지 않음 |
| mode/name/line | subway/bus, 원본 표시명·호선. 같은 역명/다른 노선 후보 구분 |
| provider_ids | namespace와 ID 문자열의 목록. 선행 0을 보존하며 임의 정수 변환 금지 |
| coordinate | 확인된 좌표계와 좌표 또는 null; 공개 Point에는 검증된 WGS84 위도·경도만 사용 |
| evidence | ID 대응 및 좌표 출처 |

지하철 `STATION_CD`, 외부코드 `FR_CODE`, TOPIS `statnId`는 서로 다른 namespace다. 역명이나 코드 모양만으로 같다고 판단하지 않는다. 버스 `stId`, `arsId`, 노선 상세의 `station`도 각각 보존하고 변환 근거를 검증한다.

지하철 역 코드표에 좌표가 없으면 다른 검증된 공식 자료가 필요하다. 공개 경로 Point의 필수 좌표를 0 또는 모델 추정값으로 채우지 않는다. 정류소 검색의 GRS80 `posX/posY`와 노선 상세 WGS84 `gpsX/gpsY`를 구분하며 단위 미확인 좌표는 사용하지 않는다.

## 3. 노선과 정류소 순서 — RoutePattern / StopOccurrence

필드: 제공처 노선 ID, 교통수단, 표시 노선명, 방향/내외선, 기·종점, 급행/분기, 정류소 occurrence 목록, 근거.

각 occurrence는 정류소 ID·순번·구간 ID·방향을 가진다. 같은 정류소를 재방문하는 순환 노선은 occurrence를 별도로 식별한다. 노선 `seq/section`과 위치 API `startOrd/endOrd/sectOrd/sectionId`는 실제 매핑 검증 후에만 연결한다. 같은 역/정류소를 거꾸로 타는 경로를 생성하지 않는다.

## 4. 운행일과 시간표 — ServiceCalendar / ScheduledCall

Calendar는 운행일, 제공처의 day tag, 적용 노선/방향, 유효 기간, 확인한 공휴일/운행일 근거를 가진다. 날짜의 요일만으로 공휴일과 특별 운행을 확정하지 않는다. 공식 운행일 근거가 부족하면 요청 날짜는 미지원이다.

ScheduledCall은 다음을 보존한다.

- 노선·방향·역 occurrence, 제공처 운행편/열차 식별자와 대응 근거.
- 원문 `ARRIVETIME/LEFTTIME`, 실제 도착·출발 datetime, 운행일, 기·종점, 급행/분기, first/last flag.
- 원본 weekday/direction 코드와 정규 값의 검증된 대응.
- 시간표 개정/적용 근거.

OA-101 요청은 STATION_CD, OA-110 요청은 FR_CODE로 구분한다. 예정 도착·출발은 실제 도착이 아니다. 24시 이상, 00시 표현, 빈 값/특수 sentinel을 실응답으로 검증하고 운행일과 실제 날짜를 별도로 처리한다. 대응이 확인되지 않은 두 역의 row를 동일 열차로 연결하지 않는다.

## 5. 실시간 관측 — TransitObservation

필드: 관측 유형(position/arrival_prediction/status), 노선·방향·역 occurrence, 제공처 차량/열차 ID, 운행편 대응 근거, 기준시각·조회시각, 원문 위치/ETA/메시지/상태/막차 flag, 단위, 근거.

`recptnDt/lastRecptnDt`, 버스 `dataTm/mkTm`은 필드별 의미와 날짜를 검증한다. 잔여시간이 생성시각 기준이면 그 의미가 확인된 경우에만 생성시각 + 잔여시간으로 예정시각을 해석한다. 이미 지난 예측을 0으로 clamp하여 도착으로 표시하지 않는다. 지연·기준시각 불명·최신성 조건 미확인은 별도로 표시하며 임의 TTL이나 정확도 보장을 만들지 않는다.

실시간 위치로 ETA를 생성하지 않는다. 현재 예측으로 임의 미래 시간표를 만들지 않는다. 차량 번호만으로 운행일·방향이 다른 편을 합치지 않는다. 버스 목적 정류소와 출발 정류소 row의 동일 차량 대응은 검증 전 사용하지 않는다.

## 6. 환승 연결 — TransferLink

필드: from/to 승하차 지점 및 occurrence, 실제 보행 경로 또는 공식 연결 식별자, 최소 보행/환승 소요시간과 단위, 방향, 적용 기간/통행 제약, 좌표 대응 근거, Evidence.

동일 수단 및 subway↔bus 연결을 표현한다. 역 중심점과 정류소 중심점의 직선거리로 통행 가능성을 확정하지 않는다. 임의 속도·미확인 출입구·수직 이동시간을 추가하지 않는다. 다음 교통편 승차시각까지 최소 환승시간과 필요한 실제 대기를 확보해야 한다. 임의 주소/건물의 시작·종료 도보는 이 모델의 허용 연결이 아니다.

## 7. 검증된 후보 — JourneyCandidate

필드: 후보 ID, 요청 조건, 순서 있는 ride/walk/wait 구간, 각 구간의 근거, 예정/예측 승하차, 목적지 도착, 출처 목록, 경고, 탐색 범위/완전성, Buffer 배정.

검증 규칙:

1. 모든 datetime은 Asia/Seoul aware이며 시간 흐름이 역전되지 않는다. 구간 간 시간 공백은 wait로 설명하고 겹침/순간 이동을 허용하지 않는다.
2. 공개 `total_duration_minutes`는 권장 출발→도착 차이 및 구간 합과 일치한다. 상태 판정에는 반올림 전 datetime을 사용한다.
3. 약속 `target_arrival_at = arrival_deadline - arrival_preference_minutes`다.
4. 사용자 확정 Buffer는 첫 승차 전 5분, 여정당 한 번이다. safety_buffer wait와 buffer item에 같은 시간을 한 번 배정하며 합계는 5분이다. 기존 scheduled wait를 별도 Safety Buffer라고 중복 배정하지 않는다.
5. Buffer를 실제 출발 기준점~첫 승차 사이에 포함한다. `recommended_leave_at` 및 total_duration에 이미 반영하므로 표시 단계에서 다시 빼지 않는다. 실제 환승 최소시간과 구분한다.
6. 막차 `hard_leave_at`은 검증된 마지막 연결 여정의 이론상 최후 출발이며, 권장 출발은 첫 승차 전 Buffer를 확보한다. 운행일·방향·종착지·편·모든 연결 및 검색 완전성이 확인되어야 한다.
7. 일부 후보만 조회했거나 검색 예산으로 중단했으면 전체 마지막 여정/경로 없음으로 결론 내리지 않는다.
8. Demo 근거가 하나라도 있으면 is_demo=true다. 운영 조회 실패에 Demo 근거를 추가하지 않는다.

## 8. 기능 근거 — CoverageEvidence

서비스/기능별 상태를 `documented → configured → real_call_verified → normalized → planning_verified`로 구분한다. configured는 키 존재 여부이지 인증 성공이 아니다. planning_verified는 특정 노선·방향·날짜·시간 범위·연결의 검증을 뜻하며 서울 전체로 확대하지 않는다.

권한·한도·데이터 없음·제공처 장애·잘못된 응답을 별도 원인으로 기록한다. 연결 이상이 생기면 이전 성공 기록과 현재 사용 가능 상태를 구분한다. `/health` 프로세스 정상 또는 제공자 health=true만으로 막차 supported=true를 반환하지 않는다. 상태는 capabilities의 기존 필드/limitations에 매핑한다.

## 관계와 상태 경계

TransitPlace ↔ ProviderIdentifier → StopOccurrence → RoutePattern → ScheduledCall/TransitObservation, TransferLink가 JourneyCandidate의 순서 있는 연결을 구성한다. 모든 계산 근거는 Evidence와 해당 CoverageEvidence에 결부한다.

도메인 결과는 검증 성공 / 입력 확인 필요 / 데이터 미지원 / 완전 탐색 후 경로 없음 / Buffer 부족 / 제공처 실패를 구분한다. 실패를 빈 후보로 바꾸지 않는다. 새 데이터 모델은 대화 상태의 새로운 권위 저장소가 아니며 기존 003의 확인·revision·만료·멱등성·후보 선택 규칙을 보존한다. 새 후보 생성은 기존 선택을 변경하지 않는다.

## 실시간 사용 제한과 수용 판정

서비스/operation별 검증 기록에는 basis_at 원본 필드 의미·시간대/날짜, 예측의 시간 기준, 공식 지연/사용 제한 규칙과 근거, 규칙 확인 상태 및 경계 검증 결과를 남긴다. 새 DB나 캐시 정책을 요구하지 않는다. 기준시각 누락·해석 불가·설명되지 않는 미래 기준시각·이미 지난 예측·사용 규칙 미확정은 현재 운행 계산에서 제외한다. 임의 TTL/보정으로 정상화하지 않는다.

실제 조회 성공, 정규화 성공, 계산 사용 가능성은 별도 판정이다. 기록은 출처/근거 유형/실제·Demo/기준 확인 여부를 모두 보존한다. realtime은 확인한 생성/관측시각과 사용 규칙, static/schedule은 제공된 개정 기준일/적용 범위/운행일 및 요청에 필요한 필드의 검증을 사용 조건으로 삼는다. 일부 기준이 없으면 미확인 상태와 관련 제한을 유지한다. 기준 미확인을 null로 표현한 조회 기록은 유효하나 그것만으로 planning_verified가 되지 않는다.

### T015 operation별 확인 상태 — 2026-09-16 재조사

인증 없는 공식 설명/출력 항목을 대조했다. 아래 ‘미확정’은 추정으로 보완하지 않고 해당 실시간 자료의 현재 운행 계산을 차단하는 조건이다. 원문 시각에 offset이 없을 때는 필드별 시간대 근거를 확인하기 전 임의로 +09:00을 붙이지 않는다. 도메인에 들어온 검증된 aware 시각의 공개 직렬화는 +09:00으로 유지한다.

| service / operation | 공식 필드 의미 | 날짜·시간대와 ETA 기준 | 공식 지연·사용 안내 | 실제 호출과 현재 수용 상태 | 현재 계산에 필요한 경계 검증 | 공식 URL |
|---|---|---|---|---|---|---|
| subway-arrivals / `realtimeStationArrival` | `recptnDt`는 열차 도착정보를 생성한 시각이다. | 공개 설명은 `recptnDt`의 날짜·offset·원문 형식, 개별 도착예측 필드의 단위와 `recptnDt` 기준 여부를 정의하지 않는다. | 수집·가공 과정에서 시차가 날 수 있고 현재시각과 `recptnDt`의 차이를 고려하라고 안내한다. 그 안내의 ‘1역 진행’ 예시는 새로운 위치·ETA를 생성하거나 지난 예측을 0으로 clamp하는 승인 근거가 아니다. | 지하철 6호선 alias 최소 probe는 성공했지만, 규칙 확정과 별개다. `basis_at=null`, `verified_for_planning=false`, `usage_rules_verified=false`를 유지한다. | `recptnDt` 누락·파싱 불가·offset/날짜 미확정·미설명 미래 기준시각, 원본 ETA의 기준/단위·sentinel 미확정, 이미 지난 예측이면 제외한다. | [OA-12764](https://data.seoul.go.kr/dataList/OA-12764/A/1/datasetView.do) |
| subway-positions / `realtimePosition` | `lastRecptnDt`는 최종수신날짜, `recptnDt`는 최종수신시간이다. | 두 필드의 원문 형식·시간대와 결합 규칙은 공개 표에 없다. 위치 응답에는 ETA가 정의되지 않는다. | 이번 공식 페이지/활용 안내에서 지연 상한이나 위치→ETA 변환 규칙을 확인하지 못했다. | 지하철 6호선 alias 최소 probe는 성공했지만 `basis_at=null`, `verified_for_planning=false`다. 위치를 `arrival_prediction`으로 바꾸지 않는다. | 날짜/시간 어느 하나의 누락·파싱 불가·시간대 미확정·미설명 미래 기준시각이면 제외한다. 원본 위치만으로 ETA를 만들지 않으며 사용 규칙 미확정이면 제외한다. | [OA-12601](https://data.seoul.go.kr/dataList/OA-12601/A/1/datasetView.do) |
| bus-positions / `getBusPosByRouteSt` | `dataTm`은 제공시간이며, 응답은 차량 위치·정류소 도착 여부 등을 제공한다. | `dataTm`의 날짜/offset/원문 형식과 측정·생성시각 동일성은 확인되지 않았다. ETA 필드는 없다. | 공식 출력표에는 지연 상한·신선도·위치→ETA 사용 규칙이 없다. | 버스 4개 최소 probe는 HTTP 401에서 중단했다. 실제 성공이 없고 `basis_at=null`, `verified_for_planning=false`다. | `dataTm`이 없거나 해석 불가·시간대 미확정·미설명 미래 시각이면 제외한다. 위치에서 ETA를 만들지 않고, 사용 규칙 미확정이면 현재 계산에 쓰지 않는다. | [15000332](https://www.data.go.kr/data/15000332/openapi.do) |
| bus-arrivals / `getArrInfoByRouteAll` | `mkTm`은 제공시각이다. `exps1/2`는 도착예정시간(초), `traTime1/2`는 여행시간(분)으로 표기된다. | `mkTm`의 sample은 날짜·시간 문자열이지만 offset이 없고, `exps1/2`가 무엇을 기준으로 한 초인지와 `traTime*`의 대상 구간/ETA 채택 규칙은 공개 표에서 확정되지 않았다. | 공식 출력표에는 `mkTm`과 예측 간의 지연·신선도·사용 규칙이 없다. | 버스 4개 최소 probe는 HTTP 401에서 중단했다. 실제 성공이 없고 `basis_at=null`, `verified_for_planning=false`다. | `mkTm` 누락·파싱 불가·시간대 미확정·미설명 미래 기준시각, ETA 기준/단위·sentinel 미확정, 이미 지난 예측이면 제외한다. 초·분 필드를 공통 ETA로 추정하거나 제공시각을 생성시각으로 승격하지 않는다. | [15000314](https://www.data.go.kr/data/15000314/openapi.do) |

**공통 gate:** 기준시각 누락·해석 불가·미설명 미래시각·이미 지난 예측·사용 규칙 미확정은 현재 계산에서 제외한다. 임의 TTL, 속도 추정, 역 진행, 0 clamp 또는 그 밖의 보정으로 통과시키지 않는다. 실제 HTTP 성공은 규칙 확정이나 planning 검증과 동치가 아니다.

기존 `test_transit_domain.py`는 시간대 없는 시각, 규칙/기준시각 누락, 미검증 상태, 위치로 ETA 생성, 지난 예측의 현재 도착 변환을 거부한다. `test_transit_source_contract.py`는 공개 Source와 다른 제공처·운행일·시각의 Evidence로 실시간 후보를 승인할 수 없음을 검증한다. 이 합성 검증은 원문 parser·실제 ETA의 정확도를 입증하지 않는다. T015의 operation별 의미·단위·공식 근거·확정 상태 및 제외 조건 기록은 완료했다. 실제 의미·현재성/ETA 규칙의 미확정 사항은 T039/T040의 관측으로 후속 확정하며 현재 계산에서는 제외한다.

### 정적 근거의 공개 경고 변환

`routing_search`는 schedule Source와 provider·basis_at·retrieved_at·service_date가 일치하는 static/schedule Evidence의 `reference_date`, `revision`, `valid_from`, `valid_until`만 `SOURCE_REFERENCE` 경고로 전달한다. 제공된 항목만 표시하고 날짜를 datetime으로 만들지 않는다. 동일 경고는 한 번만 반환한다. 현재 경고 변환은 근거의 적용 적합성 판정이나 실제 Provider 연결 완료를 뜻하지 않는다.
