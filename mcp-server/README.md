# 지금 MCP 연결

`jigeum_mcp_server.py`는 stdio 진입점이다. `JIGEUM_MODE=http`이면 현재 백엔드 계약의 6개 도구를 제공한다. 생략 또는 `demo`이면 이전 고정 fixture 도구 5개를 보존한다. 두 모드의 입력·응답 스키마는 다르다.

## 설치·Hermes 연결

Python 3.12, MCP 2.0.0, httpx 0.28.1로 검증했다. 저장소 밖 가상환경을 사용한다.

```powershell
python -m pip install -r mcp-server/requirements.txt -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

백엔드는 실행 환경의 DATABASE_URL을 사용한다. 자동 검증 스크립트는 별도 임시 DB를 만든다.

Hermes 설정의 `mcp_servers`에 다음 항목을 추가한다. command·args는 본인 환경의 절대 경로로 바꾼다. 설치된 Hermes의 `tools/mcp_tool_config.py`, `tools/mcp_tool_transport.py`에서 설정 형태를 확인했다. 개인 설정은 자동 수정하지 않는다.

```yaml
mcp_servers:
  jigeum:
    command: C:/path/to/venv/Scripts/python.exe
    args:
      - C:/path/to/MABC/mcp-server/jigeum_mcp_server.py
    env:
      JIGEUM_MODE: http
      JIGEUM_API_BASE_URL: http://127.0.0.1:8000/api/v1
      JIGEUM_API_TIMEOUT: "15"
```

Base URL은 `/api/v1`을 포함한다. 설정 변경 후 MCP 연결을 다시 시작한다. HTTP 모드는 도구 인수에 mode를 넣지 않는다. `backend_mcp_server.py`를 직접 실행해도 HTTP 모드로 작동한다.

## HTTP 도구 계약

| 도구 | 백엔드 | 입력 |
|---|---|---|
| get_capabilities | GET /capabilities | 없음 |
| search_places | GET /places | query, limit |
| interpret_trip | POST /mobility/interpret | text, context, 기존 대화의 conversation_id·expected_revision |
| confirm_trip | POST /conversations/{id}/confirm | conversation_id, expected_revision, confirmed_data, user_confirmed |
| plan_journey | POST /journeys/plan 또는 /last_journey | trip, conversation_id, expected_revision, max_options |
| replan_journey | POST /journeys/replan | trip, conversation_id, expected_revision, previous_plan, current_origin_place_id, reason, user_confirmed |

조건은 `kind`, `origin_place_id`, `destination_place_id`, `arrival_deadline`, `arrival_preference_minutes`, `service_date`, `transport_modes`의 flat 구조다. confirmed_data에는 trip_draft의 설명·메타 필드를 넣지 않는다. 상세 조건은 루트 API_SPEC.md의 현재 구현 계약을 따른다.

1. 장소 후보를 검색하고 사용자 선택을 받는다.
2. interpret_trip의 조건을 보여준다. 조건이 완전해도 아직 사용자 동의가 아니다.
3. 명시적 동의 후 confirm_trip(user_confirmed=true)을 호출한다. 조건 변경은 먼저 interpret_trip으로 처리한다.
4. 성공 응답의 meta.conversation_id와 최신 meta.revision을 다음 호출에 사용한다. 충돌 시 이전 revision으로 계산을 강행하지 않는다.
5. plan_journey는 현재 백엔드의 flat Plan을 반환한다. comparison.options 후보 선택은 사용자에게 받는다.
6. 재탐색에도 사용자 동의가 필요하다. previous_plan에는 사용자가 선택한 후보의 plan_id, selected_option_id, recommended_leave_at, estimated_arrival_at을 넣는다. 새 결과를 기존 계획에 자동 적용하지 않는다.

POST마다 MCP가 UUIDv4 멱등 키를 생성한다. 통신 실패 시 같은 요청·키로 한 번만 재시도한다. 도메인 오류는 재시도하지 않는다. 두 번 모두 응답을 잃으면 처리 여부는 불확실하다. 별도 도구 호출은 새 키를 사용한다.

백엔드 envelope와 오류·unavailable·메타를 그대로 전달한다. HTTP 실패를 demo로 대체하지 않는다. 현재 백엔드 provider는 mock이므로 HTTP 성공도 실제 교통·막차 조회는 아니다.

## 검증

저장소 루트에서:

```powershell
python mcp-server/verify_backend_stdio.py
```

MCP stdio 초기화·6개 도구 발견 후 임시 FastAPI/SQLite에서 장소 → 해석 → 미확인 차단 → confirm → revision 충돌 → 계획 → 재탐색 보존 → 막차를 검증한다.

```powershell
cd mcp-server
python -m unittest discover -s tests
```

demo 회귀 테스트는 `tests/fixtures/demo_examples.json`을 사용한다. feature/mcp-demo-tools의 7b201ca에서 가져온 과거 계약이며, 현재 HTTP 예제는 루트 `Docs/api/examples.json`이다. `verify_mcp.py`, `verify_http.py`는 기존 demo/capabilities 전용 검증이다.

Hermes + Solar Pro4 실제 대화·자동 도구 선택과 실제 교통 데이터 연결은 이 검증에 포함하지 않는다.
