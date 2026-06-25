# Functional Requirements Document
## TruBoard Policies — Internal Policy Assistant
**Organisation:** TruBoard Cleantech
**Version:** 1.0 | **Date:** June 2026 | **Classification:** Internal — Confidential

---

## 1. System Architecture

### 1.1 Component Overview

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React (TypeScript), Tailwind CSS, MSAL.js, PDF.js | Three-panel UI; auth; PDF rendering |
| Backend API | FastAPI (Python) | REST API, auth middleware, RAG orchestration, SSE |
| LLM | Azure OpenAI GPT-4o | Answer generation. `temperature=0` always. |
| Embedding Model | `text-embedding-3-small` (1536-dim) | Vectorises chunks and queries |
| Vector Database | PostgreSQL 16 + pgvector | Stores and retrieves chunk embeddings |
| File Storage | Azure Blob Storage (India region) | Stores PDFs; served to browser via SAS tokens |
| Auth Provider | Azure AD / Microsoft Entra ID | Identity verification and token issuance |
| Job Processing | FastAPI `BackgroundTasks` (Phase 1) | Async ingestion pipeline |
| Real-time Updates | Server-Sent Events (SSE) | Job progress pushed to admin browser |
| Session Store | In-process dict keyed by user ID | Conversation history per active session |

### 1.2 Data Flow — Query Path

1. Employee types a query in the chatbot panel
2. Frontend sends `POST /api/chat/message` with `{query, active_document_id}` and a valid JWT
3. API middleware validates JWT; checks rate limit
4. If Hinglish detected, LLM rewrites query to English
5. Rewritten query embedded → query vector
6. **Phase 1 retrieval**: cosine similarity search filtered to `active_document_id`. Top 3 candidates retrieved.
7. If max similarity score < confidence threshold → **Phase 2 retrieval**: global search across all documents. Top 5 candidates retrieved.
8. Prompt assembled: system prompt + retrieved chunks with metadata + conversation history + query
9. Token budget enforced: trim oldest history if total exceeds 6,000 tokens
10. LLM called (temperature=0, max 800 tokens)
11. Response parsed: answer text + citations + `redirect_document_id` (nullable) + `redirect_page` (nullable) + confidence
12. If `redirect_document_id` is set: frontend switches PDF viewer to that document and scrolls to `redirect_page`
13. SAS token generated for the referenced blob (1-hour expiry, read-only)
14. Response rendered in chatbot panel; toast notification shown if PDF switched

### 1.3 Data Flow — PDF Viewing Path

1. Employee clicks a policy in the sidebar (or app loads for the first time)
2. Frontend calls `GET /api/documents/{document_id}/url` to get a fresh SAS token for the PDF blob
3. PDF.js loads the PDF from the SAS URL and renders it in the viewer panel
4. On citation "Open" button click: `PDFViewer.scrollPageIntoView({ pageNumber: N })` called
5. If PDF.js fails to render: fallback UI shown with a direct SAS download link

### 1.4 Data Flow — Ingestion Path

1. Admin uploads PDFs via the admin upload interface
2. API computes SHA-256 hash; checks for duplicates in `policies` table
3. On duplicate: admin prompted to confirm replacement or abort
4. On confirmed replacement: previous version soft-deleted; new blob uploaded
5. New `ingestion_jobs` record created (status: queued); job ID returned to frontend
6. Background worker: parsing → chunking → embedding → indexing → complete/failed
7. Each stage emits SSE event to admin browser
8. On completion: chunks live in pgvector; document appears in sidebar for all users

---

## 2. Authentication & Authorisation

### 2.1 Authentication Flow

| Step | Action |
|---|---|
| 1 | Employee clicks "Sign in with Microsoft" |
| 2 | Frontend calls `MSAL.loginRedirect()` to the company's Azure AD tenant |
| 3 | Azure AD authenticates and redirects back with authorisation code |
| 4 | Frontend exchanges code for access + refresh tokens via MSAL |
| 5 | All API calls send access token in `Authorization: Bearer` header |
| 6 | `acquireTokenSilent()` called before each request. On failure: `loginRedirect()` re-initiated |
| 7 | Backend middleware validates JWT signature, issuer, audience, and expiry on every request |
| 8 | On first authenticated request: backend upserts user record (MS Object ID, email, display name) |

### 2.2 Authorisation

