// Shared API/domain types — mirror the backend contracts in CLAUDE.md / FRD §10.

export interface Policy {
  id: string
  policy_name: string
  version: number
}

export interface Citation {
  policy: string
  page: number
  section: string
}

export type Confidence = 'found' | 'not_found' | 'out_of_scope'

// POST /api/chat/message response
export interface ChatResponse {
  answer: string
  citations: Citation[]
  redirect_document_id: string | null
  redirect_page: number | null
  confidence: Confidence
}

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  citations?: Citation[]
  confidence?: Confidence
}

export type JobStatusValue =
  | 'queued'
  | 'parsing'
  | 'chunking'
  | 'embedding'
  | 'indexing'
  | 'complete'
  | 'failed'

// SSE event payload from GET /api/admin/jobs/{id}/stream
export interface JobStatus {
  status: JobStatusValue
  progress: number
  message: string
  chunks_created?: number
  error?: string
}

export interface DocumentUrl {
  url: string
  expires_at: string
}
