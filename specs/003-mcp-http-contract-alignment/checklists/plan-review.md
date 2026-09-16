# 003 계획 검토 기록

대상: [plan.md](../plan.md). 작성일: 2026-09-16. 검토용 제안이며 구현 인수 기록이 아니다.

## 범위와 사용자 결정

- [x] 003을 대상으로 하며 004와 공통 계약 원본은 변경하지 않는다.
- [x] Hermes 구조화 승인, MCP 5개+내부 상태 경로, 로컬 통합을 반영했다.
- [x] 단계별 TTL과 대화마다 별도 MCP 프로세스라는 답변을 반영했다.
- [x] 원격 인증·상태 공유, 실제 교통 provider 구현은 별도 게이트다.
- [x] 실제 사용한 작성 도구와 실제 시연 모델을 구별했다.

## 설계 범위

- [x] 요청/응답·상태·오류·헤더와 키·revision 전달 위치를 정의했다.
- [x] 최초 응답 유실, 동시 중복, 오래된 키, 대화/후보 만료를 구분했다.
- [x] 조건 확인과 계산, 후보 생성과 선택의 commit을 분리했다.
- [x] retry 예산, HTTP timeout, 사용자 대기와 전체 호출 상한을 연결했다.
- [x] 공개 문서·002 계약·MCP 스키마·테스트의 변경 영향을 정리했다.
- [x] FR-001~021와 SC-001~008을 V01~V12에 연결했다.

## 최초 계획 작성 시 검증 기록

다음은 문서·fixture의 정적 점검이다. 실제 backend·Hermes·교통 조회·기능 테스트는 이번 계획 작성에서 실행하지 않았다.

- [x] 신규 문서·예제 8개: UTF-8 읽기, 마지막 개행, 줄끝 공백 및 미해결 템플릿 잔여 점검.
- [x] 문서 상대 링크 26개와 공통 fixture 참조 경로의 존재 확인.
- [x] JSON 예제 20건: 유일 ID, UUIDv4 요청 키, 응답 헤더 반향, 본문과 키 분리, envelope/HTTP 상태, demo 표시, 후보 수와 권장 ID 검사.
- [x] 최초 응답 유실·계산 재생의 요청/응답 동일성 및 과거 replay revision 보존 검사.
- [x] 확인 조건 SHA-256과 계획 trip의 canonical hash 일치 검사.
- [x] FR-001~021 및 SC-001~008이 검증 시나리오에 모두 연결됨을 확인.
- [x] API_SPEC, 공통 examples, 원본 spec, feature marker, setup-plan/common 스크립트의 작업 전후 SHA-256 일치 확인.

첫 추적성 점검기는 `FR-001/002` 형태의 축약 표기 중 첫 번호만 읽어 일부 요구사항을 누락으로 보고했다. slash로 이어진 번호까지 해석하도록 점검기를 보정한 뒤 FR 21개·SC 8개 전체 대응을 확인했다. 이 결과는 기능 테스트 통과 수치가 아니다.

독립 문서 검토에서 재탐색의 새 초안과 confirm 생략 조건이 혼동될 수 있음을 지적받아, 출발점 변경/새 초안 경로의 새 confirm 필수와 변경 없는 확인 재사용 경로를 분리해 명시했다. 상태 TTL·초기 응답 유실·전체 시간 예산도 검토했다.

## 실행 경계와 설정 보존

기본 `setup-plan.ps1 -Json`은 FEATURE_DIRECTORY 환경 변수를 지정하면 `.specify/feature.json`에 저장한다. 다른 작업의 004 설정을 보존하기 위해, 메모리에서만 호출을 `Get-FeaturePathsEnv -NoPersist -ReturnNullOnError`로 바꾼 setup-plan의 동작을 실행했다. common.ps1은 절대 경로로 로드했다. 파일의 스크립트 원본은 수정하지 않았다.

