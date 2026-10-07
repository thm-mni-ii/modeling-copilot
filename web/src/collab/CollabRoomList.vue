<template>
  <div class="collab-room-list">
    <div class="collab-room-list__header">
      <span>My rooms</span>
      <v-btn icon="mdi-refresh" size="x-small" variant="text" :loading="loading" aria-label="Reload rooms" @click="load" />
    </div>
    <div v-if="!loading && rooms.length === 0" class="collab-room-list__empty">No rooms yet</div>
    <v-list density="compact" class="py-0">
      <template v-for="room in rooms" :key="room._id">
        <v-list-subheader>{{ room.name }}</v-list-subheader>
        <v-list-item v-for="model in models[room._id] ?? []" :key="model._id" :title="model.name" prepend-icon="mdi-vector-square" :active="model._id === activeWorkpieceId" @click="emit('open', room, model)">
          <template v-if="model._id === activeWorkpieceId" #append>
            <v-icon :icon="connected ? 'mdi-lan-connect' : 'mdi-lan-disconnect'" size="small" :color="connected ? 'success' : undefined" />
          </template>
        </v-list-item>
        <v-list-item v-if="(models[room._id] ?? []).length === 0" subtitle="No models in this room" />
      </template>
    </v-list>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, getWorkpiece, listRooms, type CollabRoom, type CollabWorkpiece } from './collabApi'

defineProps<{ activeWorkpieceId: string | null; connected: boolean }>()
const emit = defineEmits<{ open: [room: CollabRoom, workpiece: CollabWorkpiece] }>()

const rooms = ref<CollabRoom[]>([])
const models = ref<Record<string, CollabWorkpiece[]>>({})
const loading = ref(false)

// Every room the token may see, with the models in it it may read.
const load = async () => {
  loading.value = true
  try {
    rooms.value = (await listRooms()).data.sort((a, b) => a.name.localeCompare(b.name))
    const entries = await Promise.all(
      rooms.value.map(async (room) => {
        const ids = room.references.filter((reference) => reference.kind === 'workpiece').map((reference) => reference.id)
        const found = await Promise.allSettled(ids.map((id) => getWorkpiece(id)))
        return [room._id, found.flatMap((result) => (result.status === 'fulfilled' ? [result.value.data] : []))] as const
      })
    )
    models.value = Object.fromEntries(entries)
  } catch (error) {
    notifyError(`Rooms could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.collab-room-list {
  /* The sync sidebar scrolls instead; with overflow hidden it could squeeze the box down to its header. */
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.collab-room-list__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 4px 10px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.15);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.collab-room-list__empty {
  padding: 8px 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.52);
}
</style>
