# MCP 담당 회신 — 공동 환경 검증 및 작업 분담

회신 기준: 2026-09-16 23:24~23:25 (Asia/Seoul).

전달받은 team-handoff.md를 확인했습니다. 아래는 이쪽 작업 트리의 코드 확인과 이번에 재실행한 검사 결과입니다. 상대 환경의 339/340개 테스트·93개 MCP 테스트·실키 probe 기록을 이쪽 실행 결과로 간주하지 않습니다. 계약을 재승인하거나 변경하는 회신도 아닙니다.

## 실행 기준

- 기준 HEAD: `44f61169c050255268ba855c6074a15bb8000a6f`
- 로컬 브랜치: `feature/backend-confirm-completion`
- 팀원 `5caef80e443a6bd694b8dd5cd8b274348ae4ad82` 변경을 작업 파일로 통합한 후 미커밋 상태 유지.
- 기존 전달 패키지: `confirm-mcp-integration.zip`. 5caef80 기준 48개 파일의 변경 내역은 ZIP의 manifest.json에 있음.
- MCP 코드: `mcp-server/backend_mcp_server.py`, stdio 진입점 `mcp-server/jigeum_mcp_server.py`.
- 검증 환경: Windows / Python 3.12.14. 기존 검증 환경의 MCP SDK는 2.0.0, httpx는 0.28.1.
- Hermes 버전·Solar Pro4 정확한 모델 ID: 이번 회신에서 미확인. 실제 Hermes 모델 호출·표시 검증은 미실행.
- 이번 회신에서는 애플리케이션 코드를 수정하지 않았음.

## R1. Schema·Source·후보 표시

| 항목 | 결과 | 근거 및 한계 |
|---|---|---|
| 기존 envelope 수신 | 통과 — adapter 범위 | 기존 집중 테스트 5개 재실행, 종료 0 |
| 승인 예시와 Source 확장 호환 | 미실행 | 상대의 최신 Source 코드·합성 예시를 아직 전달받지 않음 |
| basis_at 누락/null/+09:00, 신규 null 출력 | 미실행 | 현재 별도 Source 수신 테스트 없음. 신규 null 출력은 백엔드 책임도 포함 |
| 약속·막차·재탐색·재생의 후보별 sources/warnings | 미실행 — 새 Source 기준 | 이전 Mock stdio 검증은 Source 확장 인수 증거가 아님 |
| Demo·기준 미확인·정적 기준일 표시 | 미실행 — Hermes 표시 | JSON을 전달하는 것과 사용자에게 정확히 표시하는 것을 구분 |
| 후보 상세·추천/사용자 선택 구분 | 미실행 — 승인 합성 예시 기준 | 실제 Buffer 계산 검증과도 별도 |

현재 HTTP MCP 반환 타입은 `dict[str, Any]`이며, Source/후보 내부 필드에 대한 별도의 엄격한 응답 모델은 없습니다. SDK가 생성하는 일반 객체 스키마와 Source 전용 엄격한 검증을 혼동하지 않습니다.

`backend_mcp_server.py::_request`는 최상위 status/data/error/meta 및 일부 타입·상태를 검사한 뒤 받은 envelope를 그대로 반환합니다. basis_at을 생성·변환하거나 retrieved_at으로 대체하는 코드는 없습니다. 이는 코드 확인 사실이며, 최신 승인 예시의 수신·Hermes 표시 통과를 의미하지 않습니다.

이번 실행 명령(mcp-server 폴더):

```powershell
python -m unittest discover -s tests -p test_backend_http.py
```

결과: 5 tests, OK. 실제 제공처 호출 없이 합성 응답으로 검사했습니다.

**후속 검증에 필요한 전달물:** 현재 추가 변경의 비밀 값 없는 패치와 manifest, `contracts/transit-integration.md` §9, `contracts/flat-plan-proposal.json`, 공유 예제의 `transit_flat_plan_004`. 각 파일은 기준 커밋과 함께 전달해 주세요. 기존 패키지를 다시 전체 덮어쓰기하는 방식은 피하고, 적용한 통합본 이후 차이를 식별할 수 있게 해 주세요.

수령 후 이쪽에서 adapter·MCP stdio의 Source 수신/보존 검증을 맡는 것을 제안합니다. 실제 Hermes/Solar 표시는 실행 환경과 모델 접근을 확인한 후 일정을 정해야 하므로 현재 확정 시각은 없습니다. T018/T019 공동 인수는 계속 미완료로 두는 것이 맞습니다.

## R2. 응답 유실 재시도

