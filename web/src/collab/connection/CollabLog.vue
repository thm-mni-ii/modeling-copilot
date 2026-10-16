<template>
  <div class="collab-log" :class="{ 'collab-log--open': open }">
    <div class="collab-log__header">
      <span>Event Log</span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse event log' : 'Expand event log'" @click="open = !open" />
    </div>
    <div v-show="open" class="collab-log__body">
      <div v-if="entries.length === 0" class="collab-log__empty">No events yet</div>
      <div v-for="(entry, index) in entries" :key="index" class="collab-log__entry">{{ entry }}</div>
    </div>
  </div>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so it stays closed while another sidebar tab is shown.
const open = ref(true)
</script>

<script setup lang="ts">
defineProps<{ entries: string[] }>()
</script>

<style scoped>
.collab-log {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.01);
}

/* Open, it takes what the sync sidebar leaves, so it grows as the boxes above close. */
.collab-log--open {
  flex: 1;
  min-height: 180px;
}

.collab-log__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.collab-log__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

.collab-log__empty {
  padding: 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.52);
}

.collab-log__entry {
  padding: 8px 10px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.08);
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.75);
}
</style>
