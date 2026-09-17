# Source·공통 기반 후속 변경 전달

## 다른 PC로 전달

`Docs/transit-source-integration-20260916.zip`을 실제 파일로 전달한다. 요청 문서의 상대 링크만으로 다른 PC에 패치가 전달되지는 않는다. ZIP에는 이 폴더의 11개 patch, README.md, manifest.json, VERIFICATION.md만 포함한다. ZIP checksum은 별도 `transit-source-integration-20260916.zip.sha256` 파일을 따른다.

수신측 저장소 루트에서 ZIP을 아직 존재하지 않는 별도 폴더에 풀어 내용과 checksum을 확인한다. 기존 폴더에 강제로 덮어쓰지 않는다. 아래 적용 명령의 transitPatchDir을 실제 압축 해제 폴더로 바꾸고 전체 `git apply --check`를 먼저 실행한다. 가능하면 현재 미커밋 통합본을 보존한 별도 복사본에서 검증한다. 이후 README/manifest와 실제 적용 결과를 함께 회신한다.

VERIFICATION.md는 송신측 실행 및 기존 병행 검증 기록을 구분한 요약이다. 수신측 실행 증거가 아니며 전체 완료를 주장하지 않는다.

팀원 `team-handoff-reply.md`의 R1 전달 요청에 따른 패키지다. 계약의 재승인이나 전체 구현 완료 자료가 아니다. commit/push하지 않았다.

## 기준과 적용 범위

비교 기준은 `5caef80e443a6bd694b8dd5cd8b274348ae4ad82`에 기존 `Docs/confirm-mcp-integration/confirm-mcp-integration.patch`를 적용한 통합본이다. 상대 HEAD `44f61169c050255268ba855c6074a15bb8000a6f` 자체와 비교한 패치는 아니다. 수령한 48개 파일을 메모리에서 재구성해 원본 hunk 일치를 확인했고, 그 통합본 이후 선택된 파일의 변경만 포함했다. 기존 통합 패치를 다시 적용하거나 전체 파일을 덮어쓰지 않는다.

11개 patch는 서로 다른 29개 파일을 대상으로 한다. 파일 목록·기준/대상 SHA-256·patch SHA-256은 manifest.json을 따른다. 파일 내용 hash는 UTF-8/LF/BOM 없는 표현 기준이며 API키의 값·길이·hash를 확인한 것이 아니다. 비밀 키 파일·환경 파일·배포 변경·무관한 003/005 변경은 포함하지 않았다. 생성 중 MCP 테스트의 후속 변경을 확인해 MCP 담당 소유 파일은 패키지에서 제외했다. 팀원은 승인 예시와 백엔드 Source 계약 테스트를 기준으로 소유 MCP 테스트를 갱신한다.

저장소 루트에서 먼저 전체 적용 가능성을 확인한다. 작업 트리의 후속 변경과 충돌하면 적용을 멈추고 파일/충돌 위치를 회신한다. 사용자 변경을 되돌리거나 강제 덮어쓰지 않는다.

```powershell
$transitPatchDir = '.\Docs\transit-source-integration'
$transitPatchFiles = @(Get-ChildItem -LiteralPath $transitPatchDir -Filter '*.patch' | Sort-Object Name | ForEach-Object FullName)
git apply --check @transitPatchFiles
```

check가 통과한 뒤 적용:

```powershell
git apply @transitPatchFiles
```

송신측 현재 작업 트리에서 `git apply --reverse --check`는 통과했다. 이는 수신측 작업 트리의 check를 대신하지 않는다. 별도 commit·배포·비밀키 전달은 요청하지 않는다.

## 공동 검증과 회신

- 공개 계약: ../../specs/004-public-transit-api-integration/contracts/transit-integration.md §9.
- 전체 합성 예시: 같은 contracts의 flat-plan-proposal.json 및 ../../Docs/api/examples.json의 `transit_flat_plan_004`.
- 수령 후 팀원이 MCP adapter·stdio의 Source 누락/null/+09:00 수신·보존, 후보별 warnings 및 추천/선택 구분을 검증한다. Hermes 실제 표시 결과는 별도 기록한다.
- 백엔드 담당은 provider/정규화·Source 생성·계획 서비스와 진행 중 동일 요청의 외부 조회/상태 보호 검증을 맡는다. MCP 담당은 응답 유실·동일 key/body/revision 재전송과 사용자 안내를 맡는다. R3의 파일 분담 제안을 이 기준으로 수용한다.
- backend worker/인스턴스 수는 아직 미정이며 진행 중 HTTP 중복 조회 방지는 미구현·미검증이다. 새 `REQUEST_IN_PROGRESS` 등의 오류를 이 패키지에서 도입하지 않았다.
- T018/T019는 실제 공동 수신/표시 및 제공처 변환 인수가 남아 있어 완료 체크하지 않는다. 실시간/미확인 근거를 현재 운행 계산에서 제외하는 보호와 Buffer 계산의 전체 반영을 구분한다.

## 배포 주소 후속 확인

사용자 제공 MCP 백엔드 주소는 `http://127.0.0.1:18080/api/v1`이다. 송신측에서 health·capabilities의 HTTP 200과 `meta.is_demo=true`를 확인했다. 연결 성공은 실제 교통/계산 인수 완료가 아니다. 로컬 Hermes v0.21.2의 `solar-pro4` 환경에 연결 설정을 추가했다. 실제 Hermes 도구 호출 결과는 004의 live-verification.md에 별도로 기록한다. 개인 Hermes 설정이나 모델/교통 자격증명은 패키지에 포함하지 않았다.

## 병렬 Implement 결과 — 2026-09-16

- 09 patch는 capabilities의 기본 3개·상한 5개를 TripRequest 스키마에서 읽도록 수정한다. 배포 주소에서 관측한 기본 5개·상한 10개와 구분하며, 이 전달은 배포를 수행하지 않는다.
- 10 patch는 OA-15442 역 코드표의 순수 row 정규화와 12개 합성 테스트다. STATION_CD/FR_CODE namespace·선행 0·좌표 없음·Evidence 경계를 보존한다. 실제 조회 client와 시간표/경로 계획 연결은 포함하지 않는다.
- 11 patch는 실시간 operation별 기준시각/ETA와 운행일·좌표 근거의 확인/미확정 상태를 기록한다. 미확정 규칙이나 새 좌표 제공처를 채택하지 않는다. T015의 확인 상태 기록은 완료했으며, 실제 규칙 검증(T039/T040)과 T020~T022 전체 완료를 의미하지 않는다.
- 현재 작업 트리의 백엔드 회귀 361 passed, 12 warnings. 새 정규화·capabilities 코드/테스트 4개 파일의 Black/isort/Ruff 통과. 별도 읽기 전용 검토에서 중요한 결함이 발견되지 않았다.
- 개인 Hermes + Solar Pro4에서 실제 get_capabilities 1회와 status=ok, is_demo=true 표시를 확인했다. 도구 설명 호출은 별도 1회다. Source 포함 후보의 실제 표시, 실제 약속·막차 계획 검증은 남는다.
