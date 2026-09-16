# 공공 교통 연동 계약 및 기준시각 변경안

작성일: 2026-09-16. **변경안 작성은 사용자 승인, 공개 계약 반영은 공동 개발자 합의 대기**다. 이 문서는 `API_SPEC.md`를 대체하지 않으며 현재 코드/예제를 변경하지 않았다.

## 1. 기존 공개 인터페이스 보존

| 인터페이스 | 연동 후 책임 |
|---|---|
| GET /api/v1/health | 프로세스 연결 확인. 외부 교통 제공처 전체 정상 보장이 아님 |
| GET /api/v1/capabilities | 검증된 지역·수단·날짜 및 기능 상태. 매번 모든 외부 API를 호출하지 않음 |
| GET /api/v1/places | 실제 역/정류소 후보. 이름 충돌 해소·선택 가능한 opaque place_id. 임의 주소를 몰래 역/정류소로 변환하지 않음 |
| POST /api/v1/journeys/plan | 기존 확인·revision·멱등성 검증 후 약속 또는 막차 후보 계산 |
| POST /api/v1/journeys/replan | 확인한 새 출발 기준점으로 현재 시각에 재조회; 사용자 선택 전 기존 선택 보존 |
| POST /api/v1/mobility/interpret | 기존 자연어 조건 해석/확인. 이번 API 연동이 모델/확인 규칙을 대체하지 않음 |

새 사용자용 교통 조회 HTTP endpoint나 MCP 도구를 추가하지 않는다. 개별 6+4 서비스 조회·정규화 검증은 내부 Adapter와 백엔드 운영자 검증 모듈에서 실행한다. 이 모듈은 독립 제품 클라이언트가 아니다.

공개 envelope는 status/data/error/meta, transport_modes는 subway/bus, 연결 구간은 walk/wait, 후보 상한은 3을 유지한다. 실제 조회 실패에 is_demo=true 후보를 반환하지 않는다. 확인·선택·revision·멱등성 계약은 현재 `API_SPEC.md`와 기존 003을 기준으로 영향받는 경로만 정합화한다.

## 2. Source.basis_at 변경안

현재 Source는 provider/basis/retrieved_at/service_date만 있어 제공처 기준시각과 조회시각을 구조적으로 구분할 수 없다. 아래 필드를 추가하는 안을 작성한다.

| 필드 | 타입 | 의미 |
|---|---|---|
| basis_at | Asia/Seoul aware datetime 또는 null | 제공처가 데이터의 생성/관측 기준으로 반환한 시각. null은 확인 못함 |

```json
{
  "basis_at": {
    "anyOf": [
      {"type": "string", "format": "date-time"},
      {"type": "null"}
    ],
    "description": "제공처 데이터 기준시각. 조회시각으로 대체하지 않음."
  }
}
```

이 조각은 **제안 Schema**이며 성공 호출 예제가 아니다. 기존 클라이언트와의 전환을 위해 추가 optional 필드로 제안하되, 변경 적용 후 신규 백엔드 응답은 null을 포함해 명시한다. 엄격한 MCP Schema를 포함한 양쪽 호환 검증이 선행한다. field required 여부를 포함한 최종 계약은 공동 합의로 확정한다.

- realtime 근거의 기준시각을 확인하지 못하면 null이고, 이를 검증된 현재 운행 근거로 사용하지 않는다. 일정만으로 유효한 후보는 schedule 근거와 경고로 구분한다.
- null을 retrieved_at/generated_at/server_time으로 채우지 않는다.
- schedule/static의 개정 기준이 날짜뿐이면 임의 00:00 timestamp를 생성하지 않는다. 내부 reference_date/revision 및 사용자 경고에 정확한 원본 기준을 보존한다.
- 과거 fixture는 실제 조회로 인정하지 않는다. Demo 출처가 하나라도 있으면 meta.is_demo=true다.
- refresh_after는 기존 계약의 재확인 권고이며 데이터 최신성/승차 보장이나 자동 조회 지시가 아니다.

실제 적용 순서: 공동 개발자 합의 → API_SPEC.md와 Docs/api/examples.json 동시 갱신 → Source/응답 스키마·fixtures·계약 테스트 → MCP JSON Schema/표시 갱신 → 합성 및 실제 응답 대조. 이번 계획에서는 이 순서를 실행하지 않았다.

## 3. 결과/오류 매핑

