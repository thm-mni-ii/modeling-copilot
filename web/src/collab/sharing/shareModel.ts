import { reactive, ref, readonly, watch } from 'vue'
import type { AxiosError } from 'axios'
import type { Router } from 'vue-router'
import httpClient from '@/services/api/httpClient'
import modelService from '@/services/model/model.service'
import { cloneJson, type ModelSnapshot } from '@/model/ModelSnapshot'
import { notifyError } from '@/composables/useNotifications'
import type { JsonObject } from '@/services/api/types/common'
import type { Model, WorkspaceLanguageReference } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { createModelPatch } from '@/utils/modelPatches'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Right } from '@/collab/kit/collabKitV1'
import { openWorkpiece } from '@/collab/connection/openWorkpiece'
import { splitModel } from '@/collab/storage/modelCells'
import { LANGUAGES_KEY, type ModelUnit } from '@/collab/storage/modelUnits'
import { CELLS_MAP, newWorkpiece } from '@/collab/storage/workpiece'

/** What the host answers in the dialog before the link; visitors always see. */
export interface ShareOptions {
  anonymous: boolean
  edit: boolean
  comment: boolean
}

/** Where the state goes on leaving: a new version of the private model, or a new model. */
export type LeaveTarget = 'version' | 'model'

/** What this browser shares: room, workpiece and the two models attached. Only one is shared at a time. */
interface Share {
  roomId: string
  workpieceId: string
  /** The ID of the host, so everyone can tell whose cursor is the presenter's; empty for a share stored before this was kept. */
  hostId: string
  /** The host's private model; it stays unlinked while sharing. Null for visitors. */
  privateModelId: string | null
  /** The model linked to the workpiece, open in the editor; it has no access after closing and is deleted. */
  linkedModelId: string | null
}

const SHARE_KEY = 'collabShare'

/** What the browser kept of the share before a reload; a stored value of another shape counts as none. */
const storedShare = (): Share | null => {
  try {
    const stored = JSON.parse(localStorage.getItem(SHARE_KEY) ?? 'null') as Partial<Share> | null
    return typeof stored?.roomId === 'string' && typeof stored.workpieceId === 'string' ? ({ ...stored, hostId: typeof stored.hostId === 'string' ? stored.hostId : '' } as Share) : null
  } catch {
    return null
  }
}

const current = ref<Share | null>(storedShare())
export const currentShare = readonly(current)

// Kept across a reload, so the sidebar still knows a share is running; localStorage may be unavailable.
watch(
  current,
  (share) => {
    try {
      if (share) localStorage.setItem(SHARE_KEY, JSON.stringify(share))
      else localStorage.removeItem(SHARE_KEY)
    } catch {
      // The share then just starts over after a reload.
    }
  },
  { deep: true }
)
/** Set for a visitor once the host has closed the room; the dialog to save the local copy listens to it. */
export const hostClosed = ref(false)

/** How often and how long to wait until collab-kit holds the first state of the workpiece. */
const ATTEMPTS = 10
const PAUSE_MS = 200

const pause = () => new Promise((resolve) => setTimeout(resolve, PAUSE_MS))

/** Fails with the reason the backend names (`{ code, message }`), else with the message of the error. */
const request = async <Value>(run: () => Promise<{ data: Value }>) => {
  try {
    return (await run()).data
  } catch (error) {
    throw new Error((error as AxiosError<{ message?: string }>).response?.data?.message ?? (error as Error).message)
  }
}

/** Writes the state into the new workpiece before anyone joins, and waits until collab-kit holds it. */
const writeState = async (ck: CollabKitApi, workpieceId: string, xml: string, languages: WorkspaceLanguageReference[]) => {
  const cells = splitModel(xml, new Map())
  const session = ck.open<ModelUnit>(workpieceId, { map: CELLS_MAP })
  try {
    await session.synced
    session.units.update({ set: { ...Object.fromEntries(cells), [LANGUAGES_KEY]: languages } }, { undoable: false })
    for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
      if ((await ck.workpieces.unitsAt<ModelUnit>(workpieceId, { map: CELLS_MAP })).units.size === cells.size + 1) return
      await pause()
    }
    throw new Error('collab-kit did not take the model in time.')
  } finally {
    session.close()
  }
}

/** Whether the host presents: then everyone sees only the host's cursor and selection. Announced by the host through presence. */
export const presenting = ref(false)

/** Whether the host is presenting, as a visitor learns it from presence; the host reads `presenting`. */
export const hostPresenting = ref(false)

/** What the visitor may do here, as the session and CK tell it; the host may do everything. `locked` is the host leaving. */
export const visitorRights = reactive({ edit: false, comment: false, locked: false })

/** Which color each person has: the host hands them out and announces them, the visitors read them from the host's presence. */
export const personColors = ref<Record<string, string>>({})

/** What the host announced through presence for the visitors, which comes at once; CK tells it only after a reconnect, `speak` never. */
export const announcedRights = ref<{ edit: boolean; comment: boolean; anonymous: boolean } | null>(null)

