# MCP 서비스의 계산 백엔드

친구 담당: FastAPI, 서비스 Agent·Skill 실행, Solar·공공데이터 연결, 코드 기반 계산, Cloud Run 배포. 사용자에게 제공되는 제품은 MCP이며 이 백엔드는 MCP 도구의 요청을 처리한다. 본인은 MCP·Hermes 연결과 시연을 담당한다.

이번 공유본은 공통 계약과 폴더 골격이다. 작성자 로컬의 작업 중 백엔드 코드·테스트는 포함하지 않으며, 공유된 app/main.py와 Dockerfile은 자리표시자다. 의존성 설치·서버 실행 명령은 구현 후 검증해 추가한다.

작업 시작 순서와 공동 합의 항목은 [백엔드 인수인계 안내](../Docs/BACKEND_HANDOFF.md)를 따른다.

- app/api: API_SPEC.md의 요청·응답 계약.
- app/agents: MainAgent·SubAgent 생성과 공통 Skill 원본 로딩.
- app/domain: 시간 계산, 상태·사용자 확인 정책.
- app/integrations: 모델·장소·공공데이터 연결. UserData DB는 현재 필수 범위가 아니다.
- app/schemas: 입력·모델 출력·외부 데이터 검증.
- tests: 단위·계약·연동 테스트.

Docker는 패키징, Cloud Run은 HTTP 백엔드 실행 환경이다. 로컬 stdio MCP 서버는 이 HTTP 백엔드와 별도 실행 경계다. 백엔드의 비밀키를 Hermes 대화·설정 예제·로그에 노출하지 않는다.

컨테이너 구현 시 공통 Skill 원본과 agent_specs를 어떻게 포함·로드할지 명시한다. 개발용 Hermes 홈·개인 메모리·API 키를 이미지에 복사하지 않는다.
