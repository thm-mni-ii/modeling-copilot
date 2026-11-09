import { computed, reactive, ref, readonly, watch } from 'vue'
import type { AxiosError } from 'axios'
import type { RouteLocationNormalized, Router } from 'vue-router'
import httpClient from '@/services/api/httpClient'
import modelService from '@/services/model/model.service'
import { cloneJson } from '@/model/ModelSnapshot'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import type { Model } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { Right } from '@/collab/kit/collabKitV1'
import { openWorkpiece } from '@/collab/connection/openWorkpiece'
import type { HistoryMode } from '@/collab/converters/model/modelHistory'
import { forgetRoomHistory, keepRoomAsOwnModel, saveRoomAsNewModel, writeRoomToPrivateModel } from '@/collab/historyBuilder/fromRoom'
import { buildRoomHistory, roomHistoryStart } from '@/collab/historyBuilder/toRoom'
import { newWorkpiece } from '@/collab/storage/workpiece'

/** What the host answers in the dialog before the link; visitors always see. */
export interface ShareOptions {
  anonymous: boolean
  edit: boolean
  comment: boolean
}

/** What the host picks in the dialog before the link, and what the dialog with the link shows afterwards. It lives here and not in a component, as the editor is rebuilt while sharing. */
const defaultChoice = () => ({ anonymous: false, edit: true, comment: true, task: true, history: 'none' as HistoryMode })
export const shareChoice = reactive(defaultChoice())

// Kommentare von collab-kit nutzt der Editor noch nicht; bis dahin ist der Schalter ausgeblendet, Besucher behalten `speak`.
export const COMMENTS_ENABLED = false

/** The visitor settings of both dialogs: a new one needs its key in `ShareOptions` and one entry here. `on` and `off` tell how the dialog with the link shows it; `open` is the value that gives the visitors more, shown in green, the other one in gray. */
export const visitorSettings: { key: keyof ShareOptions; label: string; hint: string; open: boolean; on: { icon: string; text: string }; off: { icon: string; text: string } }[] = [
  { key: 'anonymous', label: 'Anonymous', hint: 'Others see a pseudonym instead of the name', open: false, on: { icon: 'mdi-incognito', text: 'Anonymous' }, off: { icon: 'mdi-account-outline', text: 'Named' } },
  { key: 'edit', label: 'May edit', hint: 'Change the model together with you', open: true, on: { icon: 'mdi-pencil', text: 'May edit' }, off: { icon: 'mdi-pencil-off', text: 'View only' } },
  ...(COMMENTS_ENABLED ? [{ key: 'comment' as const, label: 'May comment', hint: 'Leave comments on elements', open: true, on: { icon: 'mdi-comment-outline', text: 'May comment' }, off: { icon: 'mdi-comment-off-outline', text: 'No comments' } }] : [])
]

/** How much of the private history goes into the shared workpiece. */
export const historyChoices: { value: HistoryMode; icon: string; title: string; hint: string }[] = [
  { value: 'none', icon: 'mdi-camera-outline', title: 'Current state', hint: 'Only the model as it is now' },
  { value: 'versions', icon: 'mdi-source-branch', title: 'Versions', hint: 'Releases and checkpoints' },
  { value: 'steps', icon: 'mdi-history', title: 'Every change', hint: 'Versions and all changes between them' }
]

/** Where the state goes on leaving: a new version of the private model, a new model, or nowhere. */
export type LeaveTarget = 'version' | 'model' | 'discard'

/** The ways the host may leave; the dialog to quit shows them in this order, and a new one needs its case in `leaveShare`. */
export const leaveChoices: { value: LeaveTarget; icon: string; title: string; hint: string; danger?: boolean }[] = [
  { value: 'version', icon: 'mdi-source-commit', title: 'New version of your model', hint: 'Added to the history of the model you shared' },
  { value: 'model', icon: 'mdi-file-plus-outline', title: 'New model', hint: 'Your original model stays as it was' },
  { value: 'discard', icon: 'mdi-delete-outline', title: 'Do not save', hint: 'The changes made while sharing are lost', danger: true }
]

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

/** Set for a visitor together with `hostClosed` when the room is no longer reachable, as `checkShareGone` finds it, and not closed by the host. */
export const roomGone = ref(false)

/** Set for a visitor while the host has been gone from the room for a while, as the presence tells it. */
export const hostAway = ref(false)

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

/** Whether the host presents: then everyone sees only the host's cursor and selection. Announced by the host through presence. */
export const presenting = ref(false)

/** Whether the host is presenting, as a visitor learns it from presence; the host reads `presenting`. */
export const hostPresenting = ref(false)

/** What the visitor may do here, as the session and CK tell it; the host may do everything. `locked` is the host leaving. */
export const visitorRights = reactive({ edit: false, comment: false, locked: false, autoLocked: false })

/** Which color each person has: the host hands them out and announces them, the visitors read them from the host's presence. */
export const personColors = ref<Record<string, string>>({})

