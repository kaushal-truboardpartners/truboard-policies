# TruBoard Policies

Internal RAG policy assistant for TruBoard Cleantech. Three-panel desktop web app: policy
sidebar + PDF.js viewer + grounded chatbot. Answers come exclusively from official policy
PDFs (no hallucination, `temperature=0`).

See `brd.md` / `prd.md` / `frd.md` for requirements and `CLAUDE.md` for engineering rules.

## Layout

```
truboard-policies/
├── backend/          # FastAPI + RAG pipeline (Python 3.12, uv). Runs in docker-compose.
├── frontend/         # Vite + React + TS + Tailwind 4 + Redux Toolkit/RTK Query. Deployed separately.
├── docker-compose.yml# Postgres 16 + pgvector and the backend (local dev).
└── *.md              # Specs.
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python 3.12), Node 20+, Docker.
- Real Azure OpenAI + Azure Blob Storage credentials (filled into `.env`).

## Quick start

```bash
cp .env.example .env          # then fill in Azure creds

# Backend + DB
docker compose up --build     # API at http://localhost:8000, Swagger at /docs

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### Backend without Docker

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

## Dev auth

`AUTH_DEV_MODE=true` skips JWT validation and resolves the current user from the `X-Dev-User`
header (falling back to `AUTH_DEV_DEFAULT_USER`). Real MSAL/Entra-ID auth replaces this in prod
(`AUTH_DEV_MODE=false`).

## Common commands

```bash
# Backend
uv run uvicorn main:app --reload --port 8000   # dev server (from backend/)
uv run ruff check .                            # lint
uv run pytest -v                               # tests
uv run alembic upgrade head                    # migrations
uv run python scripts/seed_admin.py --email admin@truboard.com

# Frontend (from frontend/)
npm run dev
npm run lint
npm run test
```
