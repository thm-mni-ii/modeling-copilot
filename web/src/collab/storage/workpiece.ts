import type { JsonObject } from '@/services/api/types/common'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { CollabKitApi, NewWorkpiece, Session, UpdateSummary, Workpiece } from '@/collab/kit/collabKitV1'
import type { HistoryMode } from '@/collab/converters/model/modelHistory'
import { collabSettings } from '@/collab/settings/collabSettings'

/** The top map of the doc, one cell per key; named as units, so a conflict names its cell. */
export const CELLS_MAP = 'cells'

/** The UML class diagram the Copilot seeds with fixed IDs; the default language of a shared model. */
export const UML_CLASS_DIAGRAM: WorkspaceLanguageReference = {
  languageId: 'a7fb2523-f7a0-4d23-b476-72882454b9e8',
  versionId: '51cd9919-36b9-42d9-861d-8c619a2ac6d5',
  source: 'required'
}

/** A Copilot workpiece in a room: the cell format with its languages, and the cells as units. `history` tells how much of the private versions it was given. */
export const newWorkpiece = (roomId: string, name: string, languages: WorkspaceLanguageReference[], history: HistoryMode = 'none'): NewWorkpiece => ({
  name,
  roomId,
  contract: { tool: 'modeling-copilot', format: 'copilot-cells', version: 1, languages, history },
  units: [{ path: [CELLS_MAP] }]
})

/** What the host's own model needs to show the whole history: the private model it comes from, and where the history of the room starts, which the private one does not have. */
export interface HostLink {
  modelId: string
  /** The newest checkpoint of the workpiece when sharing began; null if there was none. */
  checkpoint: string | null
  /** The newest change of the task workpiece then; null if there was none. */
  taskUpdate: string | null
}

/** Where an own model keeps the workpiece it shares; the other preferences stay as they are. */
interface CollabLink {
  workpieceId: string
  roomId: string
  host?: HostLink
}

export const linkOf = (preferences: JsonObject | undefined): CollabLink | null => {
  const link = preferences?.collab as Partial<CollabLink> | undefined
  if (typeof link?.workpieceId !== 'string' || typeof link.roomId !== 'string') return null
  const host = link.host
  return {
    workpieceId: link.workpieceId,
    roomId: link.roomId,
    ...(typeof host?.modelId === 'string' ? { host: { modelId: host.modelId, checkpoint: typeof host.checkpoint === 'string' ? host.checkpoint : null, taskUpdate: typeof host.taskUpdate === 'string' ? host.taskUpdate : null } } : {})
  }
}

/** The languages the workpiece was created with; older ones without get the UML class diagram. */
export const languagesOf = (workpiece: Workpiece): WorkspaceLanguageReference[] => {
  const languages = workpiece.contract.languages
  const usable = Array.isArray(languages) && languages.every((language) => typeof language?.languageId === 'string' && typeof language?.versionId === 'string')
  return usable && languages.length > 0 ? (languages as WorkspaceLanguageReference[]) : [UML_CLASS_DIAGRAM]
}

/** How much of the private history the workpiece was created with; older ones without it count as none. */
export const historyModeOf = (workpiece: Workpiece): HistoryMode => {
  const mode = workpiece.contract.history
  return mode === 'versions' || mode === 'steps' ? mode : 'none'
}

/** States read at once from collab-kit while catching up on stored changes. */

/** Reads the units after each of these updates, a batch at a time, and hands them on in their order. */
export const forEachState = async <Value, Update extends UpdateSummary>(ck: CollabKitApi, workpieceId: string, updates: readonly Update[], map: string, each: (update: Update, units: ReadonlyMap<string, Value>) => void) => {
  for (let start = 0; start < updates.length; start += collabSettings.sharing.apiBatch) {
    const batch = updates.slice(start, start + collabSettings.sharing.apiBatch)
    const states = await Promise.all(batch.map((update) => ck.workpieces.unitsAt<Value>(workpieceId, { at: update._id, map })))
    batch.forEach((update, index) => each(update, states[index].units))
  }
}

/** Whether collab-kit holds every unit as the session has it, so nothing of the own is on its way. */
const sameUnits = <Value>(stored: ReadonlyMap<string, Value>, own: [string, Value][]) => stored.size === own.length && own.every(([key, unit]) => JSON.stringify(stored.get(key)) === JSON.stringify(unit))
export const isHeld = async <Value>(ck: CollabKitApi, session: Session<Value>, map: string) => sameUnits((await ck.workpieces.unitsAt<Value>(session.workpieceId, { map })).units, session.units.entries())

export const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
