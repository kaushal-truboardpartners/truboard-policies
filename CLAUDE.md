# TruBoard Policies — CLAUDE.md

Internal policy assistant for TruBoard Cleantech. Three-panel web app: sidebar (policy list) + PDF viewer (PDF.js) + chatbot. RAG-based chatbot answers from the active PDF first, falls back to all documents, and can redirect the viewer to a different document and page mid-conversation. No hallucination tolerance. `temperature=0` always.

---

## Stack

| Layer | Choice |
|---|---|
| Frontend | React (TypeScript), Tailwind CSS, MSAL.js, PDF.js |
| Backend | FastAPI (Python) |
| LLM | Azure OpenAI GPT-4o — `temperature=0`, always |
| Embeddings | `text-embedding-3-small` (1536-dim) |
| Vector DB | PostgreSQL 16 + pgvector |
| File Storage | Azure Blob Storage (India region) — private container, SAS tokens only |
| Auth | Microsoft Entra ID (Azure AD) via MSAL |
| Job Queue | FastAPI `BackgroundTasks` (Phase 1) |
| Real-time | Server-Sent Events (SSE) for ingestion job progress |
| Session | In-process dict keyed by user ID (Phase 1) |

---

## Project Structure

```
truboard-policies/
├── backend/
│   ├── main.py                    # FastAPI app, lifespan, router registration
│   ├── config.py                  # All settings via pydantic-settings from env vars
│   ├── auth/
│   │   ├── middleware.py          # JWT validation on every request
│   │   └── routes.py              # /api/auth/login, /callback, /logout
│   ├── documents/
│   │   └── routes.py              # /api/documents — list + SAS URL generation
│   ├── chat/
│   │   ├── routes.py              # /api/chat/message, /session
│   │   ├── pipeline.py            # Orchestrates full RAG pipeline
│   │   ├── retrieval.py           # Two-phase retrieval + deduplication
│   │   ├── rewriter.py            # Hinglish → English query rewriting
│   │   ├── context.py             # Prompt assembly + token budget (tiktoken)
│   │   └── session.py             # In-memory conversation history store
│   ├── admin/
│   │   ├── routes.py              # /api/admin/* endpoints
│   │   ├── upload.py              # File validation, hash check, blob upload
│   │   ├── ingestion/
│   │   │   ├── job.py             # Job state machine + SSE event emitter
│   │   │   ├── extractor.py       # pdfplumber text + table extraction
│   │   │   ├── chunker.py         # Recursive splitting + table chunking
│   │   │   └── embedder.py        # Batch embedding via Azure OpenAI
│   │   └── versioning.py          # Soft-delete + version increment
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models (users, policies, policy_chunks, ingestion_jobs)
│   │   ├── connection.py          # Async DB pool (asyncpg)
│   │   └── migrations/            # Alembic migrations
│   ├── storage/
│   │   └── blob.py                # Azure Blob client + SAS token generation
│   └── prompts/
│       └── system_prompt.txt      # Canonical system prompt — edit here only, never inline
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Root layout — three-panel grid
│   │   ├── components/
│   │   │   ├── Sidebar/
│   │   │   │   └── PolicyList.tsx # Alphabetical list, active highlight, click handler
│   │   │   ├── Viewer/
│   │   │   │   ├── PDFViewer.tsx  # PDF.js wrapper, scrollPageIntoView, SAS token refresh
│   │   │   │   └── ViewerFallback.tsx # Shown when PDF.js fails — download link
│   │   │   ├── Chat/
│   │   │   │   ├── ChatPanel.tsx  # Full chat panel
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── CitationButton.tsx  # "Open →" button — triggers viewer switch + scroll
│   │   │   │   └── SwitchToast.tsx     # "Switched to X — conversation continues"
│   │   │   └── Admin/
│   │   │       ├── UploadZone.tsx
│   │   │       ├── FileRow.tsx
│   │   │       └── ConfirmModal.tsx
│   │   ├── hooks/
│   │   │   ├── useActiveDocument.ts   # Active document state; triggers viewer switch
│   │   │   ├── useChat.ts             # Query submission, redirect handling, session
│   │   │   ├── usePDFViewer.ts        # PDF.js lifecycle, scroll-to-page, SAS refresh
│   │   │   └── useUpload.ts           # File upload + SSE job status
│   │   ├── lib/
│   │   │   ├── api.ts             # Axios instance with MSAL token interceptor
│   │   │   └── msal.ts            # MSAL config + acquireTokenSilent wrapper
│   │   └── types/
│   │       └── index.ts           # Policy, ChatMessage, Citation, JobStatus, ChatResponse
└── scripts/
    ├── seed_admin.py              # Set is_admin=true for first IT user by email
    └── reindex_all.py             # Re-embed all active chunks (run on model change)
```

