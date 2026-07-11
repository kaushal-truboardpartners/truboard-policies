import { usePDFViewer } from '../../hooks/usePDFViewer'
import { ViewerFallback } from './ViewerFallback'
import type { Policy } from '../../types'

interface PDFViewerProps {
  activeDocument: Policy | null
  /** 1-indexed target page — scrolls to it once the PDF is loaded. */
  targetPage?: number | null
  /** SAS URL for the fallback download link (passed in from parent). */
  downloadUrl?: string | null
}

/**
 * PDF.js-powered viewer panel.
 *
 * Wraps usePDFViewer and renders:
 * - Loading skeleton while the PDF pages are rendering
 * - Error/fallback UI (ViewerFallback) on PDF.js failure
 * - All PDF pages stacked vertically in a scrollable container
 */
export function PDFViewer({ activeDocument, targetPage, downloadUrl }: PDFViewerProps) {
  const { containerRef, isLoading, error } = usePDFViewer({ activeDocument, targetPage })

  if (!activeDocument) {
    return (
      <div
        className="flex h-full items-center justify-center text-sm"
        style={{ color: 'var(--color-muted-fg)' }}
      >
        Select a policy from the sidebar to get started.
      </div>
    )
  }

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Loading overlay */}
      {isLoading && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center"
          style={{ backgroundColor: 'var(--color-background)', opacity: 0.85 }}
        >
          <div className="flex flex-col items-center gap-3">
            <div
              className="h-8 w-8 animate-spin rounded-full border-2 border-t-transparent"
              style={{ borderColor: 'var(--color-truboard-primary-300)', borderTopColor: 'transparent' }}
            />
            <p className="text-sm" style={{ color: 'var(--color-muted-fg)' }}>
              Loading {activeDocument.policy_name}…
            </p>
          </div>
        </div>
      )}

      {/* Error fallback */}
      {error && !isLoading ? (
        <ViewerFallback
          downloadUrl={downloadUrl ?? null}
          documentName={activeDocument.policy_name}
        />
      ) : (
        /* PDF canvas container — PDF.js renders pages into this div */
        <div
          ref={containerRef}
          id="pdf-canvas-container"
          className="h-full w-full overflow-y-auto px-4 py-4"
          style={{ backgroundColor: 'hsl(220 13% 93%)' }}
        />
      )}
    </div>
  )
}
