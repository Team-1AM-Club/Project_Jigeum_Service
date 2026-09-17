# Source 보완 패키지 수령·검증 회신

2026-09-17, Asia/Seoul. 아래는 수신측 실제 실행 결과입니다.

## 적용 결과

- ZIP SHA-256: `0571fd599f27e867d577fbb9cc3c67f60a5c00c1b459420c1c89959a688d839b` — 전달값과 일치.
- ZIP CRC, 압축 해제 파일의 원본 바이트, 4개 patch checksum 통과.
- 대상 6개 파일은 현재 코드와 manifest의 baseline checksum이 모두 일치. MCP 두 파일을 포함해 충돌·중복 변경 없음.
- 별도 임시 폴더에서 전체 git apply --check 및 실제 적용 통과. 6개 target checksum 모두 일치.
- 기존 파일을 백업하고 작업 트리에 통합. 수령 패키지는 `Docs/transit-source-supplement-20260917/`에 보관.
- 환경파일·API 키·개인 Hermes 설정 보존. commit/push/배포 없음.
- 브랜치 feature/backend-confirm-completion, HEAD 44f61169c050255268ba855c6074a15bb8000a6f의 미커밋 변경 상태.

## 수신측 실행 결과

| 검사 | 결과 |
|---|---|
| 백엔드 전체 pytest | **361 passed, 12 warnings** |
| MCP HTTP/Source 집중 unittest | **9 tests OK** |
| MCP stdio → 실제 로컬 FastAPI/임시 SQLite | **exit 0**, 6개 도구·미확인 차단·confirm·revision 충돌·계획·재탐색 보존·막차 통과 |
| git diff --check | 통과 |

기존 Schema 누락 1건과 날짜 의존 실패 4건은 모두 해결됐습니다. HTTP Source/완료 멱등 재생 테스트 보완으로 수집 수도 360개에서 361개로 일치합니다. 날짜 assertion이나 서비스 계산 의미를 제거/변경하지 않고 제공된 패치 그대로 검증했습니다.

실행 환경: Windows, Python 3.12.14, 기존 저장소 외부 검증 가상환경.

```powershell
# backend 폴더
python -m pytest -q --tb=short --disable-warnings --basetemp=<외부 임시 경로>
# mcp-server 폴더
python -m unittest discover -s tests -p test_backend_http.py -q
# 저장소 루트
python mcp-server/verify_backend_stdio.py
```

## 검증 범위·남은 작업

이번 실행은 합성/Mock 기반이며 실제 교통 계획·Hermes 모델 표시 인수가 아닙니다. MCP 전체 discovery는 이번에 재실행하지 않았습니다.

MCP 담당 후속인 revision 포함 confirm/plan/replan 응답 유실 재전송, 각 HTTP 오류 재시도 금지, 두 번 통신 실패 안내 보완은 이번 패치와 별도입니다. 실제 Source 후보·Buffer/legs·혼합/막차·진행 중 동일 요청의 외부 중복 실행 및 다중 worker 검증도 남아 있습니다.

이번 보완 패키지의 전달 누락·날짜 테스트·수집 수 문제에 대해서는 수신측 통합 및 검증을 완료했습니다.
