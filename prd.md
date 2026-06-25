# Product Requirements Document
## TruBoard Policies — Internal Policy Assistant
**Organisation:** TruBoard Cleantech
**Version:** 1.0 | **Date:** June 2026 | **Classification:** Internal — Confidential

---

## 1. Product Overview

**Product Name:** TruBoard Policies
**Platform:** Desktop web application, internal access only
**Users:** All employees of TruBoard Cleantech (~800–1000 persons)

TruBoard Policies is a three-panel internal workspace. Employees browse a sidebar of all 17 company policy documents, open and read them in a built-in PDF viewer, and ask questions via a chatbot. The chatbot answers from the document currently open — or finds the answer in another document and redirects the viewer there automatically. The conversation never resets. Every answer cites the exact policy and page. The system never answers from outside the official documents.

---

## 2. User Personas

### Persona 1: The Employee (Primary User)

| Attribute | Details |
|---|---|
| Representative | Priya — Operations Executive |
| Tech Comfort | Moderate; comfortable with web apps |
| Language | Primarily English; types Hinglish in Roman script |
| Typical Queries | "How many casual leaves do I get?", "kitne sick leaves milte hain?", "What is the notice period?" |
| Workflow | Opens the app, picks a policy from the sidebar, reads it, asks specific questions to the chatbot |
| Goal | Get a clear answer fast — from the open document or directed to the right one |

### Persona 2: The IT Administrator

| Attribute | Details |
|---|---|
| Representative | Rohan — IT Executive |
| Count | 2–3 persons |
| Responsibility | Uploading new or updated PDFs when HR releases revised policies |
| Goal | Upload, confirm ingestion succeeded, move on |

---

## 3. Layout & Navigation

### 3.1 Three-Panel Layout

```
┌──────────────┬────────────────────────┬──────────────────────┐
│   Sidebar    │      PDF Viewer        │      Chatbot         │
│              │                        │                      │
│  Alphabetical│  Renders active PDF    │  Ask questions.      │
│  list of     │  via PDF.js.           │  Answers from active │
│  all 17      │                        │  PDF first; falls    │
│  policies.   │  First PDF pre-loaded  │  back to all docs.   │
│              │  on app launch.        │                      │
│  Click to    │                        │  Can switch the      │
│  switch      │  Scrolls to cited      │  active PDF and      │
│  active PDF. │  page on citation      │  scroll to cited     │
│              │  click.                │  page.               │
└──────────────┴────────────────────────┴──────────────────────┘
```

### 3.2 Active Document Behaviour

- On app load: the alphabetically first PDF is pre-loaded in the viewer.
- Clicking a policy in the sidebar: switches the viewer to that document. Conversation continues.
- Chatbot redirect: when the answer is in a different document, the viewer switches and scrolls to the correct page. Conversation continues.
- On any PDF switch (sidebar or chatbot): a toast notification appears — *"Switched to [Policy Name] — your conversation continues."*
- Conversation history is never cleared on PDF switch.

---

## 4. User Stories

### 4.1 Authentication

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-001 | Employee | Log in with my Microsoft account | I don't need a separate password |
| US-002 | System | Silently refresh my access token | My session is not interrupted mid-conversation |
| US-003 | Employee | Have my chat cleared on logout or page refresh | My conversation isn't visible on shared devices |

### 4.2 PDF Viewer & Sidebar

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-004 | Employee | See all 17 policies listed alphabetically in the sidebar | I can browse and find the document I need |
| US-005 | Employee | Click a policy and have it open in the center viewer | I can read the full document without leaving the app |
| US-006 | Employee | Have the first policy pre-loaded when the app opens | I can start immediately without making a selection |
| US-007 | Employee | Have the viewer scroll to the cited page when I click a citation | I see the exact clause being referenced |
| US-008 | Employee | Have a fallback download link if the PDF fails to render | I can still access the document if PDF.js fails |

