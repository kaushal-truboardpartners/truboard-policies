import { Routes, Route } from 'react-router-dom'
import LoginCallback from './auth/LoginCallback'
import LogoutCallback from './auth/LogoutCallback'
import OAuthPage from './auth/OAuthPage'
import { useAuth } from './auth/useAuth'

function MainLayout() {
  const { isAuthenticated, oAuthLogout } = useAuth()

  if (!isAuthenticated) {
    return <OAuthPage />
  }

  return (
    <div className="grid h-full grid-cols-[260px_1fr_400px] divide-x divide-gray-200">
      <aside className="flex flex-col overflow-y-auto bg-gray-50 p-4">
        <h1 className="text-brand text-lg font-semibold">TruBoard Policies</h1>
        <p className="mt-2 text-sm text-gray-500">Sidebar — policy list (M7)</p>
        <button
          type="button"
          onClick={oAuthLogout}
          className="mt-auto rounded bg-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-300"
        >
          Logout
        </button>
      </aside>

      <main className="overflow-y-auto p-4">
        <p className="text-sm text-gray-500">PDF viewer (M7)</p>
      </main>

      <section className="flex flex-col bg-gray-50 p-4">
        <p className="text-sm text-gray-500">Chatbot (M8)</p>
      </section>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/callback" element={<LoginCallback />} />
      <Route path="/logout" element={<LogoutCallback />} />
      <Route path="/login" element={<OAuthPage />} />
      <Route path="/*" element={<MainLayout />} />
    </Routes>
  )
}
