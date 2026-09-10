<template>
  <div class="diagram-preview" :style="previewBoxStyle">
    <div ref="containerRef" class="diagram-preview__canvas"></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch, nextTick, computed } from 'vue'
import { Graph } from '@maxgraph/core'
import type { DiagramElement } from '@/model/DiagramLanguage'
import { createCellFromElement, addCellToGraph } from '@/utils/elementFactory'
import { createPreviewGraph, destroyPreviewGraph, fitPreviewGraph } from '@/utils/previewGraph'

interface Props {
  element?: DiagramElement
  width?: number
  height?: number
  size?: number
}

const props = defineProps<Props>()

const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null

const previewSize = computed(() => props.size ?? 120)

const renderGraph = async () => {
  await nextTick()
  if (!containerRef.value) return

  if (graph) {
    graph = destroyPreviewGraph(graph)
  }

  if (!props.element) return

  const container = containerRef.value
  graph = createPreviewGraph(container)
  const g = graph

  const parent = g.getDefaultParent()

  const model = g.getDataModel()
  model.beginUpdate()
  try {
    insertElementPreview(g, parent, props.element)
  } finally {
    model.endUpdate()
  }

  fitPreviewGraph(g)
}

const insertElementPreview = (graph: Graph, parent: any, element: DiagramElement) => {
  const cell = createCellFromElement(element, 0, 0)
  addCellToGraph(graph, cell, element, parent)
}

onMounted(() => {
  renderGraph()
})

watch(
  () => [props.element, previewSize.value],
  () => {
    renderGraph()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  graph = destroyPreviewGraph(graph)
})

const previewBoxStyle = computed(() => ({
  width: `${props.width ?? previewSize.value * 1.6}px`,
  height: `${props.height ?? previewSize.value}px`
}))
</script>

<style scoped>
.diagram-preview {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(var(--v-theme-surface), 0.4);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.1);
}

.diagram-preview__canvas {
  width: 100%;
  height: 100%;
}
</style>