- 코드 위치: `mcp-server/backend_mcp_server.py::_request`.
- 잡는 예외: `httpx.TransportError`, `httpx.TimeoutException`. timeout은 TransportError 계열에 포함되며, 연결·읽기·쓰기·프로토콜 등 TransportError 하위 예외를 폭넓게 잡습니다. 모두 응답 유실만 의미하는 것은 아닙니다.
- 횟수: 최초 요청 후 **즉시 추가 1회**, 총 2회까지. 현재 500ms 대기는 없습니다.
- 대상: 공통 _request를 사용하는 HTTP 모드 6개 도구의 GET/POST 요청. confirm/replan이 동의 검사에서 차단되면 HTTP 호출 자체가 없습니다.
- HTTP 응답을 수신한 경우 429·502·503·504를 자동 재시도하지 않습니다. 유효한 오류 envelope는 보존하고, JSON/계약 파손은 UPSTREAM_RESPONSE_INVALID로 처리합니다.
- POST의 UUIDv4 키는 반복문 전에 생성합니다. 재시도는 같은 headers/body를 사용하고 expected_revision을 갱신하지 않습니다.
- 두 번 모두 통신 실패하면 현재 코드는 ROUTING_PROVIDER_UNAVAILABLE/retryable=true를 반환합니다. **서버 미적용을 보장하지 않으며**, OUTCOME_UNKNOWN·보류 상태·resume은 아직 구현하지 않았습니다. 새 도구 호출은 새 키를 생성하므로 이를 이전 요청의 안전한 복구라고 안내하면 안 됩니다.

검증 파일: `mcp-server/tests/test_backend_http.py`.

- `test_retry_preserves_key_and_body`: ReadTimeout 후 두 호출의 인수와 UUIDv4 키 동일성을 검증, 이번 실행 통과.
- 단, 이 테스트는 최초 interpret 요청이라 expected_revision을 넣지 않습니다. **revision이 포함된 POST의 응답 유실 재시도는 별도 직접 검증이 아직 없습니다.** 코드상 body 재사용과 실행 검증을 구분합니다.
- `test_plan_cannot_override_revision_via_trip`: 명시적으로 전달한 conversation_id/expected_revision이 trip 내부 값에 덮이지 않는 것을 검증, 이번 실행 통과. 위의 재시도 테스트를 대신하지 않습니다.
- 진행 중 첫 요청과 재시도의 동시 실행에서 외부 조회 0회 추가 보장: 미구현·미검증으로 유지합니다.

공동 검증 분담 제안: 백엔드 담당이 지연 제공처·동시 동일 키·worker 간 처리 fixture와 외부 호출 횟수/상태 변경 검증을 맡고, MCP 담당은 응답 유실·동일 키/본문/revision 재전송 및 사용자 안내를 검증합니다. 담당 확정은 회신 부탁드립니다. REQUEST_IN_PROGRESS 등 새 오류는 자동 도입하지 않습니다.

현재 또는 배포 예정 worker/인스턴스 수: **미정**. 과거 로컬 단일 서버 테스트를 배포 인스턴스 수나 프로세스 간 보장으로 확대하지 않습니다.

## R3. 동시 수정 경계와 전달

현재 이 회신에서 수정하는 파일은 `Docs/team-handoff-reply.md`뿐입니다. 공공 교통 제공처·설정·전송 코드는 수정 중이지 않습니다.

다음 작업 분담을 제안합니다.

- 상대 담당: `backend/app/integrations/`, 공통 설정·client 수명주기, 실제 provider/정규화, Source 생성, backend schema·계획 서비스·관련 backend 테스트.
- 이쪽 담당: `mcp-server/backend_mcp_server.py`, `mcp-server/tests/`, `mcp-server/verify_backend_stdio.py`, MCP 실행 안내 및 Hermes 수신·표시 검증.
- 공동 조율: `API_SPEC.md`, `Docs/api/examples.json`, Source·Buffer 공개 계약. 상대 작업 중인 버전을 수령하기 전 이쪽에서 병렬 수정하지 않음.

후속 변경은 기준 커밋·파일별 manifest·검증 기록이 있는 비밀 값 없는 패치로 전달합니다. 커밋·푸시는 사용자 요청 없이 하지 않습니다. 기존 입력한 .env는 보존하고 전달하지 않습니다.

## 남은 확인

- 최신 Source·전송 구현과 승인 예시 수령 후 R1 재검증.
- 응답 유실과 진행 중 요청의 중복 조회/늦은 commit 공동 검증, timeout 및 retry 예산 조율.
- Hermes 버전·정확한 모델 ID·실제 표시 검증 시점 확인.
- 버스 키 승인·Decoding 입력과 OA-21232 채택 여부는 사용자 확인 사항으로 유지. 이 회신은 해당 항목의 승인이나 해결을 뜻하지 않음.
