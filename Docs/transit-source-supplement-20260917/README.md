# Source 전달 누락·날짜 테스트 보완 패키지

작성일: 2026-09-17 (Asia/Seoul)

`Docs/transit-package-receipt.md`의 요청을 반영한 후속 패키지다. 앞서 수령/적용한 transit-source-integration-20260916.zip을 대체하거나 다시 적용하지 않는다. 이번 ZIP만 별도 새 폴더에 풀어 적용한다. 현재 송신측의 이후 병행 구현 전체를 보내는 패키지가 아니다.

## 포함 내용

| 순서 | patch | 내용 |
|---|---|---|
| 1 | 01-shared-schema.patch | 실제 공동 검증에 사용한 Docs/api/source-envelope.schema.json 추가. 백엔드 모델로 새 스키마를 임의 생성하지 않았다. |
| 2 | 02-deterministic-dates.patch | unit 공통 요청 및 integration 직접 호출 요청에 service_date=2026-09-16 각각 1줄 추가. 서비스 코드·날짜 assertion·테스트 개수 유지. |
| 3 | 03-missing-http-source-test.patch | 이전 전달에서 빠진 HTTP Source 보존/사용자 미확인 차단/완료 멱등 응답 재생 검증 1건 보완. 기존 confirm 테스트 파일에 1건 추가. |
| 4 | 04-mcp-source-validation.patch | 기존 공동 Schema 수신 validator와 관련 Source 전환/SDK/잘못된 입력/시각 format 테스트 4건 전달. MCP 담당의 별도 후속 수정이 있으면 먼저 충돌/중복을 확인. |

총 4개 patch·6개 대상 파일이다. baseline/target LF SHA-256과 patch checksum은 manifest.json에 있다. 변경 기준은 기존 confirm 통합본 + 앞선 Source 11개 patch 적용 상태다. MCP 두 파일은 앞선 Source ZIP에서 제외됐던 기존 confirm 통합본을 기준으로 한다. 그 이후 팀원 소유 변경이 있다면 강제 적용하지 않는다.

Schema 검증에는 MCP 2.0.0이 이미 요구하는 jsonschema>=4.20.0을 사용한다. 검증 환경은 jsonschema 4.26.0이다. 새 requirements 파일이나 선택적 format 의존성은 추가하지 않았다. 기존 MCP 요구사항으로 설치된 환경에서 import 가능 여부를 확인한다. 승인 flat-plan-proposal.json fixture는 앞선 ZIP의 08 patch에 이미 포함돼 있어 다시 보내지 않는다.

## 적용

이 ZIP과 transit-source-supplement-20260917.zip.sha256을 실제 파일로 함께 전달한다. 문서의 상대 링크만 전달하면 다른 PC에 파일이 생기지 않는다. ZIP checksum을 확인하고 기존 자료와 겹치지 않는 새 폴더로 압축 해제한다.

수신측 저장소 루트에서 아래 경로를 실제 해제 위치로 바꾼다. 가능하면 현재 미커밋 통합본을 보존한 별도 복사본에서 검증한다.

```powershell
$transitSupplementDir = '.\Docs\transit-source-supplement-20260917'
$transitSupplementPatches = @(Get-ChildItem -LiteralPath $transitSupplementDir -Filter '*.patch' | Sort-Object Name | ForEach-Object FullName)
git apply --check @transitSupplementPatches
```

check가 통과한 뒤 적용한다.

```powershell
git apply @transitSupplementPatches
```

현재 MCP 소유 변경 때문에 04만 충돌한다면 01~03의 backend 필수 보완과 04의 공동 MCP 전달을 구분해 조율하고, 04를 억지로 덮어쓰지 않는다. 이미 Source validator/해당 4개 테스트가 있다면 동일 변경인지 checksum/내용을 대조하고 상태를 회신한다. 전체 overwrite·assertion 제거·서비스 의미 변경으로 충돌이나 테스트 실패를 숨기지 않는다.

## 테스트 수 차이의 원인

이전 수령본 기준 backend에는 HTTP Source 전달 및 동일 key 완료 응답 재생 테스트 1건이 없었다. 테스트 파일이 앞선 29개 전달 목록에서 빠진 것이 원인이며 환경 차이가 아니다. 누락 Schema는 수집 항목을 없애는 것이 아니라 이미 수집한 테스트를 실패시킨다.

이번 03 patch는 해당 Source 전용 검증을 1개 항목으로 보완해 수령본 360 → 361개를 맞춘다. 현재 송신 작업 트리의 같은 테스트는 후속 Buffer/details 병행 구현에서 2개 조합으로 확장돼 있다. 그 확장과 추가 후보/계산/정규화 테스트를 이 작은 보완 패키지에 섞지 않았다. 조사 시점 송신 작업 트리에서는 411개가 수집됐으나 수령본 검증 기준과 다르다.

test-count-inventory.json에는 보완본 기준 실제 collect 결과와 파일별 수를 담았다. 수신측에서도 같은 명령으로 수집해 차이가 있으면 파일별로 대조해 주세요.

## 검증 결과

송신측에서 5caef80 + 수령한 confirm 통합 패치 + 이전 Source ZIP의 backend/MCP 실행 관련 파일을 별도 검증본으로 재구성했다. 실제 .env·키·개인 Hermes 설정은 복사하지 않았다.

- 보완 전 backend 전체: **355 passed, 5 failed, 12 warnings / 360개**. 수령증의 Schema 누락 1건·날짜 실패 4건을 동일하게 재현했다.
- 이번 4개 patch의 전체 git apply --check 및 실제 적용: 통과.
- 보완 후 backend 전체: **361 passed, 12 warnings**.
- 관련 MCP HTTP adapter 테스트: **9 tests OK**.
- stdio → 별도 로컬 FastAPI/임시 DB: **exit 0**, 6개 도구·미확인 차단·confirm·stale revision·계획·재탐색 보존·막차, Mock 기반.
- MCP 전체 discovery는 별도 60초 제한에 걸려 완료 결과를 얻지 못했다. 전체 MCP 통과로 보고하지 않는다. 위 집중 9개와 stdio의 통과 범위를 구분한다.

backend 실행은 기존 검증 가상환경의 python으로 검증본 backend에서 `python -m pytest -o addopts= -q -p no:cacheprovider --disable-warnings`, 수집은 `python -m pytest -o addopts= --collect-only -q -p no:cacheprovider`다. MCP 집중은 mcp-server 폴더의 `python -m unittest discover -s tests -p test_backend_http.py -q`, stdio는 저장소 루트의 `python mcp-server/verify_backend_stdio.py`다.

01~03에는 새 날짜 테스트를 추가하지 않았다. service_date 명시로 현재 날짜에 의존하지 않게 했으며 기존 날짜 경계 검증을 보존했다. MCP 04는 이전 공동 검증 구현의 전달이며 실제 Hermes/교통 API 인수를 수행한 것이 아니다.

수신 후 apply check·6개 target checksum·backend 전체 수/결과·관련 MCP/stdio 결과와 충돌 여부를 회신해 주세요. 실제 Source 계획·Buffer/legs·혼합/막차·진행 중 중복 실행은 여전히 별도 인수다. commit/push/배포하거나 비밀값을 전달하지 않았다.