/** The situations of a visitor leaving; the dialog takes its texts from `visitorCases` and the situation from `visitorCase`. */
export type VisitorCase = 'leave' | 'hostAway' | 'hostEnding' | 'hostLeft' | 'roomGone'

/** What the dialog says in each situation. `tone` colors the icon and the chip; without `canStay` the room is closed and the visitor can only go on alone. */
export const visitorCases: Record<VisitorCase, { icon: string; tone: 'ok' | 'warn'; title: string; text: string; chip: { icon: string; text: string }; canStay: boolean; confirm: string }> = {
  leave: { icon: 'mdi-exit-run', tone: 'ok', title: 'Leave sharing', text: 'You leave the shared model. Keep the current state to continue on your own.', chip: { icon: 'mdi-door-open', text: 'Room is open' }, canStay: true, confirm: 'Keep and leave' },
  hostAway: { icon: 'mdi-lan-disconnect', tone: 'warn', title: 'Leave sharing', text: 'The host is disconnected and editing is paused. You can wait or leave now.', chip: { icon: 'mdi-lan-disconnect', text: 'Host disconnected' }, canStay: true, confirm: 'Keep and leave' },
  hostEnding: { icon: 'mdi-lock-outline', tone: 'warn', title: 'Leave sharing', text: 'The host is ending the session. Keep the current state before the room closes.', chip: { icon: 'mdi-lock-outline', text: 'Host is ending the session' }, canStay: true, confirm: 'Keep and leave' },
  hostLeft: { icon: 'mdi-exit-run', tone: 'warn', title: 'The host has left', text: 'The room is closed. Keep the current state to continue on your own.', chip: { icon: 'mdi-lock-outline', text: 'Room closed' }, canStay: false, confirm: 'Keep and continue' },
  roomGone: { icon: 'mdi-link-off', tone: 'warn', title: 'The room is no longer available', text: 'You can no longer reach this room. Keep the current state to continue on your own.', chip: { icon: 'mdi-link-off', text: 'Room closed' }, canStay: false, confirm: 'Keep and continue' }
}

/** What a visitor may do with the state on leaving. */
export type VisitorChoice = 'keep' | 'drop'
export const visitorChoices: { value: VisitorChoice; icon: string; title: string; hint?: string; danger?: boolean }[] = [
  { value: 'keep', icon: 'mdi-file-plus-outline', title: 'Keep as a model of your own' },
  { value: 'drop', icon: 'mdi-delete-outline', title: 'Do not keep', hint: 'The state is lost for you', danger: true }
]

/** The situation of the visitor now; the host being gone counts before the host ending, and a closed room before both. */
export const visitorCase = (): VisitorCase => {
  if (hostClosed.value) return roomGone.value ? 'roomGone' : 'hostLeft'
  if (hostAway.value || visitorRights.autoLocked) return 'hostAway'
  return visitorRights.locked ? 'hostEnding' : 'leave'
}

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

/** Ein Schalter des Hosts, gleich in der Sidebar und in der Leiste am Canvas; `sidebarOnly` fehlt in der Leiste. `label` ist der kurze, feste Name der Kachel in der Sidebar, `title` der Tooltip. */
export interface HostToggle {
  key: string
  label: string
  on: boolean
  icon: string
  title: string
  toggle: () => void
  sidebarOnly?: boolean
}

// Eine Quelle für Sidebar und ModeBar, damit Icons und Texte an beiden Stellen gleich bleiben.
export const hostToggles = computed<HostToggle[]>(() => {
  const { joinable, edit, comment, anonymous } = shareSettings
  return [
    { key: 'joinable', label: 'New visitors', sidebarOnly: true, on: joinable, icon: joinable ? 'mdi-account-plus-outline' : 'mdi-account-off-outline', title: joinable ? 'New visitors may join' : 'No new visitors', toggle: () => void toggleShareSetting('joinable') },
    { key: 'edit', label: 'Editing', on: edit, icon: edit ? 'mdi-pencil' : 'mdi-pencil-off', title: edit ? 'Visitors may edit' : 'Visitors may not edit', toggle: () => void toggleShareSetting('edit') },
    ...(COMMENTS_ENABLED ? [{ key: 'comment', label: 'Comments', on: comment, icon: comment ? 'mdi-comment-outline' : 'mdi-comment-off-outline', title: comment ? 'Visitors may comment' : 'Visitors may not comment', toggle: () => void toggleShareSetting('comment') }] : []),
    { key: 'anonymous', label: 'Anonymous', on: anonymous, icon: anonymous ? 'mdi-incognito' : 'mdi-account-outline', title: anonymous ? 'Visitors are anonymous' : 'Visitors are named', toggle: () => void toggleShareSetting('anonymous') },
    { key: 'present', label: 'Presenting', on: presenting.value, icon: 'mdi-cursor-default-outline', title: presenting.value ? 'Stop presenting' : 'Presentation mode: others only see your cursor', toggle: () => (presenting.value = !presenting.value) }
  ]
})

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
  // The private model holds the state the host saves a version onto later; with nothing open, it does already.
  if (!workspace.model || workspace.dirty || workspace.taskEditDirty) await workspace.save()
  const privateModel = workspace.model
  if (!privateModel) throw new Error('The model could not be saved before sharing.')
  const xml = workspace.data.xml
  const languages = cloneJson(workspace.languages)

  const { name, contract, units } = newWorkpiece('', privateModel.name, languages, history)
  const task = options.task && Boolean(workspace.taskReference)
  const shared = await request(() => httpClient.post<{ roomId: string; workpieceId: string; hostId: string; created: boolean }>('/v1/share', { name, contract, units, ...options, task, modelId: privateModel.id }))
  const ck = await loadCollabKit()
  const [room, workpiece] = await Promise.all([ck.rooms.get(shared.roomId), ck.workpieces.get(shared.workpieceId)])
  // The host already shares: the workpiece holds the live state, which must not be overwritten.
  if (shared.created) {
    // The plain task is in the CK task already; what was marked or added privately goes along.
    const edit = workspace.taskEdit?.document
    const contentHtml = workspace.taskVersion?.data.contentHtml
    try {
      await buildRoomHistory(ck, workpiece, { model: privateModel, mode: history, xml, languages, task: task && edit && contentHtml ? { document: edit, contentHtml } : null }, (done, total) => (shareProgress.value = { done, total }))
    } catch (error) {
      // The room is open with a half written workpiece, and another try would take it as shared already: end the share.
      await httpClient.post('/v1/share/close').catch(() => undefined)
      throw error
    } finally {
      shareProgress.value = null
    }
  }

  await openWorkpiece(router, room, workpiece, { modelId: privateModel.id, ...(await roomHistoryStart(ck, workpiece)) })
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

