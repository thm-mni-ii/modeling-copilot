<template>
  <div ref="containerRef" class="model-excerpt-preview" role="img" :aria-label="label" :style="{ height: `${height ?? 200}px` }" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Graph } from '@maxgraph/core'
import { importModelFromXml } from '@/utils/modelPersistence'
import { createPreviewGraph, destroyPreviewGraph, fitPreviewGraph } from '@/utils/previewGraph'

// Read-only rendering of a model excerpt (stored maxGraph XML) through the canvas' own import path.
const props = defineProps<{ xml: string; label: string; height?: number }>()
const containerRef = ref<HTMLDivElement | null>(null)
let graph: Graph | null = null

const render = () => {
  graph = destroyPreviewGraph(graph)
  if (!containerRef.value) return
  graph = createPreviewGraph(containerRef.value)
  try {
    importModelFromXml(graph, props.xml)
  } catch {
    graph = destroyPreviewGraph(graph)
    return
  }
  fitPreviewGraph(graph)
}
onMounted(render)
watch(() => props.xml, render)
onBeforeUnmount(() => { graph = destroyPreviewGraph(graph) })
</script>

<style scoped>
.model-excerpt-preview {
  width: 100%;
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-outline), 0.15);
  background-color: rgba(var(--v-theme-surface), 0.4);
}
</style>
