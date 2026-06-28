# TruBoard Policies — Build Tasks

Backend-first. Each milestone ends with a **review gate** — work stops and the user reviews
before the next milestone begins.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · ⏸ awaiting review

---

## M0 — Repo scaffold & tooling  ⏸ awaiting review
- [x] `git init`, root `.gitignore`, `README.md`, `.env.example` (all CLAUDE.md env vars, no secrets), `task.md`
- [x] Backend: uv project (`pyproject.toml`, Python 3.12), `ruff` + `pytest` config
- [x] Backend: `Dockerfile` (uv-based) + `.dockerignore`
- [x] Backend: `config.py` (pydantic-settings, no defaults on secrets, fails loudly — verified)
- [x] Backend: `main.py` (app, lifespan, router registration skeleton), `GET /api/health`
- [x] Frontend: Vite + React 19 + TS, Tailwind 4 (no shadcn), Prettier + Vitest (linter: oxlint, template default)
- [x] Frontend: Redux store + RTK Query `baseApi`, typed hooks, `src/types/index.ts`, three-panel `App.tsx` placeholder
- [x] Root `docker-compose.yml`: pgvector/pg16 + backend (`docker compose config` valid; native boot + `/api/health` verified)
- [ ] NOTE: full `docker compose build` not yet run (interrupted); will run at M1 when DB is wired in.

## M1 — Database & models  `[x]`
- [x] `db/connection.py` (async SQLAlchemy over asyncpg)
- [x] `db/models.py`: users, policies, policy_chunks (vector(1536)), ingestion_jobs (per FRD §9)
- [x] Alembic init + initial migration (CREATE EXTENSION vector, tables, HNSW partial index)
- [x] `scripts/seed_admin.py` + `scripts/seed_dev_users.py`
- [x] pgAdmin added to docker-compose (http://localhost:5050)
- [x] Docker stack verified: migration ran, dev users seeded, tables + index confirmed

## M2 — Auth & RBAC (OAuth2/OIDC)  ⏸ awaiting review
- [x] **Backend**: OAuth2 token introspection middleware (replaces JWT/Entra-ID)
  - Token cache in `oauth_tokens` DB table; auto-create user on first IDP success
  - Migration 0002: `slug` replaces `microsoft_oid` on users; `oauth_tokens` table
  - `AUTH_DEV_MODE` X-Dev-User bypass preserved for local dev
  - `require_admin` (DB check, never token claims — per CLAUDE.md)
- [x] **Frontend**: OIDC auth via `oidc-client-ts` (replaces MSAL)
  - `authSlice` (Redux), `reduxStorage` (tokens in Redux), `authconfig` (OIDC UserManager)
  - `useAuth` hook, `LoginCallback`, `LogoutCallback`, `OAuthPage`
  - `baseApi` sends real Bearer token (falls back to X-Dev-User in dev)
  - Routing: `/callback`, `/logout`, `/login`, `/*` (guarded main layout)
- [x] Config: Azure AD env vars replaced with `OAUTH_INTROSPECT_URL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`
- [x] Tests: 5 backend passing, 1 frontend passing; lint + build clean

## M3 — Storage & Documents API  `[ ]`  *(needs Azure Blob creds)*
- [x] `storage/blob.py`: Azure Blob client + fresh SAS (1h, read-only); blob_key stored, SAS never stored
- [x] `documents/routes.py`: `GET /api/documents`, `GET /api/documents/{id}/url`

## M4 — Ingestion pipeline  `[ ]`  *(needs Azure OpenAI embeddings + sample PDFs)*
- [ ] `admin/upload.py`: multipart, validation, SHA-256 dedup (incl. soft-deleted)
- [ ] `ingestion/extractor.py` (pdfplumber text+tables, dedup overlapping bboxes)
- [ ] `ingestion/chunker.py` (recursive 800/120 overlap, tables atomic → Markdown, chunk_index)
- [ ] `ingestion/embedder.py` (batch text-embedding-3-small)
- [ ] `ingestion/job.py`: state machine + SSE emitter; try/except → failed; new DB session in task
- [ ] `admin/versioning.py`: soft-delete + version increment; blob key `policies/v{version}/{id}.pdf`
- [ ] `admin/routes.py`: POST /upload, GET /jobs/{id}/stream (SSE), GET /policies, POST /policies/{id}/replace

## M5 — RAG query pipeline  `[ ]`  *(needs Azure OpenAI chat)*
- [ ] `prompts/system_prompt.txt` (from FRD §6.1, read from file)
- [ ] `chat/session.py` (in-memory history) + in-process rate limiter (30/60min, 429 + Retry-After)
- [ ] `chat/rewriter.py` (Hinglish detect + rewrite)
- [ ] `chat/retrieval.py` (two-phase scoped/global, threshold 0.75, dedup 0.97, redirect metadata)
- [ ] `chat/context.py` (prompt assembly + tiktoken 6000-tok budget, trim oldest)
- [ ] `chat/pipeline.py` (temperature 0, max 800, timeout retry, JSON parse fallback)
- [ ] `POST /api/chat/message`, `DELETE /api/chat/session`; backend tests

## M6 — Frontend foundation  `[ ]`
- [ ] Three-panel grid `App.tsx`, Tailwind 4 theme, routing (main + guarded /admin)
- [ ] Redux store finalized, RTK Query baseApi with auth-header injection point, shared types

## M7 — Frontend: sidebar + PDF viewer  `[ ]`
- [ ] `Sidebar/PolicyList.tsx` + `hooks/useActiveDocument.ts` (alphabetical, highlight, first-doc preload)
- [ ] `Viewer/PDFViewer.tsx` + `hooks/usePDFViewer.ts` (PDF.js, scrollPageIntoView, 403 SAS refresh)
- [ ] `Viewer/ViewerFallback.tsx` (download link)

## M8 — Frontend: chat  `[ ]`
- [ ] `Chat/ChatPanel.tsx`, `MessageBubble.tsx` (Markdown), `CitationButton.tsx`, `SwitchToast.tsx`
- [ ] `hooks/useChat.ts` (submit, redirect, session) + chat slice; confidence styling, rate-limit countdown

## M9 — Frontend: admin  `[ ]`
- [ ] `Admin/UploadZone.tsx`, `FileRow.tsx`, `ConfirmModal.tsx`
- [ ] `hooks/useUpload.ts` (upload + SSE job status via EventSource, stage labels, retry)

## M10 — MSAL integration & end-to-end wiring  `[ ]`  *(needs user's MSAL code)*
- [ ] Integrate MSAL: `lib/msal.ts`, acquireTokenSilent, RTK Query bearer token, login/logout
- [ ] Flip backend `AUTH_DEV_MODE=false`; full end-to-end verification
