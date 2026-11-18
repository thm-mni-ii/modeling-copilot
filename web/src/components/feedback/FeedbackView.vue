<template>
  <div class="feedback-view">
    <section v-for="(entry, index) in entries" :key="`${entry.type}:${index}`" class="feedback-view__entry" :aria-label="titles[entry.type] ?? 'Feedback'">
      <p v-if="!compact && entry.type !== 'help.check'" class="feedback-view__overview">{{ entry.overview.recognized }} von {{ entry.overview.expected }} erwarteten Objekten erkannt</p>
      <component :is="components[entry.type]" v-if="components[entry.type]" :entry="entry" :compact="compact" @select="select" />
      <p v-else class="feedback-view__unknown">Diese Art von Feedback kann hier noch nicht angezeigt werden.</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, type Component } from 'vue'
import type { Cell } from '@maxgraph/core'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { notifyWarning } from '@/composables/useNotifications'
import type { HelpFeedbackEntry } from '@/services/api/types/evaluation'

// compact: no recognition line; the staff preview shows many objects.
defineProps<{ entries: HelpFeedbackEntry[]; compact?: boolean }>()
const graphContext = useGraphContextOptional()
const select = (cellIds: string[]) => {
  const graph = graphContext?.graph.value
  const cells = (graph ? cellIds.map((id) => graph.getDataModel().getCell(id)) : []).filter((cell): cell is Cell => cell != null)
  if (!graph || !cells.length) {
    notifyWarning('Das Objekt ist im aktuellen Modell nicht mehr vorhanden.')
    return
  }
  graph.setSelectionCells(cells)
  graph.scrollCellToVisible(cells[0])
}
// One renderer per feedback type the service can produce; unknown types fall back to a neutral notice.
const objectFeedback = defineAsyncComponent(() => import('./ObjectFeedback.vue'))
const focusFeedback = defineAsyncComponent(() => import('./FocusFeedback.vue'))
const checkFeedback = defineAsyncComponent(() => import('./CheckFeedback.vue'))
const scoreFeedback = defineAsyncComponent(() => import('./ScoreFeedback.vue'))
const patternFeedback = defineAsyncComponent(() => import('./PatternFeedback.vue'))
const components: Record<string, Component> = {
  'help.clarify': scoreFeedback, 'help.check': checkFeedback, 'help.solution': objectFeedback,
  'help.next_step': focusFeedback, 'help.example': patternFeedback
}
const titles: Record<string, string> = {
  'help.clarify': 'Erklärung', 'help.check': 'Prüfung', 'help.next_step': 'Nächster Schritt', 'help.example': 'Beispiel', 'help.solution': 'Lösung'
}
</script>

<style scoped>
.feedback-view__entry + .feedback-view__entry { margin-top: 10px; }
.feedback-view__overview, .feedback-view__unknown { font-size: 11px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); margin-bottom: 6px; }
</style>
