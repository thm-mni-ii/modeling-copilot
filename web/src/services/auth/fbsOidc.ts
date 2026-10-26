import { ref } from 'vue'
import { UserManager, WebStorageStateStore, type User } from 'oidc-client-ts'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'

export const standaloneSignInError = ref<string | null>(null)
export const standaloneSigningIn = ref(false)

const appUrl = new URL(import.meta.env.BASE_URL, window.location.origin)
export const fbsRedirectUri = new URL('oauth2/callback', appUrl).href
let manager: UserManager | undefined

// The rest of the application reads the token from useBearerToken only.
const keepToken = (user: User) => {
  const { bearerToken, persistToken } = useBearerToken()
  bearerToken.value = user.access_token
  persistToken()
}

// The renewal failed, so the session at the Feedbacksystem has ended: back to the sign-in page.
const endExpiredSession = async () => {
  useBearerToken().clearToken()
  await manager?.removeUser()
  standaloneSignInError.value = 'Your Feedbacksystem session has ended. Please sign in again.'
  const { default: router } = await import('@/router')
  await router.replace({ path: '/login', query: { returnTo: router.currentRoute.value.fullPath } })
}

const getManager = () => {
  const authority = import.meta.env.VITE_FBS_HOST_ORIGIN
  const clientId = import.meta.env.VITE_FBS_PROVIDER_ID
  if (!authority || !clientId) throw new Error('Feedbacksystem sign-in is not configured.')
  if (manager) return manager

  manager = new UserManager({
    authority,
    client_id: clientId,
    redirect_uri: fbsRedirectUri,
    // A minute before the token expires, a hidden frame fetches a new one on the same callback, as in the FBS web shell.
    silent_redirect_uri: fbsRedirectUri,
    response_type: 'code',
    response_mode: 'query',
    scope: 'openid profile email',
    disablePKCE: false,
    // Not in the hidden frame itself, which only lives for one renewal.
    automaticSilentRenew: window.self === window.top,
    monitorSession: false,
    loadUserInfo: false,
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    userStore: new WebStorageStateStore({ store: window.sessionStorage })
  })
  manager.events.addUserLoaded(keepToken)
  manager.events.addAccessTokenExpired(() => void endExpiredSession())
  return manager
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
  standaloneSignInError.value = null
  try {
    const user = await getManager().signinRedirectCallback(window.location.href)
    if (!user.access_token || user.expired) throw new Error('Missing or expired access token')
    keepToken(user)
    // The API validates the access-token signature, issuer and configured audience.
    if ((await authService.validateToken()).data !== true) throw new Error('Access token rejected')
    const state = user.state as { returnTo?: unknown } | undefined
    return safeReturnPath(state?.returnTo)
  } catch {
    useBearerToken().clearToken()
    await manager?.removeUser()
    standaloneSignInError.value = 'Feedbacksystem sign-in could not be completed. Please try again. If it still fails, check the registered callback URL, client type, allowed origins and API token settings.'
    return '/login'
  } finally {
    // Remove the authorization response from the URL.
    window.history.replaceState(window.history.state, '', appUrl.href)
  }
}

/** In the hidden frame of a renewal: hands the response to the page, which exchanges the code. */
export const completeFeedbacksystemRenewal = () => getManager().signinSilentCallback(window.location.href)

/** After a reload: picks up the session of this tab, so its token keeps being renewed. */
export const resumeFeedbacksystemSession = async () => {
  try {
    const user = await getManager().getUser()
    if (user && !user.expired) keepToken(user)
  } catch {
    // Not configured; signing in reports that.
  }
}

/** Ends the session in this tab, so no token is renewed after signing out. */
export const forgetFeedbacksystemSession = () => manager?.removeUser()
