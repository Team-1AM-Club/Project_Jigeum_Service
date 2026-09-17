# 지금 (Jigeum) — 이동 판단 MCP 서비스

약속과 막차의 마감시각을 기준으로 출발해야 할 순간과 다음 행동을 MCP 도구로 제공한다.

## 확정된 서비스 형태

**서비스 자체를 MCP로 제공한다.** MCP는 별도 제품 출시 전 임시 시연 수단이 아니다. 독립 사용자 클라이언트는 개발하지 않는다.

Hermes + Upstage Solar Pro4를 개발과 시연에 사용한다. Hermes는 서비스가 연결되는 MCP 클라이언트이며, FastAPI는 MCP 도구를 지원하는 내부 계산 백엔드다. 다른 MCP 클라이언트의 호환성은 별도 검증이 필요하다.

```text
사용자 ↔ Hermes + Solar Pro4 ↔ 지금 MCP 서버 ↔ FastAPI ↔ 검증된 교통 데이터
```

MVP는 로컬 stdio 연결부터 검증한다. 원격 제공 방식·접근 제어와 제출 요구 사항은 별도로 확인하며, 제품 형태를 다시 독립 클라이언트 형태를 선택하지 않는다.

## 현재 상태와 읽는 순서

이번 공통 인수인계 기준에는 문서·API 계약·폴더 골격만 포함한다. 작성자의 로컬 작업 중 코드·테스트·Skill ZIP·개인 설정은 포함하지 않는다. backend/app/main.py와 Dockerfile은 자리표시자이며 실행 가능한 서버가 아니다. 이후 구현·테스트·배포 상태는 실행 결과로 별도 확인한다.

친구는 [백엔드 인수인계 안내](Docs/BACKEND_HANDOFF.md)를 확인하고 자신의 저장소 루트 아래 backend/에서 시작한다.

1. [IDEA.md](IDEA.md): 최신 제품 방향·범위·분업·완료 기준
2. [API_SPEC.md](API_SPEC.md): MCP 연결 계층이 사용하는 REST/JSON 계산 계약
3. [agent_specs/README.md](agent_specs/README.md): 서비스 Agent 역할
4. [specs/README.md](specs/README.md): Spec Kit 명세·계획·작업
5. [Docs/api/examples.json](Docs/api/examples.json): 가상 데이터 기반 계약 예제

Docs의 서비스 PRD·Agent 제안·4일 분업안도 MCP 제공 방향을 명시한다. Timely 문서는 예선 Skill 자산과 당시의 개별 기능 설명이며 현재 구현 지시는 IDEA.md의 MCP 범위를 따른다.

## 구조와 책임

- .hermes/skills/: Skill 원본의 단일 저장 위치. 원본이 없으면 준비 상태다.
- agent_specs/: 서비스 MainAgent·SubAgent 역할 명세
- backend/app/: FastAPI, Agent, 스키마, 계산·장소·교통·모델 연동
- backend/tests/: 서버 테스트
- specs/, .specify/: 기능 명세·계획·작업과 Spec Kit 설정
- Docs/: 이전 PRD·제안·테스트 맥락과 계약 fixture
- mobile/, cli/: 이전 검토의 보존 폴더. 현재 개발·제출 대상이 아니며 초기화하지 않는다.
- MCP 서버의 구현 위치·실행 진입점은 담당 명세에서 정한다. 준비되지 않은 폴더나 명령을 구현 완료로 소개하지 않는다.

## 두 사람의 분업

- 친구: MCP 도구 5개, 기존 API 연결, 확인·선택 흐름, Hermes 설정·통합 검증·시연.
- 본인: FastAPI, MainAgent·SubAgent·Skill, 모델·교통 데이터, 시간 계산, 재탐색, 테스트·배포.
- 공동: API·MCP 계약, 확인·문맥·선택 상태의 소유권, 지원 범위, Spec Kit, 제출 자료.
- 백엔드는 FastAPI·Docker·Cloud Run을 유지한다. 교통 API 키는 저장소에 포함하지 않는다.

## 첫 연결 목표

Hermes의 Solar Pro4가 get_capabilities를 호출해 MCP 서버를 거쳐 FastAPI의 실제 응답을 받는지 확인한다. 이후 장소 확인 → 사용자 최종 확인 → 출발시각 계산 → 재탐색·후보 선택을 연결한다.

계산·경로·상태·권한은 코드로 검증하고, 사용자 확인 없이 계산하거나 새 계획을 적용하지 않는다. 실제 데이터와 fixture를 구분하며 실행하지 않은 테스트·조회·저장·배포를 성공으로 보고하지 않는다.
