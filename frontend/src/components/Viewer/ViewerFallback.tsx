interface ViewerFallbackProps {
  /** Direct SAS download URL — safe to expose to the user. */
  downloadUrl: string | null
  documentName: string
}

/**
 * Shown when PDF.js fails to render (FRD FR-PDF-009).
 * Provides a fallback download link so the user isn't stuck.
 */
export function ViewerFallback({ downloadUrl, documentName }: ViewerFallbackProps) {
  return (
    <div
      className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center"
      style={{ color: 'var(--color-muted-fg)' }}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="48"
        height="48"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ opacity: 0.4 }}
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="12" y1="12" x2="12" y2="16" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>

      <div>
        <p className="text-sm font-medium" style={{ color: 'var(--color-foreground)' }}>
          Unable to render this document.
        </p>
        <p className="mt-1 text-xs" style={{ color: 'var(--color-muted-fg)' }}>
          {documentName}
        </p>
      </div>

      {downloadUrl && (
        <a
          href={downloadUrl}
          download
          className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: 'var(--color-truboard-primary)' }}
          id="viewer-fallback-download"
        >
          Download PDF →
        </a>
      )}
    </div>
  )
}
