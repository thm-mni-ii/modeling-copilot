<template>
  <div class="canvas">
    <div class="canvas__head">
      <div class="title">What people see on the canvas</div>
      <v-btn :variant="advancedOn ? 'flat' : 'tonal'" color="info" prepend-icon="mdi-wrench-outline" :append-icon="advancedOn ? 'mdi-lock-open-variant-outline' : 'mdi-lock-outline'" class="canvas__switch" :aria-pressed="advancedOn" :title="advancedOn ? 'Lock the technical settings again' : 'The technical settings are locked; press to change them'" @click="advancedOn = !advancedOn">
        Advanced settings
      </v-btn>
    </div>
    <div class="canvas__body">
      <svg viewBox="0 0 420 336" class="canvas__svg" :class="{ 'canvas__svg--dim': active !== 0 }" role="img" aria-label="A shared model with numbered parts: bar, pointer, marks, held element, author dot, overwritten change and notice">
        <defs>
          <pattern id="canvas-grid" width="10" height="10" patternUnits="userSpaceOnUse">
            <path d="M10 0 H0 V10" fill="none" stroke="#e6e6e6" stroke-width="1" />
          </pattern>
        </defs>
        <rect x="20" y="20" width="380" height="296" fill="#fff" />
        <rect x="20" y="20" width="380" height="296" fill="url(#canvas-grid)" />

        <!-- A plain element below everything else; its author dot is part 5. -->
        <g class="part">
          <rect x="290" y="170" width="90" height="50" fill="#fff" stroke="#000" stroke-width="1" />
          <text x="335" y="194" text-anchor="middle" class="element-text">Order</text>
        </g>

        <!-- 1: the frame around the canvas and the bar in its top left corner (ModeBar). -->
        <g class="part" :class="{ 'part--on': active === 1 }" @mouseenter="active = 1" @mouseleave="active = 0">
          <rect x="21.5" y="21.5" width="377" height="293" fill="none" :stroke="bar" stroke-width="3" />
          <path d="M21.5 21.5 H170 V46 a8 8 0 0 1 -8 8 H21.5 Z" fill="#fff" />
          <path d="M170 21.5 V46 a8 8 0 0 1 -8 8 H21.5" fill="none" :stroke="bar" stroke-width="2" />
          <rect x="21.5" y="21.5" width="100" height="32.5" :fill="bar" />
          <circle cx="36" cy="37" r="4" fill="none" stroke="#fff" stroke-width="1.5" />
          <path d="M29 46 a7 5 0 0 1 14 0" fill="none" stroke="#fff" stroke-width="1.5" />
          <text x="48" y="37" dominant-baseline="central" class="chip-text">Collaborating</text>
          <rect x="128" y="26" width="28" height="22" rx="6" fill="#dcebfa" />
          <path d="M137 43 V40 L147 30 L150 33 L140 43 Z" fill="#1d5fa5" />
          <circle cx="198" cy="38" r="9" class="badge" />
          <text x="198" y="38" text-anchor="middle" dominant-baseline="central" class="badge-text">1</text>
        </g>

        <!-- 4: an element held by Ann: thick frame and lock; it is freed when she is idle. -->
        <g class="part" :class="{ 'part--on': active === 4 }" @mouseenter="active = 4" @mouseleave="active = 0">
          <rect x="50" y="95" width="130" height="64" fill="#fff" :stroke="host" stroke-width="3" />
          <text x="115" y="127" text-anchor="middle" class="element-text">Customer</text>
          <circle cx="180" cy="95" r="9" :fill="host" />
          <rect x="176" y="94" width="8" height="6" rx="1" fill="#fff" />
          <path d="M177.5 94 V92 a2.5 2.5 0 0 1 5 0 V94" fill="none" stroke="#fff" stroke-width="1.5" />
          <circle cx="34" cy="127" r="9" class="badge" />
          <text x="34" y="127" text-anchor="middle" dominant-baseline="central" class="badge-text">4</text>
        </g>

        <!-- 3: the others who selected it, at the top left. -->
        <g class="part" :class="{ 'part--on': active === 3 }" @mouseenter="active = 3" @mouseleave="active = 0">
          <g v-for="(person, at) in shownMarks" :key="at">
            <circle :cx="50 + at * 17" cy="95" r="9" :fill="person.color" />
            <text :x="50 + at * 17" y="95" text-anchor="middle" dominant-baseline="central" class="mark-text">{{ person.letter }}</text>
          </g>
          <g v-if="more > 0">
            <circle :cx="50 + shownMarks.length * 17" cy="95" r="9" fill="#888780" />
            <text :x="50 + shownMarks.length * 17" y="95" text-anchor="middle" dominant-baseline="central" class="mark-text">+{{ more }}</text>
          </g>
          <circle cx="67" cy="72" r="9" class="badge" />
          <text x="67" y="72" text-anchor="middle" dominant-baseline="central" class="badge-text">3</text>
        </g>

        <!-- 5: the author dots, bottom left inside an element: fill the creator, ring the last editor (authorMarks). -->
        <g class="part" :class="{ 'part--on': active === 5 }" @mouseenter="active = 5" @mouseleave="active = 0">
          <g :transform="`translate(${50 + dot / 2 + 3} ${159 - dot / 2 - 3}) scale(${dot / 14}) translate(-7 -7)`">
            <circle cx="7" cy="7" r="7" fill="#fff" />
            <circle cx="7" cy="7" r="4.75" :fill="palette[4]" :stroke="palette[5]" stroke-width="2.5" />
          </g>
          <g :transform="`translate(${290 + dot / 2 + 3} ${220 - dot / 2 - 3}) scale(${dot / 14}) translate(-7 -7)`">
            <circle cx="7" cy="7" r="7" fill="#fff" />
            <circle cx="7" cy="7" r="4.75" :fill="palette[2]" :stroke="palette[3]" stroke-width="2.5" />
          </g>
          <circle cx="34" cy="160" r="9" class="badge" />
          <text x="34" y="160" text-anchor="middle" dominant-baseline="central" class="badge-text">5</text>
        </g>

        <!-- 2: the pointer of another person with its name. -->
        <g class="part" :class="{ 'part--on': active === 2 }" @mouseenter="active = 2" @mouseleave="active = 0">
          <g transform="translate(215 105)">
            <path d="M1 1 L1 15 L5 11.5 L8 17 L10.5 16 L7.5 10.5 L13 10.5 Z" :fill="palette[0]" stroke="#fff" stroke-width="1" />
            <rect x="12" y="14" width="30" height="17" rx="4" :fill="palette[0]" />
            <text x="27" y="22.5" text-anchor="middle" dominant-baseline="central" class="pointer-text" :fill="textOn(palette[0])">Ben</text>
          </g>
          <circle cx="262" cy="108" r="9" class="badge" />
          <text x="262" y="108" text-anchor="middle" dominant-baseline="central" class="badge-text">2</text>
        </g>

        <!-- 6: a change of yours that someone else overwrote: dashed frame outside the element. -->
        <g class="part" :class="{ 'part--on': active === 6 }" @mouseenter="active = 6" @mouseleave="active = 0">
          <rect x="44" y="204" width="142" height="62" fill="none" :stroke="conflict" stroke-width="3" stroke-dasharray="6 4" />
          <rect x="50" y="210" width="130" height="50" fill="#fff" stroke="#000" stroke-width="1" />
          <text x="115" y="235" text-anchor="middle" class="element-text">Invoice</text>
          <g :transform="`translate(${50 + dot / 2 + 3} ${260 - dot / 2 - 3}) scale(${dot / 14}) translate(-7 -7)`">
            <circle cx="7" cy="7" r="7" fill="#fff" />
            <circle cx="7" cy="7" r="4.75" :fill="palette[6]" :stroke="palette[6]" stroke-width="2.5" />
          </g>
          <circle cx="30" cy="235" r="9" class="badge" />
          <text x="30" y="235" text-anchor="middle" dominant-baseline="central" class="badge-text">6</text>
        </g>

        <!-- 7: the notice when someone tries to change the held element. -->
        <g class="part" :class="{ 'part--on': active === 7 }" @mouseenter="active = 7" @mouseleave="active = 0">
          <rect x="150" y="280" width="240" height="26" rx="4" fill="#323232" />
          <text x="270" y="293" text-anchor="middle" dominant-baseline="central" class="toast-text">This element is locked. Ann is editing it.</text>
          <circle cx="136" cy="293" r="9" class="badge" />
          <text x="136" y="293" text-anchor="middle" dominant-baseline="central" class="badge-text">7</text>
        </g>
      </svg>

      <div class="rows">
        <div v-for="row in ROWS" :key="row.title" class="prow" :class="{ 'prow--on': active === row.n && row.n > 0, 'prow--locked': row.controls.every(locked) }" @mouseenter="active = row.n" @mouseleave="active = 0" @focusin="active = row.n" @focusout="active = 0">
          <span class="prow__n" :class="{ 'prow__n--none': row.n === 0 }">{{ row.n || '' }}</span>
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
              <div v-for="control in row.controls" :key="control.key" class="ctl" :class="{ 'ctl--locked': locked(control), 'ctl--wide': control.kind === 'time' }">
                <div class="ctl__head">
                  <span class="ctl__label">{{ control.label }}</span>
                  <span v-if="changed(control.area, control.key)" class="ctl__dot" title="Unsaved change" />
                  <v-icon v-if="control.advanced && !locked(control)" icon="mdi-lock-open-variant-outline" size="14" class="ctl__open" title="Advanced setting, unlocked" />
                  <v-icon v-if="locked(control)" icon="mdi-lock-outline" size="14" />
                  <v-btn v-else-if="isChanged(control) && control.kind !== 'shown'" icon="mdi-restore" size="x-small" density="comfortable" variant="text" :aria-label="`Reset ${control.label} to the default`" title="Reset to the default" @click="set(control, defaultOf(control))" />
                </div>
                <div class="ctl__body" :inert="locked(control)">
                  <template v-if="control.kind === 'color'">
                    <input :value="colorOf(control.key)" type="color" class="ctl__color" :aria-label="`${row.title}: ${control.label}`" @input="set(control, ($event.target as HTMLInputElement).value)" />
                    <input :value="colorOf(control.key)" type="text" maxlength="7" spellcheck="false" class="ctl__hex" :aria-label="`${row.title}: ${control.label} as hex`" @change="typedColor($event, control)" />
                  </template>

                  <!-- The host color is set under Colors, together with the palette it must differ from. -->
                  <template v-else-if="control.kind === 'shown'">
                    <span class="ctl__swatch" :style="{ background: colorOf(control.key) }" />
                    <span>{{ colorOf(control.key) }}</span>
                    <span class="ctl__hint">set under Colors</span>
                  </template>

                  <!-- Marks: click the person up to whom the marks show. -->
                  <div v-else-if="control.kind === 'people'" class="people" role="group" :aria-label="control.label">
                    <button v-for="n in 6" :key="n" type="button" class="person" :class="{ 'person--on': n <= marksShown }" :style="n <= marksShown ? { background: palette[n - 1] } : undefined" :aria-label="`Show ${n} ${n === 1 ? 'person' : 'people'}`" :aria-pressed="n <= marksShown" @click="set(control, n)">{{ LETTERS[n - 1] }}</button>
                    <span class="ctl__value">{{ marksShown }} shown{{ marksShown < 6 ? ', the rest as +n' : '' }}</span>
                  </div>

                  <!-- Idle: a dot on a time axis, from 15 s to 1 h on a scale that gives the short times room. -->
                  <template v-else-if="control.kind === 'time'">
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
                      <g v-for="tick in TICKS" :key="tick.at">
                        <line :x1="axisOf(control, tick.at)" :x2="axisOf(control, tick.at)" y1="25" y2="35" class="axis__tick" />
                        <text :x="axisOf(control, tick.at)" y="50" text-anchor="middle" class="axis__text">{{ tick.label }}</text>
                      </g>
                      <circle :cx="axisAt(control)" cy="30" r="9" class="axis__dot" />
                      <text :x="Math.min(Math.max(axisAt(control), 24), 296)" y="12" text-anchor="middle" class="axis__value">{{ fmt(control, numberOf(control.key)) }}</text>
                    </svg>
                    <span class="ctl__exact"><input type="number" class="ctl__num" :value="numberOf(control.key)" :min="minOf(control)" :max="maxOf(control)" :aria-label="`${control.label} exactly`" @change="typed($event, control)" />s</span>
                  </template>

                  <!-- Author dot: the dot itself, pulled larger or smaller at its edge. -->
                  <template v-else-if="control.kind === 'size'">
                    <svg
                      viewBox="0 0 120 64"
                      class="grip"
                      role="slider"
                      tabindex="0"
                      :aria-label="`${row.title}: ${control.label}`"
                      :aria-valuemin="minOf(control)"
                      :aria-valuemax="maxOf(control)"
                      :aria-valuenow="numberOf(control.key)"
                      :aria-valuetext="`${numberOf(control.key)} px`"
                      @pointerdown.prevent="dragSize($event, control)"
                      @pointermove="dragSize($event, control)"
                      @keydown="press($event, control)"
                    >
                      <circle cx="40" cy="32" :r="dot / 2 + 7" class="grip__ring" />
                      <circle cx="40" cy="32" :r="dot / 2" :fill="palette[4]" :stroke="palette[5]" stroke-width="3" />
                      <circle :cx="40 + dot / 2 + 7" cy="32" r="5" class="axis__dot" />
                    </svg>
                    <span class="ctl__exact"><input type="number" class="ctl__num" :value="numberOf(control.key)" :min="minOf(control)" :max="maxOf(control)" :aria-label="`${control.label} exactly`" @change="typed($event, control)" />px</span>
                  </template>

                  <!-- Pointer and waits: a few usual values; the field takes any other. -->
                  <template v-else>
                    <div class="chips" role="group" :aria-label="control.label">
                      <button v-for="preset in control.presets" :key="preset" type="button" class="chip" :class="{ 'chip--on': numberOf(control.key) === preset }" :aria-pressed="numberOf(control.key) === preset" @click="set(control, preset)">{{ fmt(control, preset) }}</button>
                    </div>
                    <span class="ctl__exact"><input type="number" class="ctl__num" :value="numberOf(control.key)" :min="minOf(control)" :max="maxOf(control)" :aria-label="`${control.label} exactly`" @change="typed($event, control)" />{{ unitOf(control) }}</span>
                  </template>
                </div>
                <div v-if="problem(control.area, control.key)" class="ctl__error">{{ problem(control.area, control.key) }}</div>
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
import { textOn } from '@/collab/settings/colorMath'
import { timeLabel } from '@/collab/settings/timeLabel'

