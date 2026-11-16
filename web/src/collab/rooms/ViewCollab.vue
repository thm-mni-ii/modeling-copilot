<template>
  <v-container fluid class="pa-3">
    <!-- Properties of the element, set as they are named there; a hyphen would name another one. -->
    <!-- eslint-disable-next-line vue/attribute-hyphenation -->
    <ck-management v-if="ck" ref="management" lang="en" theme="light" class="collab-view" .ck="ck" .newWorkpiece="createWorkpiece" .tabs="tabs" .extraTabs="extraTabs" @ck-open="open">
      <!-- Der Reiter „Group work“ zeigt diesen Slot; der Inhalt bleibt im Light DOM, also mit Vuetify. -->
      <!-- Der native Slot der Web Component, nicht der alte Slot von Vue 2. -->
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
import CollabSettings from './CollabSettings.vue'
import { newWorkpiece, UML_CLASS_DIAGRAM } from '@/collab/storage/workpiece'
import { TASK_FORMAT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { collabSettings, loadCollabSettings } from '@/collab/connection/collabSettings'

const ck = shallowRef<CollabKitApi>()
const management = shallowRef<ManagementElement>()
const { openFromRoom } = useCollabConnection()

/** Ob die Person überall manage hat; nur dann lässt collab-kit sie die Collab-Einstellungen schreiben. */
const manager = ref(false)
/** Reiter des Copilots nach denen von collab-kit, jeder zeigt den Slot seiner ID. */
const extraTabs = computed<ManagementTab[]>(() => [{ id: 'group-work', label: 'Group work' }, ...(manager.value ? [{ id: 'collab-settings', label: 'Collab settings' }] : [])])
/** Die eigenen Reiter von collab-kit; ohne Archiv in den Collab-Einstellungen fehlt der Reiter „Archive“, undefined zeigt alle. */
const tabs = computed<readonly ManagementOwnTab[] | undefined>(() => (collabSettings.archive.enabled ? undefined : ['rooms', 'groups', 'workpieces']))
/** Räume, die das Backend angelegt hat, kennt das Element erst nach dem Neuladen. */
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
    // Vor dem Element gefragt, damit der Reiter von Anfang an dabei ist; ohne Antwort bleibt er weg.
    manager.value = await api.me.rights().then(
      (rights) => rights.includes('manage'),
      () => false
    )
    // Ebenso vor dem Element, damit der Reiter „Archive“ nicht kurz erscheint; ohne Antwort gilt der Standard, also aus.
    await loadCollabSettings(api, 'archive').catch(() => undefined)
    ck.value = api
  } catch (error) {
    notifyError(`collab-kit could not be loaded: ${collabErrorMessage(error)}`)
  }
})
</script>

<style scoped>
.collab-view {
  /* Bis zur Fußzeile: Fensterhöhe ohne Kopf- und Fußzeile und ohne das Padding des Containers (pa-3). */
  --ck-height: calc(100dvh - var(--v-layout-top) - var(--v-layout-bottom) - 24px);
  --ck-accent: rgb(var(--v-theme-primary));
  --ck-on-accent: rgb(var(--v-theme-on-primary));
}
</style>
