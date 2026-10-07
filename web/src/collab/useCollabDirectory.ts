import { ref } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, listActorNames, listGroups, listRooms, listWorkpieces, type CollabGroup, type CollabRoom, type CollabWorkpiece } from './collabApi'

// Shared by both tabs of the dialog, loaded on every opening.
const rooms = ref<CollabRoom[]>([])
const groups = ref<CollabGroup[]>([])
const workpieces = ref<CollabWorkpiece[]>([])
const names = ref<Record<string, string>>({})
const loading = ref(false)

const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name)

/** Puts what collab-kit answered with in place of the entry shown, or adds it. */
const replace = <T extends { _id: string }>(list: T[], entry: T) => {
  const index = list.findIndex((known) => known._id === entry._id)
  if (index === -1) list.push(entry)
  else list.splice(index, 1, entry)
}

const drop = <T extends { _id: string }>(list: T[], id: string) => {
  const index = list.findIndex((known) => known._id === id)
  if (index !== -1) list.splice(index, 1)
}

/** Names of these people as far as collab-kit gives them; one who never connected has none yet. */
const loadNames = async (actorIds: string[]) => {
  const unknown = [...new Set(actorIds)].filter((actorId) => !(actorId in names.value))
  if (unknown.length === 0) return
  try {
    for (const { actorId, label } of (await listActorNames(unknown)).data) {
      if (label) names.value[actorId] = label
    }
  } catch {
    // Without names the members still show with their IDs.
  }
}

const load = async () => {
  loading.value = true
  try {
    const [foundRooms, foundGroups, foundWorkpieces] = await Promise.all([listRooms(), listGroups(), listWorkpieces()])
    rooms.value = foundRooms.data.sort(byName)
    groups.value = foundGroups.data.sort(byName)
    workpieces.value = foundWorkpieces.data.sort(byName)
    await loadNames(groups.value.flatMap((group) => group.members))
  } catch (error) {
    notifyError(`Rooms and groups could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

export const useCollabDirectory = () => ({
  rooms,
  groups,
  workpieces,
  loading,
  load,
  loadNames,
  showRoom: (room: CollabRoom) => replace(rooms.value, room),
  showGroup: (group: CollabGroup) => replace(groups.value, group),
  showWorkpiece: (workpiece: CollabWorkpiece) => replace(workpieces.value, workpiece),
  dropRoom: (id: string) => drop(rooms.value, id),
  dropGroup: (id: string) => drop(groups.value, id),
  roomName: (id: string) => rooms.value.find((room) => room._id === id)?.name ?? id,
  groupName: (id: string) => groups.value.find((group) => group._id === id)?.name ?? id,
  actorName: (id: string) => names.value[id] ?? `User ${id}`
})

/** One change sent at a time per panel; what is being sent shows as busy, a refusal as notification. */
export const useCollabAction = () => {
  const busy = ref<string | null>(null)
  const run = async (what: string, action: () => Promise<void>, failure: string) => {
    busy.value = what
    try {
      await action()
    } catch (error) {
      notifyError(`${failure}: ${collabErrorMessage(error)}`)
    } finally {
      busy.value = null
    }
  }
  return { busy, run }
}
