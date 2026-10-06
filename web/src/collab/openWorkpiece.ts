import type { Router } from 'vue-router'
import type { JsonObject } from '@/services/api/types/common'
import type { Model, WorkspaceLanguageReference } from '@/services/api/types/model'
import modelService from '@/services/model/model.service'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { CollabRoom, CollabWorkpiece } from './collabApi'

/** The UML class diagram the Copilot seeds with fixed IDs; the default language of a shared model. */
export const UML_CLASS_DIAGRAM: WorkspaceLanguageReference = {
  languageId: 'a7fb2523-f7a0-4d23-b476-72882454b9e8',
  versionId: '51cd9919-36b9-42d9-861d-8c619a2ac6d5',
  source: 'required'
}

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
const languagesOf = (workpiece: CollabWorkpiece): WorkspaceLanguageReference[] => {
  const languages = workpiece.contract.languages
  const usable = Array.isArray(languages) && languages.every((language) => typeof language?.languageId === 'string' && typeof language?.versionId === 'string')
  return usable && languages.length > 0 ? (languages as WorkspaceLanguageReference[]) : [UML_CLASS_DIAGRAM]
}

const PAGE = 100

/** The own model that shares this workpiece, searched through all own models. */
const findLinkedModel = async (workpieceId: string): Promise<Model | null> => {
  for (let skip = 0; ; skip += PAGE) {
    const page = (await modelService.list(skip, PAGE)).data
    const found = page.items.find((model) => linkOf(model.preferences)?.workpieceId === workpieceId)
    if (found) return found
    if (skip + PAGE >= page.total) return null
  }
}

/**
 * Opens the own model of the workpiece, creating and linking it on first use. The editor only
 * loads a model when it mounts, and it writes its canvas into the workspace store meanwhile, so it
 * is left first; the new model is set up in between.
 */
export const openWorkpiece = async (router: Router, room: CollabRoom, workpiece: CollabWorkpiece) => {
  const workspace = useModelWorkspaceStore()
  const existing = await findLinkedModel(workpiece._id)
  await router.replace('/')
  if (existing) {
    await router.push(`/modeling/${existing.id}`)
    return
  }
  await workspace.startNew(workpiece.name, languagesOf(workpiece))
  await workspace.save()
  await workspace.updatePreferences({ ...workspace.preferences, collab: { workpieceId: workpiece._id, roomId: room._id } })
  if (workspace.model) await router.push(`/modeling/${workspace.model.id}`)
}
