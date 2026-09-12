# 지금 (Jigeum)

약속과 막차의 마감시각을 기준으로 출발해야 할 순간과 다음 행동을 알려주는 AI 서비스.

## 현재 상태

이 저장소는 **제품 문서와 디렉토리 scaffold** 단계다. 실행 가능한 앱·CLI·서버, Agent 런타임, 실제 Skill 원본은 아직 포함하지 않는다. `.gitkeep`은 빈 폴더를 Git으로 공유하기 위한 파일이며 구현 완료를 의미하지 않는다.

월요일 멘토링에서 모바일 앱 또는 CLI 제출을 결정한다. 둘 다 구현하는 것을 기본 범위로 두지 않는다.

## 읽는 순서

1. [IDEA.md](IDEA.md): 최신 제품 방향·확정 사항·조건부 범위
2. [API_SPEC.md](API_SPEC.md): 공통 계산 API 초안
3. [agent_specs/README.md](agent_specs/README.md): MainAgent·SubAgent 역할 초안
4. [Docs/api/examples.json](Docs/api/examples.json): 가상 데이터 기반 계약 예제

과거 Docs 제안과 최신 IDEA.md가 다르면 제품 범위는 IDEA.md를 따른다. 앱 서비스로 결정되면 UserData·인증·권한·저장 API를 함께 구체화해야 한다.

## 구조

```text
.hermes/skills/       기존 Skill 원본을 가져올 위치 (현재 폴더만 준비)
agent_specs/         실행 Agent 역할 명세 (자동 등록 파일 아님)
backend/app/api/     FastAPI 요청·응답
backend/app/agents/  MainAgent·SubAgent 실행·Skill 연결
backend/app/domain/  코드 기반 시간 계산·상태 규칙
backend/app/integrations/  모델·공공데이터·DB 연결
backend/app/schemas/ 구조화 데이터 검증
backend/tests/      서버 테스트
mobile/             앱 선택 시 Expo 프로젝트
cli/                CLI 선택 시 클라이언트
.specify/           기존 Spec Kit 설정·템플릿·스크립트
specs/              기능별 명세·계획·작업
Docs/               기존 PRD·제안서·예제
```

## 분업과 기술

- 본인: 앱. CLI 선택 시 클라이언트 입출력·패키징.
- 친구: FastAPI, MainAgent·SubAgent·Skill, 모델·교통 API, 시간 계산, 배포. 앱 서비스 선택 시 Supabase UserData·인증·권한.
- 공동: API 계약, Spec Kit 활용, 통합 검증, 제출 자료.
- Docker는 컨테이너 패키징, Cloud Run은 백엔드 실행·배포 환경이다.
- 교통 데이터 제공처는 서울시 공공데이터 포털·공공데이터 포털이다. API 키는 발급 완료 상태이나 저장소에 포함하지 않는다.

## 다음 작업

1. 팀이 보유한 실제 Skill 파일을 `.hermes/skills/<name>/`에 가져와 도구·입출력 호환성을 검증한다.
2. 설치된 Hermes 버전과 프로젝트 Skill 탐색·신뢰 설정을 확인한다. 역할 Markdown만으로 SubAgent가 자동 생성되지는 않는다.
3. Spec Kit에서 공통 계약과 첫 약속 이동 흐름의 작업을 정의한다. 기존 `.specify` 파일은 보존한다.
4. 실제 공공데이터 응답과 지원 범위를 확인한 뒤 서버·선택한 클라이언트를 구현한다.

아직 실행 명령이나 배포 성공을 보장하지 않는다. `backend/Dockerfile`은 안내용 자리표시자이며 빌드 가능한 이미지가 아니다.
