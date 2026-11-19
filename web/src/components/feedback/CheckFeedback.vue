<template>
  <div class="check-feedback">
    <CompletionGateBars v-if="gate" :result="gate" dense />
    <p v-else class="check-feedback__text">{{ entry.overview.recognized }} von {{ entry.overview.expected }} erwarteten Objekten erkannt.</p>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { InternalEvent } from '@maxgraph/core'
import CompletionGateBars from '@/components/learningPaths/CompletionGateBars.vue'
import { useModelFileContext } from '@/composables/useModelFileContext'
import { completionGate } from '@/utils/completionGate'
import type { Cell, CellOverlay } from '@maxgraph/core'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createOverlayFromConfig } from '@/utils/feedbackOverlays'
import type { EvaluationFeedback, HelpFeedbackEntry } from '@/services/api/types/evaluation'

const props = defineProps<{ entry: HelpFeedbackEntry; isCurrent?: (id: string) => boolean }>()
// Same breakdown and thresholds as the completion check ("Abschließen").
const files = useModelFileContext()
const gate = computed(() => {
  if (!props.entry.recognition) return null
  try { return completionGate(files?.completionGate.value ?? null, { recognitions: [{ referenceKey: props.entry.referenceKey ?? '', recognition: props.entry.recognition }] } as EvaluationFeedback) }
  catch { return null }
})

// Green check marks on every correct object; runtime overlays only, the model stays unchanged.
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
      const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: 'mdi-check-circle', color: '#2E7D32',
        tooltip: `${object.label || 'Objekt'}: richtig erkannt`, align: 'right', verticalAlign: 'top', offset: { x: 8, y: -8 } })
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
</style>
