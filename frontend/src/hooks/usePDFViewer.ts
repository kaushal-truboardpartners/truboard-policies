import { useCallback, useEffect, useRef, useState } from 'react'
import { useLazyGetDocumentUrlQuery } from '../store/documentsApi'
import type { Policy } from '../types'

/**
 * PDF.js lifecycle hook.
 *
 * Responsibilities (per CLAUDE.md / FRD):
 * - Fetches a fresh SAS URL whenever the active document changes.
 * - Loads the PDF into PDF.js (GlobalWorkerOptions set once at module level).
 * - Exposes scrollToPage() — calls scrollPageIntoView after documentLoaded fires.
 * - On 403 from the blob URL: re-fetches a fresh SAS URL and reloads (FRD FR-PDF-007).
 * - Exposes error state for ViewerFallback.
 */

// Import the PDF.js worker using Vite's ?url import so the worker can be
// resolved to the correct path at runtime (avoids cross-origin worker issues).
import * as pdfjsLib from 'pdfjs-dist'
import type { PDFPageProxy } from 'pdfjs-dist'

// Point PDF.js at its bundled worker.
// Using the legacy build to avoid the ESM worker fingerprinting issues with Vite.
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const SCALE = 1.5 // device-pixel-adjusted scale factor

export interface PDFViewerHandle {
  /** Scroll to a 1-indexed page. No-op if PDF not loaded. */
  scrollToPage: (page: number) => void
}

export interface UsePDFViewerOptions {
  activeDocument: Policy | null
  targetPage?: number | null
}

export function usePDFViewer({ activeDocument, targetPage }: UsePDFViewerOptions) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sasUrl, setSasUrl] = useState<string | null>(null)
  const pageRefs = useRef<HTMLDivElement[]>([])

  const [triggerGetUrl] = useLazyGetDocumentUrlQuery()

  // Fetch a fresh SAS URL for the given document.
  const fetchSasUrl = useCallback(
    async (docId: string): Promise<string | null> => {
      try {
        const result = await triggerGetUrl(docId).unwrap()
        return result.url
      } catch {
        return null
      }
    },
    [triggerGetUrl],
  )

  // Render all pages of a PDF into the container.
  const renderPdf = useCallback(async (url: string, docId: string) => {
    const container = containerRef.current
    if (!container) return

    setIsLoading(true)
    setError(null)
    container.innerHTML = '' // clear previous render
    pageRefs.current = []

    try {
      const loadingTask = pdfjsLib.getDocument({ url })
      const pdf = await loadingTask.promise

      for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
        const page: PDFPageProxy = await pdf.getPage(pageNum)
        const viewport = page.getViewport({ scale: SCALE })

        const pageWrapper = document.createElement('div')
        pageWrapper.style.cssText = `
          margin-bottom: 8px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.12);
          border-radius: 4px;
          overflow: hidden;
          background: white;
        `
        pageWrapper.dataset.page = String(pageNum)
        pageRefs.current.push(pageWrapper as HTMLDivElement)
        container.appendChild(pageWrapper)

        const canvas = document.createElement('canvas')
        canvas.width = viewport.width
        canvas.height = viewport.height
        canvas.style.display = 'block'
        canvas.style.width = '100%'
        pageWrapper.appendChild(canvas)

        const ctx = canvas.getContext('2d')!
        await page.render({ canvasContext: ctx, viewport }).promise
      }
    } catch (err: unknown) {
      const isNetworkError =
        err instanceof Error && (err.message.includes('403') || err.message.includes('401'))

      if (isNetworkError) {
        // SAS token may have expired — re-fetch and retry once.
        const freshUrl = await fetchSasUrl(docId)
        if (freshUrl && freshUrl !== url) {
          setSasUrl(freshUrl)
          return // useEffect will trigger re-render with fresh URL
        }
      }
      setError('Unable to render this document.')
    } finally {
      setIsLoading(false)
    }
  }, [fetchSasUrl])

  // Load a new SAS URL whenever the active document changes.
  useEffect(() => {
    if (!activeDocument) {
      setSasUrl(null)
      return
    }
    let cancelled = false
    fetchSasUrl(activeDocument.id).then((url) => {
      if (!cancelled) setSasUrl(url)
    })
    return () => { cancelled = true }
  }, [activeDocument?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Render whenever we have a URL (and re-render on 403 refresh).
  useEffect(() => {
    if (sasUrl && activeDocument) {
      renderPdf(sasUrl, activeDocument.id)
    }
  }, [sasUrl]) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to target page after render completes (FR-PDF-008).
  useEffect(() => {
    if (targetPage && pageRefs.current.length >= targetPage) {
      const el = pageRefs.current[targetPage - 1]
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [targetPage, isLoading])

  const scrollToPage = useCallback((page: number) => {
    const el = pageRefs.current[page - 1]
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  return { containerRef, isLoading, error, scrollToPage }
}
