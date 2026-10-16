<template>
  <div class="collab-groups">
    <v-card class="collab-groups__list" variant="outlined">
      <v-progress-linear v-if="loading" indeterminate />
      <v-list density="compact" nav class="collab-groups__items">
        <v-list-item v-for="group in groups" :key="group._id" :title="group.name" :subtitle="`${group.members.length} members`" :active="group._id === selectedId" color="primary" rounded="lg" prepend-icon="mdi-account-multiple-outline" @click="selectedId = group._id" />
        <v-list-item v-if="!loading && groups.length === 0" disabled title="No groups yet." />
      </v-list>
    </v-card>

    <v-card v-if="selected" class="collab-groups__detail" variant="outlined">
      <v-card-title class="d-flex align-center ga-2">
        <v-text-field v-model="nameDraft" label="Group name" density="compact" variant="outlined" hide-details :loading="busy === 'rename'" @keyup.enter="saveName">
          <template #append-inner>
            <v-btn v-if="nameDraft.trim() !== selected.name" icon="mdi-check" size="x-small" variant="text" aria-label="Save name" @click="saveName" />
          </template>
        </v-text-field>
        <v-btn icon="mdi-delete-outline" color="error" variant="text" title="Delete group" :loading="busy === 'delete'" @click="removeGroup" />
      </v-card-title>
      <v-divider />
      <v-card-text class="collab-groups__content">
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
      </v-card-text>
    </v-card>

    <v-card v-else class="collab-groups__detail d-flex align-center justify-center" variant="outlined">
      <div class="text-center text-medium-emphasis">
        <v-icon size="48">mdi-account-multiple-outline</v-icon>
        <div class="mt-2">Select a group or create a new one.</div>
      </div>
    </v-card>

    <v-dialog v-model="createDialog" max-width="520">
      <v-card>
        <v-card-title>Create group</v-card-title>
        <v-card-text><v-text-field v-model="newGroupName" label="Group name" autofocus @keyup.enter="addGroup" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="createDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!newGroupName.trim()" :loading="busy === 'group'" @click="addGroup">Create</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <DialogConfirm ref="confirmDialog" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DialogConfirm from '@/components/dialog/DialogConfirm.vue'
import { notifySuccess } from '@/composables/useNotifications'
import { rightsOf, type AccessLevel } from './access'
import { TOOL_SETTINGS } from '@/collab/connection/collabApi'
import { loadCollabKit } from '@/collab/connection/collabKit'
import type { Grant, Reference } from '@/collab/connection/collabKitV1'
import CollabAccessList from './CollabAccessList.vue'
import { useCollabAction, useCollabDirectory } from './useCollabDirectory'

const { rooms, groups, loading, loadNames, showGroup, dropGroup, roomName, actorName } = useCollabDirectory()
const { busy, run } = useCollabAction()

const selectedId = ref<string | null>(null)
const grants = ref<Grant[]>([])
const newGroupName = ref('')
const createDialog = ref(false)
const newMember = ref('')
const nameDraft = ref('')
const confirmDialog = ref<InstanceType<typeof DialogConfirm> | null>(null)

// Access rows and options are keyed by place: a room, another place of collab-kit, or everywhere.
const EVERYWHERE = 'everywhere'
const keyOf = (scope?: Reference) => (scope ? `${scope.kind}:${scope.id}` : EVERYWHERE)
const scopeOf = (key: string): Reference | undefined => {
  if (key === EVERYWHERE) return undefined
  const [kind, id] = key.split(':')
  return { kind, id }
}
const labelOf = (scope?: Reference) => (!scope ? 'Everywhere' : scope.kind === 'room' ? roomName(scope.id) : `${scope.kind} ${scope.id}`)

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
  const ck = await loadCollabKit()
  const held = await ck.grants.list({ groupId: group._id }).catch(() => null)
  if (selected.value?._id === group._id) grants.value = held ?? []
}

const addGroup = () => {
  const name = newGroupName.value.trim()
  if (!name) return
  void run(
    'group',
    async (ck) => {
      const group = await ck.groups.create({ name, settings: TOOL_SETTINGS })
      showGroup(group)
      selectedId.value = group._id
      newGroupName.value = ''
      createDialog.value = false
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
    async (ck) => {
      showGroup(await ck.groups.update(group._id, { name }))
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
    async (ck) => {
      await ck.groups.remove(group._id)
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
    async (ck) => {
      showGroup(await ck.groups.addMember(group._id, actorId))
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
    async (ck) => {
      showGroup(await ck.groups.removeMember(group._id, actorId))
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
    async (ck) => {
      await ck.grants.set({ groupId: group._id, scope: scopeOf(key), rights: rightsOf(level) })
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
    async (ck) => {
      await ck.grants.remove({ groupId: group._id, scope: scopeOf(key) })
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

// The page holds the button for a new group, the dialog stays here with what it creates.
defineExpose({ openCreate: () => (createDialog.value = true) })
</script>

<style scoped>
.collab-groups {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 12px;
}

.collab-groups__list {
  width: 300px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
}

.collab-groups__detail {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* List and details scroll each on their own, so the list stays in view while the details run long. */
.collab-groups__items,
.collab-groups__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.collab-groups__label {
  margin: 20px 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.collab-groups__label:first-child {
  margin-top: 0;
}
</style>
