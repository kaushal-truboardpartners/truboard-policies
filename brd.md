# Business Requirements Document
## TruBoard Policies — Internal Policy Assistant
**Organisation:** TruBoard Cleantech
**Version:** 1.0 | **Date:** June 2026 | **Classification:** Internal — Confidential

---

## 1. Executive Summary

TruBoard Cleantech employs approximately 800–1000 people who need reliable, fast access to HR and Compliance policies. Currently, employees must manually search through 17 policy documents to answer questions about leave entitlements, reimbursement rules, notice periods, code of conduct, and similar matters. This generates repetitive HR queries, inconsistent interpretations, and avoidable delays.

TruBoard Policies is a web-based internal tool that gives employees a three-panel workspace: a sidebar listing all policy documents, a built-in PDF viewer to read them, and a chatbot to ask questions. The chatbot answers from the document currently open in the viewer — or finds the answer in another document and redirects the viewer there automatically. Every answer cites the exact policy and page number. The system is authenticated via the company's existing Microsoft identity provider.

The chatbot is grounded exclusively in official policy documents via a Retrieval-Augmented Generation (RAG) architecture. It never speculates or fabricates. If it cannot find an answer, it says so clearly.

---

## 2. Business Problem Statement

- Employees invest significant time manually locating specific policy clauses within large PDFs
- HR receives a high volume of repetitive, self-serviceable policy queries
- Policy language is formal and requires interpretation, leading to inconsistent application across teams
- No centralised, always-available tool exists to browse, read, and query policies in one place

---

## 3. Business Objectives

| ID | Objective | Measure of Success |
|---|---|---|
| BO-001 | Enable employees to self-serve policy queries without contacting HR | Measurable reduction in repetitive HR email volume |
| BO-002 | Provide accurate, policy-grounded answers with zero hallucination | 95%+ grounding accuracy on manual audit |
| BO-003 | Give employees a single place to browse, read, and query all company policies | All 17 policies accessible and queryable from one interface |
| BO-004 | Support bilingual (English and Hinglish) employee queries | Hinglish queries correctly interpreted and answered in English |
| BO-005 | Establish an IT-managed pipeline for policy document updates | Policy updates live within one business day of upload |
| BO-006 | Protect policy content behind authenticated access | Zero unauthenticated access to policy documents or chatbot |

---

## 4. Stakeholders

| Stakeholder | Role | Primary Interest |
|---|---|---|
| All Employees (~800–1000) | End Users | Fast, accurate answers; ability to read full policies in-app |
| HR & Compliance Team | Policy Owners | Accuracy of policy content; correct citations |
| IT Team (2–3 persons) | System Administrators | Document ingestion, system health, version management |
| Engineering (1 person) | Product Owner & Engineer | Architecture, build, and ongoing maintenance |
| Executive Leadership | Sponsors | Operational efficiency, compliance assurance |

---

## 5. Project Scope

### 5.1 Phase 1 — MVP
- Microsoft SSO authentication via existing company identity provider
- Three-panel layout: policy sidebar, PDF viewer, chatbot
- Alphabetical list of all 17 policy PDFs in the sidebar
- Built-in PDF viewer (PDF.js) — first policy pre-loaded on app launch
- Chatbot with two-phase retrieval: searches active PDF first, falls back to all documents
- Chatbot can redirect the viewer to a different PDF and page when the answer is found there
- Conversation persists across all PDF switches (sidebar click or chatbot redirect)
- Natural language query support including Hinglish in Roman script; English-only responses
- Every response cites the source policy and page number with a clickable "Open" button
- Scroll-to-page in the PDF viewer on citation click
- Guardrails: "I don't know" response; out-of-scope rejection
- Admin-only PDF upload with SHA-256 deduplication, versioning, and soft-delete on replacement
- Async ingestion pipeline with real-time progress via Server-Sent Events
- Per-user rate limiting (30 queries / 60 minutes)
- Role-based access: admin vs employee, enforced server-side

### 5.2 Phase 2 — First Upgrade
- Policy grouping and tag-based filtering in the sidebar
- Admin dashboard for full policy lifecycle management
- Chat history persistence across login sessions
- Per-response feedback (thumbs up / thumbs down)
- Multi-subsidiary support with conflict detection

