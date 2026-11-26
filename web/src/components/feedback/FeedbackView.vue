<template>
  <div class="feedback-view">
    <p v-if="changed" class="feedback-view__overview">Feedback zum ausgewerteten Stand. Markierungen und Objektverweise bleiben für unveränderte Objekte erhalten.</p>
    <section v-for="(entry, index) in entries" :key="`${entry.type}:${index}`" class="feedback-view__entry" :aria-label="titles[entry.type] ?? 'Feedback'">
      <p v-if="!compact && entry.referenced === false" class="feedback-view__overview">Diese Hilfe wird nicht angerechnet: Das markierte Objekt konnte keinem Element der Musterlösung zugeordnet werden.</p>
      <component :is="components[entry.type]" v-if="components[entry.type]" :entry="entry" :compact="compact" v-bind="entry.type === 'help.clarify' || entry.type === 'help.check' ? { isCurrent } : {}" @select="select" />
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
import { useFeedbackValidity } from '@/composables/useFeedbackValidity'

// compact: the staff preview shows many objects.
const props = defineProps<{ entries: HelpFeedbackEntry[]; compact?: boolean; snapshotXml?: string | null }>()
const { isCurrent, changed } = useFeedbackValidity(() => props.snapshotXml)
const graphContext = useGraphContextOptional()
const select = (cellIds: string[]) => {
  const graph = graphContext?.graph.value
  const cells = (graph ? cellIds.filter(isCurrent.value).map((id) => graph.getDataModel().getCell(id)) : []).filter((cell): cell is Cell => cell != null)
  if (!graph || !cells.length) {
    notifyWarning('Das Objekt fehlt oder wurde seit der Auswertung fachlich verändert. Das Feedback bleibt am ausgewerteten Stand verfügbar.')
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
