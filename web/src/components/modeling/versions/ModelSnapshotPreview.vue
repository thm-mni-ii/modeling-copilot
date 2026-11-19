<template>
  <div ref="viewport" class="model-snapshot-preview" :style="{ height: height == null ? '100%' : `${height}px` }">
    <DrawingCanvas v-if="data" ref="previewCanvas" :allow-edit="false" :show-toolbar="false" :show-elements="false" :show-model-sidebar="false" />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import type { Graph } from '@maxgraph/core'
import type { JsonObject } from '@/services/api/types/common'
import { useZoomOperations } from '@/composables/useZoomOperations'

const DrawingCanvas = defineAsyncComponent(() => import('@/components/modeling/canvas/DrawingCanvas.vue'))

const props = withDefaults(
  defineProps<{
    data: JsonObject | null
    height?: number | null
    /** Zentriert das Modell nach jedem Laden mit der Fit-Funktion des Editors. */
    fit?: boolean
  }>(),
  {
    height: 440,
    fit: false
  }
)

const previewCanvas = ref<{ graph?: Graph & { resetViewOnRootChange: boolean }; loadPersistedModel: (data: JsonObject) => void } | null>(null)
const viewport = ref<HTMLElement | null>(null)
defineExpose({ graph: computed(() => previewCanvas.value?.graph) })
const { fitToWindow } = useZoomOperations(computed(() => previewCanvas.value?.graph) as Ref<Graph | undefined>)
let resizeFrame = 0
const resizeObserver = new ResizeObserver(() => {
  cancelAnimationFrame(resizeFrame)
  if (props.fit) resizeFrame = requestAnimationFrame(fitToWindow)
})
watch(viewport, (element, previous) => {
  if (previous) resizeObserver.unobserve(previous)
  if (element) resizeObserver.observe(element)
}, { flush: 'post' })
onBeforeUnmount(() => { resizeObserver.disconnect(); cancelAnimationFrame(resizeFrame) })

watch(
  [() => props.data, previewCanvas],
  async ([data, canvas]) => {
    if (!data || !canvas) return
    await nextTick()
    // Ansicht (Zoom und Verschiebung) beim Wechsel zwischen Patches behalten
    if (canvas.graph) canvas.graph.resetViewOnRootChange = false
    canvas.loadPersistedModel(data)
    if (props.fit) fitToWindow()
  },
  { immediate: true }
)
// Beim ersten Öffnen steht der Graph erst nach dem Laden der Canvas; das Modell ist dann schon darin.
watch(
  () => previewCanvas.value?.graph,
  () => {
    if (props.fit) void nextTick(fitToWindow)
  }
)
</script>

<style scoped>
.model-snapshot-preview {
  min-height: 0;
  min-width: 0;
  overflow: visible;
  border: 1px solid rgba(var(--v-theme-outline), 0.22);
  border-radius: 8px;
}
</style>
