<template>
  <div ref="viewport" class="timeline-fit-viewport">
    <div ref="content" class="timeline-fit-content" :style="{ zoom: scale }"><slot /></div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ minWidth?: number; reflow?: boolean }>(), { minWidth: 0, reflow: true })
const viewport = ref<HTMLElement | null>(null)
const content = ref<HTMLElement | null>(null)
const scale = ref(1)
let frame = 0
let settledLayout = ''
const layoutKey = () => {
  if (!viewport.value || !content.value) return ''
  return [viewport.value.clientWidth, viewport.value.clientHeight,
    content.value.offsetWidth, content.value.offsetHeight,
    content.value.scrollWidth, content.value.scrollHeight].join(':')
}
const settle = (fitted: number) => {
  if (!content.value || !viewport.value) return
  scale.value = Math.min(fitted, viewport.value.clientWidth / Math.max(1, content.value.scrollWidth),
    viewport.value.clientHeight / Math.max(1, content.value.scrollHeight))
  // Commit before recording the resulting layout, so our own zoom/width changes
  // cannot start another ResizeObserver -> measure -> zoom cycle.
  content.value.style.setProperty('zoom', String(scale.value))
  settledLayout = layoutKey()
}
const measure = () => {
  if (!viewport.value || !content.value) return
  const availableWidth = viewport.value.clientWidth
  const availableHeight = viewport.value.clientHeight
  if (!availableWidth || !availableHeight) return
  if (!props.reflow) {
    // Timeline label lanes are calculated for this width. Reflowing to a wider
    // width while shrinking would change those lanes and then resize us again.
    content.value.style.width = `${Math.max(props.minWidth, availableWidth) - 2}px`
    settle(1)
    return
  }
  // Reflow into the whole column before shrinking. A transform would leave the
  // original layout bounds (and scrollbars) behind; zoom shrinks those too.
  let lower = 0
  let upper = Math.min(1, availableWidth / Math.max(1, props.minWidth))
  const fits = (candidate: number) => {
    let naturalWidth = availableWidth / candidate - 2
    content.value!.style.width = `${naturalWidth}px`
    // Account for intrinsic child margins (for example the slider's track).
    // Otherwise even a tiny overhang would reject every readable zoom level.
    for (let pass = 0; pass < 2; pass++) {
      const overhang = content.value!.scrollWidth - naturalWidth
      if (overhang <= 1) break
      naturalWidth = Math.max(1, naturalWidth - overhang)
      content.value!.style.width = `${naturalWidth}px`
    }
    return content.value!.scrollWidth * candidate <= availableWidth + 1 &&
      content.value!.scrollHeight * candidate <= availableHeight
  }
  if (fits(upper)) lower = upper
  else for (let iteration = 0; iteration < 12; iteration++) {
    const candidate = (lower + upper) / 2
    if (fits(candidate)) lower = candidate
    else upper = candidate
  }
  const fitted = lower || upper
  fits(fitted)
  settle(fitted)
}
const observer = new ResizeObserver(() => {
  if (layoutKey() === settledLayout) return
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(measure)
})
onMounted(() => {
  if (viewport.value) observer.observe(viewport.value)
  if (content.value) observer.observe(content.value)
  measure()
})
onBeforeUnmount(() => { observer.disconnect(); cancelAnimationFrame(frame) })
</script>

<style scoped>
.timeline-fit-viewport { position: relative; width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: visible; }
.timeline-fit-content { position: absolute; inset: 0 auto auto 0; display: flow-root; overflow: visible; }
</style>
