import { ref } from 'vue'
import { UserManager, WebStorageStateStore } from 'oidc-client-ts'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'

export const standaloneSignInError = ref<string | null>(null)
export const standaloneSigningIn = ref(false)

const appUrl = new URL(import.meta.env.BASE_URL, window.location.origin)
export const fbsRedirectUri = new URL('oauth2/callback', appUrl).href
let manager: UserManager | undefined

const getManager = () => {
  const authority = import.meta.env.VITE_FBS_HOST_ORIGIN
  const clientId = import.meta.env.VITE_FBS_PROVIDER_ID
  if (!authority || !clientId) throw new Error('Feedbacksystem sign-in is not configured.')

  return (manager ??= new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: fbsRedirectUri,
    response_type: 'code',
    response_mode: 'query',
    scope: 'openid profile email',
    disablePKCE: false,
    automaticSilentRenew: false,
    monitorSession: false,
    loadUserInfo: false,
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    userStore: new WebStorageStateStore({ store: window.sessionStorage })
  }))
}

// Only return to a route within this application, never to an external URL.
export const safeReturnPath = (path: unknown): string => (typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') && path.split(/[?#]/)[0] !== '/login' ? path : '/')

export const signInWithFeedbacksystem = async (returnTo: unknown = '/') => {
  if (standaloneSigningIn.value) return
  standaloneSigningIn.value = true
  standaloneSignInError.value = null
  try {
    const client = getManager()
    await client.clearStaleState()
    await client.signinRedirect({ state: { returnTo: safeReturnPath(returnTo) } })
  } catch {
    standaloneSignInError.value = 'Could not start Feedbacksystem sign-in. Check the connection and OIDC client configuration, then try again.'
  } finally {
    standaloneSigningIn.value = false
  }
}

export const isFeedbacksystemCallback = () => {
  const url = new URL(window.location.href)
  return url.pathname === new URL(fbsRedirectUri).pathname && (url.searchParams.has('code') || url.searchParams.has('error'))
}

/** The OIDC client verifies the saved state and exchanges the code using PKCE. */
export const completeFeedbacksystemSignIn = async (): Promise<string> => {
  const { bearerToken, persistToken, clearToken } = useBearerToken()
  standaloneSignInError.value = null
  try {
    const user = await getManager().signinRedirectCallback(window.location.href)
    if (!user.access_token || user.expired) throw new Error('Missing or expired access token')
    bearerToken.value = user.access_token
    persistToken()
    // The API validates the access-token signature, issuer and configured audience.
    if ((await authService.validateToken()).data !== true) throw new Error('Access token rejected')
    const state = user.state as { returnTo?: unknown } | undefined
    return safeReturnPath(state?.returnTo)
  } catch {
    clearToken()
    standaloneSignInError.value = 'Feedbacksystem sign-in could not be completed. Please try again. If it still fails, check the registered callback URL, client type, allowed origins and API token settings.'
    return '/login'
  } finally {
    // Keep one token source and remove the authorization response from the URL.
    window.history.replaceState(window.history.state, '', appUrl.href)
    await manager?.removeUser()
  }
}