### 4.3 Chatbot

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-009 | Employee | Ask a policy question in English or Hinglish | I get an answer without reading the whole document |
| US-010 | Employee | Have the chatbot answer from the currently open PDF first | The answer is in context of what I'm already reading |
| US-011 | Employee | Have the chatbot find the answer in another PDF when it's not in the open one | I'm not blocked if I'm looking at the wrong document |
| US-012 | Employee | Click an "Open" button in a citation to switch the viewer to that document and page | I can read the full clause in context with one click |
| US-013 | Employee | Have my conversation continue when the PDF switches | I don't lose context mid-conversation |
| US-014 | Employee | See a toast notification when the active PDF switches | I know which document I'm now looking at |
| US-015 | Employee | See the policy name and page number in every answer | I can verify the source |
| US-016 | Employee | Receive a clear "not found" message when the chatbot can't answer | I know to contact HR rather than act on uncertainty |
| US-017 | Employee | Receive a polite decline for questions outside policy scope | I understand what the tool is for |
| US-018 | Employee | Ask follow-up questions without repeating context | The conversation flows naturally |

### 4.4 Admin

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-019 | IT Admin | Access a secure upload interface invisible to regular employees | Policy management is restricted to IT |
| US-020 | IT Admin | Upload one or multiple PDFs at once | I can process a batch of updates efficiently |
| US-021 | IT Admin | Be warned if I upload a file that already exists | I avoid unintended duplicates |
| US-022 | IT Admin | Confirm before replacing an existing policy version | I don't overwrite without awareness |
| US-023 | IT Admin | See real-time ingestion progress after upload | I know when a policy is live and queryable |
| US-024 | IT Admin | See a clear error if a PDF fails ingestion | I can investigate and re-upload |

---

## 5. Feature Breakdown

### 5.1 Phase 1 Features

| Feature | Description | Priority |
|---|---|---|
| Microsoft SSO Authentication | Login via company Microsoft IDP; silent token refresh; session cleared on logout/refresh | P0 |
| Three-Panel Layout | Sidebar + PDF viewer (PDF.js) + chatbot. Desktop-first. | P0 |
| Alphabetical Policy Sidebar | All 17 PDFs listed by human-readable name. Click to open in viewer. | P0 |
| PDF Viewer (PDF.js) | Renders the active policy document. First PDF pre-loaded on launch. | P0 |
| Scroll-to-Page on Citation Click | Viewer scrolls to the cited page when employee clicks an "Open" citation button | P0 |
| PDF Render Fallback | If PDF.js fails to render, a direct SAS download link is shown | P0 |
| Two-Phase RAG Retrieval | Searches active PDF first; falls back to global search if confidence below threshold | P0 |
| Cross-Document Redirect | API response includes redirect metadata; frontend switches viewer to correct document and page | P0 |
| Citation "Open" Button | Each citation renders as a clickable button — switches viewer to referenced document at referenced page | P0 |
| Conversation Persists Across PDF Switches | Chat history never resets on PDF switch. Toast notification shown on switch. | P0 |
| Hinglish Query Support | Roman-script Hinglish detected and rewritten to English before retrieval | P0 |
| English-Only Responses | All responses in English regardless of query language | P0 |
| Multi-turn Session Memory | Conversation history in-memory for the browser session; cleared on logout/refresh | P0 |
| Guardrail — I don't know | Clear "not found" message + HR referral when answer unavailable | P0 |
| Guardrail — Out of Scope | Polite decline for non-policy questions | P0 |
| Admin PDF Upload Interface | Drag-and-drop multi-file upload; SHA-256 deduplication; version replacement with confirmation | P0 |
| Async Ingestion with SSE Progress | Background ingestion job; real-time progress via Server-Sent Events | P0 |
| Policy Versioning & Soft Delete | New upload increments version; previous version archived in storage | P0 |
| Role-Based Access Control | Admin role in DB; server-side check on every admin endpoint | P0 |
| Per-User Rate Limiting | 30 queries per rolling 60-minute window | P0 |

### 5.2 Phase 2 Features

