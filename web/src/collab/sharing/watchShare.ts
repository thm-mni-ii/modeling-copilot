import { notifySuccess, notifyWarning } from '@/composables/useNotifications'
import { loadCollabKit } from '@/collab/kit/collabKit'
import type { Session } from '@/collab/kit/collabKitV1'
import { currentShare, hostClosed, visitorRights } from './shareModel'

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
      locked = (room.settings.share as { open?: boolean } | undefined)?.open === false
    } catch {
      // The reason stays unknown; the plain message below still tells what changed.
    }
    visitorRights.locked = locked && !mayWrite
    if (mayWrite) notifySuccess('The host continues, editing is possible again.')
    else notifyWarning(locked ? 'The host is ending the session, editing is paused.' : 'You may no longer edit this model.')
  })
  const stopClosed = session.on('closed', () => {
    if (locked) hostClosed.value = true
  })
  return () => {
    stopRights()
    stopClosed()
  }
}
