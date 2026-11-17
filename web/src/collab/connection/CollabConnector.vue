<template>
  <CollabDialogs />
  <ModeBar />
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGraphContext } from '@/composables/useGraphContext'
import CollabDialogs from '@/collab/sharing/CollabDialogs.vue'
import ModeBar from '@/collab/sharing/ModeBar.vue'
import { announceSharedTab, dropStaleShare, guardShareLeave } from '@/collab/sharing/shareModel'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { linkOf } from '@/collab/storage/workpiece'
import { holdCollabConnection } from './useCollabConnection'

// As long as the editor is there, leaving the shared model goes through the dialog.
onBeforeUnmount(guardShareLeave(useRouter()))

// So other tabs see whether the shared model is still open here.
onBeforeUnmount(announceSharedTab())

// A share kept by this browser may belong to another account or have ended meanwhile.
void dropStaleShare()

// Sits in the editor and shows only the dialogs of sharing: the live connection lasts as long as the editor, not a sidebar tab.
holdCollabConnection(useGraphContext().graph)

// Model of a room: the name comes from the workpiece, renaming would only hit the own copy.
const LINKED_CLASS = 'collab-linked'
const workspace = useModelWorkspaceStore()
watch(
  () => Boolean(linkOf(workspace.preferences)),
  (linked) => document.body.classList.toggle(LINKED_CLASS, linked),
  { immediate: true }
)
onBeforeUnmount(() => document.body.classList.remove(LINKED_CLASS))
</script>

<style>
/* Found by its label, so nothing of the Copilot changes; renamed, the tab just stays uncolored. */
body.collab-live .sidebar-tabs .v-tab[aria-label='Collab'] {
  background: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}
/* Also found by its label; renamed, the pencil would be back. Hidden instead of removed, so the bar keeps its width. */
body.collab-linked .modeling-header [aria-label='Change model name'] {
  visibility: hidden;
}
/* Import replaces the whole model; the binding then restores the state of the room, and the import would be lost. */
body.collab-linked .sidebar-persistence .mode-switch > .v-btn:last-child {
  opacity: 0.38;
  pointer-events: none;
}
body.collab-linked .sidebar-persistence .persistence-navigation::after {
  content: 'Import is turned off in room models.';
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.6);
}
/* Chosen by keyboard after all: without controls. */
body.collab-linked .sidebar-persistence:has(.mode-switch > .v-btn:last-child[aria-pressed='true']) :is(.persistence-actions, .persistence-content) {
  display: none;
}
</style>
