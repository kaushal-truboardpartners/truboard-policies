import { clearOAuthTokens, setOAuthToken } from '../store/authSlice'
import { store } from '../store'

class ReduxStorage {
  async set(key: string, value: string): Promise<void> {
    sessionStorage.setItem(key, value)
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

  async get(key: string): Promise<string | null> {
    const value = sessionStorage.getItem(key)
    if (value) {
      const state = store.getState()
      if (!state.auth.accessToken) {
        try {
          const user = JSON.parse(value)
          store.dispatch(
            setOAuthToken({
              accessToken: user.access_token,
              idToken: user.id_token,
              refreshToken: user.refresh_token,
              userInfo: user?.profile,
            }),
          )
        } catch (e) {
          console.error('Failed to parse cached user token from sessionStorage:', e)
        }
      }
      return value
    }
    return null
  }

  async remove(key: string): Promise<string | null> {
    sessionStorage.removeItem(key)
    store.dispatch(clearOAuthTokens())
    return null
  }

  async getAllKeys(): Promise<string[]> {
    const keys: string[] = []
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i)
      if (key) keys.push(key)
    }
    return keys
  }
}

export default ReduxStorage
