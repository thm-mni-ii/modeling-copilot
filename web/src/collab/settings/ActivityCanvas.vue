<template>
  <div class="canvas">
    <div class="canvas__head">
      <div class="title">{{ area === 'log' ? 'What the event log and the bar show' : 'What short notices look like' }}</div>
      <v-btn :variant="advancedOn ? 'flat' : 'tonal'" color="info" prepend-icon="mdi-wrench-outline" :append-icon="advancedOn ? 'mdi-lock-open-variant-outline' : 'mdi-lock-outline'" class="canvas__switch" :aria-pressed="advancedOn" :title="advancedOn ? 'Lock the technical settings again' : 'The technical settings are locked; press to change them'" @click="advancedOn = !advancedOn">
        Advanced settings
      </v-btn>
    </div>
    <div class="canvas__body">
      <!-- The event log of a shared model with the bar above the model; the parts are the settings of this card. -->
      <svg v-if="area === 'log'" viewBox="0 0 420 260" class="canvas__svg" :class="{ 'canvas__svg--dim': active !== 0 }" role="img" aria-label="The event log with merged changes, a person who left and one who joined, and the bar with a release notice">
        <rect x="20" y="20" width="380" height="188" rx="6" fill="#fff" stroke="#d6d6d6" />
        <text x="32" y="38" class="small-text">Event Log</text>

        <!-- 1: changes of one person within the merge time are one entry. -->
        <g class="part" :class="{ 'part--on': active === 1 }" @mouseenter="active = 1" @mouseleave="active = 0">
          <circle cx="40" cy="58" r="9" :fill="palette[0]" />
          <text x="40" y="58" text-anchor="middle" dominant-baseline="central" class="mark-text">A</text>
          <text x="56" y="58" dominant-baseline="central" class="name-text">Anna</text>
          <text x="52" y="78" dominant-baseline="central" class="line-text">
            moved
            <tspan font-weight="600">Order</tspan>
          </text>
          <rect x="150" y="70" width="86" height="16" rx="8" fill="#e3f0fc" />
          <text x="193" y="78" text-anchor="middle" dominant-baseline="central" class="tag-text">3 moves, 1 entry</text>
          <circle cx="388" cy="68" r="9" class="badge" />
          <text x="388" y="68" text-anchor="middle" dominant-baseline="central" class="badge-text">1</text>
        </g>

        <!-- 2 and 5: Ben has gone; "left" shows only after the leave time, and the time beside him ("2 min ago") is renewed. -->
        <g class="part" :class="{ 'part--on': active === 2 }" @mouseenter="active = 2" @mouseleave="active = 0">
          <circle cx="40" cy="108" r="9" :fill="palette[1]" />
          <text x="40" y="108" text-anchor="middle" dominant-baseline="central" class="mark-text">B</text>
          <text x="56" y="108" dominant-baseline="central" class="name-text">Ben</text>
          <text x="52" y="128" dominant-baseline="central" class="line-text">left</text>
          <circle cx="388" cy="124" r="9" class="badge" />
          <text x="388" y="124" text-anchor="middle" dominant-baseline="central" class="badge-text">2</text>
        </g>
        <g class="part" :class="{ 'part--on': active === 5 }" @mouseenter="active = 5" @mouseleave="active = 0">
          <text x="330" y="108" text-anchor="end" dominant-baseline="central" class="small-text">2 min ago</text>
          <circle cx="388" cy="100" r="9" class="badge" />
          <text x="388" y="100" text-anchor="middle" dominant-baseline="central" class="badge-text">5</text>
        </g>

        <!-- 3: Carla joins; people already there on connecting do not count as joined during the settling time. -->
        <g class="part" :class="{ 'part--on': active === 3 }" @mouseenter="active = 3" @mouseleave="active = 0">
          <circle cx="40" cy="158" r="9" :fill="palette[2]" />
          <text x="40" y="158" text-anchor="middle" dominant-baseline="central" class="mark-text">C</text>
          <text x="56" y="158" dominant-baseline="central" class="name-text">Carla</text>
          <text x="52" y="178" dominant-baseline="central" class="line-text">joined</text>
          <circle cx="388" cy="174" r="9" class="badge" />
          <text x="388" y="174" text-anchor="middle" dominant-baseline="central" class="badge-text">3</text>
        </g>

        <!-- 4: the bar above the model shows a release by someone else for a moment. -->
        <g class="part" :class="{ 'part--on': active === 4 }" @mouseenter="active = 4" @mouseleave="active = 0">
          <rect x="20" y="222" width="380" height="28" rx="6" fill="#fff" stroke="#d6d6d6" />
          <rect x="28" y="228" width="150" height="16" rx="8" fill="#e3f0fc" />
          <text x="103" y="236" text-anchor="middle" dominant-baseline="central" class="tag-text">Release 2 by Anna</text>
          <circle cx="388" cy="236" r="9" class="badge" />
          <text x="388" y="236" text-anchor="middle" dominant-baseline="central" class="badge-text">4</text>
        </g>
      </svg>

      <!-- The three notices; the parts are the settings of this card. -->
      <svg v-else viewBox="0 0 420 236" class="canvas__svg" :class="{ 'canvas__svg--dim': active !== 0 }" role="img" aria-label="An element with the frame of an overwritten change, the share link shown as copied, and the group import checking its input">
        <rect x="20" y="20" width="380" height="196" rx="6" fill="#fff" stroke="#d6d6d6" />

        <!-- 1: your change was overwritten, so the element gets a dashed frame for a while. -->
        <g class="part" :class="{ 'part--on': active === 1 }" @mouseenter="active = 1" @mouseleave="active = 0">
          <rect x="44" y="40" width="142" height="62" fill="none" :stroke="conflict" stroke-width="3" stroke-dasharray="6 4" />
          <rect x="50" y="46" width="130" height="50" fill="#fff" stroke="#000" />
          <text x="115" y="71" text-anchor="middle" class="element-text">Invoice</text>
          <circle cx="218" cy="71" r="9" class="badge" />
          <text x="218" y="71" text-anchor="middle" dominant-baseline="central" class="badge-text">1</text>
        </g>

        <!-- 2: the share link says it was copied, then offers the copy again. -->
        <g class="part" :class="{ 'part--on': active === 2 }" @mouseenter="active = 2" @mouseleave="active = 0">
          <rect x="250" y="52" width="130" height="38" rx="6" fill="#e3f0fc" />
          <text x="268" y="71" dominant-baseline="central" class="tag-text">Link copied</text>
          <path d="M349 71 l5 5 l10 -10" fill="none" stroke="#1d5fa5" stroke-width="2" stroke-linecap="round" />
          <circle cx="388" cy="42" r="9" class="badge" />
          <text x="388" y="42" text-anchor="middle" dominant-baseline="central" class="badge-text">2</text>
        </g>

        <!-- 3: the group import waits until the input has been quiet, then checks it. -->
        <g class="part" :class="{ 'part--on': active === 3 }" @mouseenter="active = 3" @mouseleave="active = 0">
          <rect x="44" y="136" width="260" height="30" rx="4" fill="#fff" stroke="#9a9a9a" />
          <text x="54" y="151" dominant-baseline="central" class="line-text">Course A, Task 1, Task 2</text>
          <text x="54" y="190" dominant-baseline="central" class="small-text">Checks the input when typing has stopped</text>
          <circle cx="332" cy="151" r="9" class="badge" />
          <text x="332" y="151" text-anchor="middle" dominant-baseline="central" class="badge-text">3</text>
        </g>
      </svg>

      <div class="rows">
        <div v-for="row in rows" :key="row.title" class="prow" :class="{ 'prow--on': active === row.n, 'prow--locked': row.controls.every(locked) }" @mouseenter="active = row.n" @mouseleave="active = 0" @focusin="active = row.n" @focusout="active = 0">
          <span class="prow__n">{{ row.n }}</span>
          <div class="prow__main">
            <div class="prow__head">
              <b>{{ row.title }}</b>
              <v-tooltip :text="row.about" location="top" max-width="280">
                <template #activator="{ props: tip }">
                  <v-icon v-bind="tip" icon="mdi-information-outline" size="16" class="prow__info" tabindex="0" :aria-label="`About ${row.title}: ${row.about}`" />
                </template>
              </v-tooltip>
            </div>
            <div class="prow__ctls">
              <div v-for="control in row.controls" :key="control.key" class="ctl" :class="{ 'ctl--locked': locked(control), 'ctl--wide': control.ticks }">
                <div class="ctl__head">
                  <span class="ctl__label">{{ control.label }}</span>
                  <span v-if="changed(area, control.key)" class="ctl__dot" title="Unsaved change" />
                  <v-icon v-if="control.advanced && !locked(control)" icon="mdi-lock-open-variant-outline" size="14" class="ctl__open" title="Advanced setting, unlocked" />
                  <v-icon v-if="locked(control)" icon="mdi-lock-outline" size="14" />
                  <v-btn v-else-if="numberOf(control.key) !== defaultOf(control)" icon="mdi-restore" size="x-small" density="comfortable" variant="text" :aria-label="`Reset ${control.label} to the default`" title="Reset to the default" @click="set(control, defaultOf(control))" />
                </div>
                <div class="ctl__body" :inert="locked(control)">
                  <!-- A dot on a time axis on a logarithmic scale, so short and long times both fit. -->
                  <template v-if="control.ticks">
                    <svg
                      viewBox="0 0 320 52"
                      class="axis"
                      role="slider"
                      tabindex="0"
                      :aria-label="`${row.title}: ${control.label}`"
                      :aria-valuemin="minOf(control)"
                      :aria-valuemax="maxOf(control)"
                      :aria-valuenow="numberOf(control.key)"
                      :aria-valuetext="fmt(control, numberOf(control.key))"
                      @pointerdown.prevent="drag($event, control)"
                      @pointermove="drag($event, control)"
                      @keydown="press($event, control)"
                    >
                      <line :x1="X0" :x2="X1" y1="30" y2="30" class="axis__line" />
                      <line :x1="X0" :x2="axisAt(control)" y1="30" y2="30" class="axis__fill" />
                      <g v-for="tick in control.ticks" :key="tick">
                        <line :x1="axisOf(control, tick)" :x2="axisOf(control, tick)" y1="25" y2="35" class="axis__tick" />
                        <text :x="axisOf(control, tick)" y="50" text-anchor="middle" class="axis__text">{{ fmt(control, tick) }}</text>
                      </g>
                      <circle :cx="axisAt(control)" cy="30" r="9" class="axis__dot" />
                      <text :x="Math.min(Math.max(axisAt(control), 24), 296)" y="12" text-anchor="middle" class="axis__value">{{ fmt(control, numberOf(control.key)) }}</text>
                    </svg>
                  </template>
                  <div v-else class="chips" role="group" :aria-label="control.label">
                    <button v-for="preset in control.presets" :key="preset" type="button" class="chip" :class="{ 'chip--on': numberOf(control.key) === preset }" :aria-pressed="numberOf(control.key) === preset" @click="set(control, preset)">{{ fmt(control, preset) }}</button>
                  </div>
                  <span class="ctl__exact"><input type="number" class="ctl__num" :value="numberOf(control.key)" :min="minOf(control)" :max="maxOf(control)" :aria-label="`${control.label} exactly`" @change="typed($event, control)" />{{ unitOf(control) }}</span>
                </div>
                <div v-if="problem(area, control.key)" class="ctl__error">{{ problem(area, control.key) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { COLLAB_LIMITS } from '@/collab/settings/collabSettings'
import { timeLabel } from '@/collab/settings/timeLabel'

/** The log or hints settings as the form shows them: seconds, except copiedMs and importDelayMs in ms. */
const props = defineProps<{ area: 'log' | 'hints'; values: Record<string, unknown>; colors: Record<string, unknown>; changed: (area: 'log' | 'hints', key: string) => boolean; problem: (area: 'log' | 'hints', key: string) => string | undefined }>()
const emit = defineEmits<{ update: [key: string, value: number] }>()

interface Control {
  key: string
  label: string
  advanced?: boolean
  /** Ticks of a time axis, in the unit of the form; without them the control is a row of chips. */
  ticks?: number[]
  /** Usual values of a chips control, in the unit of the form. */
  presets?: number[]
}

/** The parts of the picture by number, each with the settings that change it. */
const ROWS: Record<'log' | 'hints', { n: number; title: string; about: string; controls: Control[] }[]> = {
  log: [
    { n: 1, title: 'Merged changes', about: 'Several changes by one person in a short time are one line in the log, so a long drag does not fill it.', controls: [{ key: 'mergeMs', label: 'One entry for changes within', ticks: [10, 60, 300, 1800] }] },
    { n: 2, title: 'Person left', about: 'Someone who disappears is only logged as "left" after this time. Anyone who comes back before that is not logged at all.', controls: [{ key: 'leaveMs', label: 'Show "left" after being away for', ticks: [60, 120, 300, 600] }] },
    { n: 3, title: 'Person joined', about: 'Right after you connect, everyone already in the room would look like a new arrival. Arrivals are ignored for this time.', controls: [{ key: 'settleMs', label: 'Ignore arrivals for', advanced: true, presets: [1, 3, 10, 30] }] },
    { n: 4, title: 'Release notice', about: 'A release by someone else shows in the bar above the model for a moment. The log keeps it.', controls: [{ key: 'releaseNoticeMs', label: 'Stays for', presets: [5, 10, 30, 60] }] },
    { n: 5, title: 'Times in the log', about: 'How often "2 min ago" is counted again while the log is open. Takes effect when the log opens.', controls: [{ key: 'refreshMs', label: 'Update "min ago" every', advanced: true, presets: [10, 30, 60, 120] }] }
  ],
  hints: [
    { n: 1, title: 'Overwritten change', about: 'Your change was overwritten by someone else. The element gets this frame for a moment. The color is set under Colors.', controls: [{ key: 'conflictFrameMs', label: 'Frame stays for', presets: [2, 4, 10, 30] }] },
    { n: 2, title: 'Link copied', about: 'After you copy the share link, the card says "Link copied" for a moment.', controls: [{ key: 'copiedMs', label: 'Shows "Link copied" for', presets: [1000, 2500, 5000, 10_000] }] },
    { n: 3, title: 'Group import check', about: 'The import waits until nothing is typed any more before it checks the input, so it does not check on every key.', controls: [{ key: 'importDelayMs', label: 'Checks after a pause of', advanced: true, presets: [200, 400, 1000, 2000] }] }
  ]
}
const rows = computed(() => ROWS[props.area])

/** Hovering a row or a part lights up the other one. */
const active = ref(0)
const advancedOn = ref(false)
const locked = (control: Control) => Boolean(control.advanced) && !advancedOn.value

// Keys in ms in the form; the other keys ending in Ms are shown in seconds (as in CollabSettings.vue).
const MS_KEYS = new Set(['copiedMs', 'importDelayMs'])
const factorOf = (key: string) => (key.endsWith('Ms') && !MS_KEYS.has(key) ? 1000 : 1)
const limitOf = (control: Control) => (COLLAB_LIMITS[props.area] as Record<string, { default: number; min: number; max: number }>)[control.key]
const minOf = (control: Control) => limitOf(control).min / factorOf(control.key)
const maxOf = (control: Control) => limitOf(control).max / factorOf(control.key)
const defaultOf = (control: Control) => limitOf(control).default / factorOf(control.key)
const unitOf = (control: Control) => (MS_KEYS.has(control.key) ? 'ms' : 's')
const numberOf = (key: string) => {
  const value = props.values[key]
  const control = { key } as Control
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : defaultOf(control)
}

const fmt = (control: Control, value: number) => (MS_KEYS.has(control.key) ? (value < 1000 ? `${value} ms` : timeLabel(value / 1000)) : timeLabel(value))

/** A value from a control, kept within the limits. */
const set = (control: Control, value: number) => emit('update', control.key, Math.min(maxOf(control), Math.max(minOf(control), value)))
const typed = (event: Event, control: Control) => {
  const value = (event.target as HTMLInputElement).valueAsNumber
  if (Number.isFinite(value)) set(control, value)
}

// The time axis: X0 to X1 is the line in the viewBox.
const X0 = 10
const X1 = 310
const axisOf = (control: Control, value: number) => X0 + ((Math.log(value) - Math.log(minOf(control))) / (Math.log(maxOf(control)) - Math.log(minOf(control)))) * (X1 - X0)
const axisAt = (control: Control) => axisOf(control, numberOf(control.key))
/** Coarser steps for longer times, so the dot lands on round values. */
const stepOf = (value: number) => (value < 60 ? 1 : value < 600 ? 5 : 30)
const roundTo = (value: number) => Math.round(value / stepOf(value)) * stepOf(value)

const drag = (event: PointerEvent, control: Control) => {
  const svg = event.currentTarget as SVGSVGElement
  if (event.type === 'pointerdown') svg.setPointerCapture(event.pointerId)
  else if ((event.buttons & 1) === 0) return
  const box = svg.getBoundingClientRect()
  const x = ((event.clientX - box.left) / box.width) * 320
  const share = Math.min(1, Math.max(0, (x - X0) / (X1 - X0)))
  set(control, roundTo(Math.exp(Math.log(minOf(control)) + share * (Math.log(maxOf(control)) - Math.log(minOf(control))))))
}
/** Arrow keys move the dot by one step. */
const press = (event: KeyboardEvent, control: Control) => {
  const direction = ['ArrowRight', 'ArrowUp'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 0
  if (direction === 0) return
  event.preventDefault()
  const value = numberOf(control.key)
  set(control, direction > 0 ? value + stepOf(value) : value - stepOf(value - 1))
}

const palette = computed(() => (Array.isArray(props.colors.palette) && props.colors.palette.length >= 3 ? (props.colors.palette as string[]) : [...COLLAB_LIMITS.colors.palette.default]))
const conflict = computed(() => (typeof props.colors.conflictColor === 'string' && /^#[0-9a-f]{6}$/i.test(props.colors.conflictColor) ? props.colors.conflictColor : COLLAB_LIMITS.colors.conflictColor.default))
</script>

<style scoped src="./canvasRows.css"></style>

<style scoped>
.canvas__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  margin-bottom: 6px;
}

.title {
  font-size: 14px;
  font-weight: 600;
}

.canvas__switch {
  flex: none;
}

.badge-text,
.mark-text {
  fill: #fff;
}

.badge-text {
  font-size: 11px;
  font-weight: 600;
}

.mark-text {
  font-size: 10px;
  font-weight: 500;
}

.name-text,
.line-text,
.element-text {
  font-size: 12px;
  fill: #000;
}

.name-text {
  font-weight: 600;
}

.line-text {
  fill: #444;
}

.small-text {
  font-size: 11px;
  fill: #777;
}

.tag-text {
  font-size: 11px;
  fill: #1d5fa5;
}

.prow__main {
  display: flex;
  flex-wrap: wrap;
  flex: 1;
  gap: 4px 12px;
  min-width: 0;
}

.prow__head {
  display: flex;
  flex: 0 0 100px;
  align-items: center;
  align-self: flex-start;
  gap: 4px;
  min-height: 26px;
}

.prow__ctls {
  display: flex;
  flex: 1 1 200px;
  flex-wrap: wrap;
  gap: 2px 12px;
  min-width: 0;
}

.ctl {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 8px;
  min-height: 26px;
  font-size: 12px;
}

.ctl--wide {
  flex-basis: 100%;
}

/* Technical values are only explained until Advanced settings is pressed: grey, faded and not clickable. */
.ctl--locked .ctl__body {
  cursor: not-allowed;
  filter: grayscale(1);
  opacity: 0.4;
}

.ctl--locked .ctl__head {
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.ctl__open {
  color: rgb(var(--v-theme-info));
}

.ctl__num {
  width: 64px;
  padding: 2px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  color: rgb(var(--v-theme-on-surface));
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 2px 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 14px;
}

.chip--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.15);
  font-weight: 600;
}
</style>
