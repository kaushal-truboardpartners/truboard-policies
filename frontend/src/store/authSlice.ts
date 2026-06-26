import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

interface OAuthUserInfo {
  first_name?: string
  last_name?: string
  email?: string
  [key: string]: unknown
}

interface AuthState {
  accessToken: string | null
  idToken: string | null
  refreshToken: string | null
  userInfo: OAuthUserInfo | null
  isAuthenticated: boolean
}

const initialState: AuthState = {
  accessToken: null,
  idToken: null,
  refreshToken: null,
  userInfo: null,
  isAuthenticated: false,
}

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    setOAuthToken(
      state,
      action: PayloadAction<{
        accessToken: string
        idToken?: string | null
        refreshToken?: string | null
        userInfo?: OAuthUserInfo | null
      }>,
    ) {
      state.accessToken = action.payload.accessToken
      state.idToken = action.payload.idToken ?? null
      state.refreshToken = action.payload.refreshToken ?? null
      state.userInfo = action.payload.userInfo ?? null
      state.isAuthenticated = true
    },
    clearOAuthTokens(state) {
      state.accessToken = null
      state.idToken = null
      state.refreshToken = null
      state.userInfo = null
      state.isAuthenticated = false
    },
  },
})

export const { setOAuthToken, clearOAuthTokens } = authSlice.actions
export default authSlice.reducer
