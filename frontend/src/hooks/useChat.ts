import { useCallback, useEffect, useRef } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { addMessage, setLoading, setRateLimitCountdown, clearMessages } from '../store/chatSlice'
import { setActiveDocument } from '../store/activeDocumentSlice'
import { useSendMessageMutation, useClearSessionMutation } from '../store/chatAdminApi'
import { useListDocumentsQuery } from '../store/documentsApi'
import type { Policy } from '../types'

/**
 * Manages the full chat interaction lifecycle per FRD §5:
 * - Submit query to POST /api/chat/message
 * - Append user + assistant messages to Redux
 * - Handle redirect_document_id → switch active document
 * - Handle 429 → start countdown timer
 * - clearChat: DELETE /api/chat/session + clear Redux messages
 */
export function useChat(activeDocument: Policy | null) {
  const dispatch = useAppDispatch()
  const messages = useAppSelector((s) => s.chat.messages)
  const isLoading = useAppSelector((s) => s.chat.isLoading)
  const rateLimitCountdown = useAppSelector((s) => s.chat.rateLimitCountdown)
  const { data: documents = [] } = useListDocumentsQuery()
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [sendMessage] = useSendMessageMutation()
  const [clearSession] = useClearSessionMutation()

  // Tick down the rate-limit countdown every second.
  useEffect(() => {
    if (rateLimitCountdown > 0) {
      countdownRef.current = setInterval(() => {
        dispatch(setRateLimitCountdown(Math.max(0, rateLimitCountdown - 1)))
      }, 1000)
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [rateLimitCountdown, dispatch])

  const submit = useCallback(
    async (query: string) => {
      if (!query.trim() || isLoading || rateLimitCountdown > 0 || !activeDocument) return

      const userMsg = {
        id: uuidv4(),
        role: 'user' as const,
        content: query.trim(),
      }
      dispatch(addMessage(userMsg))
      dispatch(setLoading(true))

      try {
        const result = await sendMessage({
          query: query.trim(),
          active_document_id: activeDocument.id,
        }).unwrap()

        dispatch(
          addMessage({
            id: uuidv4(),
            role: 'assistant',
            content: result.answer,
            citations: result.citations,
            confidence: result.confidence,
          }),
        )

        // Redirect: switch viewer to different document if instructed.
        if (result.redirect_document_id) {
          const redirectDoc = documents.find((d) => d.id === result.redirect_document_id)
          if (redirectDoc) dispatch(setActiveDocument(redirectDoc))
        }
      } catch (err: unknown) {
        // Handle rate-limit (429) with Retry-After.
        const anyErr = err as { status?: number; data?: unknown; error?: string }
        if (anyErr?.status === 429) {
          const retryAfter =
            // RTK Query error doesn't expose headers directly; fall back to 60s.
            60
          dispatch(setRateLimitCountdown(retryAfter))
          dispatch(
            addMessage({
              id: uuidv4(),
              role: 'assistant',
              content: `Query limit reached. Try again in ${Math.ceil(retryAfter / 60)} minute(s).`,
              confidence: 'not_found',
            }),
          )
        } else if (anyErr?.status === 503) {
          dispatch(
            addMessage({
              id: uuidv4(),
              role: 'assistant',
              content: 'Temporarily unavailable. Please try again in a moment.',
              confidence: 'not_found',
            }),
          )
        } else {
          dispatch(
            addMessage({
              id: uuidv4(),
              role: 'assistant',
              content: 'Something went wrong. Please try again.',
              confidence: 'not_found',
            }),
          )
        }
      } finally {
        dispatch(setLoading(false))
      }
    },
    [activeDocument, isLoading, rateLimitCountdown, sendMessage, dispatch, documents],
  )

  const clearChat = useCallback(async () => {
    dispatch(clearMessages())
    try {
      await clearSession().unwrap()
    } catch {
      // Session clear failure is non-fatal.
    }
  }, [clearSession, dispatch])

  return { messages, isLoading, rateLimitCountdown, submit, clearChat }
}
