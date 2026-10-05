import axios from 'axios'
import { useBearerToken } from '@/composables/useBearerToken'

/** Address of collab-kit, which checks the same Feedbacksystem token as the API. */
export const collabUrl: string | undefined = import.meta.env.VITE_COLLAB_URL

const collabClient = axios.create({ baseURL: collabUrl })

collabClient.interceptors.request.use((config) => {
  if (!collabUrl) throw new Error('VITE_COLLAB_URL is not set.')
  const { bearerToken } = useBearerToken()
  if (bearerToken.value) {
    config.headers.Authorization = `Bearer ${bearerToken.value}`
  }
  return config
})

/** Rights the current token holds, everywhere or at one thing of collab-kit. */
export const getRights = (target?: { kind: string; id: string }) => collabClient.get<string[]>('/me/rights', { params: target })

/** Short reason for the sync log. */
export const collabErrorMessage = (error: unknown) => {
  if (!collabUrl) return 'VITE_COLLAB_URL is not set'
  const status = (error as { response?: { status?: number } }).response?.status
  if (status === 401) return 'token rejected (expired?)'
  if (status !== undefined) return `request failed with HTTP ${status}`
  return `not reachable at ${collabUrl}`
}
