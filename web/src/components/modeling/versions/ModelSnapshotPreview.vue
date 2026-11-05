<template>
  <div class="model-snapshot-preview" :style="{ height: `${height}px` }">
    <DrawingCanvas v-if="data" ref="previewCanvas" :allow-edit="false" :show-toolbar="false" :show-elements="false" :show-model-sidebar="false" />
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref, watch, type Ref } from 'vue'
import type { Graph } from '@maxgraph/core'
import type { JsonObject } from '@/services/api/types/common'
import { useZoomOperations } from '@/composables/useZoomOperations'

const DrawingCanvas = defineAsyncComponent(() => import('@/components/modeling/canvas/DrawingCanvas.vue'))

const props = withDefaults(
  defineProps<{
    data: JsonObject | null
    height?: number
    /** Zentriert das Modell nach jedem Laden mit der Fit-Funktion des Editors. */
    fit?: boolean
  }>(),
  {
    height: 440,
    fit: false
  }
)

const previewCanvas = ref<{ graph?: Graph & { resetViewOnRootChange: boolean }; loadPersistedModel: (data: JsonObject) => void } | null>(null)
const { fitToWindow } = useZoomOperations(computed(() => previewCanvas.value?.graph) as Ref<Graph | undefined>)

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
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.22);
  border-radius: 8px;
}
</style>
