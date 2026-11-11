import type { CollabKitApi, Room, Workpiece } from '@/collab/kit/collabKitV1'
import { TASK_FORMAT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { roleOf } from '@/collab/rooms/roomRole'

/** Ein Modell im Gruppenraum: der Titel seiner Aufgabe, falls es eine hat, und wer gerade daran arbeitet. */
export interface GroupModel {
  workpiece: Workpiece
  task: string | null
  people: string[]
}

/** Ein Raum der Gruppe mit seinen Modellen; bei importierten Räumen dazu der Import und die Namen der Mitglieder. */
export interface GroupRoom {
  room: Room
  models: GroupModel[]
  imported?: GroupWorkMark
  members?: string[]
}

/** Wie das Backend einen importierten Raum markiert (services/collab_kit/group_work.py). */
export interface GroupWorkMark {
  /** Kurs und Semester, wie der Tutor sie beim Import angab; Räume vor dieser Angabe haben keinen. */
  course: string
  importedAt: string
  importedBy: string
}

/** Der Import eines Raums; ein Raum ohne Markierung kommt nicht aus einer Teilnehmerliste. */
export const groupWorkOf = (room: Room): GroupWorkMark | null => {
  const mark = room.settings.groupWork as Partial<GroupWorkMark> | undefined
  return typeof mark?.importedAt === 'string' && typeof mark.importedBy === 'string' ? { course: typeof mark.course === 'string' ? mark.course : '', importedAt: mark.importedAt, importedBy: mark.importedBy } : null
}

/** Die Namen der Mitglieder je importiertem Raum, aus der CK-Gruppe, die auf ihn verweist; ohne Recht an den Gruppen keine. */
const membersByRoom = async (ck: CollabKitApi) => {
  const members = new Map<string, string[]>()
  try {
    for (const group of await ck.groups.list()) {
      const roomId = (group.settings.groupWork as { roomId?: unknown } | undefined)?.roomId
      if (typeof roomId === 'string')
        members.set(
          roomId,
          group.members.map((id) => group.names?.[id] ?? id)
        )
    }
  } catch {
    // Ohne Gruppen bleiben nur die Namen weg, die Räume zeigt der Reiter trotzdem.
  }
  return members
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
 * ebenso die Aufgaben-Werkstücke, denn eine Aufgabe zeigt das Modell, das auf sie verweist. Mit `imported` nur die
 * Räume aus einer Teilnehmerliste, mit ihrem Import und ihren Mitgliedern.
 */
export const loadGroupRooms = async (ck: CollabKitApi, { imported = false } = {}): Promise<GroupRoom[]> => {
  const [rooms, visible, members] = await Promise.all([ck.me.rooms(), ck.workpieces.list(), imported ? membersByRoom(ck) : new Map<string, string[]>()])
  const workpieces = new Map(visible.map((workpiece) => [workpiece._id, workpiece]))
  return Promise.all(
    rooms
      .filter((room) => roleOf(room).kind === 'group' && (!imported || groupWorkOf(room)))
      .map(async (room) => {
        const people = await peopleByWorkpiece(ck, room._id)
        const own = room.workpieces.flatMap((id) => {
          const workpiece = workpieces.get(id)
          return workpiece && workpiece.contract.format !== TASK_FORMAT ? [workpiece] : []
        })
        const models = await Promise.all(own.map(async (workpiece) => ({ workpiece, task: await taskTitle(ck, workpiece), people: people.get(workpiece._id) ?? [] })))
        return imported ? { room, models, imported: groupWorkOf(room) ?? undefined, members: members.get(room._id) ?? [] } : { room, models }
      })
  )
}
