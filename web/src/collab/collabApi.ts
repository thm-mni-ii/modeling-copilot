import axios from 'axios'
import { useBearerToken } from '@/composables/useBearerToken'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'

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

/** A set of people; what it stands for is the tool's, kept in settings. */
export interface CollabGroup {
  _id: string
  name: string
  settings: Record<string, unknown>
  members: string[]
  createdAt: string
  createdBy: string
}

/** A place a grant holds at; without one it holds everywhere. */
export interface CollabScope {
  kind: string
  id: string
}

/** What one group may do at one place. */
export interface CollabGrant {
  _id: string
  groupId: string
  scope?: CollabScope
  rights: string[]
}

/** What marks a room, group or workpiece as one of the Copilot's. */
const TOOL_SETTINGS = { tool: 'modeling-copilot' }
/** What every own model of the workpiece is created with: the cell format and its languages. */
const workpieceContract = (languages: WorkspaceLanguageReference[]) => ({ tool: 'modeling-copilot', format: 'copilot-cells', version: 1, languages })

export const getWorkpiece = (id: string) => collabClient.get<CollabWorkpiece>(`/workpieces/${encodeURIComponent(id)}`)

/** Every room the token may see; whoever sees everywhere gets them all. */
export const listRooms = () => collabClient.get<CollabRoom[]>('/me/rooms')

export const getRoom = (id: string) => collabClient.get<CollabRoom>(`/rooms/${encodeURIComponent(id)}`)

/** Takes manage everywhere, as a room lies in nothing. */
export const createRoom = (name: string) => collabClient.post<CollabRoom>('/rooms', { name, settings: TOOL_SETTINGS })

/** A new workpiece right in the room; takes manage at the room. */
export const createWorkpieceInRoom = (roomId: string, name: string, languages: WorkspaceLanguageReference[]) => collabClient.post<CollabWorkpiece>('/workpieces', { name, roomId, contract: workpieceContract(languages) })

/** Puts an existing workpiece into the room; takes manage at the room and at the workpiece. */
export const addToRoom = (roomId: string, workpieceId: string) => collabClient.post<CollabRoom>(`/rooms/${encodeURIComponent(roomId)}/references`, { kind: 'workpiece', id: workpieceId })

/** Takes the workpiece out of the room; the workpiece itself stays. */
export const removeFromRoom = (roomId: string, workpieceId: string) => collabClient.delete<CollabRoom>(`/rooms/${encodeURIComponent(roomId)}/references`, { params: { kind: 'workpiece', id: workpieceId } })

export const getGroup = (id: string) => collabClient.get<CollabGroup>(`/groups/${encodeURIComponent(id)}`)

/** The groups the token is a member of; an admin is often in none. */
export const listMyGroups = () => collabClient.get<CollabGroup[]>('/me/groups')

/** Takes manage everywhere; a new group holds no grant yet. */
export const createGroup = (name: string) => collabClient.post<CollabGroup>('/groups', { name, settings: TOOL_SETTINGS })

/** The actor key is the Feedbacksystem user ID. */
export const addMember = (groupId: string, actorId: string) => collabClient.post<CollabGroup>(`/groups/${encodeURIComponent(groupId)}/members`, { actorId })

export const removeMember = (groupId: string, actorId: string) => collabClient.delete<CollabGroup>(`/groups/${encodeURIComponent(groupId)}/members/${encodeURIComponent(actorId)}`)

/** Every grant at a place; takes manage there. */
export const listGrantsAt = (scope: CollabScope) => collabClient.get<CollabGrant[]>('/grants', { params: { scopeKind: scope.kind, scopeId: scope.id } })

/** Every grant of a group; takes manage at the group. */
export const listGrantsOf = (groupId: string) => collabClient.get<CollabGrant[]>('/grants', { params: { groupId } })

/** Replaces what the group may do at the place, or everywhere without one; open connections are asked again. */
export const setGrant = (groupId: string, scope: CollabScope | undefined, rights: string[]) => collabClient.put<CollabGrant>('/grants', { groupId, scope, rights })

export const removeGrant = (groupId: string, scope: CollabScope | undefined) => collabClient.delete<{ removed: boolean }>('/grants', { params: { groupId, scopeKind: scope?.kind, scopeId: scope?.id } })

// collab-kit has no route for these yet; the UI keeps their controls disabled until it has.
const missingRoute = (what: string): Promise<never> => Promise.reject(new Error(`collab-kit cannot ${what} yet.`))

export const renameRoom = (roomId: string, name: string) => missingRoute(`rename room ${roomId} to "${name}"`)

export const deleteRoom = (roomId: string) => missingRoute(`delete room ${roomId}`)

export const listWorkpieces = () => missingRoute('list workpieces')

export const listGroups = () => missingRoute('list groups')

export const renameGroup = (groupId: string, name: string) => missingRoute(`rename group ${groupId} to "${name}"`)

export const deleteGroup = (groupId: string) => missingRoute(`delete group ${groupId}`)

/** Names to the actor keys; collab-kit keeps them from the tokens but gives none out. */
export const listActorNames = (actorIds: string[]) => missingRoute(`name the actors ${actorIds.join(', ')}`)

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
  // A request the browser blocks for CORS looks the same to the page, it hides the reason.
  return `not reachable at ${collabUrl} or blocked by CORS`
}
