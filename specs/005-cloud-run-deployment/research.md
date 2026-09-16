# Cloud Run 배포 연구

**확인일**: 2026-09-16
**상태**: Phase 0 조사 및 차단 사유 기록. 사용자가 0원 유지·서울 배포 보류를 확정했다. 미답변 없음. Phase 1 미진행.

공식 문서와 저장소를 읽기 전용으로 조사했다. 실제 GCP 자원·결제·권한은 조회하거나 변경하지 않았다. 아래 선택 후보는 배포 승인이나 비용 0원 보장이 아니다.

## 1. 실행 구성

**결정 후보**: 요청 기반 Cloud Run, min instances 0, 서비스 수준 max instances 1, 1 vCPU/512 MiB, 초기 concurrency 1. cold start를 허용한다.

**근거**: 사용자는 팀원 2명·하루 합계 100회 이하·약 1개월 시연을 선택했다. 상시 실행 CPU는 필요하지 않다. max instances는 비용의 절대 상한이나 데이터 동시성 보장이 아니며, revision 교체·일시 초과를 감안한 저장 transaction이 필요하다.

**검토한 대안**: instance-based/상시 최소 인스턴스는 무호출 비용 우려로 제외. 원격 MCP·VPC connector·로드밸런서·별도 도메인·CI/CD는 현재 범위에 필요하지 않다.

