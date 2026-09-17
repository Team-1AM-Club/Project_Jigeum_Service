# 전달 패키지의 검증 범위

작성일: 2026-09-16 (Asia/Seoul)

## 송신측 실행 기록

- 백엔드 전체: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --disable-warnings`, **361 passed, 12 warnings**. 실제 제공처 호출을 포함하지 않는 회귀 테스트다.
- `seoul_subway.py`, `test_seoul_subway.py`, `capabilities.py`, `test_transit_capabilities.py`의 Black/isort/Ruff 통과.
- OA-15442 순수 역 row 정규화 테스트 12건. 필수 문자열·STATION_CD/FR_CODE namespace·선행 0·Evidence service/operation·좌표/시각 미생성을 검증한다. 실제 client/시간표/최단경로 계산 완료를 뜻하지 않는다.
- capabilities는 TripRequest 스키마에서 기본 3/상한 5를 읽는다. 이 수정과 공유 예시를 패키지에 포함했다. 배포 반영은 확인하지 않았다.
- 읽기 전용 별도 검토에서 새 정규화/capabilities의 중요한 correctness/secret/contract 결함이 발견되지 않았다.
- 11개 patch의 SHA-256과 29개 대상 파일의 UTF-8/LF checksum 일치 및 현재 작업 트리의 `git apply --reverse --check` 통과. 수신측 apply check를 대신하지 않는다.

## 기존 병행 검증 기록

004의 `mcp-source-deployment-verification.md`에는 MCP 95 passed·1 skipped, Mock stdio, 공유 Source/warnings 수신 검증 및 Hermes + Solar Pro4의 capabilities/장소 검색 실제 호출이 기록돼 있다. 해당 기록의 실행 주체와 환경을 수신측 실행으로 바꾸지 않는다. 개인 주소 `http://127.0.0.1:18080/api/v1`에서 관측 응답은 `is_demo=true`다. 다른 PC의 같은 loopback 주소가 같은 서버라는 보장은 없다.

송신측 연결 점검도 Hermes v0.21.2/solar-pro4의 실제 get_capabilities 1회와 Demo 표시를 확인했다. 도구 설명 호출은 별도다. 개인 Hermes 설정이나 자격증명은 전달하지 않는다.

## 실제 제공처 최소 probe와 한계

기존 live-verification.md의 실제 최소 probe는 지하철 6개 alias의 최소 operation 정상 응답, 버스 4개 alias HTTP 401 후 중단이다. 지정 서비스별 키만 사용했고 OA-101/OA-110/OA-22724 키를 자동 교환하지 않았다. 최단경로 sample 날짜 입력의 인증/구조 확인은 미래 약속 인수가 아니다. probe의 `basis_at=null`, `verified_for_planning=false`를 유지했다.

사용자는 버스 승인·일반 인증키 입력 및 OA-21232 추가 자료 채택을 확인했다. 버스 401 해결이나 OA-21232 기존 키 사용 가능성을 실제 검증한 것은 아니다. 새 자료는 이 패키지에서 연동하지 않는다.

## 남은 조건

- T015는 operation별 공식 근거·확인/미확정 상태·계산 제외 조건의 기록만 완료했다. 실제 ETA 기준/시각/단위 규칙(T039/T040)은 미확정 사항이 남는다. 현재 작업 목록은 17/79다.
- T018/T019는 실제 제공처 원문→Evidence/Source 변환 및 Source 포함 후보의 실제 Hermes 표시가 남는다.
- 실제 좌표/역코드/운행일·시간 단위 근거, 전체 지하철/버스 정규화, 실제 보행/시간표 보완 자료, 약속/혼합/막차 계획, Buffer/legs 합계·계산·표시는 아직 미완료다.
- 진행 중 동일 HTTP 멱등 key의 중복 외부 조회 방지·worker/인스턴스 간 보장은 미구현·미검증이다. ProviderClient 요청 내부 중복 제거와 구분한다.
- MCP의 revision 포함 POST 재전송과 수신 429/502/503/504별 합성 검증, 불확실한 처리 결과 안내 보완은 팀원의 후속 작업이다.
- 배포 코드 식별·worker/replica 수·실제 DB 공유 범위·후보 수 반영 상태는 아직 확인이 필요하다. HTTPX 시도별 timeout을 전체 경과시간 상한으로 설명하지 않는다.

이 문서와 패키지 전달 과정에서 commit/push/배포하지 않는다. 신규 공개 오류·상태·resume 계약이나 DB·인프라를 도입하지 않는다. 키 파일·토큰·전체 로그·개인 이동 이력을 포함하지 않는다.