/** The presence and color settings as the form shows them: seconds, except cursorSendMs and authorMarkWaitMs in ms. */
const props = defineProps<{ presence: Record<string, unknown>; colors: Record<string, unknown>; changed: (area: 'presence' | 'colors', key: string) => boolean; problem: (area: 'presence' | 'colors', key: string) => string | undefined }>()
const emit = defineEmits<{ update: [area: 'presence' | 'colors', key: string, value: number | string] }>()

interface Control {
  area: 'presence' | 'colors'
  key: string
  label: string
  kind: 'color' | 'shown' | 'people' | 'time' | 'size' | 'chips'
  /** Technical: only to change with the switch on. */
  advanced?: boolean
  /** Usual values of a chips control, in the unit of the form. */
  presets?: number[]
}

/** The parts of the canvas by number, each with the settings that change it; number 0 has no part on the canvas. */
const ROWS: { n: number; title: string; about: string; controls: Control[] }[] = [
  {
    n: 1,
    title: 'Frame and bar',
    about: 'The colored frame around a shared model and the bar in its top left corner.',
    controls: [
      { area: 'colors', key: 'barColor', label: 'While sharing', kind: 'color', advanced: true },
      { area: 'colors', key: 'barAwayColor', label: 'Host disconnected', kind: 'color', advanced: true }
    ]
  },
  { n: 2, title: 'Pointer', about: 'How often your mouse pointer is sent to the others. Shorter looks smoother and sends more data.', controls: [{ area: 'presence', key: 'cursorSendMs', label: 'Share pointer every', kind: 'chips', advanced: true, presets: [20, 50, 100, 200] }] },
  { n: 3, title: 'Others on the same element', about: 'When several people select the same element, they show as small colored marks at its top left, then "+n".', controls: [{ area: 'presence', key: 'marksShown', label: 'People shown as marks', kind: 'people' }] },
  {
    n: 4,
    title: 'Element in use',
    about: 'Whoever selects an element first locks it for the others, until they do nothing for a while.',
    controls: [
      { area: 'colors', key: 'hostColor', label: 'Host color', kind: 'shown' },
      { area: 'presence', key: 'idleMs', label: 'Free again after no activity for', kind: 'time' },
      { area: 'presence', key: 'idleCheckMs', label: 'Checks for inactivity every', kind: 'chips', advanced: true, presets: [2, 5, 10, 30] }
    ]
  },
  {
    n: 5,
    title: 'Who made it',
    about: 'In group rooms, a small dot on every element: the fill shows who made it, the ring who changed it last.',
    controls: [
      { area: 'presence', key: 'authorMarkSize', label: 'Size', kind: 'size', advanced: true },
      { area: 'presence', key: 'authorMarkWaitMs', label: 'Update after a change', kind: 'chips', advanced: true, presets: [500, 1500, 3000, 5000] }
    ]
  },
  { n: 6, title: 'Lost change', about: 'Your change was overwritten by someone else. The element gets this frame for a moment.', controls: [{ area: 'colors', key: 'conflictColor', label: 'Frame', kind: 'color', advanced: true }] },
  { n: 7, title: '“Element is locked” notice', about: 'Shown when someone tries to change an element that another person is using.', controls: [{ area: 'presence', key: 'lockHintMs', label: 'At most every', kind: 'chips', advanced: true, presets: [2, 3, 10, 30] }] },
  { n: 0, title: 'Unknown author', about: 'Changes by someone who is not known, in the event log. The colors of the people are set under Colors below.', controls: [{ area: 'colors', key: 'someoneColor', label: 'Color', kind: 'color', advanced: true }] }
]

