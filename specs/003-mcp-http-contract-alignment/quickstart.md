# 통합 검증 안내

**현재 상태**: 실행 가이드 제안. 이번 계획 작성에서는 서버·pytest·Hermes·교통 API를 실행하지 않았다. 아래 상태 경로와 MCP action은 구현 후 검증 대상이다.

## 1. 시작 조건

1. T001에서 양측이 [HTTP](contracts/http-contract.md)·[MCP](contracts/mcp-contract.md)·[상태 모델](data-model.md)과 개발 도구 조건 미충족의 처리 근거를 검토한다. U1 진단 필드·REQUEST_TIMEOUT 도입 여부를 합의하고 T002에서 공통 API/예제를 함께 개정한다. 문서 반영만으로 구현 게이트가 열리지 않는다.
2. 백엔드 담당자가 상태/멱등 테이블의 migration·초기화·정리와 라우터 연결을 구현한다. 새 검증 DB에서 필요한 모델이 모두 등록되는지 검사한다. 현재의 여러 DeclarativeBase와 미연결 초기화는 구현 단계에서 정리해야 하며 `uvicorn` 기동만으로 스키마 준비가 끝났다고 보지 않는다.
3. MCP 담당자가 실제 저장소 경로·진입점·의존성·버전을 제공한다. 연결 문서에 적힌 테스트 경로를 이 백엔드 저장소 경로로 추정하지 않는다.
4. 설치 Hermes에서 form elicitation, 대화별 별도 stdio 프로세스, 500초 host timeout을 확인한다. MCP 전체 상한은 480초, 사용자 입력 대기는 300초다.
5. 실제 데이터 검증은 004 담당자가 확인한 제공처·지원 범위·권한·설정이 있을 때 별도로 수행한다. 모의 fixture에 실제 키는 필요 없다.

실제 비밀키는 실행 환경에만 둔다. `Get-ChildItem Env:`처럼 전체 환경을 출력하거나 자격증명이 든 주소·설정을 통째로 기록하지 않는다.

## 2. 로컬 백엔드 준비와 실행

다음 명령은 Windows PowerShell, Python 3.11이 설치된 환경을 기준으로 한다. 기존 DB를 덮어쓰지 않도록 이번 검증 전용 경로를 사용한다. 최초 1회 의존성 설치 후 같은 환경을 재사용한다.

