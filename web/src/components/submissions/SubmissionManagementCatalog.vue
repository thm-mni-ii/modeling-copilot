<template>
  <v-switch :model-value="archived" label="Archived assignments" hide-details @update:model-value="emit('archive', Boolean($event))" />
  <v-list lines="two"><v-list-item v-for="item in items" :key="item.id" :title="item.name" :subtitle="`Configuration v${item.revision}${item.archived ? ' · Archived' : ''}`" :to="{ name: 'Submissions', params: { assignmentId: item.id }, query: { view: 'management' } }" append-icon="mdi-chevron-right" /></v-list>
  <p v-if="!items.length && !busy" class="text-medium-emphasis my-5">No assignments available.</p>
  <v-pagination v-if="total > 20" :model-value="page" :length="Math.ceil(total / 20)" @update:model-value="emit('page', $event)" />
</template>
<script setup lang="ts">
import type { Assignment } from '@/services/api/types/submission'
defineProps<{ items: Assignment[]; total: number; page: number; archived: boolean; busy: boolean }>()
const emit = defineEmits<{ archive: [value: boolean]; page: [value: number] }>()
</script>
