import { useEffect } from 'react'
import { Loader } from 'lucide-react'
import { useAppSelector } from '../store/hooks'
import { useAuth } from './useAuth'

export default function OAuthPage() {
  const { isAuthenticated, oAuthLogin, oAuthLogout } = useAuth()
  const userInfo = useAppSelector((state) => state.auth.userInfo)

  useEffect(() => {
    if (!isAuthenticated) {
      oAuthLogin()
    }
  }, [isAuthenticated, oAuthLogin])

  if (!isAuthenticated) {
    return (
      <div className="flex h-screen flex-col items-center justify-center space-y-4 bg-gray-50">
        <Loader className="h-10 w-10 animate-spin text-gray-500" />
        <p className="text-xl text-gray-600">Redirecting to login...</p>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100">
      <div className="rounded-lg bg-white p-8 shadow-xl">
        <div className="space-y-3 text-center">
          <h3 className="text-lg font-bold">
            Welcome, {userInfo?.first_name} {userInfo?.last_name}
          </h3>
          <p className="text-brand text-sm font-medium">{userInfo?.email}</p>
          <button
            type="button"
            onClick={oAuthLogout}
            className="bg-brand text-brand-fg rounded px-4 py-2 text-sm font-medium hover:opacity-90"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  )
}
