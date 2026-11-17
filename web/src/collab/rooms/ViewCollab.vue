<template>
  <v-container fluid class="pa-3">
    <!-- Properties of the element, set as they are named there; a hyphen would name another one. -->
    <!-- eslint-disable-next-line vue/attribute-hyphenation -->
    <ck-management v-if="ck" ref="management" lang="en" theme="light" class="collab-view" .ck="ck" .newWorkpiece="createWorkpiece" .tabs="tabs" .extraTabs="extraTabs" @ck-open="open">
      <!-- The "Group work" tab shows this slot; the content stays in the light DOM, so with Vuetify. -->
      <!-- The native slot of the web component, not the old slot of Vue 2. -->
      <!-- eslint-disable-next-line vue/no-deprecated-slot-attribute -->
      <GroupWork slot="group-work" @created="reload" />
      <!-- eslint-disable-next-line vue/no-deprecated-slot-attribute -->
      <CollabSettings v-if="manager" slot="collab-settings" :ck="ck" />
    </ck-management>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, ManagementElement, ManagementOpen, ManagementOwnTab, ManagementTab, Room } from '@/collab/kit/collabKitV1'
import GroupWork from '@/collab/groups/GroupWork.vue'
import CollabSettings from '@/collab/settings/CollabSettings.vue'
import { mayManageAll } from './access'
import { newWorkpiece, UML_CLASS_DIAGRAM } from '@/collab/storage/workpiece'
import { TASK_FORMAT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { collabSettings, loadCollabSettings } from '@/collab/settings/collabSettings'

const ck = shallowRef<CollabKitApi>()
const management = shallowRef<ManagementElement>()
const { openFromRoom } = useCollabConnection()

/** Whether the person has manage everywhere; only then does collab-kit let them write the collab settings. */
const manager = ref(false)
/** Tabs of the Copilot after those of collab-kit, each shows the slot of its ID. */
const extraTabs = computed<ManagementTab[]>(() => [{ id: 'group-work', label: 'Group work' }, ...(manager.value ? [{ id: 'collab-settings', label: 'Collab settings' }] : [])])
/** The own tabs of collab-kit; without the archive in the collab settings the "Archive" tab is missing, undefined shows all. */
const tabs = computed<readonly ManagementOwnTab[] | undefined>(() => (collabSettings.archive.enabled ? undefined : ['rooms', 'groups', 'workpieces']))
/** Rooms the backend created are known to the element only after reloading. */
const reload = () => void management.value?.reload()

/** A workpiece created in a room is a class diagram of the Copilot. */
const createWorkpiece = (room: Room, name: string) => newWorkpiece(room._id, name, [UML_CLASS_DIAGRAM])

/** The workpiece of a shared task is no model of its own: it opens the model it belongs to, which shows the task. */
const open = async ({ detail }: CustomEvent<ManagementOpen>) => {
  const { room, workpiece } = detail
  if (workpiece.contract.format !== TASK_FORMAT || !ck.value) return openFromRoom(room, workpiece)
  const api = ck.value
  const found = await Promise.allSettled(room.workpieces.map((id) => api.workpieces.get(id)))
  const model = found.flatMap((result) => (result.status === 'fulfilled' ? [result.value] : [])).find((item) => taskLinkOf(item)?.workpieceId === workpiece._id)
  if (model) return openFromRoom(room, model)
  notifyError('This is the task of a shared model, and the model is no longer in this room.')
}

// The element is defined once collab-kit is loaded, and shows nothing before ck; what each one may do there, collab-kit decides.
onMounted(async () => {
  try {
    const api = await loadCollabKit()
    // Asked before the element, so the tab is there from the start; without an answer it stays away.
    manager.value = await mayManageAll()
    // Also before the element, so the "Archive" tab does not show briefly; without an answer the default applies, which is off.
    await Promise.allSettled([loadCollabSettings(api, 'archive'), loadCollabSettings(api, 'hints')])
    ck.value = api
  } catch (error) {
    notifyError(`collab-kit could not be loaded: ${collabErrorMessage(error)}`)
  }
})
</script>

<style scoped>
.collab-view {
  /* Down to the footer: window height without header and footer and without the padding of the container (pa-3). */
  --ck-height: calc(100dvh - var(--v-layout-top) - var(--v-layout-bottom) - 24px);
  --ck-accent: rgb(var(--v-theme-primary));
  --ck-on-accent: rgb(var(--v-theme-on-primary));
}
</style>
