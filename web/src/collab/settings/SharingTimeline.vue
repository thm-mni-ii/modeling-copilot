<template>
  <figure ref="figure" class="timeline">
    <svg ref="svg" :viewBox="`0 0 ${width} 178`" :width="width" height="178" role="group" aria-label="What happens when the host or a visitor stays away">
      <text x="20" y="18" class="t-text">Host is away</text>
      <line :x1="X0" :x2="X1" y1="52" y2="52" class="t-axis" />
      <line :x1="X0" :x2="x(notice)" y1="52" y2="52" class="t-line t-ok" />
      <line :x1="x(notice)" :x2="x(lock)" y1="52" y2="52" class="t-line t-warn" />
      <line :x1="x(lock)" :x2="x(end)" y1="52" y2="52" class="t-line t-bad" />
      <rect v-for="at in [lock, end]" :key="at" :x="x(at)" y="46" :width="sweepWidth(at)" height="12" class="t-sweep" />
      <text v-if="x(notice) - X0 > 40" :x="(X0 + x(notice)) / 2" y="76" class="t-text" text-anchor="middle">fine</text>
      <text v-if="x(lock) - x(notice) > 70" :x="(x(notice) + x(lock)) / 2" y="76" class="t-text" text-anchor="middle">notice for visitors</text>
      <text v-if="x(end) - x(lock) > 70" :x="(x(lock) + x(end)) / 2" y="76" class="t-text" text-anchor="middle">room locked</text>
      <text :x="Math.min(x(end), X1)" y="94" class="t-text" text-anchor="end">visitors leave</text>

      <text x="20" y="122" class="t-text">A visitor is away</text>
      <line :x1="X0" :x2="X1" y1="148" y2="148" class="t-axis" />
      <line :x1="X0" :x2="x(visitor)" y1="148" y2="148" class="t-line t-ok" />
      <rect :x="x(visitor)" y="142" :width="sweepWidth(visitor)" height="12" class="t-sweep" />
      <text :x="x(visitor) > width * 0.6 ? x(visitor) - 10 : x(visitor) + 10" y="170" class="t-text" :text-anchor="x(visitor) > width * 0.6 ? 'end' : 'start'">leaves, working copy deleted</text>

      <!-- The handles come last, so they lie above the lines; each one is a slider for its setting. -->
      <g
        v-for="handle in handles"
        :key="handle.id"
        class="t-handle"
        :class="{ 't-handle--active': dragging === handle.id }"
        role="slider"
        tabindex="0"
        :aria-label="handle.name"
        :aria-valuemin="boundsOf(handle.id)[0]"
        :aria-valuemax="boundsOf(handle.id)[1]"
        :aria-valuenow="handle.at"
        :aria-valuetext="label(handle.at)"
        @pointerdown.prevent="start($event, handle.id)"
        @pointermove="move($event, handle)"
        @pointerup="stop"
        @pointercancel="stop"
        @keydown="press($event, handle)"
      >
        <circle :cx="x(handle.at)" :cy="handle.y" r="14" class="t-hit" />
        <circle :cx="x(handle.at)" :cy="handle.y" r="5.5" class="t-dot" />
        <text :x="x(handle.at)" :y="handle.y - 14" class="t-value" text-anchor="middle">{{ label(handle.at) }}</text>
      </g>
    </svg>
    <figcaption class="t-note">
      <span>Drag a dot, or use the arrow keys (Shift for 10 s). The backend looks every {{ sweep }} s, so locking and leaving can come up to {{ sweep }} s later (dashed).</span>
      <v-btn variant="outlined" size="small" prepend-icon="mdi-restore" :disabled="!resettable" @click="emit('reset')">Reset to defaults</v-btn>
    </figcaption>
  </figure>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { COLLAB_LIMITS } from '@/collab/settings/collabSettings'
import { timeLabel as label } from '@/collab/settings/timeLabel'

/** The waits as the form shows them, in seconds; a value that is not a number yet falls back to the default. */
const props = defineProps<{ values: Record<string, unknown>; resettable: boolean }>()
const emit = defineEmits<{ update: [key: string, seconds: number]; reset: [] }>()

const numberOf = (key: string, fallback: number) => {
  const value = props.values[key]
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback
}
const notice = computed(() => numberOf('hostAwayMs', 30))
const lock = computed(() => numberOf('hostGraceSeconds', 120))
const end = computed(() => numberOf('hostEndSeconds', 300))
const visitor = computed(() => numberOf('visitorGraceSeconds', 120))
const sweep = computed(() => numberOf('sweepSeconds', 30))

