import { useCallback, useRef, useState } from 'react'
import { useUploadPolicyMutation } from '../store/chatAdminApi'
import type { JobStatus, JobStatusValue } from '../types'

export interface UploadFile {
  id: string
  file: File
  status: JobStatusValue | 'pending' | 'uploading'
  progress: number
  message: string
  jobId?: string
  documentId?: string
  chunksCreated?: number
  error?: string
}

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued…',
  parsing: 'Parsing PDF…',
  chunking: 'Chunking text…',
  embedding: 'Generating embeddings…',
  indexing: 'Indexing…',
  complete: 'Complete',
  failed: 'Failed',
}

/** Maximum file size: 50 MB (FRD FR-ING-003). */
const MAX_FILE_SIZE = 50 * 1024 * 1024

/**
 * Manages the multi-file admin upload flow (FRD §8 / §4):
 * - Validates MIME type + extension + size on file selection
 * - Calls POST /api/admin/upload-and-ingest for each file
 * - Opens an SSE stream (GET /api/admin/jobs/{id}/stream) per job
 * - Updates per-file status/progress from SSE events
 * - Exposes removeFile, clearAll, retryFile
 */
import { useAppSelector } from '../store/hooks'

export function useUpload() {
  const [files, setFiles] = useState<UploadFile[]>([])
  const sseRefs = useRef<Record<string, EventSource>>({})
  const [uploadPolicy] = useUploadPolicyMutation()
  const accessToken = useAppSelector((state) => state.auth.accessToken)

  const _updateFile = useCallback((id: string, patch: Partial<UploadFile>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)))
  }, [])

  const _openSSE = useCallback(
    (fileId: string, jobId: string) => {
      const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
      const token = accessToken ?? ''
      const url = `${apiBase}/api/admin/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`
      const es = new EventSource(url)

      es.onmessage = (event) => {
        try {
          const data: JobStatus = JSON.parse(event.data)
          _updateFile(fileId, {
            status: data.status,
            progress: data.progress,
            message: STAGE_LABELS[data.status] ?? data.message,
            chunksCreated: data.chunks_created,
            error: data.error,
          })
          if (data.status === 'complete' || data.status === 'failed') {
            es.close()
            delete sseRefs.current[fileId]
          }
        } catch {
          // Ignore malformed events.
        }
      }

      es.onerror = () => {
        _updateFile(fileId, { status: 'failed', error: 'Connection to job stream lost.' })
        es.close()
        delete sseRefs.current[fileId]
      }

      sseRefs.current[fileId] = es
    },
    [_updateFile, accessToken],
  )

  const addFiles = useCallback(
    (raw: FileList | File[]) => {
      const validated: UploadFile[] = []
      Array.from(raw).forEach((file) => {
        const isPdf =
          file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
        const isTooBig = file.size > MAX_FILE_SIZE
        const id = crypto.randomUUID()

        if (!isPdf) {
          validated.push({
            id,
            file,
            status: 'failed',
            progress: 0,
            message: 'Only PDF files are allowed.',
            error: 'Only PDF files are allowed.',
          })
        } else if (isTooBig) {
          validated.push({
            id,
            file,
            status: 'failed',
            progress: 0,
            message: 'File exceeds 50 MB limit.',
            error: 'File exceeds 50 MB limit.',
          })
        } else {
          validated.push({
            id,
            file,
            status: 'pending',
            progress: 0,
            message: 'Ready to upload',
          })
        }
      })
      setFiles((prev) => [...prev, ...validated])
    },
    [],
  )

  const uploadAll = useCallback(async () => {
    const pending = files.filter((f) => f.status === 'pending')
    for (const item of pending) {
      _updateFile(item.id, { status: 'uploading', progress: 5, message: 'Uploading…' })
      const formData = new FormData()
      formData.append('file', item.file)
      try {
        const res = await uploadPolicy(formData).unwrap()
        _updateFile(item.id, {
          status: 'queued',
          progress: 10,
          message: 'Queued…',
          jobId: res.job_id,
          documentId: res.document_id,
        })
        _openSSE(item.id, res.job_id)
      } catch (err: unknown) {
        const anyErr = err as { data?: { detail?: string }; status?: number }
        _updateFile(item.id, {
          status: 'failed',
          error: anyErr?.data?.detail ?? 'Upload failed.',
          message: anyErr?.data?.detail ?? 'Upload failed.',
        })
      }
    }
  }, [files, uploadPolicy, _updateFile, _openSSE])

  const removeFile = useCallback((id: string) => {
    sseRefs.current[id]?.close()
    delete sseRefs.current[id]
    setFiles((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const retryFile = useCallback(
    (id: string) => {
      _updateFile(id, { status: 'pending', progress: 0, error: undefined, message: 'Ready to upload' })
    },
    [_updateFile],
  )

  const clearAll = useCallback(() => {
    Object.values(sseRefs.current).forEach((es) => es.close())
    sseRefs.current = {}
    setFiles([])
  }, [])

  const pendingCount = files.filter((f) => f.status === 'pending').length

  return { files, addFiles, uploadAll, removeFile, retryFile, clearAll, pendingCount }
}
