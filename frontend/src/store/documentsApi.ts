import { baseApi } from './baseApi'
import type { Policy, DocumentUrl } from '../types'

export const documentsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /** GET /api/documents — alphabetical list of active policies */
    listDocuments: build.query<Policy[], void>({
      query: () => '/documents',
      providesTags: ['Documents'],
    }),

    /** GET /api/documents/{id}/url — fresh 1-hour SAS URL */
    getDocumentUrl: build.query<DocumentUrl, string>({
      query: (id) => `/documents/${id}/url`,
      // No cache tag — always fetch fresh; component controls when to call.
    }),
  }),
  overrideExisting: false,
})

export const { useListDocumentsQuery, useLazyGetDocumentUrlQuery } = documentsApi
