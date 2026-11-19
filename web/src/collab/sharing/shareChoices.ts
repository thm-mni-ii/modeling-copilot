import type { HistoryMode } from '@/collab/converters/model/modelHistory'
import { COMMENTS_ENABLED, hostAway, hostClosed, roomGone, visitorRights, type ShareOptions } from './shareModel'

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