**출처**: [Cloud Run 가격](https://cloud.google.com/run/pricing), [최대 인스턴스 제한](https://docs.cloud.google.com/run/docs/configuring/max-instances-limits), [컨테이너 계약](https://docs.cloud.google.com/run/docs/container-contract).

## 2. 상태 저장 후보

**결정 후보**: 서울(`asia-northeast3`) Cloud Run과 동일 리전의 Firestore Native Standard `(default)` DB. 무료 적용 대상인 기존 DB인지 먼저 확인하며 다른 기능의 DB 위치·설정을 변경하지 않는다. `google-cloud-firestore`를 사용하는 작은 adapter를 검토한다.

**근거**: 컨테이너 파일은 종료 후 유지되지 않는다. Firestore는 transaction으로 revision·상태·idempotency 성공 기록을 함께 기록할 수 있고 소규모 사용량의 무료 범위가 있다. 한 프로젝트의 무료 대상 DB는 하나이므로 이름만 보고 무료라고 판정하지 않는다.

**검토한 대안**: 로컬 SQLite 및 Cloud Storage에 SQLite 파일 업로드/마운트는 여러 revision의 일관된 transaction·손실 없는 복구를 충족하지 않는다. Cloud SQL은 상시 비용이 0원 조건에 부적합하다. 외부 무료 DB는 별도 계정·접근 경계·휴면 정책을 추가하므로 현재 후보보다 단순하지 않다.

**주의**: 현재 HTTP 경로는 저장 연동이 완성되지 않았다. `/mobility/interpret`는 전달된 ID 또는 빈 값, 고정 revision 1, 현재 시각+1일을 응답 메타에 넣는다. `/journeys/plan`은 계산 서비스 응답을 반환하지만 DB 호출을 하지 않는다. 저장 모델의 존재를 상태 보존 구현 완료로 해석하면 안 된다. 기존 상태 기능의 선행 작업과 adapter 연결을 구분한다.

**출처**: [Firestore 가격](https://cloud.google.com/firestore/pricing), [쿼터](https://docs.cloud.google.com/firestore/quotas), [트랜잭션](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions).

## 3. 데이터·원자성 설계 제약

**결정**: 공개 JSON 및 기존 상태 의미를 보존한다. 저장 원자성은 인스턴스 수 설정에 의존하지 않는다. provider 호출은 transaction 밖에서 실행하며 commit 직전 만료, 같은 key 성공 기록, revision을 다시 확인한다. transaction callback은 자동 재실행될 수 있으므로 외부 호출이나 다른 부수 효과를 넣지 않는다.

Conversation 문서와 개별 idempotency 기록을 분리하는 안을 우선 검토한다. 경로·응답 payload는 검색하지 않는 필드의 indexing을 해제해 저장량과 index 증폭을 줄인다. 한 문서 1 MiB, transaction 요청 10 MiB 제한을 fixture·최대 후보·응답으로 검증한다. 전체 대화 이력을 단일 문서에 계속 누적하지 않는다.

저장 오류는 일반 `500 INTERNAL_ERROR` 계약에 맞춰 민감한 예외 문자열 없이 반환하며, 없는 대화나 성공으로 바꾸지 않는다. 저장 데이터가 부족한 때 SQLite/메모리로 자동 fallback하지 않는다.

**출처**: [쿼터](https://docs.cloud.google.com/firestore/quotas), [트랜잭션](https://docs.cloud.google.com/firestore/native/docs/manage-data/transactions).

## 4. 만료와 정리: 사용자 결정 반영

**결정**: 만료 검사는 요청 시 즉시 수행한다. 물리적 정리는 다음 시작·요청 시 실행해도 된다는 사용자 답변을 받았다. 만료 기록이 남아 있으면 410, 삭제됐거나 처음부터 없으면 404로 구분한다. `expired_at`과 tombstone 정리 기준을 다시 요청했다고 연장하지 않는다.

**근거**: request-based/min=0 환경은 무호출 background timer의 실행을 보장하지 않는다. Firestore TTL은 무료 대상이 아니며 비동기 삭제라 원자 payload 제거·24시간 tombstone 규칙을 대신할 수 없다. 따라서 TTL/PITR/백업/복제/복구 기능은 이번 무료 구성에서 켜지 않는다.

**계약 선행 작업**: 현재 API 문서에 없는 대화 410과 hard delete 후404가 공존한다. startup+periodic 정리 문구도 이번 사용자 결정과 맞춰야 한다. 두 개발자가 `API_SPEC.md`와 `Docs/api/examples.json`을 함께 정합화한 후 구현한다. 이 연구에서는 원본 계약 파일을 변경하지 않았다.

정리는 한 번에 처리할 수량·transaction 크기를 제한하고 continuation을 유지하는 방식으로 설계한다. 논리적 만료는 정리 backlog와 관계없이 즉시 적용한다. 늦게 발견한 만료의 원래 시각과 tombstone 기준을 보존하며, child 기록에 응답 payload가 남는 문제도 검증한다. 구체적인 물리적 purge 작업 단위는 Phase 1에서 확정한다.

**출처**: [Firestore TTL](https://docs.cloud.google.com/firestore/native/docs/ttl), [Cloud Run 과금 설정](https://docs.cloud.google.com/run/docs/configuring/billing-settings).

## 5. 팀 호출 인증 후보

**결정 후보**: 사용자가 준비한 팀용 Google 계정으로 승인된 로컬 환경에서 user ADC를 구성하고 IAM Credentials `generateIdToken`으로 caller service account의 짧은 수명 ID token을 받는다. audience는 실제 Cloud Run service URL, `includeEmail=true`. 로컬 MCP는 만료 전 토큰을 갱신하고 로그·응답·설정 예제에 기록하지 않는다. 사용자 계정의 비밀번호·복구 코드·ADC 파일을 저장소로 전달하거나 공유하는 절차는 만들지 않는다.

**권한 후보**: 확인된 팀용 Google principal은 caller SA 리소스에 `roles/iam.serviceAccountOpenIdTokenCreator`, caller SA는 해당 서비스에 `roles/run.invoker`. runtime SA는 별도로 두고 해당 Firestore DB만 접근하도록 IAM 조건을 검증한 `roles/datastore.user`. 배포 주체의 관리 권한은 런타임/호출자에 전이하지 않는다. principal을 추가해야 할 때는 해당 주체와 범위를 확인한다.

**근거**: 공유 key나 JSON 서비스 계정 키 파일이 필요하지 않고 토큰 audience를 서비스로 한정할 수 있다. 로컬 인터넷 호출을 위해 ingress를 허용하되 Invoker 검사를 유지한다. `allUsers`/`allAuthenticatedUsers` 바인딩은 하지 않는다. Cloud Run이 먼저 거부하는 인증 응답은 backend JSON envelope와 다를 수 있으므로 MCP에서 HTTP 인증 실패로 처리해야 한다.

**대안**: 직접 user identity token은 개발 시연에 간단하지만 audience 제한이 약하다. ADC `--impersonate-service-account` 경로는 더 넓은 `roles/iam.serviceAccountTokenCreator`를 요구하므로 직접 `generateIdToken` 최소권한 경로와 섞어 설명하지 않는다. MCP 코드가 이 저장소에 없어 실제 지원 여부는 인계·통합 검증이 필요하다.

**사용자 확인**: 별도로 만든 팀용 Google 계정에서 진행한다. 실제 principal 주소와 권한은 자원 변경 전에 확인한다. 두 명 각각의 Google 계정 사용을 가정하지 않으며 현재 계획에 계정 주소를 저장하지 않는다.

**출처**: [ID token 발급 권한](https://docs.cloud.google.com/iam/docs/create-short-lived-credentials-direct), [로컬 ADC](https://docs.cloud.google.com/docs/authentication/set-up-adc-local-dev-environment), [개발자 인증](https://docs.cloud.google.com/run/docs/authenticating/developers), [서비스 인증](https://docs.cloud.google.com/run/docs/authenticating/service-to-service), [Firestore IAM](https://docs.cloud.google.com/firestore/native/docs/security/iam).

## 6. 비용 검토 기준

확정 사용 규모는 팀 합계 100회/일 × 30일 = 3,000회다. 아래 수치는 실제 계측값이 아니라 설계를 검증하기 위한 계산 예시·운영 목표다. 재시도, 검증, startup/shutdown, 정리 비용도 실제 합계에 포함해야 한다.

| 자원 | 사용량 검토 기준 | 공식 무료 범위/비용 경계 |
|---|---|---|
| Cloud Run 요청·CPU·메모리 | 3,000회 × billed 10초 예시 = 30,000 vCPU초 및 15,000 GiB초; cold start 등 가산 | 요청 기반 월 200만회, 180,000 vCPU초, 360,000 GiB초. 결제 계정 공유·리전 가격 기준 확인 |
| Cloud Run egress | 응답 100 KiB 가정 시 약 0.286 GiB/월 + 기타 전송량 | 서울발 인터넷 응답은 유료. 북미 무료 범위를 적용하지 않음. 실제 지역/목적지/통화 SKU 단가 확인 필요 |
| Firestore | 일 read/write/delete 및 document/index 저장량을 emulator/실제 사용량으로 계측. 100회 호출과 100회 DB 연산은 같지 않음 | 무료 대상 DB 하나: 1 GiB 저장, 50,000 reads/day, 20,000 writes/day, 20,000 deletes/day, 10 GiB outbound/month. 일일 reset은 Pacific 자정 |
| Artifact Registry | 현재·직전 정상 이미지의 실제 고유 layer 합계와 유지 기간 측정 | 계정당 0.5 GiB-month. 동일 location pull 외 egress, scanning 별도 |
| 빌드 | 로컬 Docker 빌드 후 push 우선 검토; 가능 여부 확인 필요 | Cloud Build를 쓰면 default pool e2-standard-2에만 월2,500분 promotional 무료. staging bucket까지 별도 계산 |
| 로그 | 요청 body·token·장소/자연어 payload를 기록하지 않고 최소 운영 로그만 사용 | Logging 50 GiB/project/month, 기본 30일 보관. 장기 retention 별도 |
| 기타 | 선택한 구성에 실제 존재하는 source/log bucket, secrets, API 기능을 목록화 | 없는 서비스를 무료라고 덧붙이지 않음. Cloud Storage 무료 리전·operation 조건 별도 확인 |

사용자는 서울 `asia-northeast3`를 선택했다. Cloud Run과 Firestore/Registry를 서울에 함께 두는 안을 검토하며 미국으로 임의 변경하지 않는다. Cloud Run 가격은 인터넷 outbound를 Premium Network Tier 요금으로 청구하고 무료 전송량을 북미에 한정한다. 따라서 크레딧이 없는 유료 계정의 서울→한국 로컬 MCP 응답을 0원으로 산정할 수 없다. 네트워크 요금표의 기본 표시 리전은 Iowa이므로 기본 표의 가격을 서울의 확정 단가로 전용하지 않는다. 정확한 원화 추정은 실제 서울/목적지 SKU·계정 통화·응답 크기를 확인한 뒤 계산한다. 소액이라도 FR-007의 0원 조건을 넘으면 사용자 결정 전 진행하지 않는다.

사용자 제공 정보는 유료 결제 계정, 체험 크레딧 소진이다. 실제 프로젝트의 결제 연결/활성 상태, 공유 무료 사용량 잔여분과 DB 무료 대상을 확인해야 한다. 크레딧이 없더라도 적격 월 무료 사용량은 별도로 적용될 수 있지만 모든 비용이 무료라는 뜻은 아니다. 기존 0원 지출 목표는 아직 변경되지 않았다.

**출처**: [Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features), [Run 가격](https://cloud.google.com/run/pricing), [네트워크 가격](https://cloud.google.com/vpc/network-pricing), [Firestore 가격](https://cloud.google.com/firestore/pricing), [Registry 가격](https://cloud.google.com/artifact-registry/pricing), [Build 가격](https://cloud.google.com/build/pricing), [Logging 가격](https://cloud.google.com/logging/pricing).

## 7. 지출 통제·복구

**결정**: 예산 알림, max instances, 요청 수/시간 운영 기준은 총 청구액의 hard cap으로 설명하지 않는다. 비용 확인 주기와 사용 중단 기준은 실제 무료 잔여량이 확인된 후 확정한다. 중단은 이 배포에만 적용하고 공유 프로젝트의 billing/타 서비스는 변경하지 않는다.

Spend Caps는 현재 Preview로 존재하지만 단일 프로젝트·지원 서비스의 할인 전 gross estimated cost 기준이며 지연 중 비용과 일부 잔여 resource 비용이 생길 수 있다. 실제 계정 지원·0원 threshold 지원은 미확인이다. 이번 구성의 0원 보장 근거로 사용하지 않는다.

이전 정상 revision과 호환되는 저장 schema를 유지한다. 단순 traffic rollback이 저장 schema rollback을 해 주지 않으므로 파괴적인 데이터 migration은 범위 밖이다. 이미지 보관은 복구 가능성과 무료 저장량을 함께 충족해야 한다.

**출처**: [Spend cap budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).

## 8. Phase 0 종료 조건

- 해소: 서울 리전, 유료 계정·크레딧 소진, 팀용 Google 계정 사용.
- 최종 결정: 사용자가 0원 유지와 서울 배포 보류를 선택했다. 월1,000원 등 소액 지출 대안은 채택하지 않았다. 미답변은 없지만 비용 게이트 BLOCK-COST-001은 해소되지 않았다.
- 실제 계정·무료 잔여량·project ID/number·기존 DB/리전은 계획과 별개의 배포 전 조회 게이트다. 미조회 자체를 기술 설계 완료나 배포 준비 완료로 바꾸지 않는다.
- Phase 1 데이터 설계·계약·quickstart는 작성하지 않는다. 향후 사용자가 재개를 요청하고 비용 게이트를 해소한 경우에만 실제 코드·계정 조건을 다시 확인한 뒤 진행한다.
