<template>
  <div class="review-canvas">
    <div class="d-flex flex-wrap align-center ga-2 pa-2 border-b">
      <v-btn-toggle :model-value="showFeedback ? 'both' : 'model'" mandatory density="compact" @update:model-value="emit('update:showFeedback', $event === 'both')"><v-btn value="model">Model only</v-btn><v-btn value="both">Model + feedback</v-btn></v-btn-toggle>
      <v-spacer /><v-btn size="small" @click="graph?.zoomOut()" aria-label="Zoom out">−</v-btn><v-btn size="small" @click="graph?.zoomIn()" aria-label="Zoom in">+</v-btn><v-btn size="small" @click="fit">Fit</v-btn>
    </div>
    <div ref="container" class="review-graph" role="region" aria-label="Read-only submitted model" />
    <v-alert v-if="error" type="error">{{ error }}</v-alert>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CellHighlight, InternalEvent, type Cell, type Graph, type MouseListenerSet } from '@maxgraph/core'
import type { ModelPackage } from '@/utils/modelPackage'
import { decodePackageModel } from '@/utils/modelPackage'
import type { FeedbackOverlayConfig, FeedbackState } from '@/model/Feedback'
import { createOverlayFromConfig } from '@/utils/feedbackOverlays'
import { createPreviewGraph, destroyPreviewGraph, fitPreviewGraph } from '@/utils/previewGraph'
import { importModelFromXml } from '@/utils/modelPersistence'
import { registerCustomShapes, registerElementShapes } from '@/utils/shapeRegistry'

export interface ReviewCanvasMark {
  key: string
  cellId: string
  state: FeedbackState
  config: FeedbackOverlayConfig
}
const props = defineProps<{ package: ModelPackage; marks: ReviewCanvasMark[]; selectedCellId: string | null; showFeedback: boolean }>()
const emit = defineEmits<{ select: [cellId: string, path: string]; overlay: [keys: string[], cellId: string]; 'update:showFeedback': [show: boolean] }>()
const container = ref<HTMLDivElement>()
const error = ref('')
let graph: Graph | null = null
let highlight: CellHighlight | null = null
const pathOf = (cell: Cell) => {
  const names: string[] = []
  let current: Cell | null = cell
  while (current?.getParent()?.getParent()) {
    names.unshift(String(current.value || (current as Cell & { diagramElementType?: string }).diagramElementType || 'Object').replace(/<[^>]*>/g, ''))
    current = current.getParent()
  }
  return names.join(' › ')
}
const mouseListener: MouseListenerSet = {
  mouseDown() {},
  mouseMove() {},
  mouseUp(_sender, event) {
    const cell = event.getCell()
    if (cell && (cell.isVertex() || cell.isEdge())) emit('select', cell.id!, pathOf(cell))
  }
}
const fit = () => {
  if (graph) fitPreviewGraph(graph, 30)
}
const highlightSelected = () => {
  if (!graph || !highlight) return
  const cell = props.showFeedback && props.selectedCellId ? graph.getDataModel().getCell(props.selectedCellId) : null
  if (cell) {
    const parents: Cell[] = []
    for (let parent = cell.getParent(); parent?.getParent(); parent = parent.getParent()) if (parent.isCollapsed()) parents.unshift(parent)
    if (parents.length) graph.foldCells(false, false, parents)
    graph.scrollCellToVisible(cell, true)
  }
  highlight.highlight(cell ? graph.view.getState(cell) : null)
}
const drawMarks = () => {
  if (!graph) return
  const visit = (cell: Cell) => {
    graph!.removeCellOverlays(cell)
    cell.getChildren().forEach(visit)
  }
  visit(graph.getDataModel().getRoot()!)
  if (props.showFeedback) {
    const groups = new Map<string, ReviewCanvasMark[]>()
    for (const mark of props.marks) {
      const key = `${mark.cellId}:${mark.state}`
      groups.set(key, [...(groups.get(key) ?? []), mark])
    }
    for (const marks of groups.values()) {
      const mark = marks[0]
      const cell = graph.getDataModel().getCell(mark.cellId)
      if (!cell) continue
      const overlay = createOverlayFromConfig({ ...mark.config, tooltip: `${mark.config.tooltip ?? mark.state}${marks.length > 1 ? ` (${marks.length})` : ''}` })
      overlay.addListener(InternalEvent.CLICK, () =>
        emit(
          'overlay',
          marks.map((m) => m.key),
          mark.cellId
        )
      )
      graph.addCellOverlay(cell, overlay)
    }
  }
  highlightSelected()
}
const load = async () => {
  if (!graph) return
  error.value = ''
  try {
    decodePackageModel(props.package.model.xml)
    registerCustomShapes()
    props.package.languages.forEach((language) => language.data.elements.forEach(registerElementShapes))
    importModelFromXml(graph, props.package.model.xml)
    // Legacy feedback remains stored in the package but does not become reviewer feedback.
    graph
      .getDataModel()
      .getRoot()
      ?.getChildren()
      .forEach((layer, index) => layer.setVisible(index === 0))
    graph.refresh()
    await nextTick()
    fit()
    drawMarks()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'The model could not be displayed.'
  }
}
watch(() => props.package.model.xml, load)
watch([() => props.marks, () => props.showFeedback], drawMarks, { deep: true })
watch(() => props.selectedCellId, highlightSelected)
onMounted(async () => {
  if (!container.value) return
  graph = createPreviewGraph(container.value)
  graph.setCellsSelectable(false)
  graph.setTooltips(true)
  graph.addMouseListener(mouseListener)
  highlight = new CellHighlight(graph, '#1565c0', 3)
  await load()
})
onBeforeUnmount(() => {
  highlight?.destroy()
  graph?.removeMouseListener(mouseListener)
  graph = destroyPreviewGraph(graph)
})
defineExpose({
  pathOf: (cellId: string) => {
    const cell = graph?.getDataModel().getCell(cellId)
    return cell ? pathOf(cell) : cellId
  }
})
</script>

<style scoped>
.review-canvas {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 1px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}
.review-graph {
  flex: 1;
  min-height: 520px;
  overflow: auto;
  background: white;
}
</style>