// Both lines share one scale, so a visitor and the host can be compared; the scale stays fixed while a dot is dragged.
const X0 = 20
// The drawing is as wide as the space it has, so the text keeps its size.
const width = ref(640)
const X1 = computed(() => width.value - 20)
const figure = ref<HTMLElement>()
let observer: ResizeObserver | undefined
onMounted(() => {
  const measure = () => (width.value = Math.max(320, Math.round(figure.value?.clientWidth ?? 640)))
  measure()
  observer = new ResizeObserver(measure)
  if (figure.value) observer.observe(figure.value)
})
onBeforeUnmount(() => observer?.disconnect())
const dragging = ref<string | null>(null)
const frozenSpan = ref(0)
// Room beyond the largest wait, at least ten minutes, so a dot can be dragged further out.
const naturalSpan = computed(() => Math.max(Math.max(notice.value, lock.value, end.value, visitor.value) * 1.5, 600))
const span = computed(() => (dragging.value ? frozenSpan.value : naturalSpan.value))
const x = (seconds: number) => X0 + ((X1.value - X0) * seconds) / span.value
/** The sweep only looks every so often, so the backend acts up to that much later than the wait. */
const sweepWidth = (seconds: number) => Math.max(0, Math.min(x(seconds + sweep.value), X1.value) - x(seconds))

const limits = COLLAB_LIMITS.sharing
const handles = computed(() => [
  { id: 'notice', key: 'hostAwayMs', at: notice.value, y: 52, name: 'Visitors are told after' },
  { id: 'lock', key: 'hostGraceSeconds', at: lock.value, y: 52, name: 'Room locks after' },
  { id: 'end', key: 'hostEndSeconds', at: end.value, y: 52, name: 'All visitors leave after' },
  { id: 'visitor', key: 'visitorGraceSeconds', at: visitor.value, y: 148, name: 'Visitor leaves after' }
])
type Handle = (typeof handles.value)[number]

/** The same rules as the fields: notice before lock, lock not after the end, and no wait shorter than the backend's look. */
const boundsOf = (id: string): [number, number] => {
  if (id === 'notice') return [limits.hostAwayMs.min / 1000, Math.min(limits.hostAwayMs.max / 1000, lock.value - 1)]
  if (id === 'lock') return [Math.max(limits.hostGraceSeconds.min, notice.value + 1, sweep.value), Math.min(limits.hostGraceSeconds.max, end.value)]
  if (id === 'end') return [Math.max(limits.hostEndSeconds.min, lock.value), limits.hostEndSeconds.max]
  return [Math.max(limits.visitorGraceSeconds.min, sweep.value), limits.visitorGraceSeconds.max]
}
const set = (handle: Handle, seconds: number) => {
  const [low, high] = boundsOf(handle.id)
  const next = Math.min(Math.max(Math.round(seconds), low), high)
  if (next !== handle.at) emit('update', handle.key, next)
}

const svg = ref<SVGSVGElement>()
const start = (event: PointerEvent, id: string) => {
  ;(event.currentTarget as Element).setPointerCapture(event.pointerId)
  frozenSpan.value = naturalSpan.value
  dragging.value = id
}
const move = (event: PointerEvent, handle: Handle) => {
  const matrix = svg.value?.getScreenCTM()
  if (dragging.value !== handle.id || !matrix) return
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
  let seconds = ((point.x - X0) / (X1.value - X0)) * frozenSpan.value
  // Held at the right edge, the scale grows, so the dot can go on.
  if (seconds > frozenSpan.value * 0.97) frozenSpan.value *= 1.25
  seconds = Math.min(Math.max(seconds, 0), frozenSpan.value)
  set(handle, seconds)
}
const stop = () => (dragging.value = null)
const press = (event: KeyboardEvent, handle: Handle) => {
  const direction = ['ArrowRight', 'ArrowUp'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 0
  if (!direction) return
  event.preventDefault()
  set(handle, handle.at + direction * (event.shiftKey ? 10 : 1))
}
</script>

<style scoped>
.timeline {
  margin: 0 0 8px;
}

.t-text {
  font-size: 12px;
  fill: rgba(var(--v-theme-on-surface), 0.65);
}

.t-value {
  font-size: 12px;
  fill: rgb(var(--v-theme-on-surface));
  pointer-events: none;
}

.t-axis {
  stroke: rgba(var(--v-theme-on-surface), 0.25);
  stroke-width: 2;
}

.t-line {
  stroke-width: 6;
}

.t-ok {
  stroke: rgb(var(--v-theme-success));
}

.t-warn {
  stroke: rgb(var(--v-theme-warning));
}

.t-bad {
  stroke: rgb(var(--v-theme-error));
}

.t-sweep {
  fill: none;
  stroke: rgba(var(--v-theme-on-surface), 0.45);
  stroke-dasharray: 3 2;
}

.t-handle {
  cursor: ew-resize;
  outline: none;
  touch-action: none;
}

.t-hit {
  fill: transparent;
}

.t-dot {
  fill: rgb(var(--v-theme-on-surface));
  stroke: rgb(var(--v-theme-surface));
  stroke-width: 1.5;
}

.t-handle:hover .t-dot,
.t-handle--active .t-dot {
  fill: rgb(var(--v-theme-primary));
}

.t-handle:focus-visible .t-hit {
  stroke: rgb(var(--v-theme-primary));
  stroke-width: 2;
}

.t-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
