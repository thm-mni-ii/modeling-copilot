import { shallowRef } from 'vue'
import type { Room } from '@/collab/kit/collabKitV1'

/** How the connected model lies in its room: shared by a host, or in a group room where everyone may do the same. */
export interface RoomRole {
  kind: 'share' | 'group'
  name: string
}

/** The role of the running connection; null without a connection or if the room could not be read, then everything is as for a share. */
export const roomRole = shallowRef<RoomRole | null>(null)

/** Rooms from sharing have `settings.share`, which only the backend sets on sharing; all others are group rooms. */
export const roleOf = (room: Room): RoomRole => ({ kind: room.settings.share ? 'share' : 'group', name: room.name })
