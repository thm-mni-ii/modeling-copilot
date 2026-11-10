<template>
  <div v-if="loading" class="d-flex justify-center py-8"><v-progress-circular indeterminate color="primary" /></div>
  <p v-else-if="!groupRooms.length" class="text-medium-emphasis text-center py-8 mb-0">No group models yet.</p>
  <template v-else>
    <v-card v-for="{ room, models } in groupRooms" :key="room._id" variant="outlined" class="mb-4">
      <v-card-title>{{ room.name }}</v-card-title>
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

<script setup lang="ts">
import { onMounted, ref, shallowRef } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { loadGroupRooms, type GroupRoom } from '@/collab/groups/groupRooms'

const headers = [
  { title: 'Model', key: 'name', sortable: false },
  { title: 'Task', key: 'task', sortable: false },
  { title: 'Working now', key: 'people', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false }
]

const { openFromRoom } = useCollabConnection()
const groupRooms = shallowRef<GroupRoom[]>([])
const loading = ref(true)

// Der Reiter lädt bei jedem Öffnen neu; wer gerade woran arbeitet, gilt für diesen Moment.
onMounted(async () => {
  try {
    groupRooms.value = await loadGroupRooms(await loadCollabKit())
  } catch (error) {
    notifyError(`The group models could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
})
</script>
