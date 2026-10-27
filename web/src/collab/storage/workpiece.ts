import type { JsonObject } from '@/services/api/types/common'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { NewWorkpiece, Workpiece } from '@/collab/kit/collabKitV1'

/** The top map of the doc, one cell per key; named as units, so a conflict names its cell. */
export const CELLS_MAP = 'cells'

/** The UML class diagram the Copilot seeds with fixed IDs; the default language of a shared model. */
export const UML_CLASS_DIAGRAM: WorkspaceLanguageReference = {
  languageId: 'a7fb2523-f7a0-4d23-b476-72882454b9e8',
  versionId: '51cd9919-36b9-42d9-861d-8c619a2ac6d5',
  source: 'required'
}

/** A Copilot workpiece in a room: the cell format with its languages, and the cells as units. */
export const newWorkpiece = (roomId: string, name: string, languages: WorkspaceLanguageReference[]): NewWorkpiece => ({
  name,
  roomId,
  contract: { tool: 'modeling-copilot', format: 'copilot-cells', version: 1, languages },
  units: [{ path: [CELLS_MAP] }]
})

/** Where an own model keeps the workpiece it shares; the other preferences stay as they are. */
interface CollabLink {
  workpieceId: string
  roomId: string
}

export const linkOf = (preferences: JsonObject | undefined): CollabLink | null => {
  const link = preferences?.collab as Partial<CollabLink> | undefined
  return typeof link?.workpieceId === 'string' && typeof link.roomId === 'string' ? { workpieceId: link.workpieceId, roomId: link.roomId } : null
}

/** The languages the workpiece was created with; older ones without get the UML class diagram. */
export const languagesOf = (workpiece: Workpiece): WorkspaceLanguageReference[] => {
  const languages = workpiece.contract.languages
  const usable = Array.isArray(languages) && languages.every((language) => typeof language?.languageId === 'string' && typeof language?.versionId === 'string')
  return usable && languages.length > 0 ? (languages as WorkspaceLanguageReference[]) : [UML_CLASS_DIAGRAM]
}
