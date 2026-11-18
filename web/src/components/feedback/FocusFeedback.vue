<template>
  <div v-if="entry.focus" class="focus-feedback">
    <p class="focus-feedback__text">{{ entry.focus.text }}</p>
    <p v-if="entry.focus.repeated" class="focus-feedback__hint">Dieser Hinweis kam schon in einer früheren Hilfe vor.</p>
    <v-btn v-if="entry.focus.cellIds.length" class="mt-1" prepend-icon="mdi-crosshairs-gps" size="small" variant="text" @click="emit('select', entry.focus.cellIds)">Im Modell zeigen</v-btn>
  </div>
</template>

<script setup lang="ts">
import type { HelpFeedbackEntry } from '@/services/api/types/evaluation'

defineProps<{ entry: HelpFeedbackEntry }>()
const emit = defineEmits<{ select: [cellIds: string[]] }>()
</script>

<style scoped>
.focus-feedback__text { font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.focus-feedback__hint { font-size: 11px; margin-top: 4px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.focus-feedback :deep(.v-btn) { text-transform: none; letter-spacing: 0; }
</style>