| 내부 원인 | 기존 공개 응답 | 자동 재시도 |
|---|---|---|
| 미확정/오래된 장소 ID | 422 error PLACE_NOT_RESOLVABLE | 없음 |
| 서울/제공처 범위 밖 | 200 unavailable OUT_OF_SERVICE_AREA | 없음 |
| 미래 약속 운행/보행 근거 부족 | 200 unavailable APPOINTMENT_TIME_UNSUPPORTED | 없음 |
| 운행일/노선/편/보행/검색 완전성으로 막차 검증 불가 | 200 unavailable LAST_JOURNEY_UNSUPPORTED | 없음 |
| 충분한 지원 자료에서 완전 탐색 후 연결 없음 | 200 unavailable NO_FEASIBLE_JOURNEY | 없음 |
| 마지막 연결 여정은 있으나 5분 정책 여유 확보 불가 | 200 unavailable BUFFER_REQUIREMENT_NOT_MET | 없음 |
| 실제 정상 빈 검색 결과 | 기존 places 정상 빈 목록; 계획은 충분한 지원 범위/완전 탐색 여부로 판정 | 없음 |
| 키/권한 설정 문제 | 503 error PLACE_PROVIDER_UNAVAILABLE 또는 ROUTING_PROVIDER_UNAVAILABLE, 안전한 안내, retryable=false | 없음 |
| 한도 초과 | 429 error RATE_LIMITED, 확인된 Retry-After만 전달 | 없음 |
| 일시 연결/제공처 장애 | 503 error 해당 PROVIDER_UNAVAILABLE | 계약상 허용 원인에만 공통 client가 500ms 후 최대 1회 |
| 외부/전체 deadline 초과 | 504 error UPSTREAM_TIMEOUT | 남은 전체 시간/횟수가 있을 때 외부 timeout에만 최대 1회; workflow retry 없음 |
| 깨진 JSON/XML/업무 응답·의미 검증 실패 | 502 error UPSTREAM_RESPONSE_INVALID | 없음 |

현재 코드에 없는 unavailable 분기 등은 영향받는 기존 공개 계약의 구현 정합화이며 새로운 오류 의미를 임의 도입하지 않는다. upstream HTTP 200의 오류도 업무 코드로 분류한다. 원문 key/URL/오류 메시지/스택은 공개 error에 포함하지 않는다. 예산 중단·자료 부족을 경로 없음으로 변환하지 않는다.

retryable은 기존 계약상 같은 입력으로 나중에 재시도 가능한지를 뜻한다. 명시적 false는 HTTP 상태보다 우선한다. provider retry 소진/예산 소진을 MCP가 동일 workflow의 반복 실행으로 증폭하지 않도록 최종 retryable을 정합화한다. 최종 오류·한도·deadline 매핑은 contract tests로 검증한다.

## 4. 내부 제공처 경계

기존 `ProviderResult`의 성공/실패 의미를 유지한다. 내부 데이터는 [data-model.md](../data-model.md)의 근거 모델로 만들고 공개 결과로 변환하기 전에 스키마/의미를 검증한다. `ok=false`를 성공 빈 목록이나 Mock으로 바꾸지 않는다. `ok=true`여도 요청에 필요한 날짜·좌표·편·연결 근거가 없으면 계산 미지원이다.

PlaceProvider는 역/정류소 ID 대응을 보존한다. RoutingProvider는 검증된 구간·시간·출처만 반환한다. TransitProvider는 관측과 시간표를 구분한다. 기존 인터페이스를 수정해야 한다면 모든 callers/Mock/서비스/tests를 함께 영향 분석하며 역할이 같은 별도 인터페이스를 중복 생성하지 않는다.

서비스별 ID/인증 방식과 host/path는 공식 활용명세에 근거해 확정한다. 최단경로는 사용자 정정으로 OA-22724/getShtrmPath이며 KEY path 인증과 역명·검색일시 입력을 동적 명세에서 확인했다. 허브 100178은 소개이고 15143842로 자동 대체하지 않는다. OA-22724의 XML header/body 구조·시간 단위·운행편/날짜 대응·pagination 완전성을 실제 검증한다. 날짜/역명은 path segment로 정확히 escaping하며 요청 전 검색에서 선택한 역코드/호선과 반환 역을 대조한다. 키 배정 혼동 가능성은 실제 인증 전 미검증 상태다. 추가 후보 15000414는 채택되지 않았다.

## 5. 상태 변경 및 수용 범위

입력·확인·conversation/revision/idempotency 검증 → DB 쓰기 트랜잭션 밖 provider 호출 → 결과 검증 → 짧은 트랜잭션에서 만료/revision/멱등성 재검증 → 기존 상태 적용 순서를 보존한다. 실패·취소·상태 충돌은 이전 선택과 TTL/revision을 변경하지 않는다. 성공 재생은 외부 조회 0회다.

각 API 조회 성공, 실제 약속 성공, 실제 막차 성공은 별도의 증거다. 현재 전부 미실행이며 버스 미래 운행/보행 자료 확보 전에는 관련 SC-007~009를 통과로 표시하지 않는다.