```powershell
Set-Location 'C:\Users\romai\Desktop\Develop\Project\Project_Jigeum_Service\backend'
py -3.11 -m venv .venv-003
& .\.venv-003\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = 'sqlite:///./jigeum-003-validation.db'
$env:ENVIRONMENT = 'development'
& .\.venv-003\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

이 명령은 `backend`를 작업 디렉터리로 사용한다. 현재 코드가 `from app...`로 import하기 때문에 기존 README의 `backend`로 이동한 뒤 `backend.app.main`을 지정하는 혼합 예제를 그대로 따르지 않는다. 상태 경로 구현·테이블 초기화 전이면 연결 점검만 성공할 수 있다. 별도 migration 실행법이 도입되면 합의된 명령을 이 가이드에 추가한 뒤 실행한다.

다른 PowerShell에서:

```powershell
$apiBase003 = 'http://127.0.0.1:8000/api/v1'
Invoke-RestMethod -Uri "$apiBase003/health" -Headers @{ Accept = 'application/json' }
Invoke-RestMethod -Uri "$apiBase003/capabilities" -Headers @{ Accept = 'application/json' }
```

기대 결과는 유효 envelope다. health 성공은 provider나 모델 연결 성공을 의미하지 않는다. mock이면 meta.is_demo=true여야 한다.

## 3. 기존 테스트와 추가할 집중 검증

구현한 뒤 `backend`에서 실행한다. 다음 경로는 기존 파일을 확인했다. 현재 코드가 이 제안을 통과한다고 주장하지 않는다.

```powershell
& .\.venv-003\Scripts\python.exe -m pytest tests/contract/test_conversations.py tests/contract/test_journeys_plan.py tests/contract/test_journeys_plan_last_journey.py tests/contract/test_journeys_replan.py tests/contract/test_replan_service_contract.py tests/integration/test_conversations_e2e.py tests/integration/test_journeys_plan_e2e.py tests/integration/test_replan_e2e.py tests/integration/test_last_journey_e2e.py
```

V01~V12의 누락 사례를 해당 테스트 계층에 추가한 다음 실행한다. 새 테스트 파일명이 정해지지 않은 상태에서 존재하는 명령처럼 기재하지 않는다. 특히 동시성은 독립 DB Session과 barrier를 써서 같은 revision·같은 키 경쟁을 실제로 만든다. 외부 provider 대기 동안 DB 쓰기 트랜잭션이 유지되지 않는지도 검사한다.

## 4. fixture HTTP 요청 사용법

[examples.json](contracts/examples.json)은 완성된 HTTP body와 별도의 headers를 담은 **가상 계약 fixture 20건**이다. 각 case의 preconditions를 구성하고 server_time을 동결한 테스트 서버에만 그대로 전송한다. 과거 운행일과 시작시각을 현재 실제 서버에 보내 성공을 기대하지 않는다.

`cases` 밖의 `fault_scenarios`는 응답 파손·시간 제어를 위한 장애 주입 절차다. 유효한 backend 응답 fixture와 구별한다. `proposed_error_examples`는 T001에서 확정할 오류 예제이며 합의 전 일반 HTTP 회귀의 확정 기대값으로 사용하지 않는다.

조건을 구성한 fixture 서버에서 초기 요청의 전송 형식을 확인하는 예:

```powershell
$cases003 = Get-Content -Raw -Encoding UTF8 '..\specs\003-mcp-http-contract-alignment\contracts\examples.json' | ConvertFrom-Json
$case003 = $cases003.cases | Where-Object id -EQ 'initial_ready'
$headers003 = @{}
$case003.request_headers.PSObject.Properties | ForEach-Object { $headers003[$_.Name] = $_.Value }
$body003 = $case003.request_body | ConvertTo-Json -Depth 30 -Compress
$result003 = Invoke-WebRequest -Uri ($apiBase003 + $case003.path) -Method Post -Headers $headers003 -Body ([System.Text.Encoding]::UTF8.GetBytes($body003)) -UseBasicParsing
$result003.StatusCode
$result003.Headers['Idempotency-Key']
$result003.Content | ConvertFrom-Json
```

서버 생성 conversation_id·confirmation_id·후보 ID는 이후 실제 HTTP 요청에서 **관측값으로 치환**한다. 테스트에서 ID 생성기를 고정한 경우에만 fixture의 고정 ID와 비교한다. 같은 논리 요청의 replay에는 치환 후 최초로 보낸 body 문자열과 키를 그대로 보관해 사용한다. 다른 case의 예제 본문으로 대체하면 같은 요청이 아니다.

직접 REST로 synthetic evidence를 보내는 테스트는 서버 계약 검증이다. 실제 사용자의 승인 증거로 기록하지 않는다. 실제 승인 검증은 아래 Hermes 단계에서 수행한다.

## 5. 검증 시나리오와 요구사항 연결

| ID | 재현·검사 | 요구사항·성공 기준 |
|---|---|---|
| V01 | 5개 도구 discovery, GET query 인코딩, nested 요청/응답, 약속 interpret→confirm→plan→select | FR-001/002/003/008/019, SC-001 |
| V02 | elicitation 미지원·decline·cancel·timeout, boolean/evidence 위조 입력 거부, 조건 변경 후 과거 확인 거부. provider 호출 0회 | FR-004, SC-002 |
| V03 | 다른 대화 ID/후보/승인 혼용, stale revision, 두 독립 세션 동시 갱신. 최신 상태를 늦은 응답이 덮어쓰지 않음 | FR-005/006/016, SC-002 |
| V04 | 초기 성공 응답 유실·동시 재전송·다른 body/path·commit 예외. confirm/plan/select commit 뒤 첫 응답 파손→보류→명시적 resume→성공 replay의 적용 총 1회, 확정 실패 0회 | FR-013/014, SC-003 |
| V05 | connect error·timeout·유효 retryable 502/503/504만 500ms 뒤 추가 1회. 4xx/409/410/false/invalid JSON·schema/key/status는 0회. 첫 깨진 POST부터 OUTCOME_UNKNOWN·GET 외 새 변경 차단·키/body/revision 보존. GET 파손은 새 변경 보류 없음 | FR-013/015/017, SC-003/004 |
| V06 | 초안30분/확인2시간/선택 ETA+2시간/상한48시간·후보·tombstone24시간 경계와 오래된 초기 요청 차단. GET/replay/실패의 TTL 연장 없음. 보류 중 만료를 과거 미적용으로 단정하지 않음 | FR-007/013/014/016, SC-002/003 |
| V07 | 현재 출발점 변경→새 조건 확인→replan. 미선택/취소/실패에서 기존 선택 유지, 명시적 select만 교체. 18:50→19:10은 변화20분·19:00 대비 지각10분 | FR-010/011/012, SC-005 |
| V08 | trip.kind=last_journey, 운행일과 다음 날 도착. 지원/미지원/경로 없음/여유 부족을 각각 검증 | FR-009, SC-006 |
| V09 | 모의 HTTP·실제 백엔드·실제 provider를 구분. HTTP가 demo를 반환해도 표시 유지. 실제 실패의 demo fallback 0회 | FR-017/018, SC-007 |
| V10 | provider 대기 중 revision 변경/만료, 서버 3/10/25초 직전·동일·초과, 늦은 미확정 결과 적용 0회. 실패의 상태/revision/updated_at/TTL 갱신 0회, 이미 commit한 성공의 지연 응답은 보존·중복 적용 0회 | FR-012/016, SC-002/005/008 |
| V11 | T062: 실제 Hermes 약속 accept/decline/cancel/timeout·직접 선택·대화 A/B 분리·mode 거부·첫 파손 보류→동일 키 resume. T055: 확장 인수·약속 회귀. 재시작 복원 미보장 | FR-004/005/013/020/021, SC-001/003/008 |
| V12 | T063: 확장 전 실제 약속 1건의 승인·출처·시각·non-demo·선택 증거. 이후 다른 담당자가 약속/재탐색 재현. 개발/작성/시연 출처 구별·비밀 제거·미실행 성공 표기 0건 | FR-019/020/021, SC-001/007/008 |

### V04/V05/V06 — 적용 불명 복구

서버의 confirm/plan/select commit을 관측한 뒤 최초 HTTP 응답에 JSON 파손·필수 schema 누락·키 불일치·status 불일치를 각각 주입한다. 자동 추가 시도 0회, OUTCOME_UNKNOWN과 안전한 원인 진단, 원본 요청 보존, GET 허용·새 변경 REQUEST_PENDING을 확인한다. 직접 elicitation 승인 후 resume POST 1회로 같은 키·본문·revision·시각을 전송하고 유효 성공 replay로 총 적용 1회를 확인한다. GET으로 최신 revision을 먼저 봤어도 오래된 replay가 이를 낮추지 않아야 한다.

유효한 서버 UPSTREAM_RESPONSE_INVALID는 미적용 확정 오류 사례로 별도 검사한다. 보류 중 대화가 만료되면 과거 결과를 복원하거나 미적용이었다고 설명하지 않는다. replan/select의 같은 장애는 확장 후 T048에서 검사한다.

### V10 — T064 서버 시간 경계

백엔드 담당자는 T004에서 실제 timeout 구현·원자 확정·테스트 파일 경로와 실행 명령을 이 절에 기록한 뒤 기존 처리를 재사용한다. 현재 해당 경로 조사·런타임 검증은 미실행이다. 측정 범위는 [HTTP 계약 §4](contracts/http-contract.md)를 따른다.

- 시간 제어 가능한 clock으로 health/capabilities 3초, places 10초, interpret/plan/replan 25초의 직전·동일·초과를 검증한다. provider 각 호출이 전체 예산을 새로 받지 않는지 확인한다.
- 공통 deadline 및 약속 경로를 T064에서, 기존 replan 진입점은 제어된 workflow로 검사한다. US4 구현 후 실제 replan 전 경로는 T048에서 다시 검증한다.
- 미확정 timeout 후 상태·revision·updated_at·TTL 및 늦은 결과 적용이 모두 갱신되지 않아야 한다. 자연 만료는 별도 구분한다. confirm 성공 뒤 plan 실패는 plan 직전 상태와 비교한다.
- 제한 전 commit 후 응답만 지연시키는 사례는 최초 성공 기록 유지와 replay의 중복 적용 0회를 확인한다. 취소 신호만 확인하거나 실시간 sleep만으로 경계 통과를 주장하지 않는다.
- REQUEST_TIMEOUT과 MCP 진단 필드의 wire 형식은 T001 합의값으로 검증한다. 합의 전 예제는 권장안이다.

## 6. 실제 Hermes와 실데이터 인수 순서

1. 실제 MCP 저장소의 설치 안내로 서버를 설치한다. `JIGEUM_API_BASE_URL`은 `/api/v1`을 포함한 로컬 주소다. FastAPI 주소를 원격 MCP URL로 설정하지 않는다.
2. Hermes의 stdio command/args는 확인된 MCP 실행 진입점으로 지정한다. 도구 5개 discovery와 elicitation capability를 확인하고 프로세스를 대화마다 분리한다.
3. `hermes chat`에서 get_capabilities를 실제 호출한다. HTTP 요청과 받은 envelope를 연결해 확인한다. 일반 채팅의 “연결됐다”는 문장은 증거가 아니다.
4. US1 기본 흐름·US2·US3(T064/T041 포함) 통과 후 T062에서 실제 사용자 약속 승인·거절·취소·timeout·직접 선택·프로세스 분리·resume을 검증한다. 가상 데이터와 실제 사람 승인을 구별하고 가짜 approval client를 배제한다.
5. T063에서 같은 로컬 Hermes→MCP→FastAPI 흐름에 004의 검증된 약속 provider를 연결한다. 장소 확인→실제 승인→출발·도착·근거 표시→선택 1건 이상을 완료한다. 날짜·장소는 당시 지원 범위·서버 시각에 맞게 사용자가 지정하며 retry는 최초 요청을 보존한다. 출처·기준시각·is_demo=false를 확인한다. 막차 자료 준비에는 의존하지 않는다.
6. T063 통과 후 US4 재탐색·US5 막차를 확장하고 T055/T056에서 확장 인수와 약속 회귀를 수행한다. Hermes 또는 약속 제공처가 미준비면 약속 모의·실패 검증은 계속하되 확장과 실제 인수는 보류한다. 실제 막차 자료가 없으면 SC-006 실데이터 인수는 미완료다.

기록 항목: 양측 commit SHA와 미커밋 변경 여부, 실제 Base URL, Python/MCP SDK/Hermes/모델 식별자, 시험 시각·조건·기대/관측 결과, meta.is_demo, 출처·기준시각, 실행하지 못한 항목. 자격증명·전체 환경·원문 개인정보는 수집하지 않는다.

## 7. 계획 단계의 검증과 다음 단계

계획 문서의 점검 결과는 [plan-review.md](checklists/plan-review.md)에 둔다. 이번 단계의 성공은 문서·예제 정합성에 한정한다. 64개 작업은 [tasks.md](tasks.md)에 있으며 T001/T002와 실제 경로·환경 게이트를 해소한 뒤 구현한다. 004를 가리키는 활성 설정은 보존하고 후속 Spec Kit 대상 경로를 003으로 명시한다. 실제 시연 성공과 개발 도구 조건·제출 적합성은 별개로 판정한다.