---

## Environment Variables

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=...
AZURE_STORAGE_ACCOUNT_KEY=...
AZURE_STORAGE_CONTAINER=truboard-policies

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/truboard_policies

# Auth
AZURE_AD_TENANT_ID=...
AZURE_AD_CLIENT_ID=...
FRONTEND_AZURE_AD_CLIENT_ID=...
ALLOWED_ORIGIN=https://policies.internal.truboard.com

# Config
RATE_LIMIT_QUERIES=30
RATE_LIMIT_WINDOW_SECONDS=3600
MAX_UPLOAD_SIZE_MB=50
SAS_TOKEN_EXPIRY_HOURS=1
RETRIEVAL_CONFIDENCE_THRESHOLD=0.75
RETRIEVAL_SCOPED_TOP_K=3
RETRIEVAL_GLOBAL_TOP_K=5
DEDUP_COSINE_THRESHOLD=0.97
```

App fails loudly on missing env vars at startup — use pydantic-settings with no defaults on secrets.

---

## Key API Contracts

### Chat Request / Response
```typescript
// POST /api/chat/message
Request:  { query: string, active_document_id: string }

Response: {
  answer: string,
  citations: Array<{ policy: string, page: number, section: string }>,
  redirect_document_id: string | null,  // null = answer is in active doc
  redirect_page: number | null,
  confidence: "found" | "not_found" | "out_of_scope"
}
```

When `redirect_document_id` is not null, the frontend:
1. Updates `activeDocument` state to the redirected document
2. Fetches a fresh SAS URL for that document
3. Loads it in the PDF viewer
4. Calls `scrollPageIntoView({ pageNumber: redirect_page })`
5. Shows the `SwitchToast`

### Document List
```typescript
// GET /api/documents
Response: Array<{ id: string, policy_name: string, version: number }>
// Alphabetically ordered by policy_name, is_deleted = false only
```

### Document SAS URL
```typescript
// GET /api/documents/{id}/url
Response: { url: string, expires_at: string }
// 1-hour expiry SAS URL, generated fresh on every call
```

---

## Architecture Decisions

### Why two-phase retrieval?
Phase 1 scopes to the active document — respects what the user is reading. Phase 2 global fallback handles questions that belong in a different policy. The redirect UX makes the fallback feel intentional, not surprising. Threshold at 0.75 is configurable — tune it with real user queries post-launch.

### Why PDF.js and not a PDF iframe or Google Docs embed?
- `scrollPageIntoView()` works programmatically — essential for citation navigation
- No external dependency (Google, Adobe) for internal documents
- SAS tokens work directly with PDF.js `PDFDataRangeTransport`
- Full control over the viewer UI and error states

### Why SSE and not WebSocket for ingestion progress?
Server → client one-way communication only. SSE is a plain HTTP connection — simpler, drops gracefully, no handshake overhead, no extra infra.

### Why FastAPI BackgroundTasks and not Celery?
No broker, no separate worker process, no Redis required for Phase 1. Two or three concurrent admin uploads is the ceiling — BackgroundTasks handles this fine. Celery is the Phase 2 upgrade path when persistence across restarts is needed.

### Why not LangChain or LlamaIndex?
The RAG pipeline is explicit and small enough to own directly. Every step is individually testable. Framework abstractions make debugging harder without adding value at this scale.

---

## Critical Patterns

### System prompt lives in a file
```python
# backend/chat/pipeline.py
SYSTEM_PROMPT = Path("prompts/system_prompt.txt").read_text()
```
Never hardcode the prompt inline. It must be editable without touching Python code.

### `active_document_id` is always sent with every query
```python
# The two-phase retrieval depends on this
# Phase 1: WHERE document_id = active_document_id AND is_deleted = false
# Phase 2: WHERE is_deleted = false (global, triggered if Phase 1 confidence < threshold)
```

### Token counting is always tiktoken, never len()
```python
import tiktoken
enc = tiktoken.encoding_for_model("gpt-4o")
token_count = len(enc.encode(text))
```
Character length is not a valid proxy for token count. Never use `len(text)` for budget calculations.

### `is_deleted = false` on every chunk query — no exceptions
```sql
-- Every single query against policy_chunks must include this
WHERE is_deleted = false
```
Forgetting this filter silently exposes replaced/archived content in retrieval.

### Admin role is always verified from the database
```python
async def require_admin(user_id: str, db: AsyncSession):
    user = await db.get(User, user_id)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
