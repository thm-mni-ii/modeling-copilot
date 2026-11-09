import type { Router } from 'vue-router'
import type { Model } from '@/services/api/types/model'
import modelService from '@/services/model/model.service'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { Room, Workpiece } from '@/collab/kit/collabKitV1'
import { languagesOf, linkOf, type HostLink } from '@/collab/storage/workpiece'

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
 * is left first; the new model is set up in between. Gibt die ID des geöffneten Modells zurück: Der Store
 * kennt sie erst, wenn der Editor geladen hat.
 */
export const openWorkpiece = async (router: Router, room: Room, workpiece: Workpiece, host?: HostLink): Promise<string | null> => {
  const workspace = useModelWorkspaceStore()
  const existing = await findLinkedModel(workpiece._id)
  await router.replace('/')
  if (existing) {
    await router.push(`/modeling/${existing.id}`)
    return existing.id
  }
  await workspace.startNew(workpiece.name, languagesOf(workpiece))
  // Linked before the first save, so its version comes from the workpiece and none is stored in the Copilot.
  await workspace.updatePreferences({ ...workspace.preferences, collab: { workpieceId: workpiece._id, roomId: room._id, ...(host ? { host } : {}) } })
  await workspace.save()
  if (!workspace.model) return null
  await router.push(`/modeling/${workspace.model.id}`)
  return workspace.model.id
}
