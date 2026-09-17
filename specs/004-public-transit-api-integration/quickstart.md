# 공공 교통 연동 검증 가이드

작성일: 2026-09-16. **현재는 계획 단계다. 아래 신규 검증 모듈·Adapter·테스트는 아직 구현되지 않았다.** 명령을 문서에 적었다는 사실은 실행/성공 증거가 아니다. 기존 서버의 Mock 응답도 실제 조회 성공이 아니다.

## 1. 현재 완료된 준비

`backend/.env.transit.local`에 입력 칸을 만들었고, 사용자가 입력 완료를 알렸다. 키 값은 읽지 않았다. OA-101/OA-110/100178의 키 배정은 사용자가 혼동 가능성을 알렸으므로 **미검증**이다. 입력 안내는 [credentials.md](credentials.md)를 따른다. 파일을 다시 생성하거나 덮어쓰지 않는다.

현재 앱은 이 키 파일을 읽지 않는다. 현재 `Settings`에 새 키 필드와 명시적 로드 연결이 없고 공통 HTTP 전송도 미구현이다. 서버를 실행하기만 해서는 실제 교통 호출로 바뀌지 않는다.

로컬 파일 제외 확인은 키 내용을 출력하지 않는 다음 명령으로 할 수 있다.

```powershell
git check-ignore -- backend/.env.transit.local
```

기대 결과는 해당 파일 경로다. 이번 작업에서 제외를 확인했다. 환경에 따라 Git ownership 오류가 발생하면 저장소의 정확한 경로에만 명령 단위 safe.directory를 지정할 수 있으며 전역 설정을 변경할 필요는 없다. 루트 및 backend의 `.dockerignore`도 `.env`와 `.env.*`를 제외한다.

## 2. 구현 전에 확인할 근거

1. 현재 브랜치/dirty worktree와 기존 003의 영향받는 공개 경로·확인·revision·멱등성 계약을 다시 대조한다.
2. `Source.basis_at`은 변경안 작성만 승인되었다. 공동 개발자 합의 후 API_SPEC/예제/스키마/양쪽 계약 검증을 갱신한다.
3. 최단경로는 사용자 정정으로 OA-22724/getShtrmPath다. 동적 명세의 KEY path·출발/도착역명·검색일시·시간표 포함 입력을 적용하고 실제 권한·단위·운행일·응답 구조를 검증한다. 허브 100178은 소개이며 15143842로 자동 대체하지 않는다.
4. 버스 미래 운행/구간 도착시각, 지하철 좌표, 실제 환승 보행 경로/시간, 운행일 유형의 근거를 확보한다. 자료가 없으면 관련 계획 성공 검증을 보류한다.
5. 서비스별 공식 host/path/scheme와 키 형식·전송 위치를 확인한다. 무키 연결 점검과 실제 인증 점검을 구분한다. TLS 가능 여부를 문서/연결 실패 하나만으로 단정하지 않는다. 미확정 전송 방식에 키를 보내지 않는다.

## 3. 구현 후 로컬 회귀 검증

기존 backend Python 환경을 사용한다. 필요 시 기존 requirements만 설치하며 이번 계획은 설치/업그레이드를 실행하지 않았다.

```powershell
Set-Location C:\Users\romai\Desktop\Develop\Project\Project_Jigeum_Service\backend
python -m pytest tests/unit tests/contract tests/integration
```

기본 테스트는 합성 응답/명시된 Demo를 사용하고, 자동으로 실제 제공처를 호출하지 않도록 한다. 기대 검증은 ID/단위/날짜·편 대응, 목표 도착/Buffer, 상태·선택 보호, 업무 오류·깨진 응답, retry 1회/500ms·금지 0회, 전체/시도 deadline, 호출 예산 및 secret sentinel 유출 0건이다.

기존 테스트 통과만으로 최신 공개 계약이나 실제 교통 연동 준수를 주장하지 않는다. `API_SPEC.md`의 후보 상한 3, subway/bus, Source/Leg/Buffer, 확인·선택·멱등성 의미를 추가로 대조한다. 설치된 lint 도구와 기존 프로젝트 규칙을 사용하며 별도 도구 설치는 필요한 경우에만 제안한다.

## 4. 구현 예정인 실제 호출 검증 모듈

다음은 **예정 CLI 계약**이다. 현재 `app.integrations.verify_transit`는 없으므로 아직 실행할 수 없다. 제품 사용자용 CLI가 아닌 백엔드 운영자의 검증 모듈이다.

```powershell
python -m app.integrations.verify_transit --live --service subway-stations --station-name "서울"
python -m app.integrations.verify_transit --live --service bus-stations --station-name "서울역"
```

키는 명령 인자로 전달하지 않고 로컬 설정에서 프로그램이 로드한다. 로그는 service alias, operation, 시도/상태, 안전한 선택 필드만 출력한다. 요청 URL/params·전체 환경변수·원문 예외/업무 오류는 출력하지 않는다. API키 앞뒤 문자·길이·해시도 기록하지 않는다.

