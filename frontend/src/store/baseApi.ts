import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { RootState } from './index'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const DEV_USER = import.meta.env.VITE_DEV_USER ?? ''

/**
 * Single RTK Query API slice. All server data (documents, chat, admin) is defined here via
 * injectEndpoints in later milestones. SSE (ingestion progress) is handled outside RTK Query
 * with EventSource.
 */
export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}/api`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.accessToken
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      } else if (DEV_USER) {
        // Fallback for dev-mode when no OAuth token is available
        headers.set('X-Dev-User', DEV_USER)
      }
      return headers
    },
  }),
  tagTypes: ['Documents', 'Policies', 'Jobs'],
  endpoints: () => ({}),
})
