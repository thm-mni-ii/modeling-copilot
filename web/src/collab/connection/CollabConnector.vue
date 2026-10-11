<template>
  <span hidden />
</template>

<script setup lang="ts">
import { useGraphContext } from '@/composables/useGraphContext'
import { holdCollabConnection } from './useCollabConnection'

// Sits in the editor and shows nothing: the live connection lasts as long as the editor, not a sidebar tab.
holdCollabConnection(useGraphContext().graph)
</script>

<style>
/* Found by its label, so nothing of the Copilot changes; renamed, the tab just stays uncolored. */
body.collab-live .sidebar-tabs .v-tab[aria-label='Sync'] {
  background: rgb(var(--v-theme-error));
  color: #ffffff;
}
</style>
