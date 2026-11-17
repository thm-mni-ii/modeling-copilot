<template>
  <div v-if="loading" class="d-flex justify-center py-8"><v-progress-circular indeterminate color="primary" /></div>
  <p v-else-if="!groupRooms.length" class="text-medium-emphasis text-center py-8 mb-0">{{ imported ? 'No group work imported yet. Import a CSV to create the rooms.' : 'No group models yet.' }}</p>
  <p v-else-if="!shown.length" class="text-medium-emphasis text-center py-8 mb-0">No room matches the search.</p>
  <!-- In the management only the overview: one table per course, one row per room with tasks and members. -->
  <template v-else-if="imported">
    <template v-for="{ key, mark, rooms } in byCourse" :key="key ?? ''">
      <div class="d-flex align-center mt-4 mb-2">
        <p class="text-subtitle-2 mb-0">
          {{ mark.course || 'Without course' }} <span class="text-medium-emphasis font-weight-regular">· {{ rooms.length }} {{ rooms.length === 1 ? 'room' : 'rooms' }} · last import {{ formattedDate(lastImport.get(key) ?? mark.importedAt) }}</span>
        </p>
        <v-spacer />
        <v-btn v-if="collabSettings.archive.enabled && mark.course" size="small" variant="text" prepend-icon="mdi-archive-arrow-down-outline" @click="askArchive(key, mark.course)">Archive course</v-btn>
      </div>
      <v-table density="compact" class="border rounded-lg mb-4">
        <thead>
          <tr>
            <th>Group</th>
            <th>Tasks</th>
            <th>Members</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="{ room, models, members } in rooms" :key="room._id">
            <td>{{ room.name }}</td>
            <td>
              <v-chip v-for="model in models" :key="model.workpiece._id" size="small" variant="outlined" prepend-icon="mdi-clipboard-text-outline" class="mr-1 my-1">{{ model.task ?? model.workpiece.name }}</v-chip>
              <span v-if="!models.length" class="text-medium-emphasis">—</span>
            </td>
            <td>
              <!-- Whoever has never been there shows with the name from the list, faded and dashed. -->
              <v-chip v-for="member in members" :key="member.name" size="small" class="mr-1 my-1" :class="{ 'member--new': !member.visited }" :variant="member.visited ? 'tonal' : 'outlined'" :prepend-icon="member.visited ? undefined : 'mdi-account-clock-outline'" :title="member.visited ? undefined : 'Hasn\'t opened the Modeling Copilot yet – the name is the one from the participant list'">{{
                member.name
              }}</v-chip>
              <span v-if="!members?.length" class="text-medium-emphasis">—</span>
            </td>
          </tr>
        </tbody>
      </v-table>
    </template>
  </template>
  <template v-else>
    <template v-for="({ room, models, imported: mark, members }, index) in shown" :key="room._id">
      <!-- Imported rooms go by course, the one imported last on top; each course gets a line above it. -->
      <p v-if="mark && courseKey(mark) !== courseKey(shown[index - 1]?.imported)" class="text-subtitle-2 mt-4 mb-2">
        {{ mark.course || 'Without course' }} <span class="text-medium-emphasis font-weight-regular">· {{ roomsPerCourse.get(courseKey(mark)) }} {{ roomsPerCourse.get(courseKey(mark)) === 1 ? 'room' : 'rooms' }} · last import {{ formattedDate(lastImport.get(courseKey(mark)) ?? mark.importedAt) }}</span>
      </p>
      <v-card variant="outlined" class="mb-4">
        <v-card-title class="d-flex align-center flex-wrap ga-2">
          <span>{{ room.name }}</span>
          <v-spacer />
          <v-chip v-for="member in members" :key="member.name" size="small" prepend-icon="mdi-account-outline">{{ member.name }}</v-chip>
        </v-card-title>
        <v-data-table :headers="headers" :items="models" :items-per-page="-1" item-value="workpiece._id" no-data-text="No models in this room yet.">
          <!-- The model is named like its task; without a task, such as when created by hand, its name shows. -->
          <template #[`item.task`]="{ item }">{{ item.task ?? item.workpiece.name }}</template>
          <template #[`item.people`]="{ item }"
            ><v-chip v-for="name in item.people" :key="name" size="small" class="mr-1">{{ name }}</v-chip
            ><span v-if="!item.people.length" class="text-medium-emphasis">—</span></template
          >
          <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary" @click="openFromRoom(room, item.workpiece)">Open</v-btn></template>
          <!-- Vuetify 3.5 does not know hide-default-footer yet; an empty slot replaces the footer. -->
          <template #bottom />
        </v-data-table>
      </v-card>
    </template>
  </template>
  <v-dialog :model-value="asked !== null" width="440" persistent>
    <v-card v-if="asked" :title="`Archive ${asked.course}?`">
      <v-card-text class="pt-0">{{ asked.rooms }} {{ asked.rooms === 1 ? 'room with its group' : 'rooms with their groups' }} and {{ asked.models }} {{ asked.models === 1 ? 'model' : 'models' }} go to the archive, the tasks along with them. Nobody can open them meanwhile. You restore them one by one in the Archive tab.</v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="archiving" @click="asked = null">Cancel</v-btn>
        <v-btn color="error" variant="text" :loading="archiving" @click="archiveCourse">Archive</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import type { AxiosError } from 'axios'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import httpClient from '@/services/api/httpClient'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { collabSettings } from '@/collab/connection/collabSettings'
