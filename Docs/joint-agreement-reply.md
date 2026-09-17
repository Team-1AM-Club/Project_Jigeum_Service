# 003 공동 개발자 합의 요청 회신 초안

검토 대상: 전달받은 `joint-agreement.md` (작성일 2026-09-16)

**상태: MCP 측 기술 검토 초안. 사용자·양측 개발자의 최종 승인 기록이 아닙니다.** 아래의 동의는 제안에 대한 기술적 의견이며 공개 계약 변경이나 구현 착수를 자동 승인하지 않습니다. 첨부 문서에 적힌 과거 사용자 결정은 전달받은 내용으로 구분하며 이 회신에서 새로 확정하지 않습니다.

## 검토 기준

- 검토 작성: 현재 MCP·백엔드 통합 작업 기준.
- 검토일: 2026-09-16.
- MCP 통합본 SHA: 없음. 현재 MCP 코드는 미커밋·미푸시 상태.
- 로컬 브랜치: `feature/backend-confirm-completion`.
- 기준 HEAD: `44f61169c050255268ba855c6074a15bb8000a6f`.
- 파일로 반영한 백엔드 원격 커밋: `5caef80` (`feature/mcp-server-integrate`).
- 위 두 커밋 어느 것도 현재 미커밋 통합본 전체를 재현하지 않습니다.
- 검토 문서: 전달받은 요청서 A1~A3/B1~B9/C1~C5. 상대 작업 트리의 최신 003 diff 전체를 확인한 것은 아닙니다.
- 현재 구현 위치와 confirm JSON: [confirm-mcp-handoff.md](confirm-mcp-handoff.md).

현재 HTTP MCP는 confirm_trip을 포함한 6개 도구이며, flat HTTP Plan 응답을 전달합니다. 현재 대화 상태·조건 확인·revision·멱등 처리는 백엔드가 관리하지만, 실제 선택 snapshot의 서버 검증·select API·elicitation evidence·resume는 구현되지 않았습니다. 요청서의 5개 action 도구 설계로 전환하려면 별도 마이그레이션이 필요합니다.

## A. 미결정 3건

### A1 — 수정 제안

POST 응답 파손을 확정 실패로 취급하지 않고 `OUTCOME_UNKNOWN`으로 구분하는 방향에 동의합니다. 원문 HTML·응답·stack을 진단에 넣지 않는 원칙도 동의합니다.

필드 위치는 **MCP 자체 오류 결과의 `structuredContent.diagnostics.cause_code`**를 후보로 제안합니다. backend envelope에는 추가하지 않습니다. 원인 값은 `UPSTREAM_RESPONSE_INVALID`로 제한하며, MCP 오류 결과의 전체 JSON Schema와 설치 SDK/Hermes의 수신·표시 검증 후 확정해야 합니다. TextContent도 제공한다면 같은 안전한 의미만 전달합니다.

현재 어댑터에는 보류 요청 저장·REQUEST_PENDING·resume가 없습니다. 따라서 첫 파손 후 자동 재시도 금지, 원래 요청 보존, 새 변경 차단, 승인 후 원본 POST 재개를 현재 지원한다고 답할 수 없습니다. 키와 본문을 모델 출력에 노출하지 않는 저장 방식도 함께 정해야 합니다.

### A2 — 조건부 동의 의견

개별 제공처 `UPSTREAM_TIMEOUT`과 전체 예산 `REQUEST_TIMEOUT`의 의미를 분리하는 방향에 동의합니다.

`504 / error / REQUEST_TIMEOUT / retryable=true`는 **해당 논리 요청이 미적용이며 늦은 commit도 불가능함을 서버가 보장하는 경우에만** 사용할 것을 제안합니다. 이 보장이 없으면 결과 불명으로 처리해야 합니다. 이미 완료한 confirm은 이후 plan 실패로 취소된 것으로 표현하지 않습니다.

3/10/25초는 목표 예산으로 검토 가능하지만 아직 검증된 SLA는 아닙니다. DB 확정 단계의 여유, 취소 전파, 단조 시계 기반 deadline, provider와 공유할 남은 예산 및 confirm/select 대기 상한을 백엔드 조사 결과로 확정해야 합니다.

