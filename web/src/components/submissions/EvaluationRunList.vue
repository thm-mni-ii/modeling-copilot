<template>
  <v-list class="evaluation-run-list" nav density="compact" :aria-label="ariaLabel">
    <v-list-item v-for="run in runs" :key="run.id" :active="selectedId === run.id" :disabled="disabled" color="primary" class="evaluation-run-item" @click="emit('select', run.id)">
      <template #prepend>
        <v-icon :icon="run.state === 'running' ? 'mdi-progress-clock' : hasFailures(run) ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline'" :color="hasFailures(run) ? 'warning' : undefined" size="18" />
      </template>
      <div class="text-body-2 font-weight-medium">{{ formatDate(run.createdAt) }}</div>
      <div class="text-caption text-medium-emphasis mt-1">{{ run.state === 'running' ? 'Running' : 'Completed' }} · {{ run.items.length }} cases</div>
      <div v-if="hasFailures(run)" class="text-caption text-warning">{{ run.items.filter(item => item.status === 'failed').length }} failed</div>
      <v-progress-linear v-if="run.state === 'running'" :model-value="100 * run.items.filter(item => ['done', 'failed'].includes(item.status)).length / Math.max(run.items.length, 1)" class="mt-2" aria-label="Processed test cases" />
    </v-list-item>
  </v-list>
</template>

<script setup lang="ts">
import type { ReplayBatch } from '@/services/synonymGlossary'

withDefaults(defineProps<{ runs: ReplayBatch[]; selectedId: string | null; disabled?: boolean; ariaLabel?: string }>(), {
  disabled: false,
  ariaLabel: 'Choose a test run'
})
const emit = defineEmits<{ select: [id: string] }>()
const hasFailures = (run: ReplayBatch) => run.items.some(item => item.status === 'failed')
const formatDate = (date: string) => new Date(date).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
</script>

<style scoped>
.evaluation-run-list { background: transparent; padding-top: 0; }
.evaluation-run-item { padding-block: 10px; margin-bottom: 4px; }
.evaluation-run-item :deep(.v-list-item__prepend) { align-self: start; padding-top: 2px; }
.evaluation-run-item :deep(.v-list-item__spacer) { width: 12px; }
</style>
