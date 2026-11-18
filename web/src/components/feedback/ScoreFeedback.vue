<template>
  <div class="score-feedback">
    <ul class="score-feedback__list">
      <li v-for="object in entry.objects ?? []" :key="object.cellId" class="mb-2">
        <div class="d-flex align-center ga-2">
          <v-icon :color="statuses[statusOf(object)].color" size="16">{{ statuses[statusOf(object)].icon }}</v-icon>
          <span class="score-feedback__name">{{ object.label || 'Unbeschriftetes Objekt' }}</span>
          <span class="text-medium-emphasis">{{ statuses[statusOf(object)].label }}</span>
          <v-spacer />
          <strong v-if="object.score">{{ format(object.score.percent) }}</strong>
          <v-btn icon="mdi-crosshairs-gps" size="x-small" variant="text" :aria-label="`${object.label || 'Objekt'} im Modell zeigen`" @click="emit('select', [object.cellId])" />
        </div>
        <template v-if="object.score">
          <v-progress-linear :model-value="object.score.percent" :color="statuses[statusOf(object)].color" height="4" rounded :aria-label="`Vollständigkeit: ${format(object.score.percent)}`" />
          <div v-for="part in object.score.parts" :key="part.label" class="d-flex justify-space-between score-feedback__part">
            <span>{{ part.label }}</span><span>{{ part.text ?? `${part.present} von ${part.expected}` }}</span>
          </div>
          <p v-if="object.score.hint" class="score-feedback__hint">{{ object.score.hint }}</p>
        </template>
      </li>
    </ul>    <p class="score-feedback__hint">Die Objekte sind im Modell mit diesen Symbolen gekennzeichnet, solange dieses Feedback angezeigt wird.</p>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import type { Cell, CellOverlay } from '@maxgraph/core'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createOverlayFromConfig } from '@/utils/feedbackOverlays'
import type { HelpFeedbackEntry, HelpFeedbackObject } from '@/services/api/types/evaluation'

const props = defineProps<{ entry: HelpFeedbackEntry }>()
const emit = defineEmits<{ select: [cellIds: string[]] }>()
type CheckStatus = 'correct' | 'deviation' | 'unassigned'
const statuses: Record<CheckStatus, { icon: string; color: string; label: string }> = {
  correct: { icon: 'mdi-check-circle', color: '#2E7D32', label: 'korrekt' },
  deviation: { icon: 'mdi-alert-circle', color: '#B26A00', label: 'Abweichung' },
  unassigned: { icon: 'mdi-help-circle', color: '#6D4C9F', label: 'nicht zuordenbar' }
}
// Unclear or unevaluated objects cannot be matched to an expectation, so they count as not assignable.
const statusOf = (object: HelpFeedbackObject): CheckStatus =>
  object.identity === 'unassigned' || object.identity === 'not_evaluated' ? 'unassigned'
    : object.verdict === 'matches' ? 'correct' : object.verdict === 'differs' ? 'deviation' : 'unassigned'
const format = (value: number) => `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(value)} %`

// The status is shown visually in the diagram, not as text; runtime overlays only, the model stays unchanged.
const graphContext = useGraphContextOptional()
let installed: { cell: Cell; overlay: CellOverlay }[] = []
const remove = () => {
  const graph = graphContext?.graph.value
  if (graph) for (const { cell, overlay } of installed) graph.removeCellOverlay(cell, overlay)
  installed = []
}
watch([() => graphContext?.graph.value, () => props.entry], ([graph]) => {
  remove()
  if (!graph) return
  for (const object of props.entry.objects ?? []) {
    const cell = graph.getDataModel().getCell(object.cellId)
    if (!cell) continue
    const status = statuses[statusOf(object)]
    const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: status.icon, color: status.color,
      tooltip: `${object.label || 'Objekt'}: ${status.label}${object.score ? ` (${format(object.score.percent)})` : ''}`, align: 'right', verticalAlign: 'top', offset: { x: 8, y: -8 } })
    graph.addCellOverlay(cell, overlay)
    installed.push({ cell, overlay })
  }
}, { immediate: true })
onBeforeUnmount(remove)
</script>

<style scoped>
.score-feedback__list { list-style: none; padding: 0; font-size: 12px; }
.score-feedback__name { overflow-wrap: anywhere; }
.score-feedback__part { font-size: 11px; padding-left: 24px; }
.score-feedback__hint { font-size: 11px; margin-top: 4px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
</style>
