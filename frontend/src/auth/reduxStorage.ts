/**
 * Custom WebStorageStateStore that persists OIDC tokens in Redux instead of localStorage.
 * This keeps auth state centralized and accessible to RTK Query's prepareHeaders.
 */
import { WebStorageStateStore } from 'oidc-client-ts'
import { clearOAuthTokens, setOAuthToken } from '../store/authSlice'
import { store } from '../store'

class ReduxStorage extends WebStorageStateStore {
  constructor() {
    super()
  }

  async set(_key: string, value: string): Promise<void> {
    const user = JSON.parse(value)
    store.dispatch(
      setOAuthToken({
        accessToken: user.access_token,
        idToken: user.id_token,
        refreshToken: user.refresh_token,
        userInfo: user?.profile,
      }),
    )
  }

  async get(_key: string): Promise<string | null> {
    const state = store.getState()
    const accessToken = state.auth.accessToken
    const refreshToken = state.auth.refreshToken

    if (accessToken && refreshToken) {
      return JSON.stringify({
        access_token: accessToken,
        refresh_token: refreshToken,
      })
    }
    return null
  }

  async remove(_key: string): Promise<string | null> {
    store.dispatch(clearOAuthTokens())
    return null
  }

  async getAllKeys(): Promise<string[]> {
    return []
  }
}

export default ReduxStorage
