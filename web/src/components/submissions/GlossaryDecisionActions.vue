<template>
  <div class="decision-actions">
    <template v-if="status === 'accepted'">
      <v-btn size="x-small" variant="tonal" color="warning" :disabled="disabled" @click="$emit('source')">{{ matchingSource ? 'Source on' : 'New Source' }}</v-btn>
      <v-btn size="x-small" variant="outlined" :disabled="disabled" @click="$emit('remove')">Remove</v-btn>
    </template>
    <template v-else>
    <v-btn size="x-small" variant="tonal" color="success" :disabled="disabled" @click="$emit('decide', 'accepted')">Accept</v-btn>
    <v-btn size="x-small" variant="tonal" color="error" :disabled="disabled || status === 'rejected'" @click="$emit('decide', 'rejected')">Reject</v-btn>
    <v-btn size="x-small" variant="outlined" :disabled="disabled || status === 'ignored'" @click="$emit('decide', 'ignored')">Ignore</v-btn>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EntryStatus } from '@/services/synonymGlossary'
defineProps<{ status?: EntryStatus; disabled: boolean; matchingSource?: boolean }>()
defineEmits<{ decide: [status: EntryStatus]; source: []; remove: [] }>()
</script>

<style scoped>
.decision-actions { display: flex; flex-direction: column; gap: 4px; width: 80px; padding-block: 6px; }
.decision-actions :deep(.v-btn__content) { overflow: visible; }
</style>
