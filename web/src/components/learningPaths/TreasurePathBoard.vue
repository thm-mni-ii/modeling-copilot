<template>
  <section class="treasure-journey" aria-label="Your treasure journey">
    <header class="journey-summary">
      <div>
        <h2>{{ finished ? 'Journey finished!' : `${run.completed} / ${run.total} completed` }}</h2>
        <p>{{ run.progress }} %{{ run.skipped ? ` · ${run.skipped} skipped` : '' }}</p>
      </div>
      <div class="coin-counter" :aria-label="`${run.completed} coins collected`" role="status" aria-live="polite">
        <TreasureMapArt kind="coin" />
        <div>
          <strong>{{ run.completed }}</strong
          ><span class="sr-only">{{ run.completed === 1 ? 'coin' : 'coins' }} collected</span>
        </div>
      </div>
      <v-progress-linear class="journey-progress" :model-value="run.progress" color="#467966" bg-color="#e7dcc2" rounded height="8" aria-label="Treasure journey progress" />
    </header>

    <div class="map-toolbar">
      <p>Choose any available activity on the map.</p>
      <details class="map-help">
        <summary>Map guide</summary>
        <div class="journey-legend" aria-label="Legend">
          <span><v-icon size="16">mdi-lock-outline</v-icon> Locked</span>
          <span><i class="legend-dot" /> Next activity</span>
          <span><v-icon size="16">mdi-arrow-right</v-icon> Available</span>
          <span><v-icon size="16" color="#32736d">mdi-pencil</v-icon> In progress</span>
          <span><v-icon size="16" color="#397052">mdi-check-circle</v-icon> Completed</span>
          <span v-if="run.steps.some((step) => step.type === 'survey')"><v-icon size="16">mdi-skip-next</v-icon> Skipped (unanswered)</span>
        </div>
        <p class="map-hint">Treasure chests are modeling tasks; bottles contain questionnaires. Complete an activity to collect a coin.</p>
      </details>
    </div>

    <div v-if="!run.steps.length" class="empty-map">New treasure stations will appear here soon.</div>
    <div v-else ref="mapElement" class="treasure-map" :style="{ height: `${mapHeight}px` }" :aria-busy="Boolean(busy) || travelling">
      <svg class="map-landscape" :viewBox="`0 0 1000 ${mapHeight}`" preserveAspectRatio="none" aria-hidden="true" focusable="false">
        <g v-for="(point, index) in points" :key="point.step.id">
          <path v-if="index < points.length - 1" :d="connection(index)" class="map-connection" :class="{ 'map-connection--complete': point.step.status === 'completed' && points[index + 1].step.status !== 'locked', 'map-connection--locked': points[index + 1].step.status === 'locked', 'map-connection--next': points[index + 1].step.id === nextStep?.id }" />
        </g>
      </svg>
      <ol class="map-stations" aria-label="Activities on your treasure journey">
        <li
          v-for="(point, index) in points"
          :key="point.step.id"
          :data-step-id="point.step.id"
          class="map-station"
          :class="[`station--${point.step.status}`, { 'station--next': nextStep?.id === point.step.id, 'station--reward': rewardedIds.includes(point.step.id), 'station--new': newlyAvailable.includes(point.step.id) }]"
          :style="{ left: `${point.x / 10}%`, top: `${point.y - 88}px`, '--island-ground': terrainColors[point.zone] }"
        >
          <button type="button" class="station-target" :disabled="Boolean(busy) || travelling" :title="point.step.title" :aria-label="stationLabel(point.step, index)" :aria-expanded="selectedId === point.step.id" :aria-controls="selectedId === point.step.id ? `station-details-${run.id}` : undefined" :aria-current="pirateIndex === index ? 'step' : undefined" @click="select(point.step)">
            <TreasureMapArt :kind="point.zone === 0 ? 'palm' : point.zone === 1 ? 'rocks' : 'mountain'" class="island-scenery" />
            <span class="station-number">{{ index + 1 }}</span>
            <span v-if="nextStep?.id === point.step.id" class="station-next">{{ point.step.status === 'in_progress' ? 'CONTINUE' : 'NEXT' }}</span>
            <span class="chest-platform">
              <TreasureMapArt :kind="point.step.type === 'survey' ? 'map' : 'chest'" :opened="point.step.status === 'completed'" class="station-chest" />
              <span v-if="rewardedIds.includes(point.step.id)" class="reward-coin"><TreasureMapArt kind="coin" /><span>+1</span></span>
            </span>
            <span class="station-status-icon" aria-hidden="true"
              ><v-progress-circular v-if="busy === point.step.id" indeterminate size="18" width="2" /><v-icon v-else size="17">{{ statusIcons[point.step.status] }}</v-icon></span
            >
            <span class="station-title">{{ shortTitle(point.step.title) }}</span>
          </button>
        </li>
      </ol>
      <div v-if="piratePosition" class="journey-pirate" :class="{ 'journey-pirate--walking': travelling }" :style="{ left: `${piratePosition.x}px`, top: `${piratePosition.y}px` }" aria-hidden="true"><TreasureMapArt kind="pirate" /></div>
      <p class="sr-only" role="status" aria-live="polite">{{ travelMessage }}</p>
      <section v-if="selectedStep && selectedPoint" :id="`station-details-${run.id}`" ref="detailsElement" class="station-panel" :class="`station-panel--${detailsPlacement}`" :style="detailsStyle" tabindex="-1" aria-labelledby="station-panel-title" @keydown.esc.stop.prevent="closeDetails">
        <v-card class="station-panel-card">
          <v-card-text class="pa-4">
            <div v-if="blockedStep" class="station-panel-note station-panel-note--locked mb-5" role="alert">
              <h3 class="text-subtitle-2 mb-2"><v-icon size="18" class="mr-1">mdi-lock-outline</v-icon>Not unlocked yet</h3>
              <p class="font-weight-medium mb-2">{{ blockedStep.title }}</p>
              <ul v-if="blockedStep.reasons.length" class="pl-5">
                <li v-for="reason in blockedStep.reasons" :key="reason">{{ reason }}</li>
              </ul>
              <p v-else>This station will become available as you progress.</p>
              <p class="mt-2">{{ selectedStep.id !== blockedStep.id ? 'Your pirate stopped at the reachable station shown below.' : 'There is no reachable station yet.' }}</p>
            </div>
            <div class="station-panel-heading">
              <TreasureMapArt :kind="selectedStep.type === 'survey' ? 'map' : 'chest'" :opened="selectedStep.status === 'completed'" />
              <div>
                <p class="journey-eyebrow">STATION {{ run.steps.findIndex((step) => step.id === selectedStep?.id) + 1 }} · {{ selectedStep.type === 'survey' ? 'QUESTIONNAIRE' : 'MODELING TASK' }}</p>
                <h2 id="station-panel-title">{{ selectedStep.title }}</h2>
              </div>
            </div>
            <div class="d-flex flex-wrap ga-2 mt-4">
              <v-chip size="small" :prepend-icon="statusIcons[selectedStep.status]" :color="selectedStep.status === 'locked' ? undefined : 'success'" variant="tonal">{{ labels[selectedStep.status] }}</v-chip>
              <v-chip v-if="selectedStep.type === 'survey'" size="small" variant="outlined">{{ selectedStep.required === false ? 'Optional' : 'Required' }}</v-chip>
            </div>
            <p v-if="selectedStep.beforeSurveyId || selectedStep.afterSurveyId" class="station-panel-note mt-3">
              <v-icon size="18" class="mr-1">mdi-clipboard-list-outline</v-icon>
              Required questionnaire {{ selectedStep.beforeSurveyId && selectedStep.afterSurveyId ? 'before and after' : selectedStep.beforeSurveyId ? 'before' : 'after' }} this task. Answer in the modeling view.
            </p>
            <div v-if="selectedStep.challenge && selectedStep.status !== 'locked'" class="station-panel-note mt-4">
              <h3 class="text-subtitle-2 mb-1">
                <v-icon size="18" class="mr-1">{{ selectedStep.challenge.icon }}</v-icon
                >{{ selectedStep.challenge.title }}
              </h3>
              <p>{{ challengeGoal(selectedStep.challenge) }}</p>
            </div>
            <p v-if="selectedStep.status === 'completed'" class="station-panel-note mt-4"><v-icon size="18" class="mr-1" color="#a47724">mdi-circle-multiple</v-icon>Treasure collected! You earned 1 coin.</p>
            <p v-else-if="selectedStep.status === 'skipped'" class="station-panel-note mt-4">You skipped this questionnaire. No answers were submitted.</p>
          </v-card-text>
          <v-card-actions class="station-panel-actions px-4 pb-4">
            <v-btn variant="text" :disabled="Boolean(busy)" @click="closeDetails">Close</v-btn>
            <v-spacer />
            <v-btn v-if="selectedStep.type !== 'survey' && selectedStep.status === 'in_progress'" variant="outlined" :disabled="Boolean(busy)" @click="finishSelected">Complete</v-btn>
            <v-btn v-if="canOpenSelected" color="#356458" variant="flat" append-icon="mdi-arrow-right" :disabled="Boolean(busy)" @click="openSelected">{{ selectedStep.status === 'completed' ? 'Open model' : selectedStep.status === 'in_progress' ? 'Continue' : selectedStep.type === 'survey' ? 'Open questionnaire' : 'Start task' }}</v-btn>
          </v-card-actions>
        </v-card>
      </section>
      <div v-if="expandedPoint" class="survey-station-panel" :style="{ top: `${expandedPoint.y + 106 + (selectedId === expandedId ? detailsExtra : 0)}px` }" tabindex="-1" role="region" :aria-label="`Questionnaire: ${expandedPoint.step.title}`"><slot name="activity" :step="expandedPoint.step" /></div>
      <div class="journey-destination" :class="{ 'journey-destination--reached': finished }" :style="{ top: `${mapHeight - 90}px` }">
        <v-icon>{{ finished ? 'mdi-flag-checkered' : 'mdi-flag-outline' }}</v-icon
        ><span>{{ finished ? 'All treasures in this learning path discovered!' : 'Your goal: finish every activity' }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import type { PathRun, StepRun } from '@/services/learningPaths'
import TreasureMapArt from './TreasureMapArt.vue'
import { challengeGoal } from '@/services/challenges'
import { journeyDestination } from '@/utils/learningPathJourney'

const props = defineProps<{ run: PathRun; busy: string; expandedId?: string | null }>()
const emit = defineEmits<{ open: [step: StepRun]; complete: [step: StepRun] }>()
const labels = { locked: 'Locked', available: 'Available', in_progress: 'In progress', completed: 'Completed', skipped: 'Skipped' }
const statusIcons = { locked: 'mdi-lock-outline', available: 'mdi-arrow-right', in_progress: 'mdi-pencil', completed: 'mdi-check', skipped: 'mdi-skip-next' }
const terrainColors = ['#eddbab', '#d2d7b3', '#c0cbbb']
const mapElement = ref<HTMLElement | null>(null)
const mobile = ref(false)
const mapWidth = ref(1000)
const detailsElement = ref<HTMLElement | null>(null)
const detailsHeight = ref(280)
let detailsObserver: ResizeObserver | undefined
type Position = { x: number; y: number }
const animatedPosition = ref<Position | null>(null)
const travelling = ref(false)
const travelMessage = ref('')
let travelFrame: number | undefined
let pendingId: string | null = null
const visitedId = ref<string | null>(null)
const selectedId = ref<string | null>(null)
const blockedId = ref<string | null>(null)
const blockedStep = computed(() => props.run.steps.find((step) => step.id === blockedId.value && step.status === 'locked'))
const selectedStep = computed(() => props.run.steps.find((step) => step.id === selectedId.value))
const canOpenSelected = computed(() => selectedStep.value && selectedStep.value.status !== 'locked' && !(selectedStep.value.type === 'survey' && ['completed', 'skipped'].includes(selectedStep.value.status)))
const rewardedIds = ref<string[]>([])
const newlyAvailable = ref<string[]>([])
let observer: ResizeObserver | undefined
let rewardTimer: ReturnType<typeof setTimeout> | undefined
const finished = computed(() => props.run.total > 0 && (props.run.finished ?? props.run.completed + (props.run.skipped ?? 0) === props.run.total))
const nextStep = computed(() => props.run.steps.find((step) => step.status === 'in_progress') ?? props.run.steps.find((step) => step.status === 'available'))
const stationSpacing = 216
const detailsBeside = computed(() => mapWidth.value >= 760)
const detailsExtra = computed(() => (selectedId.value ? (detailsBeside.value ? Math.max(0, detailsHeight.value + 24 - (selectedId.value === props.expandedId ? 194 : stationSpacing)) : detailsHeight.value + 24) : 0))
const mapHeight = computed(() => props.run.steps.length * stationSpacing + 120 + (props.expandedId ? 740 : 0) + detailsExtra.value)
const points = computed(() =>
  props.run.steps.map((step, index) => ({
    step,
    x: mobile.value ? 500 : [300, 700][index % 2],
    y: 120 + index * stationSpacing + (props.expandedId && index > props.run.steps.findIndex((item) => item.id === props.expandedId) ? 740 : 0) + (selectedId.value && index > props.run.steps.findIndex((item) => item.id === selectedId.value) ? detailsExtra.value : 0),
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
const expandedPoint = computed(() => points.value.find((point) => point.step.id === props.expandedId))
const selectedPoint = computed(() => points.value.find((point) => point.step.id === selectedId.value))
const detailsPlacement = computed(() => (!detailsBeside.value ? 'below' : (selectedPoint.value?.x ?? 0) < 500 ? 'right' : 'left'))
const detailsStyle = computed(() => {
  const point = selectedPoint.value
  if (!point) return {}
  const x = (point.x * mapWidth.value) / 1000
  const width = Math.min(360, mapWidth.value - 32)
  const left = detailsBeside.value ? (detailsPlacement.value === 'right' ? x + 140 : x - 140 - width) : Math.max(16, Math.min(x - width / 2, mapWidth.value - width - 16))
  return { left: `${left}px`, top: `${point.y + (detailsBeside.value ? -88 : 106)}px`, width: `${width}px` }
})
const closeDetails = () => {
  const id = selectedId.value
  selectedId.value = null
  const station = [...(mapElement.value?.querySelectorAll<HTMLElement>('.map-station') ?? [])].find((element) => element.dataset.stepId === id)
  station?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true })
}
const restingPosition = (index: number): Position | null => {
  const point = points.value[index]
  return point ? { x: (point.x * mapWidth.value) / 1000 + 74, y: point.y + 28 } : null
}
const piratePosition = computed(() => animatedPosition.value ?? restingPosition(pirateIndex.value))
const stopTravel = () => {
  if (travelFrame !== undefined) cancelAnimationFrame(travelFrame)
  travelFrame = undefined
  pendingId = null
  travelling.value = false
  animatedPosition.value = null
}
const arrive = (requestedId: string) => {
  // Re-read unlocks: the server may have refreshed them during the walk.
  const destination = journeyDestination(props.run.steps, requestedId)
  stopTravel()
  if (!destination) return
  blockedId.value = destination.blocked?.id ?? null
  if (destination.target) {
    visitedId.value = destination.target.id
    try {
      sessionStorage.setItem(`treasure-path:${props.run.id}`, destination.target.id)
    } catch {
      /* Optional visual position. */
    }
  }
  selectedId.value = destination.target?.id ?? destination.blocked?.id ?? null
  travelMessage.value = destination.blocked ? `${destination.blocked.title} is not unlocked yet.` : `Arrived at ${destination.target?.title ?? ''}.`
}
const connection = (index: number) => {
  const a = points.value[index],
    b = points.value[index + 1]
  return `M ${a.x} ${a.y + 70} C ${a.x} ${a.y + 148}, ${b.x} ${b.y - 148}, ${b.x} ${b.y - 70}`
}
const shortTitle = (title: string) => {
  const text = title.trim().replace(/\s+/g, ' ')
  if (text.length <= 26) return text
  const prefix = text.slice(0, 25)
  return `${prefix.replace(/\s+\S*$/, '') || prefix}…`
}
const stationLabel = (step: StepRun, index: number) => `${index + 1}. ${step.title}: ${labels[step.status]}. ${step.status === 'locked' ? 'View unlock details' : 'View activity details'}`
const select = async (step: StepRun) => {
  if (props.busy || travelling.value) return
  const runId = props.run.id
  stopTravel()
  selectedId.value = null
  blockedId.value = null
  travelling.value = true
  await nextTick()
  if (props.run.id !== runId || props.busy) {
    stopTravel()
    return
  }
  const destination = journeyDestination(props.run.steps, step.id)
  if (!destination) {
    stopTravel()
    return
  }
  const start = piratePosition.value
  const from = pirateIndex.value
  const to = props.run.steps.findIndex((item) => item.id === destination.target?.id)
  if (!start || from < 0 || to < 0 || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    arrive(step.id)
    return
  }
  const route: Position[] = [start]
  const paths = mapElement.value?.querySelectorAll<SVGPathElement>('.map-connection')
  const direction = to >= from ? 1 : -1
  for (let index = from; index !== to; index += direction) {
    const point = points.value[index]
    route.push({ x: (point.x * mapWidth.value) / 1000, y: point.y })
    const path = paths?.[Math.min(index, index + direction)]
    if (!path) {
      arrive(step.id)
      return
    }
    const length = path.getTotalLength()
    for (let sample = 0; sample <= 32; sample++) {
      const location = path.getPointAtLength(length * (direction === 1 ? sample / 32 : 1 - sample / 32))
      route.push({ x: (location.x * mapWidth.value) / 1000, y: location.y })
    }
  }
  const end = restingPosition(to)!
  const targetPoint = points.value[to]
  if (from !== to) route.push({ x: (targetPoint.x * mapWidth.value) / 1000, y: targetPoint.y })
  route.push(end)
  const distances = [0]
  for (let i = 1; i < route.length; i++) distances.push(distances[i - 1] + Math.hypot(route[i].x - route[i - 1].x, route[i].y - route[i - 1].y))
  const total = distances[distances.length - 1]
  if (total < 1) {
    arrive(step.id)
    return
  }
  const duration = Math.min(1800, Math.max(280, total / 0.8))
  let started: number | undefined
  pendingId = step.id
  travelling.value = true
  travelMessage.value = `Your pirate is walking to ${destination.target?.title}.`
  const frame = (now: number) => {
    started ??= now
    const progress = Math.min(1, (now - started) / duration)
    const distance = progress * total
    let segment = 1
    while (segment < distances.length - 1 && distances[segment] < distance) segment++
    const part = (distance - distances[segment - 1]) / (distances[segment] - distances[segment - 1] || 1)
    const a = route[segment - 1],
      b = route[segment]
    animatedPosition.value = { x: a.x + (b.x - a.x) * part, y: a.y + (b.y - a.y) * part }
    if (progress < 1) travelFrame = requestAnimationFrame(frame)
    else arrive(step.id)
  }
  travelFrame = requestAnimationFrame(frame)
}
const openSelected = () => {
  const step = selectedStep.value
  if (!step || !canOpenSelected.value || props.busy) return
  selectedId.value = null
  emit('open', step)
}
const finishSelected = () => {
  const step = selectedStep.value
  if (!step || step.type === 'survey' || step.status !== 'in_progress' || props.busy) return
  selectedId.value = null
  emit('complete', step)
}
watch(
  () => props.run.id,
  () => {
    stopTravel()
    visitedId.value = null
    selectedId.value = null
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
  () => props.expandedId,
  (id) => {
    if (!id) return
    const panel = mapElement.value?.querySelector<HTMLElement>('.survey-station-panel')
    panel?.focus({ preventScroll: true })
    panel?.scrollIntoView({ block: 'start' })
  },
  { flush: 'post' }
)
watch(
  mapElement,
  (element) => {
    observer?.disconnect()
    if (!element) return
    observer = new ResizeObserver((entries) => {
      mobile.value = entries[0].contentRect.width < 600
      mapWidth.value = entries[0].contentRect.width
    })
    observer.observe(element)
  },
  { flush: 'post' }
)
watch([mapWidth, () => props.expandedId], () => {
  if (pendingId) arrive(pendingId)
})
watch(
  detailsElement,
  (element) => {
    detailsObserver?.disconnect()
    if (!element) return
    const measure = () => {
      detailsHeight.value = element.offsetHeight
    }
    measure()
    detailsObserver = new ResizeObserver(measure)
    detailsObserver.observe(element)
    element.focus({ preventScroll: true })
    element.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  },
  { flush: 'post' }
)
onUnmounted(() => {
  stopTravel()
  observer?.disconnect()
  detailsObserver?.disconnect()
  clearTimeout(rewardTimer)
})
</script>

<style scoped>
.station-panel {
  position: absolute;
  z-index: 6;
  color: #334e49;
  background: #fcf9f1;
  border: 2px solid #d8c8a4;
  border-radius: 20px;
  box-shadow: 0 8px 20px #334e491a;
  scroll-margin: 90px 16px 24px;
}
.station-panel:focus-visible {
  outline: 2px solid #356458;
  outline-offset: 4px;
}
.station-panel-card {
  color: inherit;
  background: transparent;
  border-radius: inherit;
  box-shadow: none;
}
.station-panel::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  background: #fcf9f1;
  transform: rotate(45deg);
}
.station-panel--right::before {
  left: -9px;
  top: 66px;
  border-left: 2px solid #d8c8a4;
  border-bottom: 2px solid #d8c8a4;
}
.station-panel--left::before {
  right: -9px;
  top: 66px;
  border-right: 2px solid #d8c8a4;
  border-top: 2px solid #d8c8a4;
}
.station-panel--below::before {
  top: -9px;
  left: calc(50% - 8px);
  border-left: 2px solid #d8c8a4;
  border-top: 2px solid #d8c8a4;
}
.station-panel-heading {
  display: flex;
  align-items: center;
  gap: 16px;
}
.station-panel-heading > svg {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}
.station-panel-heading h2 {
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.station-panel-note {
  padding: 14px;
  border: 1px solid #e6ddc8;
  border-radius: 12px;
  background: #f3eddf;
  font-size: 0.85rem;
  line-height: 1.6;
}
.station-panel-note--locked {
  border-color: #d3b56b;
  background: #fff0c9;
  box-shadow: inset 4px 0 #b18a38;
}
.station-panel-actions {
  flex-wrap: wrap;
  gap: 8px;
}
.survey-station-panel {
  scroll-margin-top: 88px;
  position: absolute;
  left: 50%;
  width: min(650px, calc(100% - 24px));
  max-height: 690px;
  overflow: auto;
  background: #fffdf5;
  border: 1px solid #e6ddc8;
  border-radius: 16px;
  padding: 16px;
  transform: translateX(-50%);
  text-align: left;
  z-index: 8;
}

.treasure-journey {
  --map-ink: #334e49;
  color: var(--map-ink);
  overflow: hidden;
  border: 1px solid #b9d8d2;
  border-radius: 24px;
  background: #fcf9f1;
}
.journey-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 20px;
  padding: 18px 22px 12px;
}
.journey-eyebrow {
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.17em;
  color: #82714d;
  margin-bottom: 7px;
}
.journey-summary h2 {
  font-size: 1rem;
  font-weight: 700;
  margin-bottom: 2px;
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
  width: 32px;
  height: 32px;
}
.coin-counter strong {
  display: block;
  font-size: 1.3rem;
  line-height: 1.1;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.journey-progress {
  flex-basis: 100%;
}
.map-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 24px;
  padding: 0 22px 12px;
  font-size: 0.8rem;
  color: #5e716e;
}
.map-toolbar > p {
  flex: 1;
}
.map-help {
  margin-left: auto;
  max-width: 100%;
}
.map-help[open] {
  flex-basis: 100%;
}
.map-help summary {
  cursor: pointer;
  width: fit-content;
  margin-left: auto;
  padding: 4px;
  color: #334e49;
  font-weight: 600;
}
.map-help summary:focus-visible {
  outline: 2px solid #286d74;
  outline-offset: 2px;
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
  border-top: 1px solid #cbded4;
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
  opacity: 0.55;
}
.map-connection--next {
  stroke: #ac8233;
  stroke-dasharray: 6 9;
}

.map-stations {
  list-style: none;
  padding: 0;
  margin: 0;
}
.map-station {
  position: absolute;
  width: min(244px, 86%);
  height: 176px;
  transform: translateX(-50%);
  text-align: center;
}
.station-target {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 25px 36px 23px;
  border: 7px solid #f8eed3;
  border-radius: 46% 52% 43% 49% / 47% 44% 52% 46%;
  background: radial-gradient(ellipse at 50% 40%, #ffffff24, transparent 70%), var(--island-ground);
  box-shadow:
    0 6px 0 #92bfb4,
    0 10px 0 5px #b5d5cb66;
  color: var(--map-ink);
  cursor: pointer;
  font: inherit;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
  -webkit-tap-highlight-color: transparent;
}
.station-target:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow:
    0 9px 0 #92bfb4,
    0 13px 0 5px #b5d5cb66;
}
.station-target:focus-visible {
  outline: 3px solid #286d74;
  outline-offset: 7px;
}
.station-target:disabled {
  cursor: wait;
}
.chest-platform {
  position: relative;
  display: block;
  width: 76px;
  height: 76px;
  flex-shrink: 0;
}
.station-chest {
  display: block;
  width: 76px;
  height: 76px;
}
.station-number,
.station-status-icon {
  position: absolute;
  top: 27px;
  display: grid;
  place-items: center;
  width: 25px;
  height: 25px;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 800;
}
.station-number {
  left: 36px;
  background: #fff6dc;
  color: #716044;
}
.station-status-icon {
  right: 36px;
  background: #fff6dc;
  color: #716044;
}
.station-title {
  display: block;
  width: 100%;
  margin-top: 4px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.5;
}
.station-next {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  padding: 2px 9px;
  border-radius: 4px 4px 8px 8px;
  background: #356458;
  color: #fff;
  font-size: 0.55rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.station--next .station-target {
  border-color: #ffe6a0;
  box-shadow:
    0 6px 0 #8ba887,
    0 0 0 3px #c9ab58;
}
.station--next .station-target:hover:not(:disabled) {
  box-shadow:
    0 9px 0 #8ba887,
    0 0 0 4px #c9ab58;
}
.station--completed .station-target {
  --island-ground: #d1ddc2;
  border-color: #eaf0da;
}
.station--completed .station-chest {
  filter: saturate(0.65);
}
.station--completed .island-scenery {
  opacity: 0.35;
}
.station--locked .station-target {
  --island-ground: #d5dfd3;
  border-color: #e8eee1;
  color: #61736b;
}
.station--locked .station-chest,
.station--locked .island-scenery {
  filter: saturate(0.15);
  opacity: 0.6;
}
.station--locked .station-number,
.station--locked .station-status-icon {
  background: #e8eee1;
  color: #61736b;
}
.station--completed .station-status-icon,
.station--in_progress .station-status-icon {
  background: #356458;
  color: #fff;
}
.island-scenery {
  position: absolute;
  left: 10px;
  bottom: 41px;
  width: 44px;
  height: 50px;
  opacity: 0.7;
  pointer-events: none;
}
.journey-pirate {
  position: absolute;
  width: 44px;
  height: 54px;
  transform: translate(-50%, -100%);
  z-index: 4;
  pointer-events: none;
}
.journey-pirate > svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 3px 2px #334e4926);
}
.journey-pirate--walking > svg {
  animation: pirate-walk 0.24s ease-in-out infinite alternate;
}
@keyframes pirate-walk {
  from {
    transform: translateY(0) rotate(-3deg);
  }
  to {
    transform: translateY(-4px) rotate(3deg);
  }
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
.station--new .station-target {
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
    padding: 16px 18px 10px;
    gap: 10px;
  }
  .coin-counter {
    margin-left: auto;
  }
  .treasure-map {
    border-radius: 0;
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
