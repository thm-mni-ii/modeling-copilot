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

/** A thing a room bundles; for us the workpieces in it. */
export interface CollabReference {
  kind: string
  id: string
}

/** A room as collab-kit keeps it; settings are the tool's switches and never read by the service. */
export interface CollabRoom {
  _id: string
  name: string
  settings: Record<string, unknown>
  references: CollabReference[]
  createdAt: string
  createdBy: string
}

/** The workpiece as a thing: its name and what the tool registered, not its content. */
export interface CollabWorkpiece {
  _id: string
  name: string
  contract: Record<string, unknown>
}

/** What marks a room or workpiece as one of the Copilot's. */
const ROOM_SETTINGS = { tool: 'modeling-copilot' }
const WORKPIECE_CONTRACT = { tool: 'modeling-copilot', format: 'copilot-cells', version: 1 }

export const getWorkpiece = (id: string) => collabClient.get<CollabWorkpiece>(`/workpieces/${encodeURIComponent(id)}`)

/** Every room the token may see; whoever sees everywhere gets them all. */
export const listRooms = () => collabClient.get<CollabRoom[]>('/me/rooms')

export const getRoom = (id: string) => collabClient.get<CollabRoom>(`/rooms/${encodeURIComponent(id)}`)

/** Takes manage everywhere, as a room lies in nothing. */
export const createRoom = (name: string) => collabClient.post<CollabRoom>('/rooms', { name, settings: ROOM_SETTINGS })

/** A new workpiece right in the room; takes manage at the room. */
export const createWorkpieceInRoom = (roomId: string, name: string) => collabClient.post<CollabWorkpiece>('/workpieces', { name, roomId, contract: WORKPIECE_CONTRACT })

/** Puts an existing workpiece into the room; takes manage at the room and at the workpiece. */
export const addToRoom = (roomId: string, workpieceId: string) => collabClient.post<CollabRoom>(`/rooms/${encodeURIComponent(roomId)}/references`, { kind: 'workpiece', id: workpieceId })

/** Takes the workpiece out of the room; the workpiece itself stays. */
export const removeFromRoom = (roomId: string, workpieceId: string) => collabClient.delete<CollabRoom>(`/rooms/${encodeURIComponent(roomId)}/references`, { params: { kind: 'workpiece', id: workpieceId } })

// collab-kit has no route for these yet; the UI keeps their controls disabled until it has.
const missingRoute = (what: string): Promise<never> => Promise.reject(new Error(`collab-kit cannot ${what} yet.`))

export const renameRoom = (roomId: string, name: string) => missingRoute(`rename room ${roomId} to "${name}"`)

export const deleteRoom = (roomId: string) => missingRoute(`delete room ${roomId}`)

export const listWorkpieces = () => missingRoute('list workpieces')

/** Rights the current token holds, everywhere or at one thing of collab-kit. */
export const getRights = (target?: { kind: string; id: string }) => collabClient.get<string[]>('/me/rights', { params: target })

/** Short reason for the sync log and notifications. */
export const collabErrorMessage = (error: unknown) => {
  if (!collabUrl) return 'VITE_COLLAB_URL is not set'
  const response = (error as { response?: { status?: number; data?: { error?: unknown } } }).response
  const status = response?.status
  if (status === 401) return 'token rejected (expired?)'
  // collab-kit names the reason of every other refusal, such as "unknown workpiece".
  if (typeof response?.data?.error === 'string') return response.data.error
  if (status === 404) return 'not found'
  if (status !== undefined) return `request failed with HTTP ${status}`
  return `not reachable at ${collabUrl}`
}
