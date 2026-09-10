<template>
  <div class="model-snapshot-preview" :style="{ height: `${height}px` }">
    <DrawingCanvas v-if="data" ref="previewCanvas" :allow-edit="false" :show-toolbar="false" :show-elements="false" :show-model-sidebar="false" />
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, nextTick, ref, watch } from 'vue'
import type { JsonObject } from '@/services/api/types/common'

const DrawingCanvas = defineAsyncComponent(() => import('@/components/modeling/canvas/DrawingCanvas.vue'))

const props = withDefaults(
  defineProps<{
    data: JsonObject | null
    height?: number
  }>(),
  {
    height: 440
  }
)

const previewCanvas = ref<{ loadPersistedModel: (data: JsonObject) => void } | null>(null)

watch(
  [() => props.data, previewCanvas],
  async ([data, canvas]) => {
    if (!data || !canvas) return
    await nextTick()
    canvas.loadPersistedModel(data)
  },
  { immediate: true }
)
</script>

<style scoped>
.model-snapshot-preview {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-outline), 0.22);
  border-radius: 8px;
}
</style>