import { loadGroupRooms, type GroupRoom, type GroupWorkMark } from '@/collab/groups/groupRooms'

/** `imported`: only the rooms from a participant list, with import and members, as the "Group work" tab shows them. */
const props = withDefaults(defineProps<{ imported?: boolean; search?: string }>(), { imported: false, search: '' })
/** Reports that a course went to the archive, so <ck-management> reloads too. */
const emit = defineEmits<{ archived: [] }>()

const headers = [
  { title: 'Task', key: 'task', sortable: false },
  { title: 'Working now', key: 'people', sortable: false },
  // Right-aligned: the button never changes its width.
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const }
]

const { openFromRoom } = useCollabConnection()
const groupRooms = shallowRef<GroupRoom[]>([])
const loading = ref(true)

const formattedDate = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

/** How the backend compares courses: case and spaces do not count. */
const courseKey = (mark: GroupWorkMark | undefined) => (mark ? mark.course.split(/\s+/).filter(Boolean).join(' ').toLowerCase() : null)

/** The latest import per course; the courses go by it, the one imported last on top. */
const lastImport = computed(() => {
  const last = new Map<string | null, string>()
  for (const { imported } of groupRooms.value) if (imported && (last.get(courseKey(imported)) ?? '') < imported.importedAt) last.set(courseKey(imported), imported.importedAt)
  return last
})

// The search covers room, course, members and models; imported rooms by course, within it by name.
const shown = computed(() => {
  const text = props.search.trim().toLowerCase()
  const matches = (group: GroupRoom) => !text || [group.room.name, group.imported?.course ?? '', ...(group.members ?? []).map((member) => member.name), ...group.models.flatMap((model) => [model.workpiece.name, model.task ?? ''])].some((value) => value.toLowerCase().includes(text))
  const recency = (group: GroupRoom) => lastImport.value.get(courseKey(group.imported)) ?? ''
  const byCourse = (a: GroupRoom, b: GroupRoom) => recency(b).localeCompare(recency(a)) || (courseKey(a.imported) ?? '').localeCompare(courseKey(b.imported) ?? '') || a.room.name.localeCompare(b.room.name, undefined, { numeric: true })
  return groupRooms.value.filter(matches).sort(byCourse)
})
/** The imported rooms shown, per course, in the order of `shown`. */
const byCourse = computed(() => {
  const blocks: { key: string | null; mark: GroupWorkMark; rooms: GroupRoom[] }[] = []
  for (const group of shown.value) {
    if (!group.imported) continue
    const key = courseKey(group.imported)
    const last = blocks[blocks.length - 1]
    if (last && last.key === key) last.rooms.push(group)
    else blocks.push({ key, mark: group.imported, rooms: [group] })
  }
  return blocks
})
const roomsPerCourse = computed(() => {
  const counts = new Map<string | null, number>()
  for (const { imported } of shown.value) if (imported) counts.set(courseKey(imported), (counts.get(courseKey(imported)) ?? 0) + 1)
  return counts
})
/** The courses of earlier imports as first written, the one imported last first; the import offers them. */
const courses = computed(() => {
  const labels = new Map<string | null, string>()
  for (const { imported } of [...groupRooms.value].sort((a, b) => (a.imported?.importedAt ?? '').localeCompare(b.imported?.importedAt ?? ''))) if (imported?.course && !labels.has(courseKey(imported))) labels.set(courseKey(imported), imported.course)
  return [...labels.entries()].sort(([a], [b]) => (lastImport.value.get(b) ?? '').localeCompare(lastImport.value.get(a) ?? '')).map(([, label]) => label)
})

/** Reloads the rooms, such as after an import created some. */
const reload = async () => {
  try {
    groupRooms.value = await loadGroupRooms(await loadCollabKit(), { imported: props.imported })
  } catch (error) {
    notifyError(`The group models could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

/** The course asked to be archived, counted with all its rooms, also those the search hides. */
const asked = ref<{ course: string; rooms: number; models: number } | null>(null)
const archiving = ref(false)

const askArchive = (key: string | null, course: string) => {
  const all = groupRooms.value.filter((group) => courseKey(group.imported) === key)
  asked.value = { course, rooms: all.length, models: all.reduce((sum, group) => sum + group.models.length, 0) }
}

/** Sends the course to the archive; a room collab-kit refused is done by another try. */
const archiveCourse = async () => {
  if (!asked.value) return
  archiving.value = true
  try {
    const { data } = await httpClient.post<{ rooms: number; failed: string[] }>('/v1/group-work/archive', { course: asked.value.course })
    if (data.failed.length) notifyError(`Not archived: ${data.failed.join(', ')}. Archive the course again to finish.`)
    else notifySuccess(`${asked.value.course} archived with ${data.rooms} ${data.rooms === 1 ? 'room' : 'rooms'}.`)
    asked.value = null
    await reload()
    emit('archived')
  } catch (error) {
    notifyError(`The course could not be archived: ${(error as AxiosError<{ message?: string }>).response?.data?.message ?? (error as Error).message}`)
  } finally {
    archiving.value = false
  }
}

defineExpose({ reload, courses })

// The tab reloads on every opening; who works on what holds for that moment.
onMounted(reload)
</script>

<style scoped>
.member--new {
  border-style: dashed;
  opacity: 0.6;
}
</style>
