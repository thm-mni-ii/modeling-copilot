<template>
  <div v-if="loading" class="d-flex justify-center py-8"><v-progress-circular indeterminate color="primary" /></div>
  <p v-else-if="!groupRooms.length" class="text-medium-emphasis text-center py-8 mb-0">{{ imported ? 'No group work imported yet. Import a CSV to create the rooms.' : 'No group models yet.' }}</p>
  <p v-else-if="!shown.length" class="text-medium-emphasis text-center py-8 mb-0">No room matches the search.</p>
  <template v-else>
    <template v-for="({ room, models, imported: mark, members }, index) in shown" :key="room._id">
      <!-- Importierte Räume stehen nach Import, der neueste oben; jeder Import bekommt eine Zeile darüber. -->
      <p v-if="mark && mark.importedAt !== shown[index - 1]?.imported?.importedAt" class="text-body-2 text-medium-emphasis mt-2 mb-2">Imported {{ formattedDate(mark.importedAt) }} · {{ roomsPerImport.get(mark.importedAt) }} {{ roomsPerImport.get(mark.importedAt) === 1 ? 'room' : 'rooms' }}</p>
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
import { loadGroupRooms, type GroupRoom } from '@/collab/groups/groupRooms'

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

// Gesucht wird in Raum, Mitgliedern und Modellen; importierte Räume nach Import, der neueste zuerst, darin nach Namen.
const shown = computed(() => {
  const text = props.search.trim().toLowerCase()
  const matches = (group: GroupRoom) => !text || [group.room.name, ...(group.members ?? []), ...group.models.map((model) => model.workpiece.name)].some((value) => value.toLowerCase().includes(text))
  const byImport = (a: GroupRoom, b: GroupRoom) => (b.imported?.importedAt ?? '').localeCompare(a.imported?.importedAt ?? '') || a.room.name.localeCompare(b.room.name, undefined, { numeric: true })
  return groupRooms.value.filter(matches).sort(byImport)
})
const roomsPerImport = computed(() => {
  const counts = new Map<string, number>()
  for (const { imported } of shown.value) if (imported) counts.set(imported.importedAt, (counts.get(imported.importedAt) ?? 0) + 1)
  return counts
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

defineExpose({ reload })

// Der Reiter lädt bei jedem Öffnen neu; wer gerade woran arbeitet, gilt für diesen Moment.
onMounted(reload)
</script>
