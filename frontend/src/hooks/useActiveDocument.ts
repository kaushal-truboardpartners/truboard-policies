import { useEffect } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { setActiveDocument } from '../store/activeDocumentSlice'
import { useListDocumentsQuery } from '../store/documentsApi'
import type { Policy } from '../types'

/**
 * Manages which policy document is currently active in the viewer.
 *
 * - On first load: auto-selects the first document (alphabetically first,
 *   as returned by the API — FRD FR-PDF-004).
 * - Exposes `setActive` for the sidebar to call on click.
 * - Exposes `activeDocument` for the viewer and chat to read.
 */
export function useActiveDocument() {
  const dispatch = useAppDispatch()
  const activeDocument = useAppSelector((s) => s.activeDocument.document)
  const { data: documents = [], isLoading, isError } = useListDocumentsQuery()

  // Auto-select the first document on initial load (FR-PDF-004).
  useEffect(() => {
    if (!activeDocument && documents.length > 0) {
      dispatch(setActiveDocument(documents[0]))
    }
  }, [activeDocument, documents, dispatch])

  const setActive = (policy: Policy) => {
    dispatch(setActiveDocument(policy))
  }

  return { activeDocument, documents, isLoading, isError, setActive }
}
