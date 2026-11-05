import { reactive, ref, readonly, watch } from 'vue'
import type { AxiosError } from 'axios'
import type { RouteLocationNormalized, Router } from 'vue-router'
import httpClient from '@/services/api/httpClient'
import modelService from '@/services/model/model.service'
import { cloneJson, type ModelSnapshot } from '@/model/ModelSnapshot'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import type { JsonObject } from '@/services/api/types/common'
import type { Model, WorkspaceLanguageReference } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { createModelPatch } from '@/utils/modelPatches'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, Right, Session } from '@/collab/kit/collabKitV1'
import { openWorkpiece } from '@/collab/connection/openWorkpiece'
import { hasChange, stepsOf, type HistoryMode, type HistoryStep, type PrivateVersion } from '@/collab/converters/model/modelHistory'
import { sameUnits, type ModelUnit } from '@/collab/converters/model/modelUnits'
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

/** Set for a visitor while the host has been gone from the room for a while, as the presence tells it. */
export const hostAway = ref(false)

/** How often collab-kit is asked whether it holds what was written, and for how long. */
const POLL_MS = 50
const WAIT_MS = 10000

const pause = () => new Promise((resolve) => setTimeout(resolve, POLL_MS))

/** Fails with the reason the backend names (`{ code, message }`), else with the message of the error. */
const request = async <Value>(run: () => Promise<{ data: Value }>) => {
  try {
    return (await run()).data
  } catch (error) {
    throw new Error((error as AxiosError<{ message?: string }>).response?.data?.message ?? (error as Error).message)
  }
}

/** How far the history is written while sharing, for the dialog; null when nothing is being written. */
export const shareProgress = ref<{ done: number; total: number } | null>(null)

/** The versions read at once from the API, and per page. */
const BATCH = 6
const PAGE = 100

/** The versions of the private model with their whole state, oldest first. */
const readPrivateVersions = async (model: Model): Promise<PrivateVersion[]> => {
  const ids: string[] = []
  for (let total = 1; ids.length < total; ) {
    const { items, total: all } = (await modelService.listVersions(model, ids.length, PAGE)).data
    if (items.length === 0) break
    ids.push(...items.map((item) => item.id))
    total = all
  }
  // The API lists the newest first; a version builds on the one before it.
  ids.reverse()
  const versions: PrivateVersion[] = []
  for (let start = 0; start < ids.length; start += BATCH) {
    const batch = await Promise.all(ids.slice(start, start + BATCH).map((id) => modelService.getVersion(model, id)))
    for (const { data } of batch) versions.push({ info: data, xml: (data.data as ModelSnapshot).xml })
  }
  return versions
}

/** Waits until collab-kit holds every unit the session has, so a checkpoint marks exactly that state. */
const waitUntilHeld = async (ck: CollabKitApi, workpieceId: string, session: Session<ModelUnit>) => {
  const until = Date.now() + WAIT_MS
  while (!sameUnits((await ck.workpieces.unitsAt<ModelUnit>(workpieceId, { map: CELLS_MAP })).units, session.units.entries())) {
    if (Date.now() > until) throw new Error('collab-kit did not take the model in time.')
    await pause()
  }
}

