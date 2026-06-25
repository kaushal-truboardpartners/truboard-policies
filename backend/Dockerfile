# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv: fast, lockfile-based dependency management.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (cached layer) using only the lockfiles.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then copy the application source.
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# --reload is enabled via docker-compose for local dev; the image default is a plain run.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
