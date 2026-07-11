import { Routes, Route, Navigate } from 'react-router-dom'
import LoginCallback from './auth/LoginCallback'
import LogoutCallback from './auth/LogoutCallback'
import OAuthPage from './auth/OAuthPage'
import { useAuth } from './auth/useAuth'
import { useActiveDocument } from './hooks/useActiveDocument'
import { PolicyList } from './components/Sidebar/PolicyList'
import { PDFViewer } from './components/Viewer/PDFViewer'

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar() {
  const { documents, activeDocument, isLoading, isError, setActive } = useActiveDocument()
  const { oAuthLogout } = useAuth()

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
          {/* TruBoard wordmark dot */}
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
        <p
          className="mt-0.5 text-xs"
          style={{ color: 'var(--color-muted-fg)' }}
        >
          Internal Policy Assistant
        </p>
      </div>

      {/* Policy list — scrollable */}
      <div className="min-h-0 flex-1 overflow-y-auto py-2">
        <PolicyList
          documents={documents}
          activeDocument={activeDocument}
          isLoading={isLoading}
          isError={isError}
          onSelect={setActive}
        />
      </div>

      {/* Logout */}
      <div
        className="shrink-0 px-3 py-3"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
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

  return (
    <div
      className="grid h-full"
      style={{ gridTemplateColumns: '260px 1fr 400px' }}
    >
      {/* Panel 1: Sidebar */}
      <Sidebar />

      {/* Panel 2: PDF Viewer */}
      <main className="h-full overflow-hidden">
        <PDFViewer
          activeDocument={activeDocument}
          targetPage={null}
        />
      </main>

      {/* Panel 3: Chatbot placeholder (M8) */}
      <section
        className="flex h-full flex-col overflow-hidden"
        style={{ borderLeft: '1px solid var(--color-border)' }}
      >
        <div
          className="shrink-0 px-4 py-3 text-sm font-semibold"
          style={{
            borderBottom: '1px solid var(--color-border)',
            color: 'var(--color-truboard-primary)',
          }}
        >
          Policy Assistant
        </div>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm" style={{ color: 'var(--color-muted-fg)' }}>
            Chat panel coming in M8
          </p>
        </div>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Guarded shell — redirects to /login if not authenticated
// ---------------------------------------------------------------------------
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/callback" element={<LoginCallback />} />
      <Route path="/logout" element={<LogoutCallback />} />
      <Route path="/login" element={<OAuthPage />} />
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
