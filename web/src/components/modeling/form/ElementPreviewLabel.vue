<template>
  <div class="element-preview-label" :title="label">
    <DiagramPreviewItem v-if="element" :element="element" :width="56" :height="40" class="element-preview-label__image" aria-hidden="true" />
    <v-icon v-else size="24" class="element-preview-label__fallback" aria-hidden="true">mdi-shape-outline</v-icon>
    <span class="element-preview-label__text">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import type { DiagramElement } from '@/model/Element'
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'

defineProps<{ element?: DiagramElement; label: string }>()
</script>

<style scoped>
.element-preview-label { display: inline-flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; width: 80px; flex: 0 0 auto; vertical-align: middle; }
.element-preview-label__image { pointer-events: none; border: 0; border-radius: 4px; background: transparent; }
.element-preview-label__fallback { height: 40px; }
.element-preview-label__text { width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: center; font-size: 11px; font-weight: 500; line-height: 1.3; }
</style>