| ID | Requirement |
|---|---|
| FR-AUTH-001 | Two roles: `admin` and `user`. `is_admin` boolean on `users` table is authoritative. |
| FR-AUTH-002 | Admin assignments managed directly in DB by IT. No self-service role assignment. |
| FR-AUTH-003 | Every admin endpoint queries DB to verify `is_admin = true`. Role never inferred from JWT claims. |
| FR-AUTH-004 | Non-admin users hitting admin routes receive HTTP 403; silently redirected to main app in frontend. |
| FR-AUTH-005 | On logout: frontend clears MSAL token cache; backend session invalidated; chat history cleared. |

---

## 3. PDF Viewer

### 3.1 Sidebar

| ID | Requirement |
|---|---|
| FR-PDF-001 | Sidebar lists all active (non-deleted) policy documents in alphabetical order by `policy_name`. |
| FR-PDF-002 | Each list item displays the human-readable `policy_name`. No raw filenames exposed to employees. |
| FR-PDF-003 | The currently active document is visually highlighted in the sidebar. |
| FR-PDF-004 | On app load, the alphabetically first document is automatically set as the active document. |
| FR-PDF-005 | Clicking a sidebar item sets that document as active: viewer switches, conversation continues, toast shown. |

### 3.2 PDF Viewer Panel

| ID | Requirement |
|---|---|
| FR-PDF-006 | Active PDF is rendered using PDF.js. The viewer fetches the document via a fresh SAS token from `GET /api/documents/{document_id}/url`. |
| FR-PDF-007 | SAS token for PDF viewing has 1-hour expiry. On expiry, viewer re-fetches a fresh token before re-rendering. |
| FR-PDF-008 | `PDFViewer.scrollPageIntoView({ pageNumber: N })` is called when: (a) a citation "Open" button is clicked, or (b) a chatbot redirect response arrives. |
| FR-PDF-009 | If PDF.js fails to load or render, the viewer displays: "Unable to render this document. [Download PDF →]" with the SAS download link. |
| FR-PDF-010 | The viewer supports standard PDF navigation: scroll, zoom in/out, page number indicator. |

### 3.3 Document Switch Behaviour

| ID | Requirement |
|---|---|
| FR-PDF-011 | When the active document changes (any trigger), the viewer immediately loads the new document and, if a page number is provided, scrolls to it. |
| FR-PDF-012 | A toast notification appears on every document switch: "Switched to [Policy Name] — your conversation continues." Toast auto-dismisses after 3 seconds. |
| FR-PDF-013 | The chat input remains enabled and the conversation history remains intact during and after a document switch. |

---

## 4. Document Ingestion Pipeline

### 4.1 File Upload

| ID | Requirement |
|---|---|
| FR-ING-001 | `POST /api/admin/upload` — accepts `multipart/form-data`, multiple files, admin only |
| FR-ING-002 | Validates each file: PDF MIME type and `.pdf` extension required. Non-PDFs rejected with HTTP 400. |
| FR-ING-003 | Maximum file size: 50 MB per file. Larger files rejected with HTTP 413. |
| FR-ING-004 | Password-protected PDFs detected on first extraction attempt. Job immediately fails with error: "PDF is password-protected. Please upload an unprotected version." |
| FR-ING-005 | Corrupt PDFs that fail extraction: job marked `failed`, error surfaced via SSE. No crash. |

### 4.2 SHA-256 Deduplication

| ID | Requirement |
|---|---|
| FR-ING-006 | SHA-256 hash computed from raw file bytes before any processing |
| FR-ING-007 | Hash compared against `file_hash` in `policies` table (including soft-deleted records) |
| FR-ING-008 | On exact hash match: HTTP 409 returned with existing policy name, version, upload date. Admin prompted to upload as new version or abort. |
| FR-ING-009 | On name match (different hash): admin notified this will replace the existing version and prompted to confirm. |
| FR-ING-010 | File hash stored in `policies` table on ingestion completion. |

### 4.3 Policy Versioning

| ID | Requirement |
|---|---|
| FR-ING-011 | Each uploaded document assigned a UUID `document_id`. First upload of a policy name: `version = 1`. |
| FR-ING-012 | On confirmed replacement: all `policy_chunks` for the previous `document_id` soft-deleted. Previous `policies` record soft-deleted. Old blob retained in storage. |
| FR-ING-013 | New `policies` record created with `version = previous + 1` and a new `document_id`. |
| FR-ING-014 | Soft-deleted chunks excluded from all retrieval queries via `WHERE is_deleted = false`. |
| FR-ING-015 | Soft-deleted documents excluded from the sidebar listing. |

