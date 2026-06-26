import { useEffect, useRef } from 'react'
import { Loader } from 'lucide-react'
import { useAppDispatch } from '../store/hooks'
import { clearOAuthTokens } from '../store/authSlice'
import authconfig, { userManager } from './authconfig'

export default function LogoutCallback() {
  const dispatch = useAppDispatch()
  const processed = useRef(false)

  useEffect(() => {
    if (processed.current) return
    processed.current = true

    userManager
      .signoutRedirectCallback()
      .then(() => {
        dispatch(clearOAuthTokens())
        Object.keys(localStorage).forEach((key) => {
          if (key.startsWith('oidc')) {
            localStorage.removeItem(key)
          }
        })
        window.location.href = authconfig.redirect_uri
      })
      .catch((err) => console.error('Logout callback error:', err))
  }, [dispatch])

  return (
    <div className="flex h-screen flex-col items-center justify-center space-y-4">
      <Loader className="h-10 w-10 animate-spin text-gray-500" />
      <p className="text-4xl font-bold">Processing logout...</p>
    </div>
  )
}
