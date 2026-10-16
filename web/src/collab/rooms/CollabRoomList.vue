<template>
  <div class="collab-room-list">
    <div class="collab-room-list__header">
      <span>My rooms</span>
      <div>
        <v-btn icon="mdi-refresh" size="x-small" variant="text" :loading="loading" aria-label="Reload rooms" @click="load" />
        <v-btn :icon="listOpen ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="listOpen ? 'Collapse rooms' : 'Expand rooms'" @click="listOpen = !listOpen" />
      </div>
    </div>
    <v-expand-transition>
      <div v-show="listOpen" class="collab-room-list__body">
        <div v-if="!loading && rooms.length === 0" class="collab-room-list__empty">No rooms yet</div>
        <v-list v-model:opened="openedRooms" density="compact" class="py-0">
          <v-list-group v-for="room in rooms" :key="room._id" :value="room._id">
            <template #activator="{ props: activator }">
              <v-list-item v-bind="activator" :title="room.name" :subtitle="`${(models[room._id] ?? []).length} models`" prepend-icon="mdi-door" />
            </template>
            <v-list-item v-for="model in models[room._id] ?? []" :key="model._id" :title="model.name" prepend-icon="mdi-vector-square" :active="model._id === activeWorkpieceId" @click="emit('open', room, model)">
              <template v-if="model._id === activeWorkpieceId" #append>
                <v-icon :icon="connected ? 'mdi-lan-connect' : 'mdi-lan-disconnect'" size="small" :color="connected ? 'success' : undefined" />
              </template>
            </v-list-item>
            <v-list-item v-if="(models[room._id] ?? []).length === 0" subtitle="No models in this room" />
          </v-list-group>
        </v-list>
      </div>
    </v-expand-transition>
  </div>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so what is open stays while another sidebar tab is shown.
const listOpen = ref(true)
const openedRooms = ref<string[]>([])
let openedFor: string | null = null
</script>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage } from '@/collab/connection/collabApi'
import { loadCollabKit } from '@/collab/connection/collabKit'
import type { Room, Workpiece } from '@/collab/connection/collabKitV1'

const props = defineProps<{ activeWorkpieceId: string | null; connected: boolean }>()
const emit = defineEmits<{ open: [room: Room, workpiece: Workpiece] }>()

const rooms = ref<Room[]>([])
const models = ref<Record<string, Workpiece[]>>({})
const loading = ref(false)

// Every room the token may see, with the models in it it may read.
const load = async () => {
  loading.value = true
  try {
    const ck = await loadCollabKit()
    rooms.value = (await ck.me.rooms()).sort((a, b) => a.name.localeCompare(b.name))
    const entries = await Promise.all(
      rooms.value.map(async (room) => {
        const found = await Promise.allSettled(room.workpieces.map((id) => ck.workpieces.get(id)))
        return [room._id, found.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : []))] as const
      })
    )
    models.value = Object.fromEntries(entries)
    openActiveRoom()
  } catch (error) {
    notifyError(`Rooms could not be loaded: ${collabErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

// The room of a newly opened model opens by itself; what else is open stays as the person left it.
const openActiveRoom = () => {
  const id = props.activeWorkpieceId
  const room = rooms.value.find((entry) => id && entry.workpieces.includes(id))
  if (!id || id === openedFor || !room) return
  openedFor = id
  if (!openedRooms.value.includes(room._id)) openedRooms.value = [...openedRooms.value, room._id]
}

watch(() => props.activeWorkpieceId, openActiveRoom)
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
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.collab-room-list__body {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

.collab-room-list__empty {
  padding: 8px 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.52);
}
</style>
