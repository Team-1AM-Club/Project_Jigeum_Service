# confirm 라우트·HTTP MCP 통합본 전달 안내

작성일: 2026-09-16

> 후속 전달 자료 생성: `work/handoff/confirm-mcp-integration.zip`에 실제 패치·적용 안내·파일 목록·검증 기록을 묶었다. 패치 단독 경로는 `work/handoff/confirm-mcp/confirm-mcp-integration.patch`다. 아래의 패치 미첨부 설명은 최초 문서 작성 시점 기록이며, 현재는 ZIP을 함께 전달하면 된다.

## 1. 현재 체크아웃에 코드가 없는 이유

통합본은 **아직 커밋·푸시하지 않은 로컬 작업 파일**입니다. 원격 브랜치를 체크아웃해도 아래 변경이 나타나지 않는 것이 맞습니다.

- 로컬 브랜치: `feature/backend-confirm-completion`
- 기준 HEAD: `44f61169c050255268ba855c6074a15bb8000a6f`
- 반영한 팀원 커밋: `feature/mcp-server-integrate`의 `5caef80`
- **기준 HEAD와 팀원 커밋 어느 쪽에도 현재 미커밋 통합본 전체가 포함돼 있지 않습니다.** Git merge·commit·push 없이 파일로 통합했습니다.

위 경로는 작성자 PC의 경로입니다. 다른 PC에서 접근하려면 별도의 소스/패치 전달이 필요합니다. 이 문서는 안내 자료이며 소스 패치가 첨부된 것은 아닙니다.

## 2. 확인할 파일

아래 경로는 작업 폴더 기준입니다.

| 내용 | 파일 |
|---|---|
| confirm 라우트·interpret 상태 저장 | `backend/app/api/mobility.py` |
| `/api/v1` 라우터 등록 | `backend/app/main.py` |
| ConfirmRequest·Conditions·조건 정규화 | `backend/app/services/confirmation.py` |
| 상태 변경·revision·멱등성 | `backend/app/services/http_state.py` |
| 대화 저장 모델 | `backend/app/models/conversation.py` |
| DB 시작·정리 처리 | `backend/app/lifecycle.py` |
| 확인 후 계산 게이트 | `backend/app/api/journeys.py` |
| HTTP MCP 6개 도구 | `mcp-server/backend_mcp_server.py` |
| MCP stdio 진입점·모드 선택 | `mcp-server/jigeum_mcp_server.py` |
| 현재 구현 계약 | `API_SPEC.md` 상단의 현재 구현 계약 |
| 실제 로컬 HTTP 예제 | `Docs/api/examples.json`의 `confirm_conditions`, `confirm_last_journey` |
| 백엔드 HTTP 회귀 검증 | `backend/tests/integration/test_confirmation_http.py` |
| 실제 MCP → FastAPI 연결 검증 | `mcp-server/verify_backend_stdio.py` |
| 설치·호출 안내 | `mcp-server/README.md` |

위 표는 탐색용이며 독립 실행에 필요한 전체 변경 파일 목록은 아닙니다. 라우트 파일만 복사하지 말고 연관 서비스·스키마·모델·테스트를 포함한 통합 변경분을 받아야 합니다.

## 3. confirm HTTP 계약

```http
POST /api/v1/conversations/{conversation_id}/confirm
Idempotency-Key: <UUID v4>
Content-Type: application/json
```

- 먼저 `POST /api/v1/mobility/interpret`로 초안을 저장합니다.
- 반환된 `meta.conversation_id`를 URL에, 최신 `meta.revision`을 expected_revision에 넣습니다.
- 해석 조건을 사용자에게 보여주고 명시적 동의 후 호출합니다.
- confirmed_data는 저장 초안과 정규화한 조건이 일치해야 합니다. confirm으로 초안을 임의 변경할 수 없습니다.
- HTTP 본문에는 user_confirmed가 없습니다. MCP confirm_trip의 user_confirmed와 구분합니다.

### 요청 예제

다음 요청·응답은 기존 `Docs/api/examples.json`의 Mock provider/격리 DB 실행 예제에서 가져온 고정 사례입니다. 현재 시각의 실제 교통 조회나 배포 서버 응답이 아닙니다. 실행 시 날짜·ID·revision·멱등 키는 해당 대화에 맞게 사용해야 합니다.

