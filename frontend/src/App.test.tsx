import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'
import { store } from './store'

// App has its own BrowserRouter, so for testing we render individual route content.
// The MainLayout checks isAuthenticated — without a real OIDC provider, it shows OAuthPage.
describe('App shell', () => {
  it('renders the login callback route', () => {
    render(
      <Provider store={store}>
        <MemoryRouter initialEntries={['/callback']}>
          <App />
        </MemoryRouter>
      </Provider>,
    )
    expect(screen.getByText(/Processing login/)).toBeInTheDocument()
  })
})
