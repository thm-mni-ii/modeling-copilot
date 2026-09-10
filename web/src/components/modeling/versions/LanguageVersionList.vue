<template>
  <div v-if="entries.length">
    <div v-for="entry in entries" :key="entry.id" class="version-row">
      <div class="version-info">
        <div class="d-flex align-center ga-2">
          <span class="font-weight-medium text-truncate">{{ versionLabel(entry) }}</span>
          <v-chip :color="entry.kind === 'release' ? 'primary' : undefined" size="x-small" variant="tonal">{{ entry.kind === 'release' ? 'Release' : 'Checkpoint' }}</v-chip>
          <v-chip v-if="entry.id === currentVersionId" size="x-small" variant="tonal">Current</v-chip>
        </div>
        <div class="text-caption text-medium-emphasis">{{ formattedDate(entry.createdAt) }}</div>
        <div v-if="entry.description" class="text-caption text-truncate">{{ entry.description }}</div>
      </div>
      <div class="version-actions">
        <v-btn v-if="showTry" size="small" variant="text" prepend-icon="mdi-play" @click="emit('try', entry)">Try</v-btn>
        <v-btn v-if="showFork" size="small" variant="text" @click="emit('fork', entry)">Use as new language</v-btn>
        <v-btn size="small" variant="tonal" :disabled="disableCurrentAction && entry.id === currentVersionId" @click="emit('restore', entry)">{{ actionLabel }}</v-btn>
      </div>
    </div>
  </div>
  <div v-else class="text-medium-emphasis pa-2">{{ emptyText }}</div>
</template>

<script setup lang="ts">
import type { LanguageVersionInfo } from '@/services/api/types/language'

withDefaults(
  defineProps<{
    entries: LanguageVersionInfo[]
    currentVersionId?: string | null
    emptyText?: string
    actionLabel?: string
    disableCurrentAction?: boolean
    showTry?: boolean
    showFork?: boolean
  }>(),
  {
    currentVersionId: null,
    emptyText: 'No saves yet.',
    actionLabel: 'Restore',
    disableCurrentAction: true,
    showTry: false,
    showFork: false
  }
)

const emit = defineEmits<{
  restore: [entry: LanguageVersionInfo]
  try: [entry: LanguageVersionInfo]
  fork: [entry: LanguageVersionInfo]
}>()

const formattedDate = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const versionLabel = (entry: LanguageVersionInfo) => (entry.kind === 'release' && entry.releaseName ? `${entry.releaseName} · v${entry.versionNumber}` : `v${entry.versionNumber}`)
</script>

<style scoped>
.version-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.version-info {
  min-width: 0;
}

.version-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  flex-shrink: 0;
}

@media (max-width: 700px) {
  .version-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .version-actions {
    margin-left: 0;
  }
}
</style>
