# MCP 서비스의 계산 백엔드

친구 담당: FastAPI, 서비스 Agent·Skill 실행, Solar·공공데이터 연결, 코드 기반 계산, Cloud Run 배포. 사용자에게 제공되는 제품은 MCP이며 이 백엔드는 MCP 도구의 요청을 처리한다. 본인은 MCP·Hermes 연결과 시연을 담당한다.

## 빠른 시작

### Prerequisites
- Python 3.11+
- pip

### 환경 설정

```bash
# 저장소 루트에서
cd backend

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (선택 사항, 기본값은 개발용)
cp .env.example .env
# .env 파일을 편집하여 필요 시 값 변경
```

### 서버 실행

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- API 문서: http://127.0.0.1:8000/docs
- health 체크: http://127.0.0.1:8000/api/v1/health

### 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECRET_KEY` | `change-me-in-production` | 세션/서명 키 (프로덕션 필수 변경) |
| `DATABASE_URL` | `sqlite:///./jigeum.db` | 데이터베이스 연결 문자열 |
| `ENVIRONMENT` | `development` | `development` 또는 `production` |
| `API_VERSION` | `v1` | API 버전 |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8080` | CORS 허용 출처 (콤마 구분) |
| `PLACES_PROVIDER` | `mock` | 장소 제공자 (mock/실제) |
| `ROUTING_PROVIDER` | `mock` | 라우팅 제공자 (mock/실제) |
| `TRANSIT_PROVIDER` | `mock` | Transit 제공자 (mock/실제) |
| `MODEL_PROVIDER` | `mock` | 모델 제공자 (mock/실제) |
| `MODEL_PROVIDER_BASE_URL` | `http://localhost:8001` | 모델 제공자 기반 URL |
| `MODEL_PROVIDER_API_KEY` | `` | 모델 제공자 API 키 |

## 프로젝트 구조

```
backend/
├── app/
│   ├── main.py          # FastAPI 앱 진입점, 미들웨어, 예외 핸들러
│   ├── config.py        # 환경 설정 (pydantic-settings)
│   ├── db.py            # 데이터베이스 연결
│   ├── api/             # 라우터 (health, capabilities, places, mobility, journeys)
│   ├── schemas/         # Pydantic 모델 (요청/응답 검증)
│   ├── services/        # 비즈니스 로직 (plan, interpret, replan, idempotency, 대화 상태 등)
│   ├── models/          # SQLAlchemy 모델 (conversation, idempotency, plan)
│   └── agents/          # MainAgent·SubAgent (준비 중)
├── tests/
│   ├── unit/            # 단위 테스트 (서비스 계층)
│   ├── contract/        # 계약 테스트 (API 스키마·상태 코드)
│   └── integration/     # 종단 간 통합 테스트
├── Dockerfile
├── requirements.txt
└── README.md
```

## 테스트 실행

아래 명령은 `backend` 디렉터리에서 실행한다. 저장소에 남아 있는
`.test_venv_fresh`는 사용하지 않는다. 이번 검증은 저장소 밖 전용 환경에서 수행했다.
서버는 시작 시 SQLite 테이블과 확인 상태용 신규 컬럼을 생성한다.
기존 행의 확인 플래그는 false이며 다시 interpret → confirm 절차를 거쳐야 한다.
대화 만료 정리는 시작 시 및 60초마다 실행하며, 요청 시에도 만료를 검사한다.
실제 provider·Hermes·Solar·배포 검증은 포함하지 않는다. 모든 응답은 demo다.

```bash
# 전체 테스트
python -m pytest tests/ -v

# 단위 테스트만
python -m pytest tests/unit/ -v

# 계약 테스트만
python -m pytest tests/contract/ -v

# 통합 테스트만
python -m pytest tests/integration/ -v

# 특정 테스트 파일
python -m pytest tests/unit/test_plan_service.py -v
```

### 커버리지 측정

```bash
pip install pytest-cov
pytest backend/tests/ --cov=backend.app --cov-report=term-missing
```

## Docker

### 빌드
```bash
cd backend
docker build -t jigeum-api .
```

### 실행
```bash
docker run -p 8000:8000 jigeum-api
```

### Cloud Run 배포 (예시)
```bash
gcloud run deploy jigeum-api \
  --image gcr.io/PROJECT_ID/jigeum-api:latest \
  --platform managed \
  --port 8000 \
  --allow-unauthenticated
```

## API 문서

- [API_SPEC.md](../API_SPEC.md): 전체 API 명세
- [Docs/api/examples.json](../Docs/api/examples.json): 요청/응답 예제
- Swagger UI: `/docs` (서버 실행 후)

## 개발 가이드

- API 변경 시 `API_SPEC.md`와 `examples.json`을 함께 갱신한다.
- 새로운 엔드포인트 추가: `app/api/`에 라우터 파일 생성 → `app/main.py`에 등록
- 새로운 스키마 추가: `app/schemas/`에 파일 생성
- 새로운 서비스 추가: `app/services/`에 파일 생성
- 테스트는 해당 구현 파일과 동일한 이름의 test 파일로 작성 (예: `services/plan_service.py` → `tests/unit/test_plan_service.py`)

## 린터·포매터

```bash
# black 포매팅
black backend/

# isort 정렬
isort backend/

# ruff 린트
ruff check backend/
```

## 주의사항

- 비밀키·환경 변수는 저장소에 커밋하지 않는다. `.env.example`만 참조용으로 유지한다.
- 백엔드의 비밀키를 Hermes 대화·설정 예제·로그에 노출하지 않는다.
- 실제 API 키는 합의 후 설정하며, 현재는 mock 제공자로 동작한다.