/** Hovering a row or a part lights up the other one. */
const active = ref(0)
const advancedOn = ref(false)
const locked = (control: Control) => Boolean(control.advanced) && !advancedOn.value

// Keys in ms in the form; the other keys ending in Ms are shown in seconds (as in CollabSettings.vue).
const MS_KEYS = new Set(['cursorSendMs', 'authorMarkWaitMs'])
const factorOf = (key: string) => (key.endsWith('Ms') && !MS_KEYS.has(key) ? 1000 : 1)
// The palette is a list; every other color has a single default.
const COLOR_LIMITS = COLLAB_LIMITS.colors as unknown as Record<string, { default: string }>
const limitOf = (control: Control) => (COLLAB_LIMITS[control.area] as Record<string, { default: number; min: number; max: number }>)[control.key]
const minOf = (control: Control) => limitOf(control).min / factorOf(control.key)
const maxOf = (control: Control) => limitOf(control).max / factorOf(control.key)
// A color that is only shown (the host color) counts like one that can be changed here.
const isColor = (control: Control) => control.kind === 'color' || control.kind === 'shown'
const defaultOf = (control: Control) => (isColor(control) ? COLOR_LIMITS[control.key].default : limitOf(control).default / factorOf(control.key))
const unitOf = (control: Control) => (MS_KEYS.has(control.key) ? 'ms' : control.kind === 'size' ? 'px' : 's')

