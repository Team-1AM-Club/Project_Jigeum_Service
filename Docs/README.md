# 지금 — MCP 서비스 문서 안내

**서비스는 MCP로 제공한다.** Hermes + Solar Pro4는 개발·시연용 MCP 클라이언트다. 별도 제품 화면이나 설치형 사용자 클라이언트를 개발하는 계획은 없다.

- 본인: MCP 도구 5개, 백엔드 연결, 조건 확인·후보 선택 흐름, Hermes 설정·통합 검증·시연.
- 친구: FastAPI, MainAgent·SubAgent·Skill, 장소·교통 데이터, 시간 계산·재탐색, 테스트·배포.
- 공동: API·MCP 계약, 확인·문맥·선택 상태, 지원 범위와 제출 자료.

친구의 작업 시작 경로와 공유 범위는 [백엔드 인수인계 안내](BACKEND_HANDOFF.md)를 참고한다.

## 현재 개발 문서

1. [IDEA.md](../IDEA.md): 제품 범위·분업·4일 일정·완료 기준의 기준 문서
2. [API_SPEC.md](../API_SPEC.md): 기존 REST 계산 계약. MCP 도구가 호출하는 내부 API
3. [MCP 4일 분업 계획](jigeum_4day_mvp_team_plan_v0.1.md): 두 사람의 실제 작업·통합·시연
4. [MCP 서비스 PRD](jigeum_prd_v1.0.md): 제품 요구와 현재 MVP·후속 확장 구분
5. [MCP Agent·Skill 제안](jigeum_agent_skills_proposal_v0.1.md): 내부 Agent·코드 도구·Skill 책임
6. [Spec Kit 명세](../specs/README.md): 기능별 명세·계획·작업

기존 파일명은 참조 보존을 위해 유지했으며, 위 서비스 문서의 본문은 MCP 방향으로 갱신했다.

## Timely 예선 자산

timely_로 시작하는 문서는 예선 Skill의 생성 프롬프트·테스트·제출 서술이다. 당시 본인/친구의 개별 Skill 담당 구분은 현재 MCP/백엔드 개발 분업과 별개다. 이 문서들에 있는 Calendar·GPS·자동 알림·택시 관련 독립 기능을 현재 MVP 필수 요구로 해석하지 않는다.

실제 Skill 원본은 .hermes/skills에서 관리하고 새 런타임의 도구·입출력을 재검증한다. 문서 저장이나 Timely 대화 테스트만으로 MCP 연결·실제 교통 연동·배포 완료를 주장하지 않는다.
