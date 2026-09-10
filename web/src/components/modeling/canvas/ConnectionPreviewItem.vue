<template>
  <div class="connection-preview" :style="previewBoxStyle">
    <div ref="containerRef" class="connection-preview__canvas"></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch, nextTick, computed } from 'vue'
import { Graph } from '@maxgraph/core'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import { renderSimpleConnectionPreview } from '@/utils/connectionPreview'
import { createPreviewGraph, destroyPreviewGraph, fitPreviewGraph } from '@/utils/previewGraph'

interface Props {
  connection?: DiagramConnection
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

  if (!props.connection) return

  graph = createPreviewGraph(containerRef.value)
  renderSimpleConnectionPreview(graph, props.connection)
  fitPreviewGraph(graph)
}

onMounted(() => {
  renderGraph()
})

watch(
  () => [props.connection, previewSize.value],
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
.connection-preview {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(var(--v-theme-surface), 0.4);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.1);
}

.connection-preview__canvas {
  width: 100%;
  height: 100%;
}
</style>
