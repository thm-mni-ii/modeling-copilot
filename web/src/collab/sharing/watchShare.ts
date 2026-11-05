import { notifySuccess, notifyWarning } from '@/composables/useNotifications'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { Session } from '@/collab/kit/collabKitV1'
import { currentShare, hostAway, hostClosed, visitorRights } from './shareModel'

/** How long the host may be missing from the presence before a visitor is told; a reload of the host takes less. */
const HOST_AWAY_MS = 30000

/**
 * Tells a visitor what the host does. The editor already locks and unlocks the graph on
 * `rightsChanged`; this adds why. `open` in the settings of the room says whether the host
 * has locked it to leave. The connection ending while locked means the host has closed the room.
 */
export const watchShare = (session: Session) => {
  const share = currentShare.value
  // Only visitors of this workpiece; the host keeps every right.
  if (!share || share.privateModelId || share.workpieceId !== session.workpieceId) return () => undefined
  let locked = false
  // Whether the sweep of the backend locked the room because the host is gone, not the host themselves.
  let autoLocked = false

  // The editing right is known from the session at once; commenting is `speak` at the workpiece, which CK tells.
  const readRights = async () => {
    visitorRights.edit = session.mayWrite
    try {
      const rights = await (await loadCollabKit()).me.rights({ kind: 'workpiece', id: session.workpieceId })
      visitorRights.comment = rights.includes('speak')
    } catch {
      // The icon then stays as it was.
    }
  }
  void session.synced.then(readRights, () => undefined)

  const stopRights = session.on('rightsChanged', async (mayWrite) => {
    void readRights()
    try {
      const room = await (await loadCollabKit()).rooms.get(share.roomId)
      const settings = room.settings.share as { open?: boolean; autoLocked?: boolean } | undefined
      locked = settings?.open === false
      autoLocked = settings?.autoLocked === true
    } catch {
      // The reason stays unknown; the plain message below still tells what changed.
    }
    visitorRights.locked = locked && !mayWrite
    if (mayWrite) notifySuccess('The host continues, editing is possible again.')
    else notifyWarning(locked ? (autoLocked ? 'The host is disconnected, editing is paused.' : 'The host is ending the session, editing is paused.') : 'You may no longer edit this model.')
  })
  const stopClosed = session.on('closed', () => {
    if (locked) hostClosed.value = true
  })

  // The presence tells at once who is there; a host missing for a while is shown, one who is back is welcomed.
  let away: ReturnType<typeof setTimeout> | null = null
  const watchHost = () => {
    if (!share.hostId) return
    if (session.presence.people().some((person) => person.id === share.hostId)) {
      if (away) clearTimeout(away)
      away = null
      if (hostAway.value) {
        hostAway.value = false
        notifySuccess('The host is back.')
      }
    } else if (!away && !hostAway.value) {
      away = setTimeout(() => {
        away = null
        hostAway.value = true
        notifyWarning('The host is disconnected.')
      }, HOST_AWAY_MS)
    }
  }
  let stopPresence: () => void = () => undefined
  let stopped = false
  // Before the session is in sync the presence is still empty, which would count as a missing host.
  void session.synced.then(
    () => {
      if (stopped) return
      stopPresence = session.presence.onChange(watchHost)
      watchHost()
    },
    () => undefined
  )
  return () => {
    stopped = true
    stopRights()
    stopClosed()
    stopPresence()
    if (away) clearTimeout(away)
    hostAway.value = false
  }
}