```json
{
  "expected_revision": 1,
  "confirmed_data": {
    "kind": "appointment",
    "origin_place_id": "place_seoul_station",
    "destination_place_id": "place_gangnam_station",
    "arrival_deadline": "2026-09-16T19:00:00+09:00",
    "arrival_preference_minutes": 10,
    "service_date": null,
    "transport_modes": ["subway", "bus"]
  }
}
```

### 성공 응답 예제 — HTTP 200

```json
{
  "status": "ok",
  "data": {
    "confirmed_conditions": {
      "kind": "appointment",
      "origin_place_id": "place_seoul_station",
      "destination_place_id": "place_gangnam_station",
      "arrival_deadline": "2026-09-16T10:00:00Z",
      "arrival_preference_minutes": 10,
      "service_date": null,
      "transport_modes": ["bus", "subway"]
    },
    "conditions_confirmed": true,
    "places_confirmed": true
  },
  "error": null,
  "meta": {
    "request_id": "c97c9ae0-df3c-419e-b376-dc5abd0b23c3",
    "server_time": "2026-09-16T09:00:00+00:00",
    "api_version": "v1",
    "is_demo": true,
    "conversation_id": "ffe2d5ad-6cf8-5c43-97f7-30f51493d7c9",
    "revision": 2,
    "expires_at": "2026-09-17T09:00:00+00:00"
  }
}
```

조건의 시각은 UTC로 정규화하고 교통수단은 중복 제거·정렬합니다. 응답의 Z 시각은 요청의 +09:00 시각과 같은 순간입니다. 다음 plan 요청에는 응답 revision인 2를 전달합니다.

### 주요 오류·재생

| 상황 | 응답 |
|---|---|
| 초안 부재·미해결 조건·확인 조건 불일치 | 422 `USER_CONFIRMATION_REQUIRED` |
| 오래된 revision | 409 `CONVERSATION_VERSION_CONFLICT` |
| 같은 키에 다른 요청 | 409 `IDEMPOTENCY_KEY_REUSED` |
| 만료 기록이 남은 대화 | 410 `CONVERSATION_EXPIRED` |
| 없는 대화·삭제된 대화 | 404 `CONVERSATION_NOT_FOUND` |
| 유효한 대화에서 같은 키·같은 요청 재시도 | 저장 응답 재생, revision 추가 증가 없음 |

실패 응답도 status/data/error/meta envelope를 사용합니다. 동일 논리 요청의 통신 재시도에는 키·본문·revision을 그대로 유지합니다.

## 4. HTTP MCP 연결

`JIGEUM_MODE=http`로 stdio 진입점을 실행합니다. `JIGEUM_API_BASE_URL`은 `/api/v1`을 포함합니다. 기본 demo 모드는 과거 fixture용이며 HTTP 모드와 스키마가 다릅니다.

HTTP 모드 도구는 다음 6개입니다.

- get_capabilities
- search_places
- interpret_trip
- confirm_trip
- plan_journey
- replan_journey

confirm_trip 입력은 conversation_id, expected_revision, confirmed_data, user_confirmed입니다. user_confirmed의 기본값은 false이며, 명시적 true가 아니면 HTTP 요청 없이 확인 필요 오류를 반환합니다. 모델이 실제 사용자 동의를 임의로 만들어도 된다는 의미가 아닙니다.

MCP가 UUIDv4 멱등 키를 생성하고, 백엔드 응답 envelope와 revision을 보존합니다. 실패 시 demo 데이터로 대체하지 않습니다. HTTP 도구 인수에 mode를 넣는 방식이 아니라 서버 시작 환경변수로 모드를 선택합니다.

## 5. 검증 범위와 다음 전달

앞선 통합 작업에서 백엔드 210개 테스트, MCP HTTP 어댑터 5개, 실제 로컬 MCP stdio → FastAPI → 임시 SQLite 흐름을 통과했습니다. 이 문서 작성에서는 라우트·스키마·예제·브랜치·HEAD를 다시 확인했으며 전체 테스트를 재실행하지 않았습니다.

실제 공공 교통 API, GCP 배포·인증, Hermes/Solar 모델 대화는 위 검증과 별개입니다. 입력한 .env·API 키는 전달 자료에 포함하지 않습니다.

**상대 개발자에게 요청:** 통합 소스/패치를 받은 후 위 파일과 예제를 기준으로 검토해 주세요. 그전에는 confirm 라우트를 중복 구현하거나 기존 003 제안을 현재 구현으로 간주해 자동 적용하지 않는 방향이 맞습니다. Source.basis_at·Buffer 변경안은 별도 공동 합의 후 현재 API 계약과 함께 반영해야 합니다.