### 4.4 Blob Storage

| ID | Requirement |
|---|---|
| FR-ING-016 | Blob key pattern: `policies/v{version}/{document_id}.pdf` |
| FR-ING-017 | Blob container is private. No public access. All access via SAS tokens. |
| FR-ING-018 | Blob URL and blob key stored in `policies` table. |

### 4.5 Text Extraction

| ID | Requirement |
|---|---|
| FR-ING-019 | Text extraction using `pdfplumber` per page. |
| FR-ING-020 | Body text and tables extracted separately. `find_tables()` identifies table bounding boxes before body text extraction. |
| FR-ING-021 | Tables serialised to Markdown table format. Never split across chunk boundaries. |
| FR-ING-022 | Each block tagged: `document_id`, `policy_name`, `page_number`, `section_heading` (if detectable), `chunk_type` (text \| table) |

### 4.6 Chunking

| ID | Requirement |
|---|---|
| FR-ING-023 | Body text: recursive character splitting. Target: 800 tokens. Overlap: 120 tokens (~15%). Respects paragraph/sentence boundaries. |
| FR-ING-024 | Table chunks: stored as-is. If table exceeds 1200 tokens, split at row boundaries with 1-row overlap. |
| FR-ING-025 | Each chunk assigned a sequential `chunk_index` within the document. |

### 4.7 Embedding & Indexing

| ID | Requirement |
|---|---|
| FR-ING-026 | Each chunk embedded using `text-embedding-3-small` (1536-dim). Batch API calls used. |
| FR-ING-027 | Chunk text, metadata, and embedding inserted into `policy_chunks`. Embedding column: `vector(1536)`. |
| FR-ING-028 | HNSW index on embedding column created/refreshed after each ingestion batch. |

### 4.8 SSE Job Status

| ID | Requirement |
|---|---|
| FR-ING-029 | `GET /api/admin/jobs/{job_id}/stream` — `text/event-stream`, admin only |
| FR-ING-030 | Events at each stage: `{ status, progress (0–100), message, chunks_created? (on complete), error? (on failed) }` |
| FR-ING-031 | On complete: connection closes. On failed: error event sent, then closes. On client disconnect: stream terminated. |

---

## 5. RAG Query Pipeline

### 5.1 Rate Limiting

| ID | Requirement |
|---|---|
| FR-RAG-001 | 30 queries per user per rolling 60-minute window, keyed by user ID |
| FR-RAG-002 | On breach: HTTP 429 with `Retry-After` header. Chat input disabled with countdown timer in UI. |

### 5.2 Input Processing

| ID | Requirement |
|---|---|
| FR-RAG-003 | Input sanitised: HTML tags stripped, null bytes removed, length capped at 2000 characters |
| FR-RAG-004 | Hinglish detection: query classified as Hinglish if significant non-English token proportion found |
| FR-RAG-005 | Hinglish queries rewritten to English via lightweight LLM call before embedding. Prompt: *"Rewrite the following in clear English, preserving intent exactly. Output only the rewritten query: {query}"*. Original displayed in UI. |

### 5.3 Two-Phase Retrieval

| ID | Requirement |
|---|---|
| FR-RAG-006 | **Phase 1 — Scoped**: query vector searched against `policy_chunks WHERE document_id = {active_document_id} AND is_deleted = false`. Top 3 candidates retrieved with similarity scores. |
| FR-RAG-007 | Confidence threshold: if max similarity score from Phase 1 < 0.75, Phase 2 is triggered. |
| FR-RAG-008 | **Phase 2 — Global**: query vector searched across all `policy_chunks WHERE is_deleted = false`. Top 5 candidates retrieved. |
| FR-RAG-009 | If Phase 2 top result belongs to a different `document_id` than the active document: `redirect_document_id` and `redirect_page` are set in the API response. |
| FR-RAG-010 | Deduplication: chunks with cosine similarity > 0.97 to already-selected chunks are excluded from the final set. |

### 5.4 Context Assembly & Token Management

| ID | Requirement |
|---|---|
| FR-RAG-011 | Prompt order: (1) system prompt, (2) retrieved chunks with metadata labels, (3) conversation history, (4) current query |
| FR-RAG-012 | Token budget for chunks + history combined: 6,000 tokens (measured with tiktoken, never `len()`). Oldest turns trimmed first if exceeded. |
| FR-RAG-013 | If history trimmed to zero and prompt still exceeds budget: proceed with no history. No partial turns. |

