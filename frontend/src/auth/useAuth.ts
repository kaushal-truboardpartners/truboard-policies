import { useCallback } from 'react'
import { useAppDispatch, useAppSelector } from '../store/hooks'
import { clearOAuthTokens } from '../store/authSlice'
import { userManager } from './authconfig'

export function useAuth() {
  const dispatch = useAppDispatch()
  const accessToken = useAppSelector((state) => state.auth.accessToken)
  const isAuthenticated = useAppSelector((state) => state.auth.isAuthenticated)

  const oAuthLogin = useCallback(() => userManager.signinRedirect(), [])

  const oAuthLogout = useCallback(() => {
    userManager.signoutRedirect()
    dispatch(clearOAuthTokens())
  }, [dispatch])

  return {
    isAuthenticated,
    accessToken,
    oAuthLogin,
    oAuthLogout,
  }
}