```
Never trust a JWT claim, request header, or cookie for admin status.

### SAS tokens are never stored — always generated fresh
```python
# Generate at request time, not at ingestion time
sas_url = generate_sas_url(blob_key, expiry_hours=SAS_TOKEN_EXPIRY_HOURS)
```
Storing SAS tokens creates stale/expired links. `blob_key` is stored; SAS URL is ephemeral.

### User input is always wrapped in delimiters before LLM injection
```python
user_block = f"<user_query>{sanitised_input}</user_query>"
```
Structurally separates user content from system instructions. Reduces prompt injection risk.

### temperature is always 0
This is a policy lookup tool. Deterministic, reproducible responses are required. Never change this.

---

## Database

Using Alembic for all migrations. Never `CREATE TABLE` manually.

```bash
# Enable pgvector first (one-time, in psql)
CREATE EXTENSION IF NOT EXISTS vector;

# Generate migration
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

HNSW index for vector search (created in migration, not in application code):
```sql
CREATE INDEX CONCURRENTLY policy_chunks_embedding_idx
ON policy_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE is_deleted = false;
```

---

## Key Commands

```bash
# Backend dev server
uvicorn backend.main:app --reload --port 8000

# Frontend dev server
cd frontend && npm run dev

# Seed first admin (run after first login)
python scripts/seed_admin.py --email admin@truboard.com

# Re-index all active documents (run after embedding model change)
python scripts/reindex_all.py

# Run backend tests
pytest backend/tests/ -v

# Run Alembic migration
alembic upgrade head
```

---

## Never Do This

- **Never change `temperature`** on the main LLM call. Always 0.
- **Never omit `is_deleted = false`** in any `policy_chunks` or `policies` query.
- **Never trust the client** for role information. Always verify from DB.
- **Never hardcode secrets.** Everything via env vars.
- **Never split a table chunk** across boundaries. Tables are atomic.
- **Never store SAS tokens.** Store `blob_key`; generate SAS at request time.
- **Never use `len(text)` as a token estimate.** Always use tiktoken.
- **Never answer from LLM training knowledge.** Retrieval runs before every LLM call.
- **Never render admin routes** in the employee navigation, even if the API would 403 them.

---

## Known Gotchas

- **MSAL + React StrictMode**: MSAL fires double renders in StrictMode. Wrap `MsalProvider` outside `<StrictMode>` or disable StrictMode in dev.
- **PDF.js + SAS tokens**: SAS tokens expire mid-session. The `usePDFViewer` hook must detect a 403 on the blob URL and re-fetch a fresh token via `GET /api/documents/{id}/url` before re-rendering.
- **SSE + FastAPI BackgroundTasks**: Unhandled exceptions in `BackgroundTasks` silently fail — the HTTP response is already sent. Wrap the entire job function in `try/except` and always update job status to `"failed"` on exception.
- **`scrollPageIntoView` timing**: Call it only after PDF.js fires the `documentLoaded` event. Calling it before the document loads silently does nothing.
- **pgvector HNSW index and soft-delete**: The partial index (`WHERE is_deleted = false`) won't be used if you query without the filter. Always verify query plans with `EXPLAIN` after schema changes.
- **pdfplumber table overlaps**: `find_tables()` occasionally returns overlapping bounding boxes on complex layouts. Deduplicate by bounding box area overlap before extraction.
- **FastAPI `BackgroundTasks` and request context**: The DB session from the request scope is closed before the background task runs. Create a new DB session inside the background task function — don't pass the request's session.
- **Two-phase retrieval confidence threshold**: 0.75 is a starting estimate. After launch, sample real query similarity scores and tune the threshold. Log all Phase 1 max scores for the first 2 weeks.