const numberOf = (key: string) => {
  const value = props.presence[key]
  const fallback = (COLLAB_LIMITS.presence as Record<string, { default: number }>)[key].default / factorOf(key)
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback
}
const colorOf = (key: string) => {
  const value = props.colors[key]
  return typeof value === 'string' && /^#[0-9a-f]{6}$/i.test(value) ? value : COLOR_LIMITS[key].default
}
const isChanged = (control: Control) => (isColor(control) ? colorOf(control.key).toLowerCase() !== String(defaultOf(control)).toLowerCase() : numberOf(control.key) !== defaultOf(control))

const msLabel = (ms: number) => (ms < 1000 ? `${ms} ms` : timeLabel(ms / 1000))
const fmt = (control: Control, value: number) => (control.kind === 'size' ? `${value} px` : MS_KEYS.has(control.key) ? msLabel(value) : timeLabel(value))

/** A value from a control, kept within the limits. */
const set = (control: Control, value: number | string) => emit('update', control.area, control.key, typeof value === 'number' ? Math.min(maxOf(control), Math.max(minOf(control), value)) : value)
const typed = (event: Event, control: Control) => {
  const value = (event.target as HTMLInputElement).valueAsNumber
  if (Number.isFinite(value)) set(control, value)
}

// The time axis: a logarithmic scale, so seconds and hours both fit; X0 to X1 is the line in the viewBox.
const X0 = 10
const X1 = 310
const TICKS = [
  { at: 15, label: '15 s' },
  { at: 60, label: '1 min' },
  { at: 300, label: '5 min' },
  { at: 900, label: '15 min' },
  { at: 3600, label: '1 h' }
]
const axisOf = (control: Control, value: number) => X0 + ((Math.log(value) - Math.log(minOf(control))) / (Math.log(maxOf(control)) - Math.log(minOf(control)))) * (X1 - X0)
const axisAt = (control: Control) => axisOf(control, numberOf(control.key))
/** Coarser steps for longer times, so the dot lands on round values. */
const stepOf = (value: number) => (value < 60 ? 1 : value < 600 ? 5 : 30)
const roundTo = (value: number) => Math.round(value / stepOf(value)) * stepOf(value)

