import type { CollabKitApi, Room, Workpiece } from '@/collab/kit/collabKitV1'
import { TASK_FORMAT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { roleOf } from '@/collab/rooms/roomRole'

/** A model in a group room: the title of its task, if it has one, and who is working on it now. */
export interface GroupModel {
  workpiece: Workpiece
  task: string | null
  people: string[]
}

/** A room of the group with its models; for imported rooms also the import and the names of the members. */
export interface GroupRoom {
  room: Room
  models: GroupModel[]
  imported?: GroupWorkMark
  members?: GroupMember[]
}

/** A member of an imported room; `visited`: CK knows the person, so they have been there before. */
export interface GroupMember {
  name: string
  visited: boolean
}

/** How the backend marks an imported room (services/collab_kit/group_work.py). */
export interface GroupWorkMark {
  /** Course and semester as the tutor gave them on import; rooms from before this field have none. */
  course: string
  importedAt: string
  importedBy: string
}

/** The import of a room; a room without the mark does not come from a participant list. */
export const groupWorkOf = (room: Room): GroupWorkMark | null => {
  const mark = room.settings.groupWork as Partial<GroupWorkMark> | undefined
  return typeof mark?.importedAt === 'string' && typeof mark.importedBy === 'string' ? { course: typeof mark.course === 'string' ? mark.course : '', importedAt: mark.importedAt, importedBy: mark.importedBy } : null
}

/**
 * The members per imported room, from the CK group that points to it; without rights on the groups none.
 * CK knows a name only after the first visit; until then the name from the list, stored by the import, applies.
 */
const membersByRoom = async (ck: CollabKitApi) => {
  const members = new Map<string, GroupMember[]>()
  try {
    for (const group of await ck.groups.list()) {
      const mark = group.settings.groupWork as { roomId?: unknown; names?: Record<string, unknown> } | undefined
      const listed = (id: string) => (typeof mark?.names?.[id] === 'string' ? (mark.names[id] as string) : `ID ${id}`)
      if (typeof mark?.roomId === 'string')
        members.set(
          mark.roomId,
          group.members.map((id) => (group.names?.[id] ? { name: group.names[id], visited: true } : { name: listed(id), visited: false }))
        )
    }
  } catch {
    // Without groups only the names are missing, the tab still shows the rooms.
  }
  return members
}

/** The title of the task; none without a task or without rights on it. */
const taskTitle = async (ck: CollabKitApi, workpiece: Workpiece) => {
  const link = taskLinkOf(workpiece)
  if (!link) return null
  try {
    return (await ck.tasks.get(link.taskId)).title
  } catch {
    return null
  }
}

/** Who is connected to which workpiece of the room now; collab-kit sends this only when asked, never by itself. */
const peopleByWorkpiece = async (ck: CollabKitApi, roomId: string) => {
  const people = new Map<string, string[]>()
  try {
    for (const entry of await ck.rooms.presence(roomId)) {
      people.set(entry.workpieceId, [...(people.get(entry.workpieceId) ?? []), entry.names?.[entry.actorId] ?? entry.actorId])
    }
  } catch {
    // Without presence only the column stays empty, the tab still shows the models.
  }
  return people
}

/**
 * The rooms one sees, with their models. Rooms from sharing are left out, they belong to the host and end with them;
 * so are the task workpieces, as the model that points to a task shows it. With `imported` only the rooms from a
 * participant list, with their import and their members.
 */
export const loadGroupRooms = async (ck: CollabKitApi, { imported = false } = {}): Promise<GroupRoom[]> => {
  const [rooms, visible, members] = await Promise.all([ck.me.rooms(), ck.workpieces.list(), imported ? membersByRoom(ck) : new Map<string, GroupMember[]>()])
  const workpieces = new Map(visible.map((workpiece) => [workpiece._id, workpiece]))
  return Promise.all(
    rooms
      .filter((room) => roleOf(room).kind === 'group' && (!imported || groupWorkOf(room)))
      .map(async (room) => {
        // Who works on what is shown by "Group models" only; the overview in the management does not need it.
        const people = imported ? new Map<string, string[]>() : await peopleByWorkpiece(ck, room._id)
        const own = room.workpieces.flatMap((id) => {
          const workpiece = workpieces.get(id)
          return workpiece && workpiece.contract.format !== TASK_FORMAT ? [workpiece] : []
        })
        const models = await Promise.all(own.map(async (workpiece) => ({ workpiece, task: await taskTitle(ck, workpiece), people: people.get(workpiece._id) ?? [] })))
        return imported ? { room, models, imported: groupWorkOf(room) ?? undefined, members: members.get(room._id) ?? [] } : { room, models }
      })
  )
}
