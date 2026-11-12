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

// Andere Tabs sehen so, ob das geteilte Modell hier noch offen ist.
onBeforeUnmount(announceSharedTab())

// A share kept by this browser may belong to another account or have ended meanwhile.
void dropStaleShare()

// Sits in the editor and shows only the dialogs of sharing: the live connection lasts as long as the editor, not a sidebar tab.
holdCollabConnection(useGraphContext().graph)

// Modell eines Raums: Der Name kommt vom Werkstück, Umbenennen träfe nur die eigene Kopie.
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
/* Ebenso über das Label gefunden; umbenannt, wäre der Stift wieder da. Unsichtbar statt entfernt, damit die Leiste ihre Breite behält. */
body.collab-linked .modeling-header [aria-label='Change model name'] {
  visibility: hidden;
}
/* Import ersetzt das ganze Modell; die Bindung stellt dann den Stand des Raums wieder her, der Import ginge verloren. */
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
/* Per Tastatur doch gewählt: ohne Bedienelemente. */
body.collab-linked .sidebar-persistence:has(.mode-switch > .v-btn:last-child[aria-pressed='true']) :is(.persistence-actions, .persistence-content) {
  display: none;
}
</style>
