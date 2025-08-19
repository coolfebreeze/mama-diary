# LLM Analytics API

PostgreSQL + TimescaleDB를 사용한 LLM 사용량 분석 수집 API입니다. FastAPI와 SQLAlchemy Async를 기반으로 구축되었습니다.

## 주요 기능

- **TimescaleDB 하이퍼테이블**: 일별 청크로 자동 파티셔닝
- **gzip 압축 지원**: 대용량 데이터 효율적 전송
- **멱등성 보장**: event_id 기반 중복 제거
- **자동 관리**: 압축, 보존 정책 자동화
- **연속 집계**: 실시간 통계 뷰 제공
- **Docker Compose**: 완전한 개발/운영 환경

## 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│   FastAPI API   │───▶│  TimescaleDB    │
│                 │    │                 │    │   (PostgreSQL)  │
│ - gzip bulk     │    │ - Validation    │    │ - Hypertables   │
│ - JSON payload  │    │ - Error handling│    │ - Compression   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 빠른 시작

### 1. 환경 설정

```bash
# 환경 변수 파일 복사
cp env.example .env

# 필요한 값 수정
vim .env
```

### 2. Docker Compose로 실행

```bash
# 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f api

# 상태 확인
docker-compose ps
```

### 3. API 테스트

```bash
# 헬스체크
curl http://localhost:8000/healthz

# API 정보
curl http://localhost:8000/

# Swagger 문서
open http://localhost:8000/docs
```

## API 엔드포인트

### 사용량 이벤트 수집

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/requests:bulk" \
  -H "Content-Type: application/json" \
  -H "Content-Encoding: gzip" \
  --data-binary @events.json.gz
```

### 메시지 아카이브 수집

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/archives:bulk" \
  -H "Content-Type: application/json" \
  -H "Content-Encoding: gzip" \
  --data-binary @archives.json.gz
```

## 데이터 스키마

### Usage Events (핫 데이터)

```sql
CREATE TABLE analytics.usage_events (
  event_id      UUID PRIMARY KEY,
  event_time    TIMESTAMPTZ NOT NULL,
  user_id       TEXT NOT NULL,
  team          TEXT NOT NULL,
  service       TEXT NOT NULL,
  provider      TEXT NOT NULL,
  model         TEXT NOT NULL,
  total_tokens  INT NOT NULL DEFAULT 0,
  latency_ms    INT,
  status_code   INT,
  error_type    TEXT,
  prompt        TEXT,
  extra         JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Message Archives (콜드 데이터)

```sql
CREATE TABLE analytics.message_archives (
  event_id       UUID PRIMARY KEY REFERENCES analytics.usage_events(event_id),
  user_id        TEXT NOT NULL,
  service        TEXT NOT NULL,
  prompt_full    TEXT,
  response_full  TEXT,
  stored_at      TIMESTAMPTZ NOT NULL
);
```

## 설정 옵션

### 환경 변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `DB_URL` | `postgresql+asyncpg://user:pass@pg:5432/analytics` | 데이터베이스 연결 URL |
| `DB_POOL_SIZE` | `10` | 연결 풀 크기 |
| `MAX_BULK_SIZE` | `1000` | 배치당 최대 아이템 수 |
| `MAX_GZIP_SIZE` | `10485760` | 최대 gzip 크기 (10MB) |
| `COMPRESSION_AFTER_DAYS` | `7` | 압축 시작 일수 |
| `RETENTION_DAYS` | `180` | 데이터 보존 일수 |
| `CHUNK_TIME_INTERVAL_HOURS` | `24` | 청크 시간 간격 (시간 단위) |

### TimescaleDB 정책

- **압축**: 7일 후 자동 압축
- **보존**: 180일 후 자동 삭제
- **청크**: 24시간(1일) 파티셔닝
- **인덱스**: 시간, 팀, 사용자, 서비스별 최적화

## 개발

### 로컬 개발 환경

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 데이터베이스 마이그레이션

```bash
# Alembic 초기화 (필요시)
alembic init alembic

# 마이그레이션 생성
alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
alembic upgrade head
```

## 모니터링

### 헬스체크

```bash
curl http://localhost:8000/healthz
```

응답:
```json
{
  "status": "healthy",
  "database": true,
  "timestamp": "2024-01-01T00:00:00"
}
```

### 로그

```bash
# 애플리케이션 로그
docker-compose logs -f api

# 데이터베이스 로그
docker-compose logs -f postgres
```

## 성능 최적화

### 배치 크기 권장사항

- **소량 데이터**: 100-500 items/batch
- **대용량 데이터**: 500-1000 items/batch
- **gzip 압축**: 50-80% 크기 감소

### 데이터베이스 튜닝

```sql
-- 연결 풀 설정
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';

-- TimescaleDB 설정
ALTER SYSTEM SET timescaledb.max_background_workers = 8;
```

## 보안 고려사항

1. **환경 변수**: 민감한 정보는 `.env` 파일에 저장
2. **네트워크**: 프로덕션에서는 방화벽 설정
3. **인증**: 필요시 API 키 또는 JWT 추가
4. **CORS**: 프로덕션에서는 허용 도메인 제한

## 문제 해결

### 일반적인 문제

1. **데이터베이스 연결 실패**
   ```bash
   docker-compose logs postgres
   docker-compose restart postgres
   ```

2. **TimescaleDB 확장 로드 실패**
   ```sql
   CREATE EXTENSION IF NOT EXISTS timescaledb;
   ```

3. **메모리 부족**
   ```bash
   # Docker 메모리 제한 증가
   docker-compose down
   docker system prune
   ```

## 라이선스

MIT License