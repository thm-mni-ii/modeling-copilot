<template>
  <CollabDialogs />
  <ModeBar />
</template>

<script setup lang="ts">
import { onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useGraphContext } from '@/composables/useGraphContext'
import CollabDialogs from '@/collab/sharing/CollabDialogs.vue'
import ModeBar from '@/collab/sharing/ModeBar.vue'
import { announceSharedTab, dropStaleShare, guardShareLeave } from '@/collab/sharing/shareModel'
import { holdCollabConnection } from './useCollabConnection'

// As long as the editor is there, leaving the shared model goes through the dialog.
onBeforeUnmount(guardShareLeave(useRouter()))

// Andere Tabs sehen so, ob das geteilte Modell hier noch offen ist.
onBeforeUnmount(announceSharedTab())

// A share kept by this browser may belong to another account or have ended meanwhile.
void dropStaleShare()

// Sits in the editor and shows only the dialogs of sharing: the live connection lasts as long as the editor, not a sidebar tab.
holdCollabConnection(useGraphContext().graph)
</script>

<style>
/* Found by its label, so nothing of the Copilot changes; renamed, the tab just stays uncolored. */
body.collab-live .sidebar-tabs .v-tab[aria-label='Collab'] {
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}
</style>