/**
 * Writes what the room added into the host's private model, as an evaluation needs a saved submission;
 * gives back that model. What is open becomes a version of the room first, so the room goes on after it.
 */
export const saveRoomCheckpoint = async () => {
  const share = current.value
  if (!share?.privateModelId) throw new Error('Only the host can evaluate the model.')
  const workspace = useModelWorkspaceStore()
  if (workspace.dirty) await workspace.save()
  await writeRoomToPrivateModel(share.privateModelId, share.workpieceId, { xml: workspace.data.xml, languages: cloneJson(workspace.languages) })
  return share.privateModelId
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
  roomGone.value = false
  hostAway.value = false
  visitorRights.locked = false
  visitorRights.autoLocked = false
  Object.assign(shareChoice, defaultChoice())
  forgetRoomHistory()
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
  const state = { xml: workspace.data.xml, languages: cloneJson(workspace.languages) }
  // Discarding writes nothing: the private model holds what it had when sharing began, and that is what opens.
  const saved = target === 'discard' ? (await modelService.get(share.privateModelId)).data : target === 'version' ? await writeRoomToPrivateModel(share.privateModelId, share.workpieceId, state) : await saveRoomAsNewModel(share.privateModelId, share.workpieceId, name ?? workspace.data.name, state)
  await request(() => httpClient.post('/v1/share/close'))
  await leaveLinked(router, saved)
}

/**
 * A visitor keeps the state held locally as an own model or drops it. Going always works: the
 * backend takes the visitor out of the room as far as it still can, and a refusal does not hold them.
 */
export const leaveAsVisitor = async (router: Router, keep: boolean, name?: string) => {
  const workspace = useModelWorkspaceStore()
  const saved = keep ? await keepRoomAsOwnModel(name ?? workspace.data.name, { xml: workspace.data.xml, languages: cloneJson(workspace.languages) }) : null
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
 * The browser keeps the share of a host across sign-ins, so it may belong to another account or have
 * ended meanwhile. What the backend no longer gives this user as their share is forgotten here, or the
 * sidebar stays stuck on it. No answer at all (network) changes nothing.
 */
export const dropStaleShare = async () => {
  const share = current.value
  if (!share?.privateModelId) return
  try {
    const { data } = await httpClient.get<{ roomId: string; workpieceId: string | null }>('/v1/share')
    if (data.roomId === share.roomId && data.workpieceId === share.workpieceId) return
  } catch (error) {
    if ((error as AxiosError).response?.status !== 404) return
  }
  current.value = null
  settingsLoaded.value = false
}

/**
 * Asks the backend whether the room of a visitor is still the one they sit in. If it is closed, gone
 * or shows another workpiece, the dialog to save the local copy opens, whatever the host did before.
 * No answer at all (network) changes nothing, so a dropped connection is not taken for a closed room.
 */
export const checkShareGone = async () => {
  const markGone = () => {
    roomGone.value = true
    hostClosed.value = true
  }
  const share = current.value
  if (!share || share.privateModelId || hostClosed.value) return
  try {
    const { data } = await httpClient.post<{ workpieceId: string }>('/v1/share/join', { roomId: share.roomId })
    if (data.workpieceId !== share.workpieceId) markGone()
  } catch (error) {
    const status = (error as AxiosError).response?.status
    if (status === 403 || status === 404) markGone()
  }
}
