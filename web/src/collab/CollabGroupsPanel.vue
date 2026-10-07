<template>
  <div class="collab-groups">
    <div class="collab-groups__list">
      <v-progress-linear v-if="loading" indeterminate />
      <v-list density="compact" nav>
        <v-list-item v-for="group in groups" :key="group._id" :title="group.name" :subtitle="`${group.members.length} members`" :active="group._id === selectedId" @click="selectedId = group._id" />
      </v-list>
      <p v-if="!loading && groups.length === 0" class="text-caption text-medium-emphasis px-2">No groups found</p>
      <div class="d-flex ga-2 mt-2">
        <v-text-field v-model="newGroupName" label="New group" density="compact" variant="outlined" hide-details @keyup.enter="addGroup" />
        <v-btn icon="mdi-plus" size="small" variant="tonal" :loading="busy === 'group'" aria-label="Create group" @click="addGroup" />
      </div>
    </div>

    <div v-if="selected" class="collab-groups__detail">
      <v-text-field v-model="nameDraft" label="Name" density="compact" variant="outlined" hide-details :loading="busy === 'rename'" @keyup.enter="saveName">
        <template #append-inner>
          <v-btn v-if="nameDraft.trim() !== selected.name" icon="mdi-check" size="x-small" variant="text" aria-label="Save name" @click="saveName" />
        </template>
      </v-text-field>

      <div class="collab-groups__label">Members</div>
      <v-list density="compact" border rounded>
        <v-list-item v-for="member in selected.members" :key="member" :title="actorName(member)" :subtitle="`Feedbacksystem ID ${member}`">
          <template #append>
            <v-btn icon="mdi-account-remove-outline" size="small" variant="text" title="Remove member" :loading="busy === `member:${member}`" @click="removeFromGroup(member)" />
          </template>
        </v-list-item>
        <v-list-item v-if="selected.members.length === 0" subtitle="No members yet" />
      </v-list>
      <div class="d-flex ga-2 mt-3">
        <v-text-field v-model="newMember" label="Add member by Feedbacksystem user ID" density="compact" variant="outlined" hide-details @keyup.enter="addToGroup" />
        <v-btn variant="tonal" prepend-icon="mdi-account-plus-outline" :loading="busy === 'member'" @click="addToGroup">Add</v-btn>
      </div>

      <div class="collab-groups__label">Access</div>
      <CollabAccessList :rows="accessRows" :options="placeOptions" add-label="Give access to" empty-text="This group has no access yet" :busy="busy" @change="changeAccess" @remove="removeAccess" @add="changeAccess" />

      <v-btn class="mt-5" variant="text" color="error" prepend-icon="mdi-delete-outline" :loading="busy === 'delete'" @click="removeGroup">Delete group</v-btn>
    </div>
    <DialogConfirm ref="confirmDialog" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DialogConfirm from '@/components/dialog/DialogConfirm.vue'
import { notifySuccess } from '@/composables/useNotifications'
import { rightsOf, type AccessLevel } from './access'
import { addMember, createGroup, deleteGroup, listGrantsOf, removeGrant, removeMember, renameGroup, setGrant, type CollabGrant, type CollabScope } from './collabApi'
import CollabAccessList from './CollabAccessList.vue'
import { useCollabAction, useCollabDirectory } from './useCollabDirectory'

const { rooms, groups, loading, loadNames, showGroup, dropGroup, roomName, actorName } = useCollabDirectory()
const { busy, run } = useCollabAction()

const selectedId = ref<string | null>(null)
const grants = ref<CollabGrant[]>([])
const newGroupName = ref('')
const newMember = ref('')
const nameDraft = ref('')
const confirmDialog = ref<InstanceType<typeof DialogConfirm> | null>(null)

// Access rows and options are keyed by place: a room, another place of collab-kit, or everywhere.
const EVERYWHERE = 'everywhere'
const keyOf = (scope?: CollabScope) => (scope ? `${scope.kind}:${scope.id}` : EVERYWHERE)
const scopeOf = (key: string): CollabScope | undefined => {
  if (key === EVERYWHERE) return undefined
  const [kind, id] = key.split(':')
  return { kind, id }
}
const labelOf = (scope?: CollabScope) => (!scope ? 'Everywhere' : scope.kind === 'room' ? roomName(scope.id) : `${scope.kind} ${scope.id}`)

