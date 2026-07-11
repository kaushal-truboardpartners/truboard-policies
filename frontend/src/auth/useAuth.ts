import { useCallback, useEffect, useState } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { clearOAuthTokens } from '../store/authSlice'
import { userManager } from './authconfig'

export function useAuth() {
  const dispatch = useAppDispatch()
  const accessToken = useAppSelector((state) => state.auth.accessToken)
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)
  const [isInitializing, setIsInitializing] = useState(!isAuthenticated)

  useEffect(() => {
    if (!isAuthenticated) {
      userManager
        .getUser()
        .then((user) => {
          // ReduxStorage.get will automatically dispatch setOAuthToken if user is found.
          if (!user) {
            // No user in storage.
          }
        })
        .catch((err) => {
          console.error('Failed OIDC user restore:', err)
        })
        .finally(() => {
          setIsInitializing(false)
        })
    } else {
      setIsInitializing(false)
    }
  }, [isAuthenticated])

  const oAuthLogin = useCallback(() => userManager.signinRedirect(), [])

  const oAuthLogout = useCallback(() => {
    userManager.signoutRedirect()
    dispatch(clearOAuthTokens())
  }, [dispatch])

  return {
    isAuthenticated,
    accessToken,
    isInitializing,
    oAuthLogin,
    oAuthLogout,
  }
}