기존 템플릿 구조로 작성한 003 plan이 있어 template copy는 건너뛰었고, setup 결과는 FEATURE_SPEC/IMPL_PLAN/FEATURE_DIR 모두 003, BRANCH는 `feature/mcp-server-integrate`였다. 종료 코드는 0이며 호출 전후 004 feature marker는 같았다. 표준 스크립트를 수정 없이 실행했다고 보고하지 않는다.

before_plan과 after_plan 모두 `.specify/extensions.yml`이 없어 건너뛰었다. commit·push·공통 계약 개정·구현·배포는 이번 작업에서 수행하지 않았다.

## 상위 4건 수정 반영 — 2026-09-16

사용자 답변에 따라 003 관련 문서를 함께 동기화했다. 공통 API·공통 예제는 공동 합의 작업으로 남기며 MCP 진단 필드와 REQUEST_TIMEOUT은 T001 합의 전까지 미확정 권장안이다. 위 최초 검증의 파일 수·링크 수·원본 spec 보존은 당시 기록이며 이번 수정 상태를 뜻하지 않는다.

- [x] C1: II-a 설계 경계, II-b 개발 도구 조건 미충족, II-c 실제 시연 미검증을 분리했고 전체 헌법 게이트를 통과로 표시하지 않았다.
- [x] C2: T041→T062 실제 Hermes 약속→T063 실제 데이터 약속→US4→US5 순서를 계획·작업·quickstart에 반영했다. 막차 제공처 준비를 T063 선행 조건으로 두지 않았다.
- [x] U1: 첫 깨진 POST 응답도 자동 재시도 0회·OUTCOME_UNKNOWN 보류·원본 resume으로 처리한다. 유효 서버 오류와 MCP 원인 진단, GET 실패, 만료 종료를 구분했다.
- [x] G1: T064에 백엔드 담당·T004 기존 경로 조사·3/10/25초 경계·원자 확정·늦은 commit 차단을 명시했다. T041 이전 공통/약속 검증과 T048의 확장 replan 검증을 구별했다.
- [x] 작업 64개와 T001~T064 ID의 유일성·누락 없음, 대상 경로 표기, 14개 병렬 후보를 확인했다. US1 13·US2 8·US3 9·US4 8·US5 8·공통 18개다. 추가 ID는 의존성 순서에 배치했다.
- [x] JSON 파싱, 기존 HTTP 사례 20개·장애 시나리오 4개·별도 오류 예제 2개의 ID/참조를 검사했다. 새 오류 예제의 키 반향·기대 revision·기존 만료시각 보존을 확인했다. 실제 fixture 실행 결과가 아니다.
- [x] 공통 API_SPEC·Docs/api/examples.json·헌법·004 feature marker의 SHA-256이 작업 전후 같았다.

setup-plan/setup-tasks는 NoPersist 메모리 변형으로 실행했고 종료 코드 0, FEATURE_DIR은 003이었다. 이번 출력의 BRANCH는 기능 이름 `003-mcp-http-contract-alignment`이며 Git 브랜치 전환을 의미하지 않는다. 기존 plan은 보존돼 template copy를 건너뛰었고 원본 스크립트를 고치지 않았다. before/after plan/tasks 확인 시 extensions.yml이 없어 실행할 hook은 없었다.

### 남은 게이트와 미실행 검증

- [ ] T001 개발 도구 조건 처리 근거 및 공동 계약 합의. 이 기록은 예외 승인이 아니다.
- [ ] T001 MCP `diagnostics.cause_code`의 정확한 wire 위치·필드와 REQUEST_TIMEOUT 도입 여부 확정, T002 공통 문서 동기화.
- [ ] T003 실제 MCP 경로·T004 기존 timeout 구현/테스트 경로·T005 설치 환경 확인.
- [ ] 코드 구현, 서버 처리 제한·복구 런타임 테스트, T062/T063 실제 Hermes·실데이터 약속 인수.

이번 검토는 문서 정합성에 한정한다. 서버·pytest·교통 제공처·배포는 실행하지 않았다.
