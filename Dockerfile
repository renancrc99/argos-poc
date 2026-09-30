FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala uv via imagem oficial
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Instala dependências antes de copiar o código (layer cacheada)
COPY pyproject.toml ./
RUN uv pip install --no-cache \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "pydantic>=2.9.0" \
    "pydantic-settings>=2.5.0" \
    "httpx>=0.27.0" \
    "boto3>=1.35.0" \
    "structlog>=24.4.0" \
    "pymupdf>=1.24.0" \
    "python-docx>=1.1.0" \
    "python-multipart>=0.0.9" \
    "anthropic>=0.39.0" \
    "pytest>=8.3.0" \
    "pytest-asyncio>=0.24.0" \
    "ruff>=0.7.0"

# Copia código após instalar deps (mudanças no src não invalidam o cache de uv)
COPY src/ ./src/
ENV PYTHONPATH=/app/src

RUN mkdir -p /app/data /app/cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/src"]
