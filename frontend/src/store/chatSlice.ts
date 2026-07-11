import { createSlice, type PayloadAction } from '@reduxjs/toolkit'
import type { ChatMessage } from '../types'

interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean
  /** seconds remaining on rate-limit countdown; 0 = not rate-limited */
  rateLimitCountdown: number
}

const initialState: ChatState = {
  messages: [],
  isLoading: false,
  rateLimitCountdown: 0,
}

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    addMessage(state, action: PayloadAction<ChatMessage>) {
      state.messages.push(action.payload)
    },
    setLoading(state, action: PayloadAction<boolean>) {
      state.isLoading = action.payload
    },
    setRateLimitCountdown(state, action: PayloadAction<number>) {
      state.rateLimitCountdown = action.payload
    },
    clearMessages(state) {
      state.messages = []
    },
  },
})

export const { addMessage, setLoading, setRateLimitCountdown, clearMessages } = chatSlice.actions
export default chatSlice.reducer
