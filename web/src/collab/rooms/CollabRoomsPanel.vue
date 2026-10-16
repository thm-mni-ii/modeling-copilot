<template>
  <div class="collab-rooms">
    <v-card class="collab-rooms__list" variant="outlined">
      <v-progress-linear v-if="loading" indeterminate />
      <v-list density="compact" nav class="collab-rooms__items">
        <v-list-item v-for="room in rooms" :key="room._id" :title="room.name" :subtitle="`${room.workpieces.length} models`" :active="room._id === selectedId" color="primary" rounded="lg" prepend-icon="mdi-door" @click="selectedId = room._id" />
        <v-list-item v-if="!loading && rooms.length === 0" disabled title="No rooms yet." />
      </v-list>
    </v-card>

    <v-card v-if="selected" class="collab-rooms__detail" variant="outlined">
      <v-card-title class="d-flex align-center ga-2">
        <v-text-field v-model="nameDraft" label="Room name" density="compact" variant="outlined" hide-details :loading="busy === 'rename'" @keyup.enter="saveName">
          <template #append-inner>
            <v-btn v-if="nameDraft.trim() !== selected.name" icon="mdi-check" size="x-small" variant="text" aria-label="Save name" @click="saveName" />
          </template>
        </v-text-field>
        <v-btn icon="mdi-delete-outline" color="error" variant="text" title="Delete room" :loading="busy === 'delete'" @click="removeRoom" />
      </v-card-title>
      <v-divider />
      <v-card-text class="collab-rooms__content">
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
          <v-select v-model="newModelLanguage" :items="languages" item-title="name" item-value="id" label="Language" density="compact" variant="outlined" hide-details class="collab-rooms__language" />
          <v-btn variant="tonal" prepend-icon="mdi-plus" :loading="busy === 'model'" @click="addModel">Create</v-btn>
        </div>
        <div class="d-flex ga-2 mt-3">
          <v-autocomplete v-model="existingId" :items="existingOptions" label="Add an existing model" density="compact" variant="outlined" hide-details />
          <v-btn variant="tonal" prepend-icon="mdi-link-variant" :disabled="!existingId" :loading="busy === 'existing'" @click="addExisting">Add</v-btn>
        </div>

        <div class="collab-rooms__label">Access</div>
        <CollabAccessList :rows="accessRows" :options="groupOptions" add-label="Give a group access" empty-text="No group has access yet" :busy="busy" @change="changeAccess" @remove="removeAccess" @add="changeAccess" />
      </v-card-text>
    </v-card>

    <v-card v-else class="collab-rooms__detail d-flex align-center justify-center" variant="outlined">
      <div class="text-center text-medium-emphasis">
        <v-icon size="48">mdi-door</v-icon>
        <div class="mt-2">Select a room or create a new one.</div>
      </div>
    </v-card>

    <v-dialog v-model="createDialog" max-width="520">
      <v-card>
        <v-card-title>Create room</v-card-title>
        <v-card-text><v-text-field v-model="newRoomName" label="Room name" autofocus @keyup.enter="addRoom" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="createDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!newRoomName.trim()" :loading="busy === 'room'" @click="addRoom">Create</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <DialogConfirm ref="confirmDialog" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import type { LanguageOverview } from '@/services/api/types/language'
import languageService from '@/services/language/language.service'
import DialogConfirm from '@/components/dialog/DialogConfirm.vue'
import { rightsOf, type AccessLevel } from './access'
import { newWorkpiece, TOOL_SETTINGS } from '@/collab/connection/collabApi'
import { loadCollabKit } from '@/collab/connection/collabKit'
import type { CollabKitApi, Grant, Reference, Workpiece } from '@/collab/connection/collabKitV1'
import CollabAccessList from './CollabAccessList.vue'
import { UML_CLASS_DIAGRAM } from '@/collab/connection/openWorkpiece'
import { useCollabAction, useCollabDirectory } from './useCollabDirectory'

const { rooms, groups, workpieces, loading, showRoom, showWorkpiece, dropRoom, groupName } = useCollabDirectory()
const { busy, run } = useCollabAction()

const selectedId = ref<string | null>(null)
const models = ref<Pick<Workpiece, '_id' | 'name'>[]>([])
const grants = ref<Grant[]>([])
const newRoomName = ref('')
const createDialog = ref(false)
const newModelName = ref('')
const existingId = ref<string | null>(null)
const nameDraft = ref('')
const confirmDialog = ref<InstanceType<typeof DialogConfirm> | null>(null)
const languages = ref<LanguageOverview[]>([])
const newModelLanguage = ref<string | null>(null)

const selected = computed(() => rooms.value.find((room) => room._id === selectedId.value) ?? null)
const scope = computed<Reference | undefined>(() => (selected.value ? { kind: 'room', id: selected.value._id } : undefined))

const accessRows = computed(() => grants.value.map((grant) => ({ id: grant.groupId, label: groupName(grant.groupId), rights: grant.rights })))
// Every model collab-kit lists that is not in this room yet, with the end of its ID to tell equal names apart.
const existingOptions = computed(() => {
  const inRoom = new Set(selected.value?.workpieces)
  return workpieces.value.filter((workpiece) => !inRoom.has(workpiece._id)).map((workpiece) => ({ value: workpiece._id, title: `${workpiece.name} · ${workpiece._id.slice(-6)}` }))
})
const groupOptions = computed(() => groups.value.filter((group) => !grants.value.some((grant) => grant.groupId === group._id)).map((group) => ({ value: group._id, title: group.name })))