### 5.5 LLM Call

| ID | Requirement |
|---|---|
| FR-RAG-014 | Model: GPT-4o (Azure OpenAI, India region). Temperature: 0. Max output tokens: 800. Never change temperature. |
| FR-RAG-015 | On timeout (>15s): one retry with 2s backoff. On second failure: HTTP 503 with user-friendly message. |

### 5.6 Response Parsing

| ID | Requirement |
|---|---|
| FR-RAG-016 | LLM appends structured JSON to every response. API parses: `citations[]`, `redirect_document_id` (nullable), `redirect_page` (nullable), `confidence` ("found" \| "not_found" \| "out_of_scope") |
| FR-RAG-017 | On parse failure: raw answer returned, citations omitted, failure logged. |

---

## 6. System Prompt & Guardrails

### 6.1 System Prompt

```
You are TruBoard Policies, an internal policy assistant for TruBoard Cleantech.
Your sole purpose is to answer questions about the company's official HR and
Compliance policies using only the policy excerpts provided below.

RULES:
1. Answer ONLY using the content in the provided policy excerpts.
   Do not use any knowledge from your training data.
2. If the answer is not in the excerpts, respond with exactly:
   "I could not find information about this in the available policies.
   Please contact HR directly for clarification."
3. If the question is not related to company HR or Compliance policies, respond with exactly:
   "This question is outside my scope. I can only assist with questions
   about company HR and Compliance policies."
4. Always respond in English, regardless of the language of the question.
5. Never speculate, infer, or extrapolate beyond what is explicitly stated.
6. After your answer, always append the following JSON and nothing else after it:
   {
     "citations": [{"policy": "...", "page": N, "section": "..."}],
     "redirect_document_id": "uuid-or-null",
     "redirect_page": N_or_null,
     "confidence": "found" | "not_found" | "out_of_scope"
   }
```

### 6.2 Guardrail Behaviours

| Scenario | LLM Behaviour | UI Presentation |
|---|---|---|
| Answer found in active PDF | Answer + citations from active document. `redirect_document_id = null`. | Answer shown. Citation "Open" button scrolls to page in current viewer. |
| Answer found in different PDF | Answer + citations. `redirect_document_id` and `redirect_page` set. | Viewer switches to correct document and page. Toast shown. Conversation continues. |
| Answer not in any document | Exact "not found" message. `confidence = "not_found"`. | Muted styling. "Contact HR" prompt shown. |
| Out-of-scope question | Exact "out of scope" message. `confidence = "out_of_scope"`. | Distinct styling. Scope reminder shown. |
| Hinglish query | Query rewritten to English before retrieval. Response in English. | Original query in user bubble. English response in assistant bubble. |
| Prompt injection attempt | System prompt includes injection-resistance. User input isolated with `<user_query>` delimiters. | No special UI handling. |

---

## 7. Chat Interface

### 7.1 Login Screen

| ID | Requirement |
|---|---|
| FR-UI-001 | Displays company logo, product name ("TruBoard Policies"), and a single "Sign in with Microsoft" button |
| FR-UI-002 | No username/password fields. No alternative auth path. |
| FR-UI-003 | On successful auth: redirect to main three-panel interface |

### 7.2 Chatbot Panel

| ID | Requirement |
|---|---|
| FR-UI-004 | Scrollable message thread. User messages right-aligned; assistant messages left-aligned. |
| FR-UI-005 | Text input pinned to bottom. Send on button click or Enter (Shift+Enter for newline). |
| FR-UI-006 | Input placeholder: "Ask about any company policy..." |
| FR-UI-007 | During LLM response: animated typing indicator. Input disabled. |
| FR-UI-008 | On rate limit: input disabled with countdown — "Query limit reached. Try again in {N} minutes." |

### 7.3 Response Display

| ID | Requirement |
|---|---|
| FR-UI-009 | Responses rendered with Markdown support (bold, italics, lists) |
| FR-UI-010 | Citations shown as "Open" buttons below the response. Format: `[Policy Name — Page X] [Open →]`. Clicking triggers viewer switch and scroll. |
| FR-UI-011 | `not_found` responses: muted grey styling + "Contact HR" prompt |
| FR-UI-012 | `out_of_scope` responses: distinct left border + scope reminder |

