import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
// Dev-mode auth: backend resolves the user from this header when AUTH_DEV_MODE=true.
// Replaced by a real MSAL bearer token in M10.
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
    prepareHeaders: (headers) => {
      // M10: set `Authorization: Bearer <msal token>` here instead.
      if (DEV_USER) headers.set('X-Dev-User', DEV_USER)
      return headers
    },
  }),
  tagTypes: ['Documents', 'Policies', 'Jobs'],
  endpoints: () => ({}),
})
