<template>
  <svg viewBox="0 0 190 64" width="190" height="64" role="img" :aria-label="`${tries} asks with a pause of ${pauseMs} milliseconds, up to ${total} in all`">
    <text x="95" y="14" class="label" text-anchor="middle">ask, wait, ask again</text>
    <circle v-for="at in dots" :key="at" :cx="6 + (at - 1) * step" cy="32" r="4" class="dot" />
    <text v-if="tries > dots" x="184" y="50" class="label" text-anchor="end">+{{ tries - dots }}</text>
    <line :x1="6" :x2="6 + (dots - 1) * step" y1="44" y2="44" class="span" />
    <text x="95" y="62" class="label" text-anchor="middle">up to {{ total }}</text>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/** The tries as dots (twelve at most) and how long they take together. */
const props = defineProps<{ tries: number; pauseMs: number }>()

const dots = computed(() => Math.max(1, Math.min(Math.round(props.tries) || 1, 12)))
const step = computed(() => (dots.value > 1 ? 178 / (dots.value - 1) : 0))
const total = computed(() => {
  const ms = (Number(props.tries) || 0) * (Number(props.pauseMs) || 0)
  return ms >= 1000 ? `${Math.round(ms / 100) / 10} s` : `${ms} ms`
})
</script>

<style scoped>
.dot {
  fill: rgb(var(--v-theme-warning));
}

.span {
  stroke: rgb(var(--v-theme-warning));
  stroke-width: 2;
}

.label {
  font-size: 11px;
  fill: rgba(var(--v-theme-on-surface), 0.65);
}
</style>