// The room only names its workpieces; one that cannot be read still shows with its ID.
const loadDetail = async () => {
  const room = selected.value
  if (!room) {
    models.value = []
    grants.value = []
    return
  }
  const ck = await loadCollabKit()
  const ids = room.workpieces
  const [found, held] = await Promise.all([Promise.allSettled(ids.map((id) => ck.workpieces.get(id))), ck.grants.list({ scope: { kind: 'room', id: room._id } }).catch(() => null)])
  if (selected.value?._id !== room._id) return
  models.value = found.map((result, index) => (result.status === 'fulfilled' ? result.value : { _id: ids[index], name: '(not readable)' }))
  grants.value = held ?? []
}

const reloadGrants = async (ck: CollabKitApi) => {
  if (scope.value) grants.value = await ck.grants.list({ scope: scope.value })
}

const addRoom = () => {
  const name = newRoomName.value.trim()
  if (!name) return
  void run(
    'room',
    async (ck) => {
      const room = await ck.rooms.create({ name, settings: TOOL_SETTINGS })
      showRoom(room)
      selectedId.value = room._id
      newRoomName.value = ''
      createDialog.value = false
      notifySuccess('Room created')
    },
    'Room could not be created'
  )
}

// Every own model of the workpiece starts with this language; the UML class diagram unless another is chosen.
const loadLanguages = async () => {
  try {
    languages.value = (await languageService.list(0, 100)).data.items.filter((language) => language.latestVersionId)
  } catch (error) {
    notifyError(`Languages could not be loaded: ${(error as Error).message}`)
  }
  newModelLanguage.value = languages.value.find((language) => language.id === UML_CLASS_DIAGRAM.languageId)?.id ?? languages.value[0]?.id ?? null
}

const addModel = () => {
  const room = selected.value
  const name = newModelName.value.trim()
  const language = languages.value.find((entry) => entry.id === newModelLanguage.value)
  if (!room || !name) return
  if (!language?.latestVersionId) {
    notifyError('Choose a language for the model')
    return
  }
  const versionId = language.latestVersionId
  void run(
    'model',
    async (ck) => {
      showWorkpiece(await ck.workpieces.create(newWorkpiece(room._id, name, [{ languageId: language.id, versionId, source: 'required' }])))
      showRoom(await ck.rooms.get(room._id))
      newModelName.value = ''
      notifySuccess('Model created')
    },
    'Model could not be created'
  )
}

const addExisting = () => {
  const room = selected.value
  const id = existingId.value
  if (!room || !id) return
  void run(
    'existing',
    async (ck) => {
      showRoom(await ck.rooms.addWorkpiece(room._id, id))
      existingId.value = null
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
    async (ck) => {
      showRoom(await ck.rooms.removeWorkpiece(room._id, id))
      notifySuccess('Model taken out of the room')
    },
    'Model could not be taken out'
  )
}

// Setting replaces what the group had here, so adding and changing are the same call.
const changeAccess = (groupId: string, level: AccessLevel) => {
  void run(
    groupId,
    async (ck) => {
      await ck.grants.set({ groupId, scope: scope.value, rights: rightsOf(level) })
      await reloadGrants(ck)
      notifySuccess('Access changed')
    },
    'Access could not be changed'
  )
}

const removeAccess = (groupId: string) => {
  void run(
    groupId,
    async (ck) => {
      await ck.grants.remove({ groupId, scope: scope.value })
      await reloadGrants(ck)
      notifySuccess('Access removed')
    },
    'Access could not be removed'
  )
}

const saveName = () => {
  const room = selected.value
  const name = nameDraft.value.trim()
  if (!room || !name || name === room.name) return
  void run(
    'rename',
    async (ck) => {
      showRoom(await ck.rooms.update(room._id, { name }))
      notifySuccess('Room renamed')
    },
    'Room could not be renamed'
  )
}

const removeRoom = async () => {
  const room = selected.value
  if (!room) return
  const confirmed = await confirmDialog.value?.openDialog(`Delete room "${room.name}"?`, 'Its models stay and can be put into another room. Everyone who had access only through this room loses it at once.', 'Delete')
  if (!confirmed) return
  void run(
    'delete',
    async (ck) => {
      await ck.rooms.remove(room._id)
      dropRoom(room._id)
      selectedId.value = rooms.value[0]?._id ?? null
      notifySuccess('Room deleted')
    },
    'Room could not be deleted'
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
watch(selected, (room) => (nameDraft.value = room?.name ?? ''), { immediate: true })
onMounted(loadLanguages)

// The page holds the button for a new room, the dialog stays here with what it creates.
defineExpose({ openCreate: () => (createDialog.value = true) })
</script>

<style scoped>
.collab-rooms {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 12px;
}

.collab-rooms__list {
  width: 300px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
}

.collab-rooms__detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* List and details scroll each on their own, so the list stays in view while the details run long. */
.collab-rooms__items,
.collab-rooms__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.collab-rooms__language {
  flex: 0 0 200px;
}

.collab-rooms__label {
  margin: 20px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.collab-rooms__label:first-child {
  margin-top: 0;
}
</style>
