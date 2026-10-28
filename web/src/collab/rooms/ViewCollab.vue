<template>
  <v-container fluid class="pa-3">
    <!-- Properties of the element, set as they are named there; a hyphen would name another one. -->
    <!-- eslint-disable-next-line vue/attribute-hyphenation -->
    <ck-management v-if="ck" lang="en" theme="light" class="collab-view" .ck="ck" .newWorkpiece="createWorkpiece" @ck-open="open" />
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import type { CollabKitApi, ManagementOpen, Room } from '@/collab/kit/collabKitV1'
import { newWorkpiece, UML_CLASS_DIAGRAM } from '@/collab/storage/workpiece'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'

const ck = shallowRef<CollabKitApi>()
const { openFromRoom } = useCollabConnection()

/** A workpiece created in a room is a class diagram of the Copilot. */
const createWorkpiece = (room: Room, name: string) => newWorkpiece(room._id, name, [UML_CLASS_DIAGRAM])

const open = ({ detail }: CustomEvent<ManagementOpen>) => openFromRoom(detail.room, detail.workpiece)

// The element is defined once collab-kit is loaded, and shows nothing before ck; what each one may do there, collab-kit decides.
onMounted(async () => {
  try {
    ck.value = await loadCollabKit()
  } catch (error) {
    notifyError(`collab-kit could not be loaded: ${collabErrorMessage(error)}`)
  }
})
</script>

<style scoped>
.collab-view {
  --ck-accent: rgb(var(--v-theme-primary));
  --ck-on-accent: rgb(var(--v-theme-on-primary));
}
</style>