/** A hex code typed next to the swatch; anything but #rrggbb (the # is optional) puts the last color back. */
const typedColor = (event: Event, control: Control) => {
  const input = event.target as HTMLInputElement
  const hex = `#${input.value.trim().replace(/^#/, '')}`.toLowerCase()
  if (/^#[0-9a-f]{6}$/.test(hex)) set(control, hex)
  input.value = /^#[0-9a-f]{6}$/.test(hex) ? hex : colorOf(control.key)
}

/** A pointer on an SVG control as x in its viewBox. */
const xOf = (event: PointerEvent, width: number) => {
  const svg = event.currentTarget as SVGSVGElement
  if (event.type === 'pointerdown') svg.setPointerCapture(event.pointerId)
  else if ((event.buttons & 1) === 0) return null
  const box = svg.getBoundingClientRect()
  return ((event.clientX - box.left) / box.width) * width
}
const drag = (event: PointerEvent, control: Control) => {
  const x = xOf(event, 320)
  if (x === null) return
  const share = Math.min(1, Math.max(0, (x - X0) / (X1 - X0)))
  set(control, roundTo(Math.exp(Math.log(minOf(control)) + share * (Math.log(maxOf(control)) - Math.log(minOf(control))))))
}
const dragSize = (event: PointerEvent, control: Control) => {
  const x = xOf(event, 120)
  if (x !== null) set(control, Math.round((x - 47) * 2))
}
/** Arrow keys move the dot by one step. */
const press = (event: KeyboardEvent, control: Control) => {
  const direction = ['ArrowRight', 'ArrowUp'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 0
  if (direction === 0) return
  event.preventDefault()
  const value = numberOf(control.key)
  set(control, control.kind === 'size' ? value + direction : direction > 0 ? value + stepOf(value) : value - stepOf(value - 1))
}

const LETTERS = ['B', 'C', 'D', 'E', 'F', 'G']
const marksShown = computed(() => Math.min(6, Math.max(1, Math.round(numberOf('marksShown')))))
const dot = computed(() => Math.min(32, Math.max(8, numberOf('authorMarkSize'))))
const host = computed(() => colorOf('hostColor'))
const bar = computed(() => colorOf('barColor'))
const conflict = computed(() => colorOf('conflictColor'))
const palette = computed(() => (Array.isArray(props.colors.palette) && props.colors.palette.length >= 7 ? (props.colors.palette as string[]) : [...COLLAB_LIMITS.colors.palette.default]))

// Ann holds the element; six others selected it too. As many as the setting allows show as marks with their initial, the rest as "+n".
const OTHERS = LETTERS
const shownMarks = computed(() => OTHERS.slice(0, marksShown.value).map((letter, at) => ({ letter, color: palette.value[at] })))
const more = computed(() => Math.max(0, OTHERS.length - marksShown.value))
</script>

<style scoped>
.canvas {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
  font-size: 13px;
  container-type: inline-size;
}

.title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}

.canvas__body {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
  align-items: flex-start;
}

.canvas__svg {
  flex: 1 1 300px;
  min-width: 0;
  max-width: clamp(380px, 36cqw, 480px);
}

/* While a part or a row is lit up, the other parts fade. */
.part {
  transition: opacity 0.15s;
}

.canvas__svg--dim .part:not(.part--on) {
  opacity: 0.3;
}

.badge {
  fill: rgb(var(--v-theme-primary));
}

.badge-text,
.chip-text,
.toast-text,
.mark-text {
  fill: #fff;
}

.badge-text {
  font-size: 11px;
  font-weight: 600;
}

.element-text {
  font-size: 12px;
  fill: #000;
}

.chip-text,
.toast-text {
  font-size: 12px;
}

.chip-text {
  font-weight: 500;
}

.mark-text {
  font-size: 10px;
  font-weight: 500;
}

.pointer-text {
  font-size: 11px;
}

.rows {
  flex: 1 1 340px;
  min-width: 0;
}

.canvas__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
}

