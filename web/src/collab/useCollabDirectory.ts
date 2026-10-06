import { ref } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, getGroup, listGrantsAt, listMyGroups, listRooms, type CollabGroup, type CollabRoom } from './collabApi'

// Shared by both tabs of the dialog and kept for the page, so a group created here stays listed.
const rooms = ref<CollabRoom[]>([])
const groups = ref<CollabGroup[]>([])
const loading = ref(false)

const byName = (a: { name: string }, b: { name: string }) => a.name.localeCompare(b.name)

/** Puts what collab-kit answered with in place of the entry shown, or adds it. */
const replace = <T extends { _id: string }>(list: T[], entry: T) => {
  const index = list.findIndex((known) => known._id === entry._id)
  if (index === -1) list.push(entry)
  else list.splice(index, 1, entry)
}

/**
 * Rooms come complete from /me/rooms. collab-kit cannot list all groups yet, so these are the own
 * ones, those with access to a room, and those created on this page.
 */
const load = async () => {
  loading.value = true
  try {
    rooms.value = (await listRooms()).data.sort(byName)
    const grants = await Promise.allSettled(rooms.value.map((room) => listGrantsAt({ kind: 'room', id: room._id })))
    const ids = new Set([...(await listMyGroups()).data.map((group) => group._id), ...grants.flatMap((result) => (result.status === 'fulfilled' ? result.value.data.map((grant) => grant.groupId) : [])), ...groups.value.map((group) => group._id)])
    const found = await Promise.allSettled(Array.from(ids, (id) => getGroup(id)))
    groups.value = found.flatMap((result) => (result.status === 'fulfilled' ? [result.value.data] : [])).sort(byName)
  } catch (error) {
    notifyError(`Rooms and groups could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

export const useCollabDirectory = () => ({
  rooms,
  groups,
  loading,
  load,
  showRoom: (room: CollabRoom) => replace(rooms.value, room),
  showGroup: (group: CollabGroup) => replace(groups.value, group),
  roomName: (id: string) => rooms.value.find((room) => room._id === id)?.name ?? id,
  groupName: (id: string) => groups.value.find((group) => group._id === id)?.name ?? id
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