/** Writes the steps into the new workpiece before anyone joins; a version ends in a checkpoint, set once collab-kit holds its state. */
const writeHistory = async (ck: CollabKitApi, workpieceId: string, steps: HistoryStep[]) => {
  const session = ck.open<ModelUnit>(workpieceId, { map: CELLS_MAP })
  try {
    await session.synced
    shareProgress.value = { done: 0, total: steps.length }
    for (const [index, step] of steps.entries()) {
      // Out of undo, so the host cannot take the history back.
      if (hasChange(step.change)) session.units.update(step.change, { undoable: false })
      if (step.checkpoint) {
        await waitUntilHeld(ck, workpieceId, session)
        await ck.workpieces.checkpoint(workpieceId, step.checkpoint)
      }
      shareProgress.value = { done: index + 1, total: steps.length }
    }
    // The session may close only once collab-kit holds the last of it.
    await waitUntilHeld(ck, workpieceId, session)
  } finally {
    session.close()
    shareProgress.value = null
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
export const shareDialog = ref<'ask' | 'link' | 'quit' | 'leave' | null>(null)

/** The link of a room; the router builds it, as the app keeps its routes behind a hash. */
export const shareLink = (router: Router, roomId: string) => new URL(router.resolve({ name: 'Join', params: { roomId } }).href, window.location.origin).href

/** Shares the open model: creates room and workpiece at the backend, writes the state, opens the room model. Gives back the link. */
/** With `task`, the task of the model comes along; the backend reads it from the model. `history` tells how much of the private versions goes into the workpiece. */
export const shareModel = async (router: Router, { history = 'none', ...options }: ShareOptions & { task: boolean; history?: HistoryMode }) => {
  // A second share saves and closes the first one beforehand, as on leaving.
  if (current.value) await leaveShare(router, 'version')

  const workspace = useModelWorkspaceStore()
  // The private model holds the state the host saves a version onto later.
  await workspace.save()
  const privateModel = workspace.model
  if (!privateModel) throw new Error('The model could not be saved before sharing.')
  const xml = workspace.data.xml
  const languages = cloneJson(workspace.languages)

  const { name, contract, units } = newWorkpiece('', privateModel.name, languages, history)
  const task = options.task && Boolean(workspace.taskReference)
  const shared = await request(() => httpClient.post<{ roomId: string; workpieceId: string; hostId: string; created: boolean }>('/v1/share', { name, contract, units, ...options, task, modelId: privateModel.id }))
  const ck = await loadCollabKit()
  // The host already shares: the workpiece holds the live state, which must not be overwritten.
  if (shared.created) {
    try {
      const versions = history === 'none' ? [] : await readPrivateVersions(privateModel)
      await writeHistory(ck, shared.workpieceId, stepsOf(versions, history, { xml, languages }))
    } catch (error) {
      // The room is open with a half written workpiece, and another try would take it as shared already: end the share.
      await httpClient.post('/v1/share/close').catch(() => undefined)
      throw error
    }
  }

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

/** Where the guard stopped someone on their way out; once they have decided, they go there. */
export const pendingTarget = ref<RouteLocationNormalized | null>(null)

/** Leaves the room model and opens `model`, or the place the guard stopped; after closing, the linked model has no access and is deleted. */
const leaveLinked = async (router: Router, model: Model | null) => {
  const linkedModelId = current.value?.linkedModelId
  const target = pendingTarget.value
  pendingTarget.value = null
  current.value = null
  settingsLoaded.value = false
  presenting.value = false
  personColors.value = {}
  hostClosed.value = false
  hostAway.value = false
  await router.replace('/')
  if (linkedModelId) await httpClient.delete(`/v1/models/${linkedModelId}`)
  if (target) await router.push(target.fullPath)
  else if (model) await router.push(`/modeling/${model.id}`)
}

/**
 * Keeps host and visitors from walking out of the shared model unnoticed: logo, home, the menu and the
 * back button of the browser are stopped and the dialog to leave opens instead (vue-router stops
 * the navigation in `beforeEach`; the tab closing only gets the standard warning of the browser through
 * `beforeunload`, a dialog of the page is not possible there). The sharing's own way out clears `current` first.
 */
export const guardShareLeave = (router: Router) => {
  const removeGuard = router.beforeEach((to, from) => {
    const share = current.value
    if (!share?.linkedModelId || from.name !== 'Modeling' || from.params.modelId !== share.linkedModelId) return true
    if (to.name === 'Modeling' && to.params.modelId === share.linkedModelId) return true
    // A dialog is open already; it asks, and the target of the first attempt stays.
    if (shareDialog.value === 'quit' || shareDialog.value === 'leave' || hostClosed.value) return false
    pendingTarget.value = to
    if (share.privateModelId) {
      openQuitDialog().catch((error) => {
        pendingTarget.value = null
        notifyError(`Sharing could not be quit: ${(error as Error).message}`)
      })
    } else {
      shareDialog.value = 'leave'
    }
    return false
  })
  const warn = (event: BeforeUnloadEvent) => {
    if (current.value) event.preventDefault()
  }
  window.addEventListener('beforeunload', warn)
  return () => {
    removeGuard()
    window.removeEventListener('beforeunload', warn)
  }
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

/**
 * A visitor keeps the state held locally as an own model or drops it. Going always works: the
 * backend takes the visitor out of the room as far as it still can, and a refusal does not hold them.
 */
export const leaveAsVisitor = async (router: Router, keep: boolean, name?: string) => {
  const workspace = useModelWorkspaceStore()
  const saved = keep ? await createModelFrom(cloneJson(workspace.data), cloneJson(workspace.languages), name) : null
  const roomId = current.value?.roomId
  if (roomId) await httpClient.post('/v1/share/leave', { roomId }).catch(() => undefined)
  await leaveLinked(router, saved)
}

/**
 * A host who comes back asks for the share they left: that wakes the sweep of the backend, which opens
 * a room it locked because the host was gone, and tells what happened meanwhile. Visitors skip it, and
 * a host with no share just gets nothing back.
 */
export const resumeShare = async () => {
  const share = current.value
  if (share && !share.privateModelId) return
  try {
    const { data } = await httpClient.get<{ workpieceId: string | null; autoLocked: boolean }>('/v1/share')
    if (data.autoLocked) notifyWarning('Your share was paused while you were away and the visitors were removed. It continues now; they can rejoin through the link.')
  } catch {
    // Nothing is shared, or the backend is not reachable; the connection goes on either way.
  }
}

/**
 * Asks the backend whether the room of a visitor is still the one they sit in. If it is closed, gone
 * or shows another workpiece, the dialog to save the local copy opens, whatever the host did before.
 * No answer at all (network) changes nothing, so a dropped connection is not taken for a closed room.
 */
export const checkShareGone = async () => {
  const share = current.value
  if (!share || share.privateModelId || hostClosed.value) return
  try {
    const { data } = await httpClient.post<{ workpieceId: string }>('/v1/share/join', { roomId: share.roomId })
    if (data.workpieceId !== share.workpieceId) hostClosed.value = true
  } catch (error) {
    const status = (error as AxiosError).response?.status
    if (status === 403 || status === 404) hostClosed.value = true
  }
}
