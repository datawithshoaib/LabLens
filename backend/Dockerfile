FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
RUN mkdir -p /data/uploads && chown 10001:10001 /data/uploads

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "lablens.main:app", "--host", "0.0.0.0", "--port", "8000"]
