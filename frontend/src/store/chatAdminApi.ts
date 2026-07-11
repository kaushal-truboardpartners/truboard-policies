import { baseApi } from './baseApi'
import type { ChatResponse } from '../types'

interface ChatRequest {
  query: string
  active_document_id: string
}

interface AdminPolicy {
  id: string
  policy_name: string
  version: number
  is_deleted: boolean
  created_at: string
}

interface UploadResponse {
  job_id: string
  document_id: string
  status: string
}

interface ReplaceResponse {
  old_document_id: string
  new_document_id: string
  new_job_id: string
  status: string
}

export const chatApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** POST /api/chat/message */
    sendMessage: build.mutation<ChatResponse, ChatRequest>({
      query: (body) => ({
        url: '/chat/message',
        method: 'POST',
        body,
      }),
    }),

    /** DELETE /api/chat/session */
    clearSession: build.mutation<void, void>({
      query: () => ({ url: '/chat/session', method: 'DELETE' }),
    }),
  }),
  overrideExisting: false,
})

export const adminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** GET /api/admin/policies */
    listAdminPolicies: build.query<AdminPolicy[], void>({
      query: () => '/admin/policies',
      providesTags: ['Policies'],
    }),

    /** POST /api/admin/upload-and-ingest (multipart) */
    uploadPolicy: build.mutation<UploadResponse, FormData>({
      query: (body) => ({
        url: '/admin/upload-and-ingest',
        method: 'POST',
        body,
        // Don't set Content-Type — browser sets multipart boundary automatically.
        formData: true,
      }),
      invalidatesTags: ['Policies', 'Documents'],
    }),

    /** POST /api/admin/policies/{id}/replace */
    replacePolicy: build.mutation<ReplaceResponse, string>({
      query: (id) => ({
        url: `/admin/policies/${id}/replace`,
        method: 'POST',
      }),
      invalidatesTags: ['Policies', 'Documents'],
    }),
  }),
  overrideExisting: false,
})

export const { useSendMessageMutation, useClearSessionMutation } = chatApi
export const {
  useListAdminPoliciesQuery,
  useUploadPolicyMutation,
  useReplacePolicyMutation,
} = adminApi
