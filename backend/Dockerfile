# Jigeum API 백엔드 Docker 이미지
FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# uvicorn이 0.0.0.0에서 리스닝하도록 환경 변수 설정
ENV HOST=0.0.0.0
ENV PORT=8000

# Cloud Run에서 주입하는 PORT 사용 (기본 8000)
EXPOSE 8000

# 서버 기동
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
