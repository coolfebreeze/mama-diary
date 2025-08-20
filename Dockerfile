# Build stage
FROM python:3.11-slim-bookworm AS builder

# [Optional proxy]
ARG http_proxy
ARG https_proxy
ENV DEBIAN_FRONTEND=noninteractive \
    http_proxy=${http_proxy} \
    https_proxy=${https_proxy}

# Copy custom sources.list for better connectivity
COPY sources.list /etc/apt/sources.list

# COPY pip.conf /etc/pip.conf  # Optional: uncomment if you have pip.conf

# Install build dependencies
RUN set -eux; \
    apt-get update -o Acquire::Retries=3; \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    ; \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim-bookworm AS production

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/opt/venv/bin:$PATH"

# Copy custom sources.list for runtime stage too
COPY sources.list /etc/apt/sources.list

# Install runtime dependencies
RUN set -eux; \
    apt-get update -o Acquire::Retries=3; \
    apt-get install -y --no-install-recommends \
        curl \
    ; \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r app && useradd -r -g app app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY app/ ./app/
RUN mkdir -p /app/logs /app/data && chown -R app:app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","4"]

# Development stage
FROM production AS development
USER root
RUN pip install --no-cache-dir pytest pytest-asyncio black flake8 mypy
USER app
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload"]
