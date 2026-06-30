# Dockerfile
# Server-only image for the FastAPI translation history API.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_NO_DEV=1
ENV PORT=8000

COPY pyproject.toml uv.lock README.md ./
COPY server ./server

RUN uv sync --locked

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn server.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