### A3 — 수정 제안

응답 가능한 동일 키 대기 종료의 후보는 다음과 같습니다. **신규 제안이며 현재 구현된 오류가 아닙니다.**

| 항목 | 제안 |
|---|---|
| HTTP 상태 | 409 |
| error.code | `REQUEST_IN_PROGRESS` |
| retryable | false — 자동 반복 호출 억제. 미적용 확정의 의미가 아님 |
| MCP 매핑 | `OUTCOME_UNKNOWN`, 진단 원인 `REQUEST_IN_PROGRESS`, 보류 유지 |
| 후속 처리 | 사용자 승인 후 같은 단계·키·본문·revision으로 resume. 새로운 키로 재실행하지 않음 |

다른 payload의 `IDEMPOTENCY_KEY_REUSED`, stale revision, 전체 처리 실패와 구별해야 합니다. 연결이 이미 끊긴 경우에는 이 응답을 보장하지 않습니다. 대기자 취소가 처리자를 취소하거나 잠금을 해제하지 않는다는 원칙에 동의합니다.

성공 재생 / 대기 종료 후 원래 처리 성공 / 확정 실패 공유 후 순차 재시도 세 사례를 검증한 뒤 확정해 주세요. 현재 구현의 원자적 상태 반영은 provider 중복 실행 방지나 exactly-once 보장을 뜻하지 않습니다.

## B. 계약 묶음

| ID | 검토 의견 | 근거·필요 조치 |
|---|---|---|
| B1 | 수정 제안 | 현재 natural_language/context, flat TripRequest·Plan을 먼저 통합 기준으로 삼아 주세요. text/draft/중첩 plan.options 전환은 호환성 변경입니다. 기존 막차 전용 경로도 전환 완료 전 보존하고 새 구체 JSON·호출처 전환 범위를 먼저 정해야 합니다. |
| B2 | 보류 | confirm은 이미 구현돼 있습니다. GET conversation/select와 5개 action MCP는 미구현입니다. 기존 6개 도구에서 전환할 전체 schema·호환 기간·Hermes 지원 확인이 필요합니다. |
| B3 | 부분 동의·수정 제안 | 최초 ID/revision 생략, 후속 ID/expected_revision 전달, meta의 상태 정보는 현재 구현과 맞습니다. request_started_at 필수화는 새 계약입니다. 시간 형식·오차 허용·보존·복구 규칙을 정해야 하며 서버 TTL 시계와 혼동하지 않아야 합니다. |
| B4 | 방향 동의·실행 보류 | 실제 사용자 승인과 모델 boolean을 구분하는 원칙에 동의합니다. 현재 user_confirmed는 암호학적 승인 증명이 아닙니다. Hermes elicitation 지원 확인 후 evidence schema·재사용 방지·대상 바인딩을 확정해야 합니다. 로컬에서 evidence 생성자가 신뢰된다는 한계도 명시해야 합니다. |
| B5 | 보류 | 현재 confirm은 초안을 소비하지 않으며 서버 select API도 없습니다. 제안 TTL과 후보 무효화는 기존 구현과 다른 상태 전이입니다. 기존 대화·후보에 대한 migration 및 재탐색 실패 시 선택 보존 테스트가 필요합니다. |
| B6 | 부분 동의·수정 제안 | MCP UUIDv4, 동일 요청 재생, 상태와 응답 원자 저장 방향은 동의합니다. 현재 키 유일성 범위는 conversation_id + key이며 전역 UNIQUE가 아닙니다. 전역 전환·동시 처리 잠금·실패 공유·최초 유실 복구는 별도 구현과 migration이 필요합니다. |
| B7 | 부분 동의 | 미존재/삭제 404, tombstone 410, stale 409는 현재 방향과 일치합니다. 후보 만료/select·A1~A3는 신규 오류표와 판정 순서를 예제로 확정해야 합니다. |
| B8 | 수정 제안·예산 보류 | 현재 MCP는 통신 실패만 즉시 1회 재시도하고 HTTP 오류는 재시도하지 않습니다. 500ms 정책을 반영할 때 004 provider 재시도와 MCP 재시도를 곱셈으로 증폭시키지 않아야 합니다. retryable=true만으로 자동 재시도 허용을 추정하지 말고 상태/코드/단계별 허용표를 확정해 주세요. 300/480/500초는 설치 Hermes 제한과 실제 timeout 취소 동작을 검증하기 전 확정할 수 없습니다. |
| B9 | 동의 의견 | demo/실데이터를 구분하고 실패를 demo로 대체하지 않는 원칙에 동의합니다. 현재 모드는 JIGEUM_MODE로 서버 시작 시 선택하므로 도구별 mode 인수 제안과 차이를 명시해야 합니다. |