/** What the host set for visitors, shown by the switches in the sidebar and the buttons on the canvas alike. */
export const shareSettings = reactive({ joinable: true, edit: true, comment: true, anonymous: false })
export const settingsLoaded = ref(false)
const settingsSaving = ref(false)
export const shareSettingsBusy = () => !settingsLoaded.value || settingsSaving.value

type SettingKey = keyof typeof shareSettings

/** Reads the settings once per share, so a reload shows what is set and not the defaults. */
export const loadShareSettings = async () => {
  if (settingsLoaded.value || !current.value) return
  try {
    Object.assign(shareSettings, await readShareSettings())
    settingsLoaded.value = true
  } catch (error) {
    notifyError(`The settings could not be read: ${(error as Error).message}`)
  }
}

/** Flips one setting and sends it; the value counts, and is announced, only once it is set. */
export const toggleShareSetting = async (key: SettingKey) => {
  if (shareSettingsBusy()) return
  settingsSaving.value = true
  const next = !shareSettings[key]
  try {
    if (key === 'joinable') await setJoinable(next)
    else await setVisitorRights({ edit: shareSettings.edit, comment: shareSettings.comment, anonymous: shareSettings.anonymous, [key]: next })
    shareSettings[key] = next
  } catch (error) {
    notifyError(`The setting was not changed: ${(error as Error).message}`)
  } finally {
    settingsSaving.value = false
  }
}

/** Which dialog is open; it lives here and not in a component, as the editor and its sidebar are rebuilt while sharing and leaving. */
export const shareDialog = ref<'ask' | 'link' | 'quit' | null>(null)

/** The link of a room; the router builds it, as the app keeps its routes behind a hash. */
export const shareLink = (router: Router, roomId: string) => new URL(router.resolve({ name: 'Join', params: { roomId } }).href, window.location.origin).href

/** Shares the open model: creates room and workpiece at the backend, writes the state, opens the room model. Gives back the link. */
/** With `task`, the task of the model comes along; the backend reads it from the model. */
export const shareModel = async (router: Router, options: ShareOptions & { task: boolean }) => {
  // A second share saves and closes the first one beforehand, as on leaving.
  if (current.value) await leaveShare(router, 'version')

  const workspace = useModelWorkspaceStore()
  // The private model holds the state the host saves a version onto later.
  await workspace.save()
  const privateModel = workspace.model
  if (!privateModel) throw new Error('The model could not be saved before sharing.')
  const xml = workspace.data.xml
  const languages = cloneJson(workspace.languages)

  const { name, contract, units } = newWorkpiece('', privateModel.name, languages)
  const task = options.task && Boolean(workspace.taskReference)
  const shared = await request(() => httpClient.post<{ roomId: string; workpieceId: string; hostId: string; created: boolean }>('/v1/share', { name, contract, units, ...options, task, modelId: privateModel.id }))
  const ck = await loadCollabKit()
  // The host already shares: the workpiece holds the live state, which must not be overwritten.
  if (shared.created) await writeState(ck, shared.workpieceId, xml, languages)

  const [room, workpiece] = await Promise.all([ck.rooms.get(shared.roomId), ck.workpieces.get(shared.workpieceId)])
  await openWorkpiece(router, room, workpiece)
  current.value = { roomId: shared.roomId, workpieceId: shared.workpieceId, hostId: shared.hostId, privateModelId: privateModel.id, linkedModelId: workspace.model?.id ?? null }
  return shareLink(router, shared.roomId)
}

/** Joins through the link and opens the workpiece; the host of the room passes as host. */
export const joinShare = async (router: Router, roomId: string) => {
  const joined = await request(() => httpClient.post<{ roomId: string; workpieceId: string; role: 'host' | 'visitor'; hostId: string }>('/v1/share/join', { roomId }))
  const ck = await loadCollabKit()
  const [room, workpiece] = await Promise.all([ck.rooms.get(joined.roomId), ck.workpieces.get(joined.workpieceId)])
  if (joined.role === 'host') return openWorkpiece(router, room, workpiece)
  // Set before the editor mounts, so the connection of the visitor finds the share.
  current.value = { roomId, workpieceId: joined.workpieceId, hostId: joined.hostId, privateModelId: null, linkedModelId: null }
  await openWorkpiece(router, room, workpiece)
  current.value = { ...current.value, linkedModelId: useModelWorkspaceStore().model?.id ?? null }
}

/** Room and the visitors' group of the own share, as the rights and the settings need them. */
const visitorGroup = async () => {
  if (!current.value) throw new Error('Nothing is shared.')
  const ck = await loadCollabKit()
  const room = await ck.rooms.get(current.value.roomId)
  const share = room.settings.share as { groups: { visitors: string }; joinable?: boolean; before?: { rights: Right[]; anonymous: boolean } }
  return { ck, share, groupId: share.groups.visitors, scope: { kind: 'room', id: room._id } }
}

