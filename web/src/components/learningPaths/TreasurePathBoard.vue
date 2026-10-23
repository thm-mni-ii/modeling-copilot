<template>
  <section class="treasure-journey" aria-label="Your treasure journey">
    <header class="journey-summary">
      <div>
        <p class="journey-eyebrow">YOUR TREASURE JOURNEY</p>
        <h2>{{ finished ? 'Learning path completed!' : 'One task. A new treasure.' }}</h2>
        <p>{{ run.completed }} of {{ run.total }} tasks completed · {{ run.progress }} %</p>
      </div>
      <div class="coin-counter" aria-label="Collected coins" role="status" aria-live="polite">
        <TreasureMapArt kind="coin" />
        <div>
          <strong>{{ run.completed }}</strong
          ><span>{{ run.completed === 1 ? 'coin' : 'coins' }} collected</span>
        </div>
      </div>
      <v-progress-linear class="journey-progress" :model-value="run.progress" color="#467966" bg-color="#e7dcc2" rounded height="8" aria-label="Treasure journey progress" />
    </header>

    <div class="journey-legend" aria-label="Legend">
      <span><v-icon size="16">mdi-lock-outline</v-icon> Locked</span>
      <span><i class="legend-dot" /> Available</span>
      <span><v-icon size="16" color="#32736d">mdi-pencil</v-icon> In progress</span>
      <span><v-icon size="16" color="#397052">mdi-check-circle</v-icon> Completed</span>
    </div>
    <p class="map-hint">Select a treasure chest to open your task. The map shows the sequence; you can choose any available task.</p>

    <div v-if="!run.steps.length" class="empty-map">New treasure stations will appear here soon.</div>
    <div v-else ref="mapElement" class="treasure-map" :style="{ height: `${mapHeight}px` }" :aria-busy="Boolean(busy)">
      <svg class="map-landscape" :viewBox="`0 0 1000 ${mapHeight}`" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <g v-for="(point, index) in points" :key="point.step.id">
          <ellipse :cx="point.x" :cy="point.y + 24" :rx="mobile ? 420 : 235" ry="106" fill="#acd4ce" opacity=".65" />
          <ellipse :cx="point.x" :cy="point.y + 17" :rx="mobile ? 390 : 218" ry="94" :fill="terrainColors[point.zone]" stroke="#f7eed7" stroke-width="9" />
          <ellipse :cx="point.x + 20" :cy="point.y + 8" :rx="mobile ? 280 : 158" ry="62" :fill="point.zone === 0 ? '#f2dfad' : point.zone === 1 ? '#cad5ae' : '#b4c1ae'" opacity=".55" />
          <path v-if="index < points.length - 1" :d="connection(index)" class="map-connection" :class="{ 'map-connection--complete': point.step.status === 'completed' && points[index + 1].step.status !== 'locked', 'map-connection--locked': points[index + 1].step.status === 'locked' }" />
        </g>
      </svg>
      <div v-for="lock in connectionLocks" :key="`lock-${lock.id}`" class="connection-lock" :style="{ left: `${lock.x}%`, top: `${lock.y}px` }" role="img" :aria-label="`Path to ${lock.title} is locked`"><v-icon size="18">mdi-lock</v-icon></div>

      <div v-for="(point, index) in points" :key="`scenery-${point.step.id}`" class="map-scenery" :style="{ left: `${point.x / 10}%`, top: `${point.y}px` }" aria-hidden="true">
        <span class="terrain-label">{{ zoneNames[point.zone] }}</span>
        <TreasureMapArt :kind="point.zone === 0 ? 'palm' : point.zone === 1 ? 'rocks' : 'mountain'" class="terrain-art" />
        <TreasureMapArt v-if="index === 0 || point.zone === 2" :kind="point.zone === 2 ? 'rocks' : 'palm'" class="terrain-art terrain-art--small" />
      </div>

      <ol class="map-stations" aria-label="Tasks on your treasure journey">
        <li v-for="(point, index) in points" :key="point.step.id" class="map-station" :class="[`station--${point.step.status}`, { 'station--reward': rewardedIds.includes(point.step.id), 'station--new': newlyAvailable.includes(point.step.id) }]" :style="{ left: `${point.x / 10}%`, top: `${point.y - 64}px` }">
          <button type="button" class="station-target" :disabled="Boolean(busy) || point.step.status === 'locked'" :title="point.step.status === 'locked' ? point.step.reasons.join(' · ') : undefined" :aria-label="stationLabel(point.step, index)" :aria-current="pirateIndex === index ? 'step' : undefined" @click="select(point.step)">
            <span class="chest-platform">
              <span class="station-number">{{ index + 1 }}</span>
              <TreasureMapArt kind="chest" :opened="point.step.status === 'completed'" class="station-chest" />
              <span v-if="point.step.challenge" class="challenge-badge" :style="{ color: point.step.challenge.color ?? '#356458' }" :title="point.step.status === 'locked' ? 'Challenge available after unlocking' : `${point.step.challenge.title}: ${challengeGoal(point.step.challenge)}`" :aria-label="point.step.status === 'locked' ? 'Challenge locked' : point.step.challenge.title"
                ><v-icon size="19">{{ point.step.challenge.icon }}</v-icon></span
              >
              <span class="station-status-icon"
                ><v-progress-circular v-if="busy === point.step.id" indeterminate size="22" width="2" /><v-icon v-else size="20">{{ statusIcons[point.step.status] }}</v-icon></span
              >
              <span v-if="rewardedIds.includes(point.step.id)" class="reward-coin"><TreasureMapArt kind="coin" /><span>+1</span></span>
            </span>
            <span class="station-title">{{ point.step.title }}</span>
            <span class="station-caption">{{ labels[point.step.status] }}{{ point.step.status === 'completed' ? ' · +1 coin' : '' }}</span>
          </button>
          <v-btn v-if="point.step.status === 'in_progress'" class="complete-action" size="small" variant="text" :disabled="Boolean(busy)" @click="emit('complete', point.step)">Complete</v-btn>
        </li>
      </ol>

      <div v-if="piratePoint" class="map-pirate" :style="{ left: `calc(${piratePoint.x / 10}% + ${mobile ? 68 : 92}px)`, top: `${piratePoint.y - 79}px` }" role="img" :aria-label="`Your pirate at ${piratePoint.step.title}`">
        <TreasureMapArt kind="pirate" /><span>{{ piratePoint.step.status === 'in_progress' ? 'Continue here' : 'Your position' }}</span>
      </div>
      <div class="journey-destination" :class="{ 'journey-destination--reached': finished }" :style="{ top: `${mapHeight - 90}px` }">
        <v-icon>{{ finished ? 'mdi-flag-checkered' : 'mdi-flag-outline' }}</v-icon
        ><span>{{ finished ? 'All treasures in this learning path discovered!' : 'Your goal: open every treasure chest' }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { PathRun, StepRun } from '@/services/learningPaths'
import TreasureMapArt from './TreasureMapArt.vue'
import { challengeGoal } from '@/services/challenges'

const props = defineProps<{ run: PathRun; busy: string }>()
const emit = defineEmits<{ open: [step: StepRun]; complete: [step: StepRun] }>()
const labels = { locked: 'Locked', available: 'Available', in_progress: 'In progress', completed: 'Completed' }
const statusIcons = { locked: 'mdi-lock-outline', available: 'mdi-arrow-right', in_progress: 'mdi-pencil', completed: 'mdi-check' }
const zoneNames = ['Palm Beach', 'Rocky Island', 'Treasure Mountains']
const terrainColors = ['#eddbab', '#d2d7b3', '#c0cbbb']
const mapElement = ref<HTMLElement | null>(null)
const mobile = ref(false)
const visitedId = ref<string | null>(null)
const rewardedIds = ref<string[]>([])
const newlyAvailable = ref<string[]>([])
let observer: ResizeObserver | undefined
let rewardTimer: ReturnType<typeof setTimeout> | undefined
const finished = computed(() => props.run.total > 0 && props.run.completed === props.run.total)
const mapHeight = computed(() => props.run.steps.length * 260 + 160)
const points = computed(() =>
  props.run.steps.map((step, index) => ({
    step,
    x: mobile.value ? 500 : [280, 680, 350, 720][index % 4],
    y: 140 + index * 260,
    zone: props.run.steps.length === 1 ? 0 : Math.min(2, Math.floor((index / (props.run.steps.length - 1)) * 3))
  }))
)
const pirateIndex = computed(() => {
  const visited = props.run.steps.findIndex((s) => s.id === visitedId.value && s.status !== 'locked')
  if (visited >= 0) return visited
  const active = props.run.steps.findIndex((s) => s.status === 'in_progress')
  if (active >= 0) return active
  const available = props.run.steps.findIndex((s) => s.status === 'available')
  if (available >= 0) return available
  return props.run.steps.map((s) => s.status).lastIndexOf('completed')
})
const piratePoint = computed(() => points.value[pirateIndex.value])
const connectionLocks = computed(() => points.value.slice(1).flatMap((point, index) => (point.step.status === 'locked' ? [{ id: point.step.id, title: point.step.title, x: (points.value[index].x + point.x) / 20, y: (points.value[index].y + point.y) / 2 + 8.125 }] : [])))
const connection = (index: number) => {
  const a = points.value[index],
    b = points.value[index + 1]
  return `M ${a.x} ${a.y + 55} C ${a.x} ${a.y + 180}, ${b.x} ${b.y - 160}, ${b.x} ${b.y - 50}`
}
const stationLabel = (step: StepRun, index: number) => (step.status === 'locked' ? `${index + 1}. ${step.title}: Locked. ${step.reasons.join('. ')}` : `${index + 1}. ${step.title}: ${labels[step.status]}. ${step.challenge ? step.challenge.title + '. ' : ''}${step.modelId ? 'Open model' : 'Start task'}`)
const select = (step: StepRun) => {
  if (step.status === 'locked' || props.busy) return
  visitedId.value = step.id
  try {
    sessionStorage.setItem(`treasure-path:${props.run.id}`, step.id)
  } catch {
    /* Optional visual position. */
  }
  emit('open', step)
}
watch(
  () => props.run.id,
  () => {
    visitedId.value = null
    rewardedIds.value = []
    newlyAvailable.value = []
    try {
      visitedId.value = sessionStorage.getItem(`treasure-path:${props.run.id}`)
    } catch {
      /* Optional visual position. */
    }
  },
  { immediate: true }
)
watch(
  () => props.run.steps.map((s) => ({ id: s.id, status: s.status })),
  (next, previous) => {
    if (!previous) return
    const old = new Map(previous.map((s) => [s.id, s.status]))
    rewardedIds.value = next.filter((s) => s.status === 'completed' && old.has(s.id) && old.get(s.id) !== 'completed').map((s) => s.id)
    newlyAvailable.value = next.filter((s) => s.status === 'available' && old.get(s.id) === 'locked').map((s) => s.id)
    clearTimeout(rewardTimer)
    rewardTimer = setTimeout(() => {
      rewardedIds.value = []
      newlyAvailable.value = []
    }, 1800)
  }
)
watch(
  mapElement,
  (element) => {
    observer?.disconnect()
    if (!element) return
    observer = new ResizeObserver((entries) => {
      mobile.value = entries[0].contentRect.width < 600
    })
    observer.observe(element)
  },
  { flush: 'post' }
)
onUnmounted(() => {
  observer?.disconnect()
  clearTimeout(rewardTimer)
})
</script>

<style scoped>
.challenge-badge {
  position: absolute;
  top: -8px;
  right: -10px;
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  background: #fffdf5;
}
.treasure-journey {
  --map-ink: #334e49;
  color: var(--map-ink);
}
.journey-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 20px;
  padding: 24px 28px;
  border: 1px solid #e6ddc8;
  border-radius: 20px;
  background: #fcf9f1;
}
.journey-eyebrow {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.17em;
  color: #82714d;
  margin-bottom: 7px;
}
.journey-summary h2 {
  font-size: clamp(1.25rem, 3vw, 1.65rem);
  font-weight: 700;
  margin-bottom: 7px;
}
.journey-summary p:last-child {
  font-size: 0.9rem;
}
.coin-counter {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.coin-counter svg {
  width: 52px;
  height: 52px;
}
.coin-counter strong {
  display: block;
  font-size: 1.7rem;
  line-height: 1.1;
}
.coin-counter span {
  font-size: 0.75rem;
}
.journey-progress {
  flex-basis: 100%;
}
.journey-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px 24px;
  padding: 22px 8px 10px;
  font-size: 0.78rem;
}
.journey-legend > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-dot {
  width: 12px;
  height: 12px;
  border: 2px solid #b38429;
  border-radius: 50%;
  background: #fff1c8;
}
.map-hint {
  max-width: 660px;
  margin: 0 auto 20px;
  text-align: center;
  color: #5e716e;
  font-size: 0.8rem;
  line-height: 1.6;
}
.treasure-map {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border: 1px solid #b9d8d2;
  border-radius: 28px;
  background-color: #d8eae4;
  background-image: radial-gradient(ellipse at 25% 25%, #ffffff40 0 2px, transparent 3px), linear-gradient(180deg, #dbefeb, #c2dad4);
  background-size:
    30px 42px,
    100% 100%;
}
.map-landscape {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.map-connection {
  fill: none;
  stroke: #9b9175;
  stroke-width: 4px;
  stroke-dasharray: 5 12;
  stroke-linecap: round;
  vector-effect: non-scaling-stroke;
}
.map-connection--complete {
  stroke: #508673;
  stroke-dasharray: 5 8;
}
.map-connection--locked {
  stroke: #88938e;
  stroke-width: 3px;
  stroke-dasharray: 3 9;
}
.connection-lock {
  position: absolute;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  transform: translate(-50%, -50%);
  border: 1px solid #94a29b;
  border-radius: 50%;
  color: #56675f;
  background: #edf3ee;
  pointer-events: none;
}
.station--locked .station-target:disabled {
  cursor: not-allowed;
}
.map-scenery {
  position: absolute;
  width: 0;
  height: 0;
  pointer-events: none;
}
.terrain-art {
  position: absolute;
  width: 110px;
  height: 110px;
  left: -200px;
  top: -83px;
  transform: rotate(-5deg);
  opacity: 0.9;
}
.terrain-art--small {
  width: 60px;
  height: 60px;
  left: 142px;
  top: 18px;
  transform: rotate(10deg);
  opacity: 0.8;
}
.terrain-label {
  position: absolute;
  top: -118px;
  left: -105px;
  width: 210px;
  text-align: center;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.61rem;
  font-weight: 700;
  color: #5e7b6e;
}
.map-stations {
  list-style: none;
  padding: 0;
  margin: 0;
}
.map-station {
  position: absolute;
  width: 230px;
  transform: translateX(-50%);
  text-align: center;
}
.station-target {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  border: none;
  border-radius: 18px;
  color: var(--map-ink);
  cursor: pointer;
  font: inherit;
  padding: 0 6px 8px;
  background: transparent;
  -webkit-tap-highlight-color: transparent;
}
.station-target:focus-visible {
  outline: 3px solid #286d74;
  outline-offset: 5px;
  background: #ffffff60;
}
.station-target:disabled {
  cursor: wait;
}
.chest-platform {
  position: relative;
  display: block;
  width: 108px;
  height: 108px;
  border: 2px solid #b28a3c;
  border-radius: 50%;
  background: #fff3ce;
  box-shadow:
    0 5px 0 #baa16b30,
    0 0 0 7px #fff9e63d;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.station-target:hover:not(:disabled) .chest-platform {
  transform: translateY(-4px);
  box-shadow:
    0 8px 0 #baa16b30,
    0 0 0 9px #fff9e680;
}
.station-chest {
  width: 94px;
  height: 94px;
  margin: 3px auto 0;
}
.station-number {
  position: absolute;
  left: -7px;
  top: -3px;
  display: grid;
  place-items: center;
  width: 27px;
  height: 27px;
  border: 2px solid #fff8e5;
  border-radius: 50%;
  background: #6d6041;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 800;
}
.station-status-icon {
  position: absolute;
  bottom: -6px;
  right: -4px;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 2px solid #fff8e5;
  border-radius: 50%;
  background: #a47724;
  color: white;
}
.station-title {
  max-width: 100%;
  margin-top: 12px;
  padding: 4px 10px;
  border-radius: 10px;
  background: #fffcf1ed;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.35;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.station-caption {
  margin-top: 4px;
  padding: 2px 7px;
  border-radius: 6px;
  font-size: 0.7rem;
  background: #faf7e9d9;
}
.station--locked .chest-platform {
  filter: saturate(0.18);
  border-color: #879590;
  background: #e6e6d8;
}
.station--locked .station-title,
.station--locked .station-caption {
  color: #596763;
}
.station--in_progress .chest-platform {
  border-color: #32736d;
  background: #e1f1e5;
  box-shadow: 0 0 0 7px #428c7820;
}
.station--in_progress .station-status-icon {
  background: #32736d;
}
.station--completed .chest-platform {
  border-color: #648b64;
  background: #e6efd0;
}
.station--completed .station-status-icon {
  background: #397052;
}
.complete-action {
  color: #36594e;
  margin-top: 2px;
  background: #ffffff8c;
}
.map-pirate {
  position: absolute;
  width: 72px;
  pointer-events: none;
  transition:
    left 0.5s ease,
    top 0.5s ease;
}
.map-pirate svg {
  display: block;
  width: 72px;
  height: 88px;
}
.map-pirate > span {
  display: block;
  width: 92px;
  margin-left: -10px;
  text-align: center;
  font-size: 0.6rem;
  font-weight: 700;
  background: #fcf9edeb;
  padding: 3px 5px;
  border-radius: 8px;
}
.journey-destination {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  width: max-content;
  max-width: 90%;
  border: 1px solid #94b7a6;
  background: #ecf4e9;
  border-radius: 14px;
  padding: 12px 18px;
  font-size: 0.8rem;
}
.journey-destination--reached {
  background: #fff0bc;
  border-color: #c4a447;
}
.reward-coin {
  position: absolute;
  left: 32px;
  top: -20px;
  display: flex;
  align-items: center;
  color: #745116;
  font-weight: 800;
  pointer-events: none;
  animation: collect-coin 1.7s ease-out both;
}
.reward-coin svg {
  width: 38px;
  height: 38px;
}
.station--new .chest-platform {
  animation: unlock-glow 1.5s ease-out;
}
.empty-map {
  padding: 50px 20px;
  text-align: center;
  border-radius: 20px;
  background: #e9f2ec;
}
@keyframes collect-coin {
  0% {
    opacity: 0;
    transform: translateY(10px) scale(0.7);
  }
  20%,
  65% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateY(-65px) scale(1.1);
  }
}
@keyframes unlock-glow {
  50% {
    box-shadow: 0 0 0 14px #f4ce6470;
  }
}
@media (max-width: 600px) {
  .journey-summary {
    padding: 20px;
    gap: 16px;
  }
  .coin-counter {
    margin-left: 0;
  }
  .treasure-map {
    border-radius: 20px;
  }
  .map-pirate,
  .map-pirate svg {
    width: 60px;
  }
  .map-pirate > span {
    width: 76px;
    margin-left: -8px;
  }
  .terrain-art {
    width: 74px;
    height: 74px;
    left: -156px;
    top: -80px;
  }
  .terrain-art--small {
    width: 46px;
    height: 46px;
    left: 110px;
    top: 35px;
  }
}
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    transition: none !important;
  }
  .reward-coin {
    display: none;
  }
}
</style>
