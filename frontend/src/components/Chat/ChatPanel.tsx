import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { MessageBubble } from './MessageBubble'
import { SwitchToast } from './SwitchToast'
import { useChat } from '../../hooks/useChat'
import type { Policy } from '../../types'

import type { Citation } from '../../types'

interface ChatPanelProps {
  activeDocument: Policy | null
  /** Called when citation "Open →" is clicked; switches document if needed + scrolls. */
  onCitationOpen: (citation: Citation) => void
  /** Called when the AI redirects to a different document; page to scroll to. */
  onDocumentRedirect: (page: number) => void
  /** Name of the last switched-to document, for the toast. */
  lastSwitchedDocName: string | null
}

/**
 * Full chat panel (FRD §7.2 / §7.3):
 * - Scrollable message thread; user right, assistant left
 * - Pinned text input; Send on click or Enter (Shift+Enter = newline)
 * - Typing indicator while loading
 * - Rate-limit countdown disables input (FRD FR-UI-008)
 * - Confidence styling delegated to MessageBubble
 * - SwitchToast on document redirect
 */
export function ChatPanel({ activeDocument, onCitationOpen, onDocumentRedirect, lastSwitchedDocName }: ChatPanelProps) {
  const { messages, isLoading, rateLimitCountdown, submit, clearChat } = useChat(activeDocument, onDocumentRedirect)
  const [inputValue, setInputValue] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to bottom on new messages.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSend = () => {
    if (!inputValue.trim()) return
    submit(inputValue)
    setInputValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isDisabled = isLoading || rateLimitCountdown > 0 || !activeDocument

  return (
    <div className="flex h-full flex-col">
      {/* ---- Header ---- */}
      <div
        className="flex shrink-0 items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <span className="text-sm font-semibold" style={{ color: 'var(--color-truboard-primary)' }}>
          Policy Assistant
        </span>
        {messages.length > 0 && (
          <button
            type="button"
            id="clear-chat-button"
            onClick={clearChat}
            className="text-xs transition-colors"
            style={{ color: 'var(--color-muted-fg)' }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-foreground)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-muted-fg)')}
          >
            Clear
          </button>
        )}
      </div>

      {/* ---- Message thread ---- */}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
        {messages.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2">
            <p className="text-center text-sm" style={{ color: 'var(--color-muted-fg)' }}>
              Ask a question about any company policy.
            </p>
            <p className="text-center text-xs" style={{ color: 'var(--color-truboard-primary-300)' }}>
              {activeDocument ? `Active: ${activeDocument.policy_name}` : 'Select a policy first'}
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onCitationOpen={onCitationOpen} />
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div
              className="flex items-center gap-1.5 rounded-2xl px-4 py-3"
              style={{
                backgroundColor: 'white',
                border: '1px solid var(--color-border)',
                borderBottomLeftRadius: '4px',
              }}
            >
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="inline-block h-2 w-2 rounded-full"
                  style={{
                    backgroundColor: 'var(--color-truboard-primary-400)',
                    animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ---- Input area ---- */}
      <div
        className="shrink-0 px-3 pb-3 pt-2"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
        {/* Rate-limit banner */}
        {rateLimitCountdown > 0 && (
          <p
            className="mb-2 text-center text-xs font-medium"
            style={{ color: 'var(--color-truboard-secondary)' }}
          >
            Query limit reached. Try again in {Math.ceil(rateLimitCountdown / 60)} minute
            {rateLimitCountdown > 60 ? 's' : ''}.
          </p>
        )}

        <div
          className="flex items-end gap-2 rounded-xl border px-3 py-2"
          style={{
            borderColor: isDisabled ? 'var(--color-border)' : 'var(--color-truboard-primary-400)',
            backgroundColor: isDisabled ? 'var(--color-truboard-primary-100)' : 'white',
            transition: 'border-color 0.15s',
          }}
        >
          <textarea
            ref={inputRef}
            id="chat-input"
            rows={1}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isDisabled}
            placeholder={
              rateLimitCountdown > 0
                ? 'Rate limited…'
                : !activeDocument
                  ? 'Select a policy first…'
                  : 'Ask about any company policy…'
            }
            className="flex-1 resize-none bg-transparent text-sm outline-none"
            style={{
              color: 'var(--color-foreground)',
              maxHeight: '120px',
              lineHeight: '1.5',
            }}
          />
          <button
            type="button"
            id="chat-send-button"
            onClick={handleSend}
            disabled={isDisabled || !inputValue.trim()}
            className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-opacity"
            style={{
              backgroundColor: 'var(--color-truboard-primary)',
              opacity: isDisabled || !inputValue.trim() ? 0.4 : 1,
            }}
          >
            Send
          </button>
        </div>
      </div>

      {/* Toast */}
      <SwitchToast documentName={lastSwitchedDocName} />

      {/* Bounce keyframe */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translate(-50%, 8px); }
          to   { opacity: 1; transform: translate(-50%, 0); }
        }
      `}</style>
    </div>
  )
}