### 7.4 Session Behaviour

| ID | Requirement |
|---|---|
| FR-UI-013 | Chat history cleared on: browser refresh, tab close, or logout |
| FR-UI-014 | Logout button in top nav. On click: MSAL cache cleared, redirect to login. |
| FR-UI-015 | On refresh: silent MSAL token acquisition. If successful, user is logged in with empty session. |

---

## 8. Admin Interface

### 8.1 Access Control

| ID | Requirement |
|---|---|
| FR-ADMIN-001 | Admin interface at `/admin`. Not linked or visible in employee navigation. |
| FR-ADMIN-002 | Non-admin navigating to `/admin` silently redirected to main app. |
| FR-ADMIN-003 | All admin API endpoints return HTTP 403 for non-admin users. |

### 8.2 Upload Interface

| ID | Requirement |
|---|---|
| FR-ADMIN-004 | Drag-and-drop + click-to-browse. Multiple files selectable. |
| FR-ADMIN-005 | Each file displayed with name, size, and status (pending / uploading / processing / complete / failed). |
| FR-ADMIN-006 | Upload button disabled until at least one valid file is selected. |

### 8.3 Deduplication & Replacement

| ID | Requirement |
|---|---|
| FR-ADMIN-007 | On SHA-256 hash match: modal — "Identical file exists: [Name] v[X], uploaded [Date]. Upload as new version?" — "Upload as New Version" / "Cancel" |
| FR-ADMIN-008 | On name match (different hash): modal — "This will archive [Name] v[X] and replace it. Continue?" — "Replace" / "Cancel" |
| FR-ADMIN-009 | On cancel: file removed from queue. No blob upload or job creation. |

### 8.4 Ingestion Progress

| ID | Requirement |
|---|---|
| FR-ADMIN-010 | Per-file progress bar driven by SSE stream |
| FR-ADMIN-011 | Stage label shown alongside bar: "Parsing PDF..." / "Chunking text..." / "Generating embeddings..." / "Indexing..." |
| FR-ADMIN-012 | On complete: 100% bar, "Complete", chunk count shown — "1,247 chunks indexed." |
| FR-ADMIN-013 | On failure: red error state, error message, "Retry" button |

---

## 9. Data Models

### 9.1 `users`

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Internal user identifier |
| microsoft_oid | TEXT, UNIQUE NOT NULL | Microsoft Object ID from JWT |
| email | TEXT NOT NULL | User email |
| display_name | TEXT | Full name |
| is_admin | BOOLEAN, DEFAULT false | Admin flag. Set in DB by IT. |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Last update timestamp |

### 9.2 `policies`

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Document identifier |
| policy_name | TEXT NOT NULL | Human-readable policy name |
| version | INTEGER NOT NULL | Version number; increments on replacement |
| file_hash | TEXT NOT NULL | SHA-256 hash of PDF bytes |
| blob_url | TEXT NOT NULL | Azure Blob URL (private) |
| blob_key | TEXT NOT NULL | Blob key for SAS generation |
| is_deleted | BOOLEAN, DEFAULT false | Soft-delete flag |
| deleted_at | TIMESTAMPTZ | Soft-delete timestamp; NULL if active |
| uploaded_by | UUID, FK → users.id | Admin who uploaded |
| created_at | TIMESTAMPTZ | Creation timestamp |

### 9.3 `policy_chunks`

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Chunk identifier |
| document_id | UUID, FK → policies.id | Parent policy document |
| chunk_index | INTEGER NOT NULL | Sequential position within document |
| chunk_text | TEXT NOT NULL | Raw text content |
| chunk_type | TEXT NOT NULL | "text" or "table" |
| page_number | INTEGER NOT NULL | Source page in the PDF |
| section_heading | TEXT | Nearest heading; NULL if not detectable |
| embedding | vector(1536) | pgvector embedding |
| is_deleted | BOOLEAN, DEFAULT false | Soft-delete flag |
| deleted_at | TIMESTAMPTZ | Soft-delete timestamp |
| created_at | TIMESTAMPTZ | Creation timestamp |

### 9.4 `ingestion_jobs`

