import { ref } from 'vue'
import { isAxiosError } from 'axios'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'
import { expiresAt } from '@/services/auth/fbsBridge'
import type { FbsTokens } from '@/services/api/types/auth'

// Signing in without the Feedbacksystem around the app. The browser only follows redirects to it,
// the API exchanges the code and renews the tokens there, so no request leaves for another origin.

export const standaloneSignInError = ref<string | null>(null)
export const standaloneSigningIn = ref(false)

const appUrl = new URL(import.meta.env.BASE_URL, window.location.origin)
export const fbsRedirectUri = new URL('oauth2/callback', appUrl).href

const REFRESH_TOKEN_KEY = 'refreshToken'
// State and PKCE verifier of a sign-in in progress.
const SIGN_IN_KEY = 'fbsSignIn'
const RENEW_BEFORE_MS = 60_000

let renewAt = 0
let renewTimer: ReturnType<typeof setTimeout> | undefined
let renewing: Promise<boolean> | null = null
let listening = false

const base64Url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
const randomString = () => base64Url(crypto.getRandomValues(new Uint8Array(32)))
const codeChallenge = async (verifier: string) => base64Url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))))

// Timers stall while the computer sleeps, so check again when the page comes back.
const onVisible = () => {
  if (document.visibilityState === 'visible' && renewAt && Date.now() >= renewAt) void renewOrSignOut()
}

const scheduleRenewal = (token: string) => {
  clearTimeout(renewTimer)
  renewAt = (expiresAt(token) ?? Date.now()) - RENEW_BEFORE_MS
  renewTimer = setTimeout(() => void renewOrSignOut(), Math.max(0, renewAt - Date.now()))
  if (!listening) {
    document.addEventListener('visibilitychange', onVisible)
    listening = true
  }
}

// The rest of the application reads the access token from useBearerToken only.
const keepTokens = ({ accessToken, refreshToken }: FbsTokens) => {
  const { bearerToken, persistToken } = useBearerToken()
  bearerToken.value = accessToken
  persistToken()
  // The Feedbacksystem issues refresh tokens to confidential clients only.
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
    scheduleRenewal(accessToken)
  }
}

const renew = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY)
  if (!refreshToken) return false
  try {
    keepTokens((await authService.refreshTokens(refreshToken)).data)
    return true
  } catch (error) {
    // Rejected: the session at the Feedbacksystem has ended. Otherwise the next navigation tries again.
    if (isAxiosError(error) && error.response?.status === 401) {
      useBearerToken().clearToken()
      forgetFeedbacksystemSession()
      standaloneSignInError.value = 'Your Feedbacksystem session has ended. Please sign in again.'
    }
    return false
  }
}

/** Renews the tokens through the API; concurrent calls share one request. */
export const renewFeedbacksystemToken = () =>
  (renewing ??= renew().finally(() => {
    renewing = null
  }))

// The session has ended for good: back to the sign-in page.
const renewOrSignOut = async () => {
  if ((await renewFeedbacksystemToken()) || localStorage.getItem(REFRESH_TOKEN_KEY)) return
  const { default: router } = await import('@/router')
  await router.replace({ path: '/login', query: { returnTo: router.currentRoute.value.fullPath } })
}

// Only return to a route within this application, never to an external URL.
export const safeReturnPath = (path: unknown): string => (typeof path === 'string' && path.startsWith('/') && !path.startsWith('//') && !path.includes('\\') && path.split(/[?#]/)[0] !== '/login' ? path : '/')

export const signInWithFeedbacksystem = async (returnTo: unknown = '/') => {
  if (standaloneSigningIn.value) return
  standaloneSigningIn.value = true
  standaloneSignInError.value = null
  try {
    const authority = import.meta.env.VITE_FBS_HOST_ORIGIN
    const clientId = import.meta.env.VITE_FBS_PROVIDER_ID
    if (!authority || !clientId) throw new Error('Feedbacksystem sign-in is not configured.')
    const state = randomString()
    const verifier = randomString()
    sessionStorage.setItem(SIGN_IN_KEY, JSON.stringify({ state, verifier, returnTo: safeReturnPath(returnTo) }))
    const url = new URL('/oauth2/authorize', authority)
    url.search = new URLSearchParams({
      response_type: 'code',
      client_id: clientId,
      redirect_uri: fbsRedirectUri,
      scope: 'openid profile email',
      state,
      code_challenge: await codeChallenge(verifier),
      code_challenge_method: 'S256'
    }).toString()
    window.location.assign(url.href)
  } catch {
    standaloneSignInError.value = 'Could not start Feedbacksystem sign-in. Check the connection and OIDC client configuration, then try again.'
    standaloneSigningIn.value = false
  }
}

export const isFeedbacksystemCallback = () => {
  const url = new URL(window.location.href)
  return url.pathname === new URL(fbsRedirectUri).pathname && (url.searchParams.has('code') || url.searchParams.has('error'))
}

/** Checks the saved state and lets the API exchange the code using PKCE. */
export const completeFeedbacksystemSignIn = async (): Promise<string> => {
  standaloneSignInError.value = null
  try {
    const saved = JSON.parse(sessionStorage.getItem(SIGN_IN_KEY) ?? '{}') as { state?: string; verifier?: string; returnTo?: unknown }
    const params = new URL(window.location.href).searchParams
    const code = params.get('code')
    if (!code || !saved.verifier || params.get('state') !== saved.state) throw new Error('Invalid sign-in response')
    keepTokens((await authService.exchangeCode(code, saved.verifier, fbsRedirectUri)).data)
    // The API validates the access-token signature, issuer and configured audience.
    if ((await authService.validateToken()).data !== true) throw new Error('Access token rejected')
    return safeReturnPath(saved.returnTo)
  } catch {
    useBearerToken().clearToken()
    forgetFeedbacksystemSession()
    standaloneSignInError.value = 'Feedbacksystem sign-in could not be completed. Please try again. If it still fails, check the registered callback URL, the client type and secret, and the API token settings.'
    return '/login'
  } finally {
    sessionStorage.removeItem(SIGN_IN_KEY)
    // Remove the authorization response from the URL.
    window.history.replaceState(window.history.state, '', appUrl.href)
  }
}

/** After a reload: keeps renewing the token of an earlier sign-in. */
export const resumeFeedbacksystemSession = () => {
  if (localStorage.getItem(REFRESH_TOKEN_KEY)) scheduleRenewal(useBearerToken().bearerToken.value)
}

/** Ends the session, so no token is renewed after signing out. */
export const forgetFeedbacksystemSession = () => {
  clearTimeout(renewTimer)
  renewAt = 0
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}
