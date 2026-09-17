# Source 패키지 수령·통합 검증 회신

작성일: 2026-09-17 (Asia/Seoul). 수신측 실제 실행 결과.

## 패키지 확인

- ZIP: transit-source-integration-20260916.zip
- SHA-256: 27c2f110f2b91a6fe0ebafcadc4d609054d2a7fb00852c0e52ef033a4cb2c5cd — 전달 checksum과 일치.
- ZIP CRC 및 압축 해제 14개 파일 바이트 일치 확인.
- 11개 patch checksum 모두 일치.
- 대상 29개 파일의 수신측 현재 내용이 manifest baseline checksum과 모두 일치. 중복 적용·충돌 없음.
- 별도 임시 폴더에서 전체 `git apply --check` 및 실제 적용 통과. 적용 후 29개 target checksum도 모두 일치.
- 기존 파일 백업 후 현재 작업 트리에 반영. `.env`·키·개인 Hermes 설정·MCP 담당 파일 변경 없음.
- 수신측 branch: feature/backend-confirm-completion, 기준 HEAD 44f61169c050255268ba855c6074a15bb8000a6f. commit/push/배포 없음.
- 수령본 보관: Docs/transit-source-integration/.

## 실행 결과

1. backend pytest: **355 passed, 5 failed, 12 warnings / 총 360개**.
2. 실제 MCP stdio → 로컬 FastAPI/임시 DB: **통과(exit 0)**. 6개 도구, 미확인 차단, confirm, stale revision, 계획, 재탐색 보존, 막차 검증. Mock 기반이며 실제 교통·Hermes 모델 인수는 아님.
3. 후보 수 기본 3/상한 5 회귀 테스트(test_transit_capabilities.py): 전체 실행 중 통과.

실행 명령:

```powershell
# backend 폴더, 기존 외부 검증 가상환경
python -m pytest -q --tb=short --disable-warnings --basetemp=<외부 임시 경로>
# 저장소 루트
python mcp-server/verify_backend_stdio.py
```

## 실패 원인 및 필요한 후속 자료

### 1. 공유 Schema 누락 — 1개

`backend/tests/contract/test_transit_source_contract.py::test_shared_source_schema_matches_backend_models`가 `Docs/api/source-envelope.schema.json`을 읽지만 해당 파일이 없습니다. ZIP manifest에도 포함되지 않았습니다.

**요청:** 실제 공동 검증에 사용한 `Docs/api/source-envelope.schema.json`과 그 파일의 관련 MCP 테스트/의존 자료가 따로 있다면 별도 패치·manifest로 전달해 주세요. 이쪽에서 모델로 동일 스키마를 임의 생성해 테스트만 통과시키지 않았습니다.

### 2. 날짜 의존 기존 테스트 — 4개

- `tests/unit/test_last_journey_service.py::TestLastJourneyPlan::test_plan_last_journey_returns_plan_with_next_day_arrival`
- `tests/unit/test_last_journey_service.py::TestArrivalDateBoundary::test_arrival_date_next_day_when_crossing_midnight`
- `tests/unit/test_last_journey_service.py::TestArrivalDateBoundary::test_arrival_date_same_day_when_not_crossing_midnight`
- `tests/integration/test_last_journey_e2e.py::TestLastJourneyE2EWithActualMock::test_e2e_last_journey_operating_date_arrival_date_distinction`

고정 fixture는 9월 16~17일을 사용하지만 service_date가 없는 요청의 operating_date는 실제 현재 날짜를 사용합니다. 9월 17일 실행에서 비교가 어긋났습니다.

이번 Source 패치 이전 통합본을 보존한 별도 임시 폴더에서도 동일한 두 테스트 파일을 실행해 **같은 4개 실패(11개 통과)**를 재현했습니다. 따라서 새 Source 패치만의 회귀로 보지 않습니다. 담당 범위를 존중해 백엔드 코드는 추가 수정하지 않았습니다. 테스트 요청의 service_date 또는 기준시각 고정을 통해 날짜 경계 검증을 결정적으로 만드는 수정이 필요합니다. 서비스 의미를 바꾸거나 assertion을 제거하는 방식은 피해야 합니다.

### 3. 송신측 테스트 개수 차이

송신 문서의 361개와 달리 수령 패키지를 적용한 이쪽은 360개가 수집됐습니다. 누락 Schema 외에 테스트 파일/후속 변경이 빠졌는지도 확인 부탁드립니다. 원인을 확인하지 않고 단순 환경 차이로 단정하지 않았습니다.

## 다음 상태

파일 통합은 완료했지만 전체 회귀 통과·004 완료로 표시하지 않습니다. 실제 Source 후보·Buffer/legs·Hermes 표시 인수와 진행 중 중복 실행 검증은 여전히 별도입니다. MCP 담당의 추가 재전송/안내 테스트는 이번 수령 검증에서 수행하지 않았습니다.