| Column | Type | Description |
|---|---|---|
| id | UUID, PK | Job identifier |
| document_id | UUID, FK → policies.id | Associated policy document |
| status | TEXT NOT NULL | "queued" \| "parsing" \| "chunking" \| "embedding" \| "indexing" \| "complete" \| "failed" |
| progress | INTEGER, DEFAULT 0 | Progress percentage (0–100) |
| chunks_created | INTEGER | Populated on completion |
| error_message | TEXT | Populated on failure |
| created_at | TIMESTAMPTZ | Job creation timestamp |
| updated_at | TIMESTAMPTZ | Last status update |

---

## 10. API Specification

### 10.1 Authentication

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/auth/login | None | Redirect to Microsoft Azure AD login |
| GET | /api/auth/callback | None | Exchange code for tokens; upsert user record |
| POST | /api/auth/logout | Required | Invalidate server session |

### 10.2 Documents (Employee)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/documents | Required | Returns list of all active policies `[{id, policy_name, version}]` ordered alphabetically |
| GET | /api/documents/{id}/url | Required | Returns a fresh 1-hour read-only SAS URL for the PDF blob |

### 10.3 Chat

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/chat/message | Required | Body: `{query: string, active_document_id: uuid}`. Returns: `{answer, citations, redirect_document_id, redirect_page, confidence}`. Rate-limited 30/hr/user. |
| DELETE | /api/chat/session | Required | Clears in-memory conversation history for the requesting user |

### 10.4 Admin

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/admin/upload | Admin | Multipart PDF upload. Returns `{job_id, document_id, status: "queued"}`. |
| GET | /api/admin/jobs/{id}/stream | Admin | SSE stream for ingestion job progress |
| GET | /api/admin/policies | Admin | All policies including soft-deleted; with version history |
| POST | /api/admin/policies/{id}/replace | Admin | Confirm replacement; soft-delete current version |

---

## 11. Error Handling

| Scenario | System Behaviour | User-Facing Message |
|---|---|---|
| Unauthenticated API request | HTTP 401 | Redirect to login screen |
| Non-admin on admin endpoint | HTTP 403 | Silent redirect to main app |
| Query rate limit exceeded | HTTP 429 + Retry-After | "Query limit reached. Try again in N minutes." |
| Query over 2000 characters | HTTP 400 | "Your query is too long. Please shorten it." |
| Corrupt PDF upload | Job marked failed; SSE error event | "Failed to process this PDF. Check the file and try again." |
| Password-protected PDF | Job fails immediately; SSE error | "PDF is password-protected. Upload an unprotected version." |
| LLM timeout (after retry) | HTTP 503 | "Temporarily unavailable. Please try again in a moment." |
| Context window exceeded | Trim oldest turns; silent retry | No user-facing impact |
| pgvector connection failure | HTTP 503; error logged | "Temporarily unavailable. Please try again in a moment." |
| LLM response JSON parse failure | Raw answer returned; no citations; logged | Answer shown without citations |
| PDF.js render failure | Fallback UI shown | "Unable to render this document. [Download PDF →]" |
| SAS token expired during PDF view | Viewer re-fetches fresh token silently | No user-facing impact |
| Blob Storage unreachable (admin) | HTTP 500 | "File storage unavailable. Please try again shortly." |

---

## 12. Security Requirements

| ID | Requirement |
|---|---|
| FR-SEC-001 | User input stripped of HTML tags, null bytes, control characters at API boundary |
| FR-SEC-002 | User input wrapped in `<user_query>...</user_query>` delimiters in prompt to prevent injection |
| FR-SEC-003 | SAS tokens for PDF viewing: 1-hour expiry, read-only, per-document scope. Never stored; generated fresh each time. |
| FR-SEC-004 | CORS restricted to internal deployment domain only |
| FR-SEC-005 | `is_admin` verified from DB on every admin request. Never from JWT or client headers. |
| FR-SEC-006 | HTTPS enforced at infrastructure level. HTTP rejected. |
| FR-SEC-007 | All credentials via environment variables. No secrets in code or version control. |
| FR-SEC-008 | No debug or introspection endpoints in production |

---

## 13. Rate Limiting

| Parameter | Value |
|---|---|
| Limit | 30 queries per user per rolling 60-minute window |
| Scope | Per authenticated user ID |
| Storage | In-process dict (Phase 1); Redis (Phase 2) |
| Enforcement | API middleware, before any LLM or DB call |
| HTTP response on breach | HTTP 429 with `Retry-After: {seconds}` |
| UI on breach | Input disabled; countdown timer shown |
| Applies to | `POST /api/chat/message` only. Admin endpoints not rate-limited. |