.canvas__head .title {
  margin: 0;
}

.canvas__switch {
  flex: none;
}

/* Every part is a framed card with the grey background; the rest of the canvas card is white. */
.prow {
  display: flex;
  gap: 10px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  transition:
    background 0.15s,
    border-color 0.15s;
}

/* A part with nothing to change yet is an empty frame on white. */
.prow--locked {
  border-style: dashed;
  background: transparent;
}

.prow--on {
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.prow__n {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}

.prow__n--none {
  background: transparent;
}

.prow__main {
  display: flex;
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

.prow__info {
  cursor: help;
  opacity: 0.55;
}

/* The controls of a part flow in a line and wrap; the time axis takes a line of its own. */
.prow__ctls {
  display: flex;
  flex: 1;
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

.ctl__head {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(var(--v-theme-on-surface), 0.75);
}

.ctl__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--v-theme-warning));
}

.ctl__body {
  display: flex;
  align-items: center;
  gap: 4px 12px;
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

.ctl__error {
  flex-basis: 100%;
  color: rgb(var(--v-theme-error));
}

.ctl__value {
  font-weight: 500;
}

.ctl__color {
  width: 30px;
  height: 22px;
  padding: 0;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  background: none;
  cursor: pointer;
}

.ctl__swatch {
  width: 30px;
  height: 22px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
}

.ctl__hint {
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.ctl__hex {
  width: 68px;
  padding: 2px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  color: rgb(var(--v-theme-on-surface));
}

.ctl__exact {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(var(--v-theme-on-surface), 0.65);
}

.ctl__num {
  width: 56px;
  padding: 2px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  color: rgb(var(--v-theme-on-surface));
}

.people {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.person {
  width: 24px;
  height: 24px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.4);
  border-radius: 50%;
  font-size: 11px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.person--on {
  border-style: solid;
  border-color: transparent;
  color: #fff;
}

.axis {
  flex: 1 1 220px;
  min-width: 180px;
  max-width: 250px;
  cursor: pointer;
  touch-action: none;
}

.axis__line,
.axis__tick {
  stroke: rgba(var(--v-theme-on-surface), 0.3);
  stroke-width: 2;
}

.axis__tick {
  stroke-width: 1;
}

.axis__fill {
  stroke: rgb(var(--v-theme-primary));
  stroke-width: 4;
}

.axis__dot {
  fill: rgb(var(--v-theme-primary));
}

.axis__text,
.axis__value {
  font-size: 12px;
  fill: rgba(var(--v-theme-on-surface), 0.65);
}

.axis__value {
  font-size: 14px;
  font-weight: 600;
  fill: rgb(var(--v-theme-on-surface));
}

.grip {
  width: 84px;
  height: 45px;
  cursor: ew-resize;
  touch-action: none;
}

.grip__ring {
  fill: none;
  stroke: rgba(var(--v-theme-on-surface), 0.4);
  stroke-dasharray: 3 3;
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

/* Where the canvas is wide, the parts run in two columns beside the picture, each with its title on top. */
@container (min-width: 1250px) {
  .rows {
    column-count: 2;
    column-gap: 24px;
  }

  .prow {
    break-inside: avoid;
  }

  .prow__main {
    flex-direction: column;
  }

  .prow__head {
    flex: none;
  }
}
</style>