| Feature | Description | Priority |
|---|---|---|
| Policy Grouping / Tags | Tag-based grouping in sidebar (e.g. HR vs Compliance); tags assigned at upload time | P1 |
| Admin Policy Dashboard | Full lifecycle management: list, version history, delete, re-upload | P1 |
| Chat History Persistence | Conversation stored and retrievable across login sessions | P1 |
| Response Feedback | Thumbs up / thumbs down per response | P1 |
| Multi-Subsidiary Support | Subsidiary tagging, conflict detection, per-subsidiary policy variants | P1 |
| Mobile Layout | Reflow for narrow viewports; chatbot-first on mobile | P1 |

---

## 6. Chatbot Retrieval Behaviour

### Two-Phase Retrieval

**Phase 1 — Scoped search:**
Query embedded and searched against chunks from the currently active document only (`document_id` filter). If the top result's similarity score exceeds the confidence threshold, answer is returned citing the active document.

**Phase 2 — Global fallback:**
If Phase 1 returns no result above threshold, the query is searched across all documents. Top result determines the answer and source document.

**Redirect trigger:**
If the best result is from a document other than the currently active one, the API response includes `redirect_document_id` and `redirect_page`. Frontend switches the viewer to the correct document and scrolls to the cited page. Conversation continues without interruption.

### Sidebar Switch Behaviour
Manually clicking a different PDF in the sidebar behaves identically to a chatbot-triggered redirect: viewer switches, conversation continues, toast notification shown. No reset. No confirmation dialog.

---

## 7. Non-Functional Requirements

### 7.1 Performance

| ID | Requirement |
|---|---|
| NFR-PERF-001 | Query response time ≤ 5 seconds at P95 |
| NFR-PERF-002 | PDF.js renders first page of active document within 2 seconds on corporate network |
| NFR-PERF-003 | Scroll-to-page executes within 500ms of citation button press |
| NFR-PERF-004 | PDF ingestion for a single document (up to 40 pages) completes within 3 minutes |
| NFR-PERF-005 | System supports up to 50 concurrent sessions without degradation |

### 7.2 Availability

| ID | Requirement |
|---|---|
| NFR-AVAIL-001 | 99.5% availability during IST business hours (08:00–20:00, Mon–Sat) |
| NFR-AVAIL-002 | Planned maintenance communicated to IT ≥ 24 hours in advance; outside business hours |

### 7.3 Security

| ID | Requirement |
|---|---|
| NFR-SEC-001 | All endpoints require valid non-expired Microsoft JWT. Unauthenticated → HTTP 401. |
| NFR-SEC-002 | Admin endpoints verify `is_admin` from DB on every request. Client claims never trusted. |
| NFR-SEC-003 | PDFs served to browser via time-limited SAS tokens (1-hour expiry, read-only). No public blob URLs. |
| NFR-SEC-004 | User input sanitised at API boundary. System prompt includes injection-resistance. |
| NFR-SEC-005 | All data in Azure India region (Central India or South India). |
| NFR-SEC-006 | All communication over HTTPS. HTTP rejected at infrastructure level. |

### 7.4 Scalability & Maintainability

| ID | Requirement |
|---|---|
| NFR-SCALE-001 | Supports up to 1000 registered users and 50 concurrent sessions |
| NFR-MAINT-001 | Fully operable by a single engineer without a dedicated DevOps team |
| NFR-MAINT-002 | Full re-indexing executable via single admin action or CLI command |
| NFR-MAINT-003 | All config via environment variables. No hardcoded secrets. |

---

## 8. Out of Scope (Phase 1)

- Mobile layout and responsive design
- Policy grouping / tag filtering in sidebar
- Multi-subsidiary support and conflict detection
- Chat history persistence across sessions
- Response feedback mechanism
- Full-text keyword search within PDFs
- Text highlighting within the PDF viewer
- HRMS integration
- Analytics or audit logging
- Email or Slack-based interface
- Policy authoring or approval workflows
