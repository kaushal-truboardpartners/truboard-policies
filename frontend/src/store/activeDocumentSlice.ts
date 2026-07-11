import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { Policy } from '../types'

interface ActiveDocumentState {
  document: Policy | null
}

const initialState: ActiveDocumentState = {
  document: null,
}

const activeDocumentSlice = createSlice({
  name: 'activeDocument',
  initialState,
  reducers: {
    setActiveDocument(state, action: PayloadAction<Policy>) {
      state.document = action.payload
    },
    clearActiveDocument(state) {
      state.document = null
    },
  },
})

export const { setActiveDocument, clearActiveDocument } = activeDocumentSlice.actions
export default activeDocumentSlice.reducer
