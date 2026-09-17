import httpClient from '@/services/api/httpClient'

const STORAGE_KEY = 'serverTimeOffset'

const readServerTimeOffset = () => {
  if (typeof localStorage === 'undefined') return 0
  try {
    const stored = Number(localStorage.getItem(STORAGE_KEY))
    return Number.isFinite(stored) ? stored : 0
  } catch {
    return 0
  }
}

const persistServerTimeOffset = (offset: number) => {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, String(offset))
  } catch {
    // Time synchronization remains usable in memory when storage is unavailable.
  }
}

let serverTimeOffset = readServerTimeOffset()

export const serverNow = () => Date.now() + serverTimeOffset

export const synchronizeServerTime = async () => {
  const startedAt = Date.now()
  const response = await httpClient.get<{ serverTime: string }>('/v1/time')
  const receivedAt = Date.now()
  const nextOffset = new Date(response.data.serverTime).getTime() - (startedAt + receivedAt) / 2
  if (!Number.isFinite(nextOffset)) throw new Error('The server returned an invalid time.')
  serverTimeOffset = nextOffset
  persistServerTimeOffset(serverTimeOffset)
}
