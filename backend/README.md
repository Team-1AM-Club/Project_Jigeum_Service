# Backend scaffold

친구 담당: FastAPI, 서비스 Agent·Skill 실행, Solar·공공데이터 연결, 코드 기반 계산, Cloud Run 배포. 앱 서비스 선택 시 Supabase UserData·인증·권한도 담당한다.

현재 폴더와 역할 경계만 준비되어 있다. FastAPI 앱·의존성·실행 명령·테스트·배포 설정은 아직 구현하지 않았다.

- app/api: API_SPEC.md의 요청·응답 계약.
- app/agents: MainAgent·SubAgent 생성과 공통 Skill 원본 로딩.
- app/domain: 시간 계산, 상태·사용자 확인 정책.
- app/integrations: 모델, 공공데이터, 조건부 Supabase 연결.
- app/schemas: 입력·모델 출력·외부 데이터 검증.
- tests: 단위·계약·연동 테스트.

Docker는 패키징, Cloud Run은 HTTP 백엔드 실행 환경이다. 앱 서비스의 PostgreSQL 5432 연결은 서버→DB 연결이며 Cloud Run의 HTTP PORT가 아니다.

컨테이너 구현 시 공통 Skill 원본과 agent_specs를 어떻게 포함·로드할지 명시한다. 개발용 Hermes 홈·개인 메모리·API 키를 이미지에 복사하지 않는다.
