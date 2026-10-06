<template>
  <div class="collab-rooms">
    <div class="collab-rooms__list">
      <v-progress-linear v-if="loading" indeterminate />
      <v-list density="compact" nav>
        <v-list-item v-for="room in rooms" :key="room._id" :title="room.name" :subtitle="`${modelIdsOf(room).length} models`" :active="room._id === selectedId" @click="selectedId = room._id" />
      </v-list>
      <p v-if="!loading && rooms.length === 0" class="text-caption text-medium-emphasis px-2">No rooms yet</p>
      <div class="d-flex ga-2 mt-2">
        <v-text-field v-model="newRoomName" label="New room" density="compact" variant="outlined" hide-details @keyup.enter="addRoom" />
        <v-btn icon="mdi-plus" size="small" variant="tonal" :loading="busy === 'room'" aria-label="Create room" @click="addRoom" />
      </div>
    </div>

    <div v-if="selected" class="collab-rooms__detail">
      <v-text-field :model-value="selected.name" label="Name" density="compact" variant="outlined" disabled hint="Renaming needs collab-kit" persistent-hint />

      <div class="collab-rooms__label">Models in this room</div>
      <v-list density="compact" border rounded>
        <v-list-item v-for="model in models" :key="model._id" :title="model.name" :subtitle="model._id">
          <template #append>
            <v-btn icon="mdi-content-copy" size="small" variant="text" title="Copy ID" @click="copyId(model._id)" />
            <v-btn icon="mdi-link-variant-off" size="small" variant="text" title="Remove from room" :loading="busy === model._id" @click="removeModel(model._id)" />
          </template>
        </v-list-item>
        <v-list-item v-if="models.length === 0" subtitle="No models in this room" />
      </v-list>

      <div class="d-flex ga-2 mt-3">
        <v-text-field v-model="newModelName" label="New model" density="compact" variant="outlined" hide-details @keyup.enter="addModel" />
        <v-btn variant="tonal" prepend-icon="mdi-plus" :loading="busy === 'model'" @click="addModel">Create</v-btn>
      </div>
      <div class="d-flex ga-2 mt-3">
        <v-text-field v-model="existingId" label="Add existing model by ID" density="compact" variant="outlined" hide-details @keyup.enter="addExisting" />
        <v-btn variant="tonal" prepend-icon="mdi-link-variant" :loading="busy === 'existing'" @click="addExisting">Add</v-btn>
      </div>
      <p class="text-caption text-medium-emphasis mt-1 mb-0">A list of all models to choose from needs collab-kit.</p>

      <div class="collab-rooms__label">Access</div>
      <CollabAccessList :rows="accessRows" :options="groupOptions" add-label="Give a group access" empty-text="No group has access yet" :busy="busy" @change="changeAccess" @remove="removeAccess" @add="changeAccess" />

      <div class="d-flex align-center ga-2 mt-5">
        <v-btn variant="text" color="error" prepend-icon="mdi-delete-outline" disabled>Delete room</v-btn>
        <span class="text-caption text-medium-emphasis">Needs collab-kit</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { rightsOf, type AccessLevel } from './access'
import { addToRoom, createRoom, createWorkpieceInRoom, getRoom, getWorkpiece, listGrantsAt, removeFromRoom, removeGrant, setGrant, type CollabGrant, type CollabRoom, type CollabScope, type CollabWorkpiece } from './collabApi'
import CollabAccessList from './CollabAccessList.vue'
import { useCollabAction, useCollabDirectory } from './useCollabDirectory'

const { rooms, groups, loading, showRoom, groupName } = useCollabDirectory()
const { busy, run } = useCollabAction()

const selectedId = ref<string | null>(null)
const models = ref<CollabWorkpiece[]>([])
const grants = ref<CollabGrant[]>([])
const newRoomName = ref('')
const newModelName = ref('')
const existingId = ref('')

