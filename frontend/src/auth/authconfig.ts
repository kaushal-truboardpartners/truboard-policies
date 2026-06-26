import { UserManager, type UserManagerSettings } from 'oidc-client-ts'
import ReduxStorage from './reduxStorage'

let reduxStorage: ReduxStorage | null = null
const getReduxStorage = () => {
  if (!reduxStorage) {
    reduxStorage = new ReduxStorage()
  }
  return reduxStorage
}

const authority = import.meta.env.VITE_OAUTH_AUTHORITY ?? ''
const domainUrl = import.meta.env.VITE_OAUTH_DOMAIN_URL ?? 'http://localhost:5173'

const oidcConfig: UserManagerSettings = {
  authority,
  client_id: import.meta.env.VITE_OAUTH_CLIENT_ID ?? '',
  redirect_uri: `${domainUrl}/callback`,
  client_secret: import.meta.env.VITE_OAUTH_CLIENT_SECRET ?? '',
  client_authentication: 'client_secret_basic',
  response_type: 'code',
  scope: 'read write introspection openid profile',
  post_logout_redirect_uri: `${domainUrl}/logout`,
  metadata: {
    authorization_endpoint: `${authority}/o/authorize/`,
    token_endpoint: `${authority}/o/token/`,
    userinfo_endpoint: `${authority}/o/userinfo/`,
    end_session_endpoint: `${authority}/o/logout/`,
  },
  loadUserInfo: true,
}

Object.assign(oidcConfig, { userStore: getReduxStorage() })

export const userManager = new UserManager(oidcConfig)
export default oidcConfig
