import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { describe, expect, it } from 'vitest'
import App from './App'
import { store } from './store'

describe('App shell', () => {
  it('renders the three panels', () => {
    render(
      <Provider store={store}>
        <App />
      </Provider>,
    )
    expect(screen.getByText('TruBoard Policies')).toBeInTheDocument()
    expect(screen.getByText(/PDF viewer/)).toBeInTheDocument()
    expect(screen.getByText(/Chatbot/)).toBeInTheDocument()
  })
})
