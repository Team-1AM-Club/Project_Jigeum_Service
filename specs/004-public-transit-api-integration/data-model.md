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