### 5.3 Out of Scope
- Mobile layout
- Multi-subsidiary support and conflict detection (Phase 2)
- Text highlighting within the PDF viewer
- Full-text keyword search within PDFs
- HRMS integration
- Analytics or audit logging
- Email or Slack-based interface
- Policy authoring or approval workflows

---

## 6. Business Requirements

| ID | Requirement | Priority |
|---|---|---|
| BR-001 | The system shall authenticate users exclusively via the company's existing Microsoft identity provider. | Must Have |
| BR-002 | The system shall present all policy documents in a browsable sidebar and render them in a built-in PDF viewer. | Must Have |
| BR-003 | The system shall accept queries in English and Hinglish (Roman script) and respond in English. | Must Have |
| BR-004 | All chatbot responses shall be grounded exclusively in official uploaded policy documents. The system shall not speculate or fabricate. | Must Have |
| BR-005 | Every chatbot response shall cite the source policy and page number, with a control to open that location in the viewer. | Must Have |
| BR-006 | When the answer to a query is in a different document than the one currently open, the system shall identify this, answer from the correct document, and redirect the viewer to that document and page. | Must Have |
| BR-007 | The conversation shall never reset when the active PDF changes, whether triggered by the chatbot or by the user clicking the sidebar. | Must Have |
| BR-008 | When the system cannot find an answer, it shall say so explicitly and suggest contacting HR. It shall never return a vague or fabricated response. | Must Have |
| BR-009 | The system shall decline questions unrelated to company policies with a clear explanation. | Must Have |
| BR-010 | Administrators shall upload new or updated policy PDFs through a secure interface. Documents shall be queryable within a reasonable time after upload. | Must Have |
| BR-011 | When a policy is replaced, the previous version shall be archived (soft-deleted), not permanently destroyed. | Must Have |
| BR-012 | The system shall enforce per-user query rate limits to prevent LLM cost overruns. | Must Have |

---

## 7. Success Metrics

| Metric | Target | How Measured |
|---|---|---|
| Answer grounding accuracy | ≥ 95% | Manual spot-audit of 50 random query-response pairs per month |
| Citation accuracy | 100% | Validation that citation "Open" buttons navigate to the correct document and page |
| Response time (P95) | ≤ 5 seconds | API response time monitoring |
| PDF render time | ≤ 2 seconds (first page) | Frontend performance monitoring |
| System availability (business hours) | 99.5% | Uptime monitoring, IST 09:00–17:00 Mon–Fri |
| Ingestion success rate | 100% for valid PDFs | Job completion tracking |

---

## 8. Assumptions

- All 17 policy PDFs are in English with selectable (non-scanned) text. No OCR required.
- All employees have active Microsoft accounts with the company's identity provider.
- Policy documents do not contain critical information embedded only in images.
- Policies are updated infrequently (quarterly at most).
- Uploaded PDFs are not password-protected. IT validates this prior to upload.
- Microsoft IDP remains operational. No fallback authentication is required.

---

## 9. Constraints

| Constraint | Description |
|---|---|
| Authentication | Must use the company's existing Microsoft IDP exclusively. |
| Language | Chatbot responds in English only. Hinglish input supported. |
| Team Size | System must be buildable and maintainable by a single engineer. |
| Platform | Desktop web application. Mobile layout is out of scope for Phase 1. |
| Admin Access | Document management is IT-only in Phase 1. |
| LLM Accuracy | System must never hallucinate. RAG with strict prompt guardrails is mandatory. |

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM hallucination producing inaccurate policy content | Low (with RAG) | High | Strict system prompt; answers grounded in retrieved chunks only; "I don't know" fallback; manual audits |
| Cross-document redirect navigating to wrong page | Medium | Medium | Page number extracted from chunk metadata at ingestion time, not inferred by LLM |
| Policy updated without re-ingestion | Medium | High | IT SOP: upload within 24 hours of any policy change |
| Embedding model deprecation requiring full re-index | Low | Medium | Re-indexing job built as first-class admin operation |
| Microsoft SSO outage blocking all access | Low | High | Clear maintenance page. No fallback auth by design. |
| Prompt injection by a malicious employee | Low | Medium | Input sanitisation at API boundary; prompt injection resistance in system prompt |
| PDF.js rendering failure on a specific PDF | Low | Low | Fallback message with direct SAS download link shown if viewer fails to render |
