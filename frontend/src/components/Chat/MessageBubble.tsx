// Note: react-markdown is used for assistant message rendering (M8).
// Add to package.json if not installed: npm install react-markdown
import ReactMarkdown from 'react-markdown'
import type { ChatMessage, Citation, Confidence } from '../../types'

// Confidence style map (FRD FR-UI-011, FR-UI-012).
const CONFIDENCE_STYLES: Record<Confidence, React.CSSProperties> = {
  found: {},
  not_found: {
    color: 'var(--color-muted-fg)',
    borderLeft: '3px solid var(--color-truboard-primary-300)',
    paddingLeft: '0.75rem',
  },
  out_of_scope: {
    borderLeft: '3px solid var(--color-truboard-warning)',
    paddingLeft: '0.75rem',
    backgroundColor: 'hsl(39 80% 65% / 8%)',
    borderRadius: '0 6px 6px 0',
    padding: '0.5rem 0.75rem',
  },
}

// ---------------------------------------------------------------------------
// CitationButton
// ---------------------------------------------------------------------------
interface CitationButtonProps {
  citation: Citation
  onOpen: (citation: Citation) => void
}

export function CitationButton({ citation, onOpen }: CitationButtonProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs" style={{ color: 'var(--color-muted-fg)' }}>
        {citation.policy} — Page {citation.page}
        {citation.section ? ` · ${citation.section}` : ''}
      </span>
      <button
        type="button"
        id={`citation-open-p${citation.page}`}
        onClick={() => onOpen(citation)}
        className="rounded px-2 py-0.5 text-xs font-medium transition-colors"
        style={{
          backgroundColor: 'var(--color-truboard-primary-200)',
          color: 'var(--color-truboard-primary)',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--color-truboard-primary)'
          e.currentTarget.style.color = 'white'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--color-truboard-primary-200)'
          e.currentTarget.style.color = 'var(--color-truboard-primary)'
        }}
      >
        Open →
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MessageBubble
// ---------------------------------------------------------------------------
interface MessageBubbleProps {
  message: ChatMessage
  onCitationOpen: (citation: Citation) => void
}

export function MessageBubble({ message, onCitationOpen }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const confidenceStyle =
    !isUser && message.confidence
      ? CONFIDENCE_STYLES[message.confidence]
      : {}

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className="max-w-[85%] rounded-2xl px-4 py-2.5"
        style={
          isUser
            ? {
                backgroundColor: 'var(--color-truboard-primary)',
                color: 'white',
                borderBottomRightRadius: '4px',
              }
            : {
                backgroundColor: 'white',
                border: '1px solid var(--color-border)',
                borderBottomLeftRadius: '4px',
                color: 'var(--color-foreground)',
                ...confidenceStyle,
              }
        }
      >
        {isUser ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div
            className="prose prose-sm max-w-none text-sm leading-relaxed"
            style={{ color: 'inherit' }}
          >
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-col gap-1 border-t pt-2" style={{ borderColor: 'var(--color-border)' }}>
            {message.citations.map((c, i) => (
              <CitationButton key={i} citation={c} onOpen={onCitationOpen} />
            ))}
          </div>
        )}

        {/* not_found sub-label */}
        {!isUser && message.confidence === 'not_found' && (
          <p className="mt-1 text-xs font-medium" style={{ color: 'var(--color-truboard-secondary)' }}>
            Please contact HR directly for clarification.
          </p>
        )}

        {/* out_of_scope sub-label */}
        {!isUser && message.confidence === 'out_of_scope' && (
          <p className="mt-1 text-xs font-medium" style={{ color: 'var(--color-truboard-warning)' }}>
            I can only assist with HR and Compliance policy questions.
          </p>
        )}
      </div>
    </div>
  )
}