const selected = computed(() => rooms.value.find((room) => room._id === selectedId.value) ?? null)
const scope = computed<CollabScope | undefined>(() => (selected.value ? { kind: 'room', id: selected.value._id } : undefined))

const modelIdsOf = (room: CollabRoom) => room.references.filter((reference) => reference.kind === 'workpiece').map((reference) => reference.id)

const accessRows = computed(() => grants.value.map((grant) => ({ id: grant.groupId, label: groupName(grant.groupId), rights: grant.rights })))
const groupOptions = computed(() => groups.value.filter((group) => !grants.value.some((grant) => grant.groupId === group._id)).map((group) => ({ value: group._id, title: group.name })))

// A reference only names the workpiece; one that cannot be read still shows with its ID.
const loadDetail = async () => {
  const room = selected.value
  if (!room) {
    models.value = []
    grants.value = []
    return
  }
  const ids = modelIdsOf(room)
  const [found, held] = await Promise.all([Promise.allSettled(ids.map((id) => getWorkpiece(id))), listGrantsAt({ kind: 'room', id: room._id }).catch(() => null)])
  if (selected.value?._id !== room._id) return
  models.value = found.map((result, index) => (result.status === 'fulfilled' ? result.value.data : { _id: ids[index], name: '(not readable)', contract: {} }))
  grants.value = held?.data ?? []
}

const reloadGrants = async () => {
  if (scope.value) grants.value = (await listGrantsAt(scope.value)).data
}

const addRoom = () => {
  const name = newRoomName.value.trim()
  if (!name) return
  void run(
    'room',
    async () => {
      const room = (await createRoom(name)).data
      showRoom(room)
      selectedId.value = room._id
      newRoomName.value = ''
      notifySuccess('Room created')
    },
    'Room could not be created'
  )
}

const addModel = () => {
  const room = selected.value
  const name = newModelName.value.trim()
  if (!room || !name) return
  void run(
    'model',
    async () => {
      await createWorkpieceInRoom(room._id, name)
      showRoom((await getRoom(room._id)).data)
      newModelName.value = ''
      notifySuccess('Model created')
    },
    'Model could not be created'
  )
}

const addExisting = () => {
  const room = selected.value
  const id = existingId.value.trim()
  if (!room || !id) return
  void run(
    'existing',
    async () => {
      showRoom((await addToRoom(room._id, id)).data)
      existingId.value = ''
      notifySuccess('Model added to the room')
    },
    'Model could not be added'
  )
}

const removeModel = (id: string) => {
  const room = selected.value
  if (!room) return
  void run(
    id,
    async () => {
      showRoom((await removeFromRoom(room._id, id)).data)
      notifySuccess('Model taken out of the room')
    },
    'Model could not be taken out'
  )
}

// Setting replaces what the group had here, so adding and changing are the same call.
const changeAccess = (groupId: string, level: AccessLevel) => {
  void run(
    groupId,
    async () => {
      await setGrant(groupId, scope.value, rightsOf(level))
      await reloadGrants()
      notifySuccess('Access changed')
    },
    'Access could not be changed'
  )
}

const removeAccess = (groupId: string) => {
  void run(
    groupId,
    async () => {
      await removeGrant(groupId, scope.value)
      await reloadGrants()
      notifySuccess('Access removed')
    },
    'Access could not be removed'
  )
}

const copyId = async (id: string) => {
  try {
    await navigator.clipboard.writeText(id)
    notifySuccess('ID copied')
  } catch {
    notifyError('ID could not be copied')
  }
}

// The first room is shown once the list is in; a changed room from collab-kit replaces the selected object.
watch(rooms, () => (selectedId.value ??= rooms.value[0]?._id ?? null), { immediate: true, deep: true })
watch(selected, loadDetail, { immediate: true })
</script>

<style scoped>
.collab-rooms {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 24px;
  min-height: 360px;
}

.collab-rooms__list {
  border-right: 1px solid rgba(var(--v-theme-outline), 0.15);
  padding-right: 16px;
}

.collab-rooms__label {
  margin: 20px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
</style>
