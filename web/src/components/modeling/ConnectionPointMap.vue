<template>
  <svg :viewBox="viewBox" :style="mapStyle" class="connection-point-map" role="group" :aria-label="ariaLabel">
    <rect
      :x="elementBounds.x"
      :y="elementBounds.y"
      :width="elementBounds.width"
      :height="elementBounds.height"
      rx="4"
      fill="rgba(var(--v-theme-primary), 0.04)"
      stroke="currentColor"
    />
    <text
      :x="elementBounds.x + elementBounds.width / 2"
      :y="elementBounds.y + elementBounds.height / 2 + 3"
      text-anchor="middle"
      font-size="10"
      fill="currentColor"
    >{{ element.defaultLabel || element.type }}</text>
    <circle
      v-for="marker in markers"
      :key="marker.id"
      :cx="elementBounds.x + marker.point.x * elementBounds.width"
      :cy="elementBounds.y + marker.point.y * elementBounds.height"
      r="5"
      :fill="marker.selected ? 'rgb(var(--v-theme-primary))' : 'rgb(var(--v-theme-surface))'"
      stroke="currentColor"
      role="button"
      :aria-label="marker.label"
      :aria-pressed="marker.selected ?? false"
      :tabindex="disabled ? -1 : 0"
      @click="select(marker.id)"
      @keydown.enter.prevent="select(marker.id)"
      @keydown.space.prevent="select(marker.id)"
    >
      <title>{{ marker.label }}</title>
    </circle>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AnchorPoint, DiagramElement } from '@/model/Element'

interface Marker {
  id: string
  label: string
  point: AnchorPoint
  selected?: boolean
}

const props = withDefaults(defineProps<{
  element: DiagramElement
  markers: Marker[]
  ariaLabel?: string
  disabled?: boolean
  width?: number
  height?: number
}>(), {
  ariaLabel: undefined,
  disabled: false,
  width: 180,
  height: 130
})
const emit = defineEmits<{ select: [id: string] }>()

const viewBox = '-15 -15 150 110'
const mapStyle = computed(() => ({ width: `${props.width}px`, height: `${props.height}px` }))
const elementBounds = computed(() => {
  const maxWidth = 120
  const maxHeight = 80
  const elementWidth = Math.max(props.element.width, 0.01)
  const elementHeight = Math.max(props.element.height, 0.01)
  const scale = Math.min(maxWidth / elementWidth, maxHeight / elementHeight)
  const width = elementWidth * scale
  const height = elementHeight * scale
  return {
    x: (maxWidth - width) / 2,
    y: (maxHeight - height) / 2,
    width,
    height
  }
})

const select = (id: string) => {
  if (!props.disabled) emit('select', id)
}
</script>

<style scoped>
.connection-point-map {
  display: block;
  max-width: 100%;
  margin: 0 auto;
  overflow: visible;
}

circle {
  cursor: pointer;
}

circle:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
}
</style>