| 서비스 alias | 최초 검증 입력/대조 |
|---|---|
| subway-arrivals | 공식 역명 → 생성시각·ETA·단위·노선/방향. 예측과 실제 도착 구분 |
| subway-positions | 공식 호선명 → 위치·상태·열차 ID·생성시각; ETA 생성 금지 |
| subway-stations | 역명/코드 → STATION_CD/FR_CODE/호선과 검증된 범위 |
| subway-timetable | 검증한 STATION_CD/day tag/direction tag → 예정 시각·기종점·편 대응 |
| subway-last-train | 검증한 FR_CODE/day tag/direction tag → FL_FLAG 의미·막차 row 및 endpoint 현행성 |
| subway-path | OA-22724의 선택한 역명·검색일시·schInclYn=Y → 열차 시각/번호·기종점·방향·환승·대기, 단위·운행일·완전성 검증 |
| bus-stations | 이름 → stId/arsId/좌표. 첫·막차 기능은 선택한 arsId + busRouteId로 금일 정보 검증 |
| bus-routes | 공식 노선 검색 → busRouteId → getStaionByRoute 순서·구간·방향·WGS84 |
| bus-positions | 검증한 busRouteId/구간 순번 → 차량 ID·dataTm·위치/stopFlag |
| bus-arrivals | 검증한 busRouteId → 각 정류소의 mkTm·ETA(초)·차량·막차 flag |

각 서비스에서 성공 최소 한 번 후 필요한 기능별 사례를 실행한다. 이름 검색의 여러 후보는 운영자가 명확히 선택하고 코드/노선·방향을 대조한다. 동일 제공처의 관련 기능도 키 권한·응답을 별도 검증한다. OA-101/OA-110은 현재 입력한 칸의 값을 해당 공식 기능에만 사용하고 실패하면 서비스명/권한/명세를 확인한다. 키 조합을 무차별 시도하거나 다른 제공처로 전송하지 않는다.

한 검증 호출은 초기 1회와 허용 retry 최대 1회다. 성공 이후 추가 호출하지 않는다. 전체 서비스 반복·한도 소진·인증 오류 유발 테스트는 하지 않는다. 원문 값과 정규화는 프로그램 내부에서 대조하고 비밀 값 없는 선택 필드/판정만 증거에 남긴다. 정상 응답인지뿐 아니라 단위·타임존·운행일·방향·해당 범위도 확인한다.

## 5. 실제 약속·막차 수용 시나리오

서비스별 조회 성공을 완료한 뒤 다음 시나리오를 명시적으로 실행한다. 원점/목적지·운행일·노선은 실제 지원 근거를 확인한 것으로 선택하며 문서에서 가상의 운행시각을 정답으로 지정하지 않는다.

| 시나리오 | 최소 사례 | 기대 판정 |
|---|---:|---|
| 지하철 약속 | 1 | 조건 확인→실제 구간→후보, 목표 도착과 첫 승차 전 5분 한 번 |
| 버스 약속 | 1 | 동일 편/방향·승하차 시각 근거, 자료 부족이면 성공 보류 |
| subway→bus 약속 | 1 | 실제 보행 연결·최소시간·다음 편 승차 가능 |
| bus→subway 약속 | 1 | 같은 검증을 역방향에도 별도로 수행 |
| 지하철·버스 막차 | 각 1 | 요청 운행일의 마지막 연결·방향·기종점·최후/권장 출발 |
| subway→bus·bus→subway 막차 | 각 1 | 마지막 편마다 도보·대기·승하차 및 검색 완전성 |

자정 이후 실제 날짜, 연결 불가, 미지원 운행일, Buffer 부족을 각각 합성 경계로 재현한다. 자료 부족/검색 예산 초과를 NO_FEASIBLE_JOURNEY로 바꾸지 않는다. 임의 주소/건물 요청은 실제 역·정류소 선택을 안내한다.

확인 전 계산, revision 충돌/만료/중복, 제공처 실패와 재탐색 후 미선택도 회귀 검증한다. 실패는 기존 선택·TTL/revision을 바꾸지 않는다. 새 결과의 적용에는 사용자 선택이 필요하다. Mock/Demo fixture의 결과는 별도 표시하고 실제 완료 건수에서 제외한다.

백엔드 로컬 실행은 구현 후 backend 디렉터리에서 다음을 기준으로 하며 실제 환경 import 경로를 검증한다.

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

공개 요청 body와 MCP 도구 사용 흐름은 `API_SPEC.md`, `Docs/api/examples.json`, 기존 003을 따른다. 새로운 확인/선택 계약을 이 가이드에서 별도로 만들지 않는다. 상대 담당자의 MCP가 `basis_at`과 경고·실제/Demo를 보존하는지도 공동 검증한다. 이 계획에서는 Hermes 호출·배포 검증을 실행하지 않았다.

## 6. 증거와 전체 완료 판정

향후 `validation/live-report.md`에 실행일·실제 코드 버전/dirty 여부·안전한 서비스/작업·비밀 값 없는 입력·기준시각/조회시각·정규화 대조·지원 범위·판정·미실행 사유를 기록한다. 전체 URL이나 raw 응답을 자동 저장하지 않는다. key를 제거하지 못한 원문은 문서/저장소에 남기지 않는다.

합의 조회 기능 100%, 기본6 및 추가4 실제 성공, 지하철/버스와 양방향 혼합의 약속·막차, 실패/경계·시간/횟수·비밀 보호를 충족해야 전체 완료다. 외부 자료/명세가 부족하면 단계와 장애물을 남기며 통과로 표시하지 않는다. 서비스 catalog 확인, 사용자의 키 입력 완료, Mock 테스트 통과는 실제 호출·계획 성공을 대체하지 않는다.

현재 결과: **키 파일 입력 완료는 사용자 진술로 확인; 키 배정·실제 인증·정규화·약속·막차·회귀 테스트는 미실행.**
