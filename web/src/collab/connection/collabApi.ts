import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { NewWorkpiece } from './collabKitV1'

/** Address of collab-kit, which checks the same Feedbacksystem token as the API. */
export const collabUrl: string | undefined = import.meta.env.VITE_COLLAB_URL

/** What marks a room or group as one of the Copilot's. */
export const TOOL_SETTINGS = { tool: 'modeling-copilot' }

/** The top map of the doc, one cell per key; named as units, so a conflict names its cell. */
export const CELLS_MAP = 'cells'

/** A Copilot workpiece in a room: the cell format with its languages, and the cells as units. */
export const newWorkpiece = (roomId: string, name: string, languages: WorkspaceLanguageReference[]): NewWorkpiece => ({
  name,
  roomId,
  contract: { tool: 'modeling-copilot', format: 'copilot-cells', version: 1, languages },
  units: [{ path: [CELLS_MAP] }]
})

/** Short reason for the sync log and notifications. */
export const collabErrorMessage = (error: unknown) => {
  if (!collabUrl) return 'VITE_COLLAB_URL is not set'
  const { status, message } = error as { status?: number; message?: string }
  if (status === 401) return 'token rejected (expired?)'
  // collab-kit names the reason of every other refusal, such as "unknown workpiece".
  if (status !== undefined) return message || `request failed with HTTP ${status}`
  // A request the browser blocks for CORS looks the same to the page, it hides the reason.
  return `not reachable at ${collabUrl} or blocked by CORS`
}
