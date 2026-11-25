<template>
  <div class="check-feedback">
    <CompletionGateBars v-if="gate" :result="gate" dense />
    <p v-else class="check-feedback__text">{{ entry.overview.recognized }} von {{ entry.overview.expected }} erwarteten Objekten erkannt.</p>
    <ul v-if="deviating.length" class="check-feedback__list" aria-label="Erkannt, aber abweichend">
      <li v-for="object in deviating" :key="object.cellId">
        <v-icon :icon="recognizedWithLocalIssuesDisplay.icon" :color="recognizedWithLocalIssuesDisplay.color" size="14" />
        <span>{{ deviationText(object) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { InternalEvent } from '@maxgraph/core'
import CompletionGateBars from '@/components/learningPaths/CompletionGateBars.vue'
import { useModelFileContext } from '@/composables/useModelFileContext'
import { completionGate } from '@/utils/completionGate'
import { recognizedWithLocalIssuesDisplay } from '@/utils/analysisFeedback'
import type { Cell, CellOverlay } from '@maxgraph/core'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createOverlayFromConfig } from '@/utils/feedbackOverlays'
import type { EvaluationFeedback, HelpFeedbackEntry, HelpFeedbackObject } from '@/services/api/types/evaluation'

const props = defineProps<{ entry: HelpFeedbackEntry; isCurrent?: (id: string) => boolean }>()
// Same breakdown and thresholds as the completion check ("Abschließen").
const files = useModelFileContext()
const gate = computed(() => {
  if (!props.entry.recognition) return null
  try { return completionGate(files?.completionGate.value ?? null, { recognitions: [{ referenceKey: props.entry.referenceKey ?? '', recognition: props.entry.recognition }] } as EvaluationFeedback) }
  catch { return null }
})

// Recognized, but an own property (type, formatting, owner, endpoints) differs: outlined mark instead of green.
const deviating = computed(() => (props.entry.objects ?? []).filter(object => object.checks.length && (!props.isCurrent || props.isCurrent(object.cellId))))
const deviationText = (object: HelpFeedbackObject) => `Erkannt, aber: ${object.checks.map(check => check.text).join(' ')}`

// Check marks on every recognized object; runtime overlays only, the model stays unchanged.
const graphContext = useGraphContextOptional()
watch([() => graphContext?.graph.value, () => props.entry, () => props.isCurrent], ([graph], _, onCleanup) => {
  if (!graph) return
  let installed: { cell: Cell; overlay: CellOverlay }[] = []
  const remove = () => {
    for (const { cell, overlay } of installed) graph.removeCellOverlay(cell, overlay)
    installed = []
  }
  const refresh = () => {
    remove()
    for (const object of props.entry.objects ?? []) {
      if (props.isCurrent && !props.isCurrent(object.cellId)) continue
      const cell = graph.getDataModel().getCell(object.cellId)
      if (!cell) continue
      const differs = object.checks.length > 0
      const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 },
        icon: differs ? recognizedWithLocalIssuesDisplay.icon : 'mdi-check-circle', color: differs ? recognizedWithLocalIssuesDisplay.color : '#2E7D32',
        tooltip: differs ? deviationText(object) : `${object.label || 'Objekt'}: richtig erkannt`, align: 'right', verticalAlign: 'top', offset: { x: 8, y: -8 } })
      graph.addCellOverlay(cell, overlay)
      installed.push({ cell, overlay })
    }
  }
  graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
  refresh()
  onCleanup(() => { graph.getDataModel().removeListener(refresh); remove() })
}, { immediate: true })
</script>

<style scoped>
.check-feedback__text { font-size: 12px; line-height: 1.5; }
.check-feedback__list { list-style: none; padding: 0; margin-top: 8px; }
.check-feedback__list li { display: flex; gap: 4px; align-items: baseline; font-size: 12px; line-height: 1.45; margin-top: 3px; }
</style>