추가 확인: 현재 plan/replan의 max_options는 기본 3, 상한 5입니다. 004의 상한 3 제안은 그대로 유지가 아니라 계약 변경으로 기록해야 합니다. Source.basis_at과 Buffer 총시간 포함 방식은 004 회신과 일치시켜 이중 차감을 막아야 합니다.

## C. 실행 조건

| ID | 담당·증거 및 답변 |
|---|---|
| C1 | 본 통합과 검토는 Codex 실행입니다. Hermes/Solar 개발 실적으로 표현하지 않습니다. 외부 제출 요건 충족이나 예외 승인은 확인되지 않았으므로 프로젝트 책임자가 별도로 확인해야 합니다. |
| C2 | MCP 측 점검 대상. 진입점 jigeum_mcp_server.py, HTTP 구현 backend_mcp_server.py, SDK mcp==2.0.0. 로컬 stdio 검증은 존재하지만 실제 Hermes elicitation·세션별 프로세스 분리·500초 host timeout은 미검증입니다. 실명 담당자와 일정은 미정이며 상대와 확정해야 합니다. |
| C3 | 백엔드 측 점검 대상. 현재 위치는 app/db.py, app/lifecycle.py, app/models/conversation.py, app/services/http_state.py입니다. 통합 패치 수령 후 기존 DB의 additive migration과 제안 migration의 차이를 확인해 주세요. 일정은 미정입니다. |
| C4 | 실제 약속을 먼저 인수하고 재탐색·막차로 확장하는 순서에 동의합니다. 실제 provider 연결본과 양측 재현 가능한 소스가 준비된 후 공동 수행하며 일정은 미정입니다. |
| C5 | 별도 PC/VM 재현에 동의합니다. 현재 통합본 SHA가 없어 아직 충족하지 못했습니다. 패치 식별자 또는 향후 승인된 커밋, 환경·명령·결과를 남겨야 합니다. 커밋 금지 요청은 현재 유지됩니다. 담당 실명·일정은 미정입니다. |

기존 실행 근거는 로컬 백엔드 210개 테스트, MCP HTTP 어댑터 5개, 실제 MCP stdio→FastAPI→임시 DB 흐름입니다. Mock provider 기준이며 003 action/evidence/elicitation/실데이터/원격 배포 인수 증거가 아닙니다. 본 회신 작성에서 이 테스트를 새로 실행하지 않았습니다.

## 남은 차이와 진행 제안

1. 미커밋 통합 소스/패치를 먼저 전달·확인해 현재 구현 기준을 일치시킵니다. 이 Markdown 자체는 패치가 아닙니다.
2. 003 후속 설계와 현재 구현의 차이를 별도 목록으로 유지하고, 004 실제 제공처 연결에서 기존 confirm/revision 게이트가 후퇴하지 않게 합니다.
3. A1~A3 오류 schema와 B1~B8 전환 범위, Hermes 지원 여부를 확정한 뒤 API_SPEC·공통 예제·양쪽 코드를 함께 변경합니다. 그전에는 해당 신규 설계를 완료 처리하지 않습니다.
4. 기존 계약 안에서 가능한 독립 provider 작업과 테스트는 진행할 수 있으나, 미합의 공개 schema·상태 전이를 선반영하지 않습니다.

**최종 합의 버전 / 양측 확인 근거: 아직 없음.** 이 초안을 검토해 항목별 결정과 양측 실제 승인 기록을 남긴 뒤 T001 완료 여부를 판단해 주세요.
