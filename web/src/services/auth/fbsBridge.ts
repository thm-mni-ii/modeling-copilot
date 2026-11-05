import { ref } from 'vue'
import { useBearerToken } from '@/composables/useBearerToken'

// The only place that talks to the Feedbacksystem when the Copilot runs in its iframe.
// Everything else just reads the token from useBearerToken.

// Set per build mode in .env.development and .env.production.
const hostOrigin: string | undefined = import.meta.env.VITE_FBS_HOST_ORIGIN
const providerId: string | undefined = import.meta.env.VITE_FBS_PROVIDER_ID

const RENEW_BEFORE_MS = 60_000
const TOKEN_TIMEOUT_MS = 10_000
// Lower bound between two renewals, in case the host keeps sending a token about to expire.
const MIN_RENEW_DELAY_MS = 10_000

export const isEmbedded = window.self !== window.top
export const fbsConnectionError = ref<string | null>(null)
export const fbsAuthenticated = ref(false)
export const fbsConnecting = ref(false)
export const fbsTargetPath = ref('/')

// Theme and locale of the Feedbacksystem, not used by the Copilot yet.
export const fbsTheme = ref<string | null>(null)
export const fbsLocale = ref<string | null>(null)

let starting: Promise<string | null> | null = null
let listening = false
let connected = false
let pending: Promise<string | null> | null = null
const waiting = new Set<(token: string | null) => void>()
let renewAt = 0
let renewTimer: ReturnType<typeof setTimeout> | undefined

const post = (type: string, payload: object = {}) => {
  if (hostOrigin) window.parent.postMessage({ source: 'FBS_PROVIDER', type, payload }, hostOrigin)
}

// Taken from the token itself, the expiresIn of the host is not always right.
export const expiresAt = (token: string) => {
  try {
    const { exp } = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof exp === 'number' ? exp * 1000 : null
  } catch {
    return null
  }
}

const nextToken = () =>
  new Promise<string | null>((resolve) => {
    const finish = (token: string | null) => {
      clearTimeout(timer)
      waiting.delete(finish)
      resolve(token)
    }
    const timer = setTimeout(() => finish(null), TOKEN_TIMEOUT_MS)
    waiting.add(finish)
  })

const receiveToken = (token: string) => {
  const { bearerToken, persistToken } = useBearerToken()
  bearerToken.value = token
  // httpClient reads the token from localStorage.
  persistToken()
  connected = true
  waiting.forEach((resolve) => resolve(token))

  clearTimeout(renewTimer)
  const exp = expiresAt(token)
  if (!exp) return
  renewAt = Math.max(Date.now() + MIN_RENEW_DELAY_MS, exp - RENEW_BEFORE_MS)
  renewTimer = setTimeout(requestFbsToken, renewAt - Date.now())
}

const onMessage = (event: MessageEvent) => {
  if (event.source !== window.parent || event.origin !== hostOrigin) return
  if (!event.data || typeof event.data !== 'object') return
  // Depending on the host's version the fields come flat or in payload.
  const data = { ...event.data, ...event.data.payload }
  switch (data.type) {
    case 'FBS_HANDSHAKE_ACK':
      fbsTheme.value = data.theme ?? null
      fbsLocale.value = data.locale ?? null
      requestFbsToken()
      break
    case 'FBS_AUTH_TOKEN_RESPONSE':
      if (typeof data.accessToken === 'string' && data.accessToken) receiveToken(data.accessToken)
      break
    case 'FBS_THEME_CHANGED':
      fbsTheme.value = data.theme ?? null
      break
    case 'FBS_LOCALE_CHANGED':
      fbsLocale.value = data.locale ?? null
      break
  }
}

// Timers stall while the computer sleeps, so check again when the page comes back.
const onVisible = () => {
  if (document.visibilityState === 'visible' && renewAt && Date.now() >= renewAt) requestFbsToken()
}

const start = async () => {
  fbsConnectionError.value = null
  if (!hostOrigin) {
    fbsConnectionError.value = 'The Feedbacksystem address is not configured.'
    return null
  }
  if (!listening) {
    window.addEventListener('message', onMessage)
    document.addEventListener('visibilitychange', onVisible)
    listening = true
  }
  fbsConnecting.value = true
  const first = nextToken()
  const handshake = () => post('FBS_INIT_HANDSHAKE', { providerId, version: '1.0.0' })
  const retry = setInterval(handshake, 2000)
  try {
    handshake()
    const token = await first
    if (!token) fbsConnectionError.value = `No sign-in token was received from the Feedbacksystem. Open the application through ${hostOrigin}.`
    return token
  } finally {
    clearInterval(retry)
    fbsConnecting.value = false
  }
}

/** Shares concurrent attempts, but permits a new handshake after failure. */
export const startFbsBridge = (): Promise<string | null> => {
  const token = useBearerToken().bearerToken.value
  if (connected && token && !fbsConnectionError.value) return Promise.resolve(token)
  return (starting ??= start().finally(() => {
    starting = null
  }))
}

/** Asks the host for a fresh token; resolves with it, or with null if the host does not answer. */
export const requestFbsToken = () => {
  if (!hostOrigin) return Promise.resolve(null)
  if (!pending) {
    pending = nextToken().finally(() => {
      pending = null
    })
    post('FBS_REQUEST_AUTH_TOKEN')
  }
  return pending
}
