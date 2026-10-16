<template>
  <div class="collab-people">
    <div class="collab-people__header">
      <span>Online</span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse online' : 'Expand online'" @click="open = !open" />
    </div>
    <v-expand-transition>
      <div v-show="open" class="collab-people__body">
        <div v-if="people.length === 0" class="collab-people__empty">Nobody announced yet</div>
        <div v-for="person in people" :key="person.id" class="collab-people__entry">
          <span class="collab-people__dot" :style="{ background: person.color }" />
          <span>{{ person.name }}</span>
          <span v-if="person.self" class="collab-people__self">(you)</span>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so it stays closed while another sidebar tab is shown.
const open = ref(true)
</script>

<script setup lang="ts">
import type { Person } from './presence'

defineProps<{ people: Person[] }>()
</script>

<style scoped>
.collab-people {
  /* The sync sidebar scrolls instead; with overflow hidden it could squeeze the box down to its header. */
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.collab-people__header {
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

.collab-people__body {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

.collab-people__empty,
.collab-people__entry {
  padding: 6px 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.75);
}

.collab-people__entry {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collab-people__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}

.collab-people__self {
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
