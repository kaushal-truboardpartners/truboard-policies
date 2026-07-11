import type { UploadFile } from '../../hooks/useUpload'

const STATUS_COLORS: Record<string, string> = {
  pending:   'var(--color-truboard-primary-400)',
  uploading: 'var(--color-truboard-primary-600)',
  queued:    'var(--color-truboard-primary-600)',
  parsing:   'var(--color-truboard-secondary)',
  chunking:  'var(--color-truboard-secondary)',
  embedding: 'var(--color-truboard-secondary)',
  indexing:  'var(--color-truboard-secondary)',
  complete:  'hsl(142 71% 45%)',  /* green */
  failed:    'var(--color-destructive)',
}

interface FileRowProps {
  item: UploadFile
  onRemove: () => void
  onRetry: () => void
}

/**
 * Displays one file with name, size, status label, progress bar, and
 * remove/retry actions (FRD FR-ADMIN-005, FR-ADMIN-012, FR-ADMIN-013).
 */
export function FileRow({ item, onRemove, onRetry }: FileRowProps) {
  const sizeKb = (item.file.size / 1024).toFixed(0)
  const barColor = STATUS_COLORS[item.status] ?? 'var(--color-truboard-primary)'
  const isDone = item.status === 'complete' || item.status === 'failed'

  return (
    <div
      className="flex flex-col gap-2 rounded-xl border p-4"
      style={{
        borderColor: item.status === 'failed'
          ? 'var(--color-destructive)'
          : 'var(--color-border)',
        backgroundColor: 'white',
      }}
    >
      {/* Top row: name + actions */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p
            className="truncate text-sm font-medium"
            style={{ color: 'var(--color-foreground)' }}
            title={item.file.name}
          >
            {item.file.name}
          </p>
          <p className="text-xs" style={{ color: 'var(--color-muted-fg)' }}>
            {sizeKb} KB
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {item.status === 'failed' && (
            <button
              type="button"
              id={`retry-${item.id}`}
              onClick={onRetry}
              className="rounded px-2 py-1 text-xs font-medium transition-colors"
              style={{
                backgroundColor: 'var(--color-truboard-primary-200)',
                color: 'var(--color-truboard-primary)',
              }}
            >
              Retry
            </button>
          )}
          {(item.status === 'pending' || isDone) && (
            <button
              type="button"
              id={`remove-${item.id}`}
              onClick={onRemove}
              className="text-xs transition-colors"
              style={{ color: 'var(--color-muted-fg)' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-destructive)')}
              onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--color-muted-fg)')}
              aria-label={`Remove ${item.file.name}`}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div
        className="h-1.5 w-full overflow-hidden rounded-full"
        style={{ backgroundColor: 'var(--color-truboard-primary-200)' }}
      >
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${item.progress}%`, backgroundColor: barColor }}
        />
      </div>

      {/* Status message */}
      <p className="text-xs font-medium" style={{ color: barColor }}>
        {item.status === 'complete' && item.chunksCreated !== undefined
          ? `Complete — ${item.chunksCreated.toLocaleString()} chunks indexed`
          : item.error || item.message}
      </p>
    </div>
  )
}
