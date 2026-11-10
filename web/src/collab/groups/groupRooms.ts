import type { CollabKitApi, Room, Workpiece } from '@/collab/kit/collabKitV1'
import { TASK_FORMAT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { roleOf } from '@/collab/rooms/roomRole'

/** Ein Modell im Gruppenraum: der Titel seiner Aufgabe, falls es eine hat, und wer gerade daran arbeitet. */
export interface GroupModel {
  workpiece: Workpiece
  task: string | null
  people: string[]
}

/** Ein Raum der Gruppe mit seinen Modellen. */
export interface GroupRoom {
  room: Room
  models: GroupModel[]
}

/** Der Titel der Aufgabe; ohne Aufgabe oder ohne Recht an ihr keiner. */
const taskTitle = async (ck: CollabKitApi, workpiece: Workpiece) => {
  const link = taskLinkOf(workpiece)
  if (!link) return null
  try {
    return (await ck.tasks.get(link.taskId)).title
  } catch {
    return null
  }
}

/** Wer gerade an welchem Werkstück des Raums verbunden ist; collab-kit schickt das nur auf Anfrage, nie von selbst. */
const peopleByWorkpiece = async (ck: CollabKitApi, roomId: string) => {
  const people = new Map<string, string[]>()
  try {
    for (const entry of await ck.rooms.presence(roomId)) {
      people.set(entry.workpieceId, [...(people.get(entry.workpieceId) ?? []), entry.names?.[entry.actorId] ?? entry.actorId])
    }
  } catch {
    // Ohne Presence bleibt nur die Spalte leer, die Modelle zeigt der Reiter trotzdem.
  }
  return people
}

/**
 * Die Räume, die man sieht, mit ihren Modellen. Räume aus dem Teilen fehlen, sie gehören dem Host und enden mit ihm;
 * ebenso die Aufgaben-Werkstücke, denn eine Aufgabe zeigt das Modell, das auf sie verweist.
 */
export const loadGroupRooms = async (ck: CollabKitApi): Promise<GroupRoom[]> => {
  const [rooms, visible] = await Promise.all([ck.me.rooms(), ck.workpieces.list()])
  const workpieces = new Map(visible.map((workpiece) => [workpiece._id, workpiece]))
  return Promise.all(
    rooms
      .filter((room) => roleOf(room).kind === 'group')
      .map(async (room) => {
        const people = await peopleByWorkpiece(ck, room._id)
        const own = room.workpieces.flatMap((id) => {
          const workpiece = workpieces.get(id)
          return workpiece && workpiece.contract.format !== TASK_FORMAT ? [workpiece] : []
        })
        const models = await Promise.all(own.map(async (workpiece) => ({ workpiece, task: await taskTitle(ck, workpiece), people: people.get(workpiece._id) ?? [] })))
        return { room, models }
      })
  )
}
