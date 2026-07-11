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

## M3 — Storage & Documents API  `[x]`
- [x] `storage/blob.py`: Azure Blob client + fresh SAS (1h, read-only); blob_key stored, SAS never stored
- [x] `documents/routes.py`: `GET /api/documents`, `GET /api/documents/{id}/url`

## M4 — Ingestion pipeline  `[x]`
- [x] `admin/upload.py`: multipart, validation, SHA-256 dedup (incl. soft-deleted)
- [x] `ingestion/extractor.py` (pdfplumber text+tables, dedup overlapping bboxes)
- [x] `ingestion/chunker.py` (recursive 800/120 overlap, tables atomic → Markdown, chunk_index)
- [x] `ingestion/embedder.py` (batch text-embedding-3-small)
- [x] `ingestion/job.py`: state machine + SSE emitter; try/except → failed; new DB session in task
- [x] `admin/versioning.py`: soft-delete + version increment; blob key `policies/v{version}/{id}.pdf`
- [x] `admin/routes.py`: POST /upload-and-ingest, GET /jobs/{id}/stream (SSE), GET /policies, POST /policies/{id}/replace
- [x] Tests: extractor bbox/overlap/markdown, chunker atomicity + heading inheritance, embedder order + error, versioning, new route endpoints

## M5 — RAG query pipeline  `[x]`
- [x] `prompts/system_prompt.txt` (from FRD §6.1, read from file)
- [x] `chat/session.py` (in-memory history) + in-process rate limiter (30/60min, 429 + Retry-After)
- [x] `chat/rewriter.py` (Hinglish detect + rewrite)
- [x] `chat/retrieval.py` (two-phase scoped/global, threshold 0.75, dedup 0.97, redirect metadata)
- [x] `chat/context.py` (prompt assembly + tiktoken 6000-tok budget, trim oldest)
- [x] `chat/pipeline.py` (temperature 0, max 800, timeout retry, JSON parse fallback)
- [x] `POST /api/chat/message`, `DELETE /api/chat/session`; backend tests

## M6 — Frontend foundation  `[x]`
- [x] Three-panel grid `App.tsx`, Tailwind 4 theme from shared TruBoard design tokens, routing (main + guarded /admin redirect)
- [x] Redux store: `activeDocumentSlice` added; `documentsApi` (listDocuments, lazyGetDocumentUrl); `index.css` full brand token system

## M7 — Frontend: sidebar + PDF viewer  `[x]`
- [x] `Sidebar/PolicyList.tsx` + `hooks/useActiveDocument.ts` (alphabetical, active highlight, first-doc preload)
- [x] `Viewer/PDFViewer.tsx` + `hooks/usePDFViewer.ts` (PDF.js, scrollToPage, 403 SAS re-fetch)
- [x] `Viewer/ViewerFallback.tsx` (download link, FRD FR-PDF-009)

## M8 — Frontend: chat  `[x]`
- [x] `Chat/ChatPanel.tsx`, `MessageBubble.tsx` (Markdown via react-markdown), `CitationButton.tsx`, `SwitchToast.tsx`
- [x] `hooks/useChat.ts` (submit, redirect, session) + chatSlice + chatAdminApi; confidence styling, rate-limit countdown

## M9 — Frontend: admin  `[x]`
- [x] `Admin/UploadZone.tsx`, `FileRow.tsx` (progress bar, stage labels, retry), `ConfirmModal.tsx`
- [x] `hooks/useUpload.ts` (upload + SSE EventSource job status, retry, clear) + AdminLayout in App.tsx

## M10 — Production auth wiring & end-to-end verification  `[ ]`  *(needs live OAuth provider)*
- NOTE: Auth is already fully implemented (M2). Frontend uses `oidc-client-ts` (not MSAL).
  Backend uses OAuth2 token introspection. M10 is a config + verification step only.
- [ ] Set real OAuth provider env vars (`VITE_OAUTH_AUTHORITY`, `VITE_OAUTH_CLIENT_ID`, etc.)
- [ ] Flip backend `AUTH_DEV_MODE=false`
- [ ] Full end-to-end login → document load → chat → logout verification
