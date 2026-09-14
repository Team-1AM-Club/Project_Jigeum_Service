# 친구용 백엔드 인수인계 — 공통 시작점

## 이번 공유 범위

이 인수인계 커밋은 공통 문서·API 계약·폴더 골격만 제공한다. 제품은 **MCP 서비스**이며 별도 사용자 화면은 개발하지 않는다.

- 포함: 제품 방향, 분업, REST 계약과 예제 JSON, Agent 역할, Spec Kit 명세, 백엔드 준비 폴더.
- 미포함: 작성자의 작업 중 백엔드 코드와 테스트, MCP 구현, Skill ZIP, 개인 Hermes 설정, 디버그 파일, 비밀키.
- backend/app/main.py와 backend/Dockerfile은 자리표시자다. 실행 가능한 서버·이미지가 아니다.
- .hermes/skills/는 준비 폴더다. 실제 원본 반입·검토·연결·실행 검증은 별도 작업이다.
- 이 문서는 실행·테스트·배포 완료를 뜻하지 않는다.

## 작업 경로와 시작 방법

저장소: https://github.com/Team-1AM-Club/Project_Jigeum_Service
공통 기준 브랜치: develop

처음 받는 경우:

~~~sh
git clone --branch develop https://github.com/Team-1AM-Club/Project_Jigeum_Service.git
cd Project_Jigeum_Service
git switch -c feature/backend-mvp
~~~

이미 복제한 저장소가 있으면 새로 복제하거나 초기화하지 않는다. 먼저 git status로 자신의 미커밋 작업을 확인하고 보존한 후 develop의 최신 변경을 반영한다.

친구의 주 작업 경로는 **<저장소 루트>/backend/**다. 작성자 PC의 예시는 E:/MABC/backend/이며 친구 PC에서 같은 절대 경로를 만들 필요는 없다.

| 경로 | 친구가 구현할 내용 |
|---|---|
| backend/app/main.py | FastAPI 진입점과 라우터 연결 |
| backend/app/api/ | API 라우트와 공통 응답·오류 처리 |
| backend/app/schemas/ | 요청·응답·외부 데이터 검증 |
| backend/app/domain/ | 시간 계산·Buffer·조건 확인 정책 |
| backend/app/integrations/ | 장소·교통·Solar 어댑터, demo/live 분리 |
| backend/app/agents/ | MainAgent·SubAgent 실행 조율 |
| backend/tests/unit/ | 계산·시간대·경계 조건 테스트 |
| backend/tests/contract/ | API 계약·예제 JSON 검증 |
| backend/tests/integration/ | 최소 흐름과 제공처 연동 검증 |

.gitkeep은 빈 폴더를 Git으로 공유하기 위한 파일이며 구현 완료 표시가 아니다.

## 먼저 읽을 문서

1. [IDEA.md](../IDEA.md): 최신 제품 범위와 역할.
2. [API_SPEC.md](../API_SPEC.md), [예제 JSON](api/examples.json): 공동 통합 기준. 예제는 가상 데이터다.
3. [Agent 역할](../agent_specs/README.md): 해당 MainAgent·SubAgent 명세.
4. [기능 명세](../specs/001-trip-intake-and-planning/spec.md), [계획](../specs/001-trip-intake-and-planning/plan.md), [작업 목록](../specs/001-trip-intake-and-planning/tasks.md).

이전 Skill 예시는 현재 MVP의 필수 구현 목록이 아니다. 충돌 시 IDEA.md와 API_SPEC.md를 우선하고, 관련 명세를 함께 정정한다.

## 분업 경계와 연결 계약

본인은 MCP 도구·HTTP 연결·Hermes 확인/선택 흐름·시연을 담당한다. 친구는 FastAPI·Agent·Skill·교통 데이터·계산·테스트·배포를 담당한다. Hermes + Upstage Solar Pro4를 개발·시연에 사용한다.

| 본인 MCP 도구 | 친구 백엔드 HTTP API |
|---|---|
| get_capabilities | GET /api/v1/capabilities |
| search_places | GET /api/v1/places |
| interpret_trip | POST /api/v1/mobility/interpret |
| plan_journey | POST /api/v1/journeys/plan |
| replan_journey | POST /api/v1/journeys/replan |

health는 내부 연결 확인용이다. 정확한 경로·필드·상태·오류 의미는 API_SPEC.md를 따른다. MCP 도구 스키마와 결과/오류 매핑은 아직 별도 합의·검증이 필요하다.

## 첫 작업 순서

1. Python 환경·의존성·실행 진입점을 준비하고 검증한 설치/실행 명령을 backend/README.md에 기록한다.
2. health와 capabilities를 계약대로 구현해 실제 HTTP 응답을 제공한다. 본인은 get_capabilities 연결을 검증한다.
3. 요청·응답 스키마와 명시적인 demo 어댑터를 마련해 두 사람의 JSON 계약을 맞춘다.
4. 장소 확정 → 조건 해석 → 사용자 최종 확인 → 약속 출발시각 계산의 최소 흐름을 연결한다.
5. 실제 제공처의 지원 범위·응답·출처·기준시각을 검증한다. 운영 조회 실패를 demo로 자동 대체하지 않는다.
6. 검증 가능한 범위에서 막차·사용자 요청 재탐색을 추가하고 계산·계약·통합 테스트를 실행한다.

## 구현 전에 함께 확정할 것

- API 변경 시 API_SPEC.md와 Docs/api/examples.json을 함께 갱신한다.
- Base URL, 포트, 접근 제어, 환경변수 이름, 정확한 Solar 모델 ID/호출 경로.
- MCP 도구 입력 스키마·결과/오류 매핑·HTTP 시간 제한.
- 사용자 확인과 확인된 조건의 연결, 대화 문맥의 소유권·수명, 후보 선택 상태.
- ready_for_plan=true는 사용자 동의가 아니다. 모델이 user_confirmed=true를 넣었다는 사실만으로 실제 확인을 받았다고 간주하지 않는다.
- 재탐색 결과 조회와 새 계획 적용은 별개다. 사용자 선택 전 기존 계획을 교체하지 않는다.
- 지원 지역·노선·운행일·데이터 최신성, Buffer 정책과 중복 계산 방지.

택시 최적화·비용 상한, 영구 UserData DB·회원가입, 자동 위치 추적·자동 알림은 현재 필수 범위가 아니다. 키는 저장소나 대화에 공유하지 않고 각자 환경 또는 합의된 비밀 관리 경로로 설정한다.

## 첫 인수인계 결과물

친구는 검증된 서버 실행 명령, Base URL, 지원 기능과 데이터 모드, 테스트 실행 결과·미완료 항목을 전달한다. 두 사람은 Hermes → MCP → FastAPI 호출 기록을 함께 확인한다. 구현 코드는 기능 브랜치에서 검토한 후 develop에 통합하며, 이번 공통 시작점을 완성된 서비스로 소개하지 않는다.
