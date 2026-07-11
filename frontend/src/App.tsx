import { useCallback, useRef, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LoginCallback from './auth/LoginCallback'
import LogoutCallback from './auth/LogoutCallback'
import OAuthPage from './auth/OAuthPage'
import { useAuth } from './auth/useAuth'
import { useActiveDocument } from './hooks/useActiveDocument'
import { PolicyList } from './components/Sidebar/PolicyList'
import { PDFViewer } from './components/Viewer/PDFViewer'
import { ChatPanel } from './components/Chat/ChatPanel'
import { UploadZone } from './components/Admin/UploadZone'
import { FileRow } from './components/Admin/FileRow'
import { useUpload } from './hooks/useUpload'
import type { Policy } from './types'

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar({ onDocumentChange }: { onDocumentChange: (d: Policy) => void }) {
  const { documents, activeDocument, isLoading, isError, setActive } = useActiveDocument()
  const { oAuthLogout } = useAuth()

  const handleSelect = (p: Policy) => {
    setActive(p)
    onDocumentChange(p)
  }

  return (
    <aside
      className="flex h-full flex-col overflow-hidden"
      style={{ borderRight: '1px solid var(--color-border)' }}
    >
      {/* Header */}
      <div
        className="flex shrink-0 flex-col px-4 pb-3 pt-4"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
            style={{ backgroundColor: 'var(--color-truboard-secondary)' }}
          />
          <h1
            className="truncate text-sm font-bold tracking-tight"
            style={{ color: 'var(--color-truboard-primary)' }}
          >
            TruBoard Policies
          </h1>
        </div>
        <p className="mt-0.5 text-xs" style={{ color: 'var(--color-muted-fg)' }}>
          Internal Policy Assistant
        </p>
      </div>

      {/* Policy list */}
      <div className="min-h-0 flex-1 overflow-y-auto py-2">
        <PolicyList
          documents={documents}
          activeDocument={activeDocument}
          isLoading={isLoading}
          isError={isError}
          onSelect={handleSelect}
        />
      </div>

      {/* Sign out */}
      <div className="shrink-0 px-3 py-3" style={{ borderTop: '1px solid var(--color-border)' }}>
        <button
          type="button"
          id="logout-button"
          onClick={oAuthLogout}
          className="w-full rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors duration-150"
          style={{ color: 'var(--color-muted-fg)' }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-truboard-primary-200)'
            e.currentTarget.style.color = 'var(--color-foreground)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
            e.currentTarget.style.color = 'var(--color-muted-fg)'
          }}
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------------------
// Main three-panel layout
// ---------------------------------------------------------------------------
function MainLayout() {
  const { activeDocument } = useActiveDocument()
  const [targetPage, setTargetPage] = useState<number | null>(null)
  const [lastSwitchedDocName, setLastSwitchedDocName] = useState<string | null>(null)
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)
  const prevDocIdRef = useRef<string | null>(null)

  // Track document switches to show the toast.
  const handleDocumentChange = useCallback((doc: Policy) => {
    if (doc.id !== prevDocIdRef.current) {
      setLastSwitchedDocName(doc.policy_name)
      prevDocIdRef.current = doc.id
      setTargetPage(null)
    }
  }, [])

  return (
    <div className="grid h-full" style={{ gridTemplateColumns: '260px 1fr 400px' }}>
      {/* Panel 1: Sidebar */}
      <Sidebar onDocumentChange={handleDocumentChange} />

      {/* Panel 2: PDF Viewer */}
      <main className="h-full overflow-hidden">
        <PDFViewer
          activeDocument={activeDocument}
          targetPage={targetPage}
          downloadUrl={downloadUrl}
        />
      </main>

      {/* Panel 3: Chat */}
      <section
        className="flex h-full flex-col overflow-hidden"
        style={{ borderLeft: '1px solid var(--color-border)' }}
      >
        <ChatPanel
          activeDocument={activeDocument}
          onScrollToPage={(page) => setTargetPage(page)}
          lastSwitchedDocName={lastSwitchedDocName}
        />
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Admin layout (guarded — /admin)
// ---------------------------------------------------------------------------
function AdminLayout() {
  const { isAuthenticated } = useAuth()
  // if (!isAuthenticated) return <Navigate to="/login" replace />

  const { files, addFiles, uploadAll, removeFile, retryFile, clearAll, pendingCount } = useUpload()

  return (
    <div
      className="min-h-screen p-8"
      style={{ backgroundColor: 'var(--color-background)' }}
    >
      <div className="mx-auto max-w-2xl">
        <div className="mb-6">
          <h1 className="text-xl font-bold" style={{ color: 'var(--color-truboard-primary)' }}>
            Policy Upload
          </h1>
          <p className="mt-1 text-sm" style={{ color: 'var(--color-muted-fg)' }}>
            Upload new policy PDFs or replace existing versions.
          </p>
        </div>

        <UploadZone onFiles={addFiles} />

        {files.length > 0 && (
          <div className="mt-6 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium" style={{ color: 'var(--color-foreground)' }}>
                {files.length} file{files.length > 1 ? 's' : ''}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  id="clear-all-button"
                  onClick={clearAll}
                  className="text-xs"
                  style={{ color: 'var(--color-muted-fg)' }}
                >
                  Clear all
                </button>
                <button
                  type="button"
                  id="upload-all-button"
                  onClick={uploadAll}
                  disabled={pendingCount === 0}
                  className="rounded-lg px-4 py-1.5 text-sm font-semibold text-white transition-opacity"
                  style={{
                    backgroundColor: 'var(--color-truboard-primary)',
                    opacity: pendingCount === 0 ? 0.4 : 1,
                  }}
                >
                  Upload {pendingCount > 0 ? `(${pendingCount})` : ''}
                </button>
              </div>
            </div>

            {files.map((f) => (
              <FileRow
                key={f.id}
                item={f}
                onRemove={() => removeFile(f.id)}
                onRetry={() => retryFile(f.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Auth guard
// ---------------------------------------------------------------------------
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <Routes>
      <Route path="/callback" element={<LoginCallback />} />
      <Route path="/logout" element={<LogoutCallback />} />
      <Route path="/login" element={<OAuthPage />} />
      <Route path="/admin" element={<AdminLayout />} />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <MainLayout />
          </AuthGuard>
        }
      />
    </Routes>
  )
}
