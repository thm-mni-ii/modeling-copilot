import { shallowRef } from 'vue'
import type { Room } from '@/collab/kit/collabKitV1'

/** Wie das verbundene Modell im Raum liegt: geteilt von einem Host, oder in einem Gruppenraum, in dem alle dasselbe dürfen. */
export interface RoomRole {
  kind: 'share' | 'group'
  name: string
}

/** Die Rolle der laufenden Verbindung; null ohne Verbindung oder wenn der Raum nicht zu lesen war, dann gilt alles wie bei einer Share. */
export const roomRole = shallowRef<RoomRole | null>(null)

/** Räume aus dem Teilen erkennt man an `settings.share`, das nur das Backend beim Teilen setzt; alle anderen sind Gruppenräume. */
export const roleOf = (room: Room): RoomRole => ({ kind: room.settings.share ? 'share' : 'group', name: room.name })
