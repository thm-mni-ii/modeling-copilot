<template>
  <div>
    <div v-for="(row, index) in result.categories" :key="row.key" class="gate-row">
      <div class="d-flex justify-space-between ga-2" :class="dense ? 'text-caption' : 'text-body-2'">
        <strong>{{ row.label }}</strong>
        <span>{{ format(row.percent) }}<span v-if="row.required != null" class="text-medium-emphasis"> · mind. {{ format(row.required) }}</span></span>
      </div>
      <div class="gate-bar">
        <v-progress-linear :model-value="index < revealed ? row.percent : 0" :color="row.required == null ? 'primary' : row.met ? 'success' : 'error'" :height="dense ? 6 : 10" rounded :aria-label="`${row.label}: ${format(row.percent)}${row.required == null ? '' : `, nötig ${format(row.required)}`}`" />
        <span v-if="row.required != null" class="gate-marker" :style="{ left: `${row.required}%` }" />
      </div>
    </div>
    <div v-if="done" class="gate-total">
      <span :class="dense ? 'text-caption' : 'text-body-2'">Gesamt erkannt</span>
      <strong :class="[dense ? 'text-h6' : 'text-h5', result.gated ? (result.passed ? 'text-success' : 'text-error') : '']">{{ format(result.overall.percent) }}</strong>
      <span v-if="result.overall.required != null" class="text-caption text-medium-emphasis">mind. {{ format(result.overall.required) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { GateResult } from '@/utils/completionGate'

const props = defineProps<{ result: GateResult; animate?: boolean; dense?: boolean }>()
const emit = defineEmits<{ done: [] }>()
// Bars fill one after another, then the total appears.
const revealed = ref(0)
const done = computed(() => revealed.value > props.result.categories.length)
let timer: ReturnType<typeof setInterval> | null = null
const stop = () => { if (timer) clearInterval(timer); timer = null }
watch(() => props.result, (result) => {
  stop()
  const instant = !props.animate || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  revealed.value = instant ? result.categories.length + 1 : 0
  if (!instant) timer = setInterval(() => { if (++revealed.value > result.categories.length) stop() }, 450)
}, { immediate: true })
watch(done, (value) => { if (value) emit('done') }, { immediate: true })
onBeforeUnmount(stop)

const number = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 })
// Rounded down so a bar never looks reached while it is not.
const format = (value: number) => `${number.format(Math.floor(value))} %`
</script>

<style scoped>
.gate-row { margin-bottom: 12px; }
.gate-bar { position: relative; margin-top: 4px; }
.gate-bar :deep(.v-progress-linear__determinate) { transition-duration: 0.6s; }
.gate-marker { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: rgb(var(--v-theme-on-surface)); border-radius: 1px; pointer-events: none; }
.gate-total { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
</style>
