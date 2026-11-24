<template>
  <CollabBox v-model="open" title="People" label="people">
    <template #title>
      <span v-if="guests > 0" class="collab-people__count">{{ guests }}</span>
    </template>
    <div v-if="people.length === 0" class="collab-people__empty">Nobody announced yet</div>
    <div v-for="person in people" :key="person.id" class="collab-people__entry">
      <span class="collab-people__dot" :style="{ background: person.color }" />
      <span>{{ person.name }}</span>
      <span v-if="noteOf(person)" class="collab-people__note">{{ noteOf(person) }}</span>
    </div>
  </CollabBox>
</template>

<script lang="ts">
import { computed, ref } from 'vue'

// Kept beside the component, so it stays closed while another sidebar tab is shown.
const open = ref(false)
</script>

<script setup lang="ts">
import CollabBox from '@/collab/connection/CollabBox.vue'
import type { Person } from './presence'

const props = defineProps<{ people: Person[] }>()

/** People in the room besides the host, shown next to the title while the box is closed. */
const guests = computed(() => props.people.filter((person) => !person.host).length)

/** What else to tell of a person, such as "(you) · read only · 2 tabs". */
const noteOf = (person: Person) => [person.self ? '(you)' : '', person.readOnly ? 'read only' : '', person.tabs > 1 ? `${person.tabs} tabs` : ''].filter(Boolean).join(' · ')
</script>

<style scoped>
.collab-people__count {
  margin-left: 6px;
  padding: 0 7px;
  border-radius: 10px;
  background: color-mix(in srgb, rgb(var(--v-theme-primary)) 18%, transparent);
  color: rgba(var(--v-theme-on-surface), 0.87);
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
