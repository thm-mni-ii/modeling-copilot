<template>
  <div v-if="entries.length">
    <div v-for="entry in entries" :key="entry.id" class="snapshot-row">
      <div class="snapshot-info">
        <div class="d-flex align-center ga-2">
          <span class="font-weight-medium text-truncate">{{ snapshotLabel(entry) }}</span
          ><v-chip :color="entry.kind === 'release' ? 'primary' : undefined" size="x-small" variant="tonal">{{ entry.kind === 'release' ? 'Release' : 'Checkpoint' }}</v-chip>
        </div>
        <div class="text-caption text-medium-emphasis">{{ formattedDate(entry.createdAt) }}</div>
      </div>
      <div class="ml-auto d-flex ga-2">
        <v-btn size="small" variant="text" @click="emit('preview', entry)">Preview</v-btn>
        <v-btn v-if="showBranch" size="small" variant="tonal" @click="emit('branch', entry)">Use as new model</v-btn>
      </div>
    </div>
  </div>
  <div v-else class="text-medium-emphasis pa-2">{{ emptyText }}</div>
</template>

<script setup lang="ts">
import type { ModelVersionInfo } from '@/services/api/types/model'

withDefaults(
  defineProps<{
    entries: ModelVersionInfo[]
    emptyText?: string
    showBranch?: boolean
  }>(),
  {
    emptyText: 'No entries.',
    showBranch: true
  }
)

const emit = defineEmits<{
  preview: [entry: ModelVersionInfo]
  branch: [entry: ModelVersionInfo]
}>()

const formattedDate = (value: string) => new Date(value).toLocaleString('en-GB')
const snapshotLabel = (entry: ModelVersionInfo) => (entry.kind === 'release' && entry.releaseName ? `${entry.releaseName} · v${entry.versionNumber}` : `v${entry.versionNumber}`)
</script>

<style scoped>
.snapshot-row {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.snapshot-info {
  min-width: 0;
}
</style>