const selected = computed(() => groups.value.find((group) => group._id === selectedId.value) ?? null)
const accessRows = computed(() => grants.value.map((grant) => ({ id: keyOf(grant.scope), label: labelOf(grant.scope), rights: grant.rights })))
const placeOptions = computed(() => {
  const held = new Set(grants.value.map((grant) => keyOf(grant.scope)))
  const places = [...rooms.value.map((room) => ({ value: keyOf({ kind: 'room', id: room._id }), title: room.name })), { value: EVERYWHERE, title: 'Everywhere' }]
  return places.filter((place) => !held.has(place.value))
})

const loadGrants = async () => {
  const group = selected.value
  if (!group) {
    grants.value = []
    return
  }
  const held = await listGrantsOf(group._id).catch(() => null)
  if (selected.value?._id === group._id) grants.value = held?.data ?? []
}

const addGroup = () => {
  const name = newGroupName.value.trim()
  if (!name) return
  void run(
    'group',
    async () => {
      const group = (await createGroup(name)).data
      showGroup(group)
      selectedId.value = group._id
      newGroupName.value = ''
      notifySuccess('Group created')
    },
    'Group could not be created'
  )
}

const saveName = () => {
  const group = selected.value
  const name = nameDraft.value.trim()
  if (!group || !name || name === group.name) return
  void run(
    'rename',
    async () => {
      showGroup((await renameGroup(group._id, name)).data)
      notifySuccess('Group renamed')
    },
    'Group could not be renamed'
  )
}

const removeGroup = async () => {
  const group = selected.value
  if (!group) return
  const confirmed = await confirmDialog.value?.openDialog(`Delete group "${group.name}"?`, 'Its members lose the access the group gave them, at once.', 'Delete')
  if (!confirmed) return
  void run(
    'delete',
    async () => {
      await deleteGroup(group._id)
      dropGroup(group._id)
      selectedId.value = groups.value[0]?._id ?? null
      notifySuccess('Group deleted')
    },
    'Group could not be deleted'
  )
}

const addToGroup = () => {
  const group = selected.value
  const actorId = newMember.value.trim()
  if (!group || !actorId) return
  void run(
    'member',
    async () => {
      showGroup((await addMember(group._id, actorId)).data)
      await loadNames([actorId])
      newMember.value = ''
      notifySuccess('Member added')
    },
    'Member could not be added'
  )
}

const removeFromGroup = (actorId: string) => {
  const group = selected.value
  if (!group) return
  void run(
    `member:${actorId}`,
    async () => {
      showGroup((await removeMember(group._id, actorId)).data)
      notifySuccess('Member removed')
    },
    'Member could not be removed'
  )
}

// Setting replaces what the group had at that place, so adding and changing are the same call.
const changeAccess = (key: string, level: AccessLevel) => {
  const group = selected.value
  if (!group) return
  void run(
    key,
    async () => {
      await setGrant(group._id, scopeOf(key), rightsOf(level))
      await loadGrants()
      notifySuccess('Access changed')
    },
    'Access could not be changed'
  )
}

const removeAccess = (key: string) => {
  const group = selected.value
  if (!group) return
  void run(
    key,
    async () => {
      await removeGrant(group._id, scopeOf(key))
      await loadGrants()
      notifySuccess('Access removed')
    },
    'Access could not be removed'
  )
}

watch(groups, () => (selectedId.value ??= groups.value[0]?._id ?? null), { immediate: true, deep: true })
// Only a change of group reloads its access; adding a member keeps what it has.
watch(selectedId, loadGrants, { immediate: true })
watch(selected, (group) => (nameDraft.value = group?.name ?? ''), { immediate: true })
</script>

<style scoped>
.collab-groups {
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 260px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 24px;
  min-height: 0;
}

/* Each side scrolls on its own, so the list stays in view while the details run long. */
.collab-groups__list,
.collab-groups__detail {
  min-height: 0;
  overflow-y: auto;
}

.collab-groups__list {
  border-right: 1px solid rgba(var(--v-theme-outline), 0.15);
  padding-right: 16px;
}

.collab-groups__detail {
  padding-right: 8px;
}

.collab-groups__label {
  margin: 20px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
</style>
