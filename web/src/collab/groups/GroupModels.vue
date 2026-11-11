<template>
  <div v-if="loading" class="d-flex justify-center py-8"><v-progress-circular indeterminate color="primary" /></div>
  <p v-else-if="!groupRooms.length" class="text-medium-emphasis text-center py-8 mb-0">{{ imported ? 'No group work imported yet. Import a CSV to create the rooms.' : 'No group models yet.' }}</p>
  <p v-else-if="!shown.length" class="text-medium-emphasis text-center py-8 mb-0">No room matches the search.</p>
  <template v-else>
    <template v-for="({ room, models, imported: mark, members }, index) in shown" :key="room._id">
      <!-- Importierte Räume stehen nach Kurs, der zuletzt importierte oben; jeder Kurs bekommt eine Zeile darüber. -->
      <p v-if="mark && courseKey(mark) !== courseKey(shown[index - 1]?.imported)" class="text-subtitle-2 mt-4 mb-2">
        {{ mark.course || 'Without course' }} <span class="text-medium-emphasis font-weight-regular">· {{ roomsPerCourse.get(courseKey(mark)) }} {{ roomsPerCourse.get(courseKey(mark)) === 1 ? 'room' : 'rooms' }} · last import {{ formattedDate(lastImport.get(courseKey(mark)) ?? mark.importedAt) }}</span>
      </p>
      <v-card variant="outlined" class="mb-4">
        <v-card-title class="d-flex align-center flex-wrap ga-2">
          <span>{{ room.name }}</span>
          <v-spacer />
          <v-chip v-for="name in members" :key="name" size="small" prepend-icon="mdi-account-outline">{{ name }}</v-chip>
        </v-card-title>
        <v-data-table :headers="headers" :items="models" :items-per-page="-1" item-value="workpiece._id" no-data-text="No models in this room yet.">
          <template #[`item.name`]="{ item }">{{ item.workpiece.name }}</template>
          <template #[`item.task`]="{ item }">{{ item.task ?? '—' }}</template>
          <template #[`item.people`]="{ item }"
            ><v-chip v-for="name in item.people" :key="name" size="small" class="mr-1">{{ name }}</v-chip
            ><span v-if="!item.people.length" class="text-medium-emphasis">—</span></template
          >
          <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary" @click="openFromRoom(room, item.workpiece)">Open</v-btn></template>
          <!-- Vuetify 3.5 kennt hide-default-footer noch nicht; ein leerer Slot ersetzt die Fußzeile. -->
          <template #bottom />
        </v-data-table>
      </v-card>
    </template>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { loadGroupRooms, type GroupRoom, type GroupWorkMark } from '@/collab/groups/groupRooms'

/** `imported`: nur die Räume aus einer Teilnehmerliste, mit Import und Mitgliedern, wie der Reiter „Group work“ sie zeigt. */
const props = withDefaults(defineProps<{ imported?: boolean; search?: string }>(), { imported: false, search: '' })

const headers = [
  { title: 'Model', key: 'name', sortable: false },
  { title: 'Task', key: 'task', sortable: false },
  { title: 'Working now', key: 'people', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false }
]

const { openFromRoom } = useCollabConnection()
const groupRooms = shallowRef<GroupRoom[]>([])
const loading = ref(true)

const formattedDate = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

/** Wie das Backend Kurse vergleicht: Groß- und Kleinschreibung und Leerzeichen zählen nicht. */
const courseKey = (mark: GroupWorkMark | undefined) => (mark ? mark.course.split(/\s+/).filter(Boolean).join(' ').toLowerCase() : null)

/** Der jüngste Import je Kurs; danach stehen die Kurse, der zuletzt importierte oben. */
const lastImport = computed(() => {
  const last = new Map<string | null, string>()
  for (const { imported } of groupRooms.value) if (imported && (last.get(courseKey(imported)) ?? '') < imported.importedAt) last.set(courseKey(imported), imported.importedAt)
  return last
})

// Gesucht wird in Raum, Kurs, Mitgliedern und Modellen; importierte Räume nach Kurs, darin nach Namen.
const shown = computed(() => {
  const text = props.search.trim().toLowerCase()
  const matches = (group: GroupRoom) => !text || [group.room.name, group.imported?.course ?? '', ...(group.members ?? []), ...group.models.map((model) => model.workpiece.name)].some((value) => value.toLowerCase().includes(text))
  const recency = (group: GroupRoom) => lastImport.value.get(courseKey(group.imported)) ?? ''
  const byCourse = (a: GroupRoom, b: GroupRoom) => recency(b).localeCompare(recency(a)) || (courseKey(a.imported) ?? '').localeCompare(courseKey(b.imported) ?? '') || a.room.name.localeCompare(b.room.name, undefined, { numeric: true })
  return groupRooms.value.filter(matches).sort(byCourse)
})
const roomsPerCourse = computed(() => {
  const counts = new Map<string | null, number>()
  for (const { imported } of shown.value) if (imported) counts.set(courseKey(imported), (counts.get(courseKey(imported)) ?? 0) + 1)
  return counts
})
/** Die Kurse früherer Importe, wie sie zuerst geschrieben wurden, der zuletzt importierte zuerst; der Import schlägt sie vor. */
const courses = computed(() => {
  const labels = new Map<string | null, string>()
  for (const { imported } of [...groupRooms.value].sort((a, b) => (a.imported?.importedAt ?? '').localeCompare(b.imported?.importedAt ?? ''))) if (imported?.course && !labels.has(courseKey(imported))) labels.set(courseKey(imported), imported.course)
  return [...labels.entries()].sort(([a], [b]) => (lastImport.value.get(b) ?? '').localeCompare(lastImport.value.get(a) ?? '')).map(([, label]) => label)
})

/** Lädt die Räume neu, etwa nachdem ein Import welche angelegt hat. */
const reload = async () => {
  try {
    groupRooms.value = await loadGroupRooms(await loadCollabKit(), { imported: props.imported })
  } catch (error) {
    notifyError(`The group models could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

defineExpose({ reload, courses })

// Der Reiter lädt bei jedem Öffnen neu; wer gerade woran arbeitet, gilt für diesen Moment.
onMounted(reload)
</script>
