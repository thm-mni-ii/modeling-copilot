<template>
  <div class="collab-people">
    <div class="collab-people__header">
      <span class="collab-people__title">
        People
        <span v-if="guests > 0" class="collab-people__count">{{ guests }}</span>
      </span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse people' : 'Expand people'" @click="open = !open" />
    </div>
    <v-expand-transition>
      <div v-show="open" class="collab-people__body">
        <div v-if="people.length === 0" class="collab-people__empty">Nobody announced yet</div>
        <div v-for="person in people" :key="person.id" class="collab-people__entry">
          <span class="collab-people__dot" :style="{ background: person.color }" />
          <span>{{ person.name }}</span>
          <span v-if="noteOf(person)" class="collab-people__note">{{ noteOf(person) }}</span>
        </div>
      </div>
    </v-expand-transition>
  </div>
</template>

<script lang="ts">
import { computed, ref } from 'vue'

// Kept beside the component, so it stays closed while another sidebar tab is shown.
const open = ref(false)
</script>

<script setup lang="ts">
import type { Person } from './presence'

const props = defineProps<{ people: Person[] }>()

/** People in the room besides the host, shown next to the title while the box is closed. */
const guests = computed(() => props.people.filter((person) => !person.host).length)

/** What else to tell of a person, such as "(you) · read only · 2 tabs". */
const noteOf = (person: Person) => [person.self ? '(you)' : '', person.readOnly ? 'read only' : '', person.tabs > 1 ? `${person.tabs} tabs` : ''].filter(Boolean).join(' · ')
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

.collab-people__count {
  margin-left: 6px;
  padding: 0 7px;
  border-radius: 10px;
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 18%, transparent);
  color: rgba(var(--v-theme-on-surface), 0.87);
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

.collab-people__note {
  color: rgba(var(--v-theme-on-surface), 0.5);
}
</style>
