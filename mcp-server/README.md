"""mcp-server 설치·실행·Hermes 연결 가이드.

## 개요

지금 MCP 서버는 `mcp-server/jigeum_mcp_server.py`에 있는 stdio MCP 서버다.
도구 `get_capabilities` 하나만 노출한다. 별도 앱·화면·CLI를 제공하지 않는다.

- Hermès는 MCP 서버를 stdio로 실행한다.
- MCP 서버 명령은 `mcp_servers`에 등록한다.
- 비밀값은 설정 파일에 넣지 않는다. 필요 시 환경변수로 전달한다.
- 실제 백엔드(FastAPI)를 준비하지 않았다면 demo 모드만 검증한다.

## 설치

커널(venv) 기준은 이 작업 공간의 Hermes venv다.

```
cd mcp-server
python -m pip install -r requirements.txt
```

현재 작성 시점에 확인된 환경:
- Python 3.11.16 (Hermes venv 기준)
- mcp 2.0.0
- httpx 0.28.1

## 실행

stdio로만 동작한다. 일반 터미널에서 서버만 실행하면 표준입출력이 MCP 프로토콜로 사용되는 상태여서 단독 실행은 의미가 적다.

```
python mcp-server/jigeum_mcp_server.py
```

이 명령은 MCP 클라이언트가 stdin/stdout으로 대화할 때 서버를 기동하는 용도다.
개발 중에는 아래 검증 스크립트를 사용한다.

## 검증

### 1) MCP 도구 목록 확인 + demo 응답 확인

```
python mcp-server/verify_mcp.py
```

이 스크립트는 다음을 확인한다.
- MCP stdio 서버 기동
- 도구 목록(list_tools)에 get_capabilities가 있음
- get_capabilities(mode=demo) 응답이 Docs/api/examples.json의 capabilities 응답과 같음
  (request_id, server_time을 제외한 구조·타입·값 비교)

### 2) capabilities 계약 검증 + HTTP 모드 처리 확인

```
python mcp-server/verify_http.py
```

이 스크립트는 다음을 MCP 도구로 호출해 확인한다.
- demo 응답의 필수 필드·타입·상태별 envelope
- HTTP 성공 응답(로컬 가짜 백엔드로 정상 200 envelope 반환)
- HTTP 연결 실패(비정상 base_url) → ROUTING_PROVIDER_UNAVAILABLE
- HTTP 타임아웃(짧은 타임아웃 + 느린 응답) → UPSTREAM_TIMEOUT
- HTTP 계약 위반(JSON 객체 아님 / JSON이 아님 / 백엔드 error envelope 전달)

별도 백엔드가 실행 중이지 않으면 실제 백엔드 연결은 미검증으로 본다.
이 스크립트는 HTTP 실패 케이스만 자동 검증한다. 실제 백엔드 연결은
JIGEUM_API_BASE_URL을 실제 주소로 설정하고 실제 백엔드가 준비된 뒤 확인한다.

## 설정 예

Hermès가 MCP 서버를 stdio로 실행하도록 Hermes 설정(.hermes/config.yaml 등)에
서버 명령을 등록한다. MCP 도구 등록·메타 설정은 Hermes 설정과 MCP 서버 구현을
함께 봐야 한다. 설정에는 비밀 값을 넣지 않는다.

예시 명령어(값은 실제 설치 경로에 맞춘다):

```
command: python
args:
  - mcp-server/jigeum_mcp_server.py
```

실제 백엔드 연결 설정:
- 환경변수 `JIGEUM_API_BASE_URL`에 /api/v1을 포함한 Base URL을 넣는다.
  예) `JIGEUM_API_BASE_URL=https://api.example.com/api/v1`
- 타임아웃은 `JIGEUM_API_TIMEOUT`으로 초 단위 지정 가능(기본 15초).

설정 예제에 API 키·비밀값은 포함하지 않는다.

## MCP 연동 흐름(도구 1개)

1. get_capabilities(mode="demo" 또는 "http")
   - meta.is_demo=true이면 시연 데이터
   - status/data/error/meta 구조를 보존
   - HTTP 실패 시 데모 응답으로 자동 대체하지 않음

## 백엔드 관련 미완료 사항(보유 담당 아님)

이 항목은 친구에게 전달할 메모다. MCP 서버의 책임이 아니다.
- 실제 교통·Solar·Skill 실행 연결 없음
- Agent import 오류
- 미확인 재탐색 허용 및 변경한 출발지 미반영
- 재탐색 예상 도착시각과 마지막 구간 시각 불일치
- 자연어 입력 대신 고정 응답
- 일부 응답의 API 계약 불일치

이 서버 코드는 backend/를 수정하지 않는다. 백엔드 문제는 위 목록으로만 정리한다.

## 제한

- 현재는 get_capabilities만 구현한다. 나머지 4개 도구는 이번 범위 밖이다.
- demo 응답은 examples.json capabilities 케이스 응답에 고정돼 있다.
- HTTP 응답은 백엔드가 계약을 지킨다고 가정했을 때의 전달 경로만 다룬다.
  백엔드가 계약을 위반할 때의 처리도 이 서버 코드에서 확인할 수 있다.