/** What the switches in the sidebar show; while locked for leaving, the rights from before the lock. */
export const readShareSettings = async (): Promise<ShareOptions & { joinable: boolean }> => {
  const { ck, share, groupId, scope } = await visitorGroup()
  // CK answers either for a group or for a place, not both, so the group is picked here.
  const grant = (await ck.grants.list({ scope })).find((item) => item.groupId === groupId)
  const { rights, anonymous } = share.before ?? { rights: grant?.rights ?? [], anonymous: grant?.anonymous === true }
  return { joinable: share.joinable !== false, anonymous, edit: rights.includes('edit'), comment: rights.includes('speak') }
}

/** The rights of the visitors at the room, anonymity included; they always have `see`. */
export const setVisitorRights = async ({ edit, comment, anonymous }: ShareOptions) => {
  const { ck, groupId, scope } = await visitorGroup()
  const rights: Right[] = ['see', ...(comment ? (['speak'] as const) : []), ...(edit ? (['edit'] as const) : [])]
  await ck.grants.set({ groupId, scope, rights, anonymous })
}

/** Closes the link for new visitors or opens it again; those already in stay, rights stay. */
export const setJoinable = (joinable: boolean) => request(() => httpClient.put('/v1/share/joinable', { joinable }))

/** Locks the room while the host decides: no one else joins, visitors may no longer edit. */
export const lockShare = () => request(() => httpClient.put('/v1/share/open', { open: false }))

/** Locks the room right on "Quit sharing", so everyone keeps the state the host is about to save, and opens the dialog. */
export const openQuitDialog = async () => {
  await lockShare()
  shareDialog.value = 'quit'
}

/** Opens the room again after a cancel and gives the visitors their rights back. */
export const reopenShare = () => request(() => httpClient.put('/v1/share/open', { open: true }))

/** Creates the model with the state as its first version, without touching the editor or the store. */
const createModelFrom = async (data: ModelSnapshot, languages: WorkspaceLanguageReference[], name = data.name) => {
  const model = (await modelService.create({ name })).data
  await modelService.createVersion(model, {
    baseVersionId: null,
    baseReleaseId: null,
    workspaceLanguages: languages,
    taskVersion: null,
    data: { ...cloneJson(data), name },
    patches: [],
    kind: 'release',
    releaseName: 'Initial release',
    description: null
  })
  return model
}

/** Writes the state as the next version of the private model; the patch is the difference to its last version. */
const saveAsVersion = async (modelId: string, data: ModelSnapshot, languages: WorkspaceLanguageReference[]) => {
  const model = (await modelService.get(modelId)).data
  const base = (await modelService.getVersion(model, model.latestVersionId)).data
  const patch = createModelPatch((base.data as ModelSnapshot).xml, data.xml)
  // A checkpoint holds the state only as a patch, as in the store.
  const withoutXml: JsonObject = cloneJson(data)
  delete withoutXml.xml
  await modelService.createVersion(model, {
    baseVersionId: base.id,
    baseReleaseId: base.kind === 'release' ? base.id : base.baseReleaseId,
    workspaceLanguages: languages,
    taskVersion: base.taskVersion,
    data: withoutXml,
    patches: patch ? [{ createdAt: new Date().toISOString(), xml: patch }] : [],
    kind: 'checkpoint'
  })
  return model
}

/** Leaves the room model and opens `model`; after closing, the linked model has no access and is deleted. */
const leaveLinked = async (router: Router, model: Model | null) => {
  const linkedModelId = current.value?.linkedModelId
  current.value = null
  settingsLoaded.value = false
  presenting.value = false
  personColors.value = {}
  hostClosed.value = false
  await router.replace('/')
  if (linkedModelId) await httpClient.delete(`/v1/models/${linkedModelId}`)
  if (model) await router.push(`/modeling/${model.id}`)
}

/**
 * The host leaves the room: lock, save, only then close. If saving fails, the room stays locked
 * and open for another try; `reopenShare` cancels. `name` is the name of the new model.
 */
export const leaveShare = async (router: Router, target: LeaveTarget, name?: string) => {
  const share = current.value
  if (!share?.privateModelId) throw new Error('Only the host can close the room.')
  const workspace = useModelWorkspaceStore()
  await lockShare()
  const data = cloneJson(workspace.data)
  const languages = cloneJson(workspace.languages)
  const saved = target === 'version' ? await saveAsVersion(share.privateModelId, data, languages) : await createModelFrom(data, languages, name)
  await request(() => httpClient.post('/v1/share/close'))
  await leaveLinked(router, saved)
}

/** A visitor keeps the state held locally as an own model or drops it; there is no access to collab-kit any more. */
export const leaveAsVisitor = async (router: Router, keep: boolean, name?: string) => {
  const workspace = useModelWorkspaceStore()
  const saved = keep ? await createModelFrom(cloneJson(workspace.data), cloneJson(workspace.languages), name) : null
  await leaveLinked(router, saved)
}
