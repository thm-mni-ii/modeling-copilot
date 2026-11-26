<template>
  <div class="editor">
    <div class="editor__grid">
      <div class="editor__left">
        <section class="block">
          <div class="block__head">
            <b>Host</b>
            <span v-if="changed('hostColor')" class="dot" title="Unsaved change" />
            <span class="hint">The person who shared their model. Only the host wears this color, so visitors recognize them at once. In group rooms there is no host.</span>
          </div>
          <div class="line">
            <input :value="host" type="color" class="color" aria-label="Host color" @input="emit('update', 'hostColor', ($event.target as HTMLInputElement).value)" />
            <input :value="host" type="text" maxlength="7" spellcheck="false" class="hex" aria-label="Host color as hex" @change="typedHost($event)" />
            <v-btn v-if="host !== HOST_DEFAULT" icon="mdi-restore" size="x-small" density="comfortable" variant="text" aria-label="Reset the host color to the default" title="Reset to the default" @click="emit('update', 'hostColor', HOST_DEFAULT)" />
          </div>
        </section>

        <section class="block">
          <div class="block__head">
            <b>Everyone else</b>
            <span v-if="changed('palette')" class="dot" title="Unsaved change" />
            <span class="hint">Visitors of a shared model and members of a group room. Newcomers get the next free color, starting at 1. {{ palette.length }} colors ({{ LIMIT.minItems }}–{{ LIMIT.maxItems }} allowed), drag to reorder.</span>
          </div>
          <div class="strip" role="list" aria-label="Palette">
            <div v-for="(color, at) in palette" :key="`${at}-${color}`" class="sw" :class="{ 'sw--selected': selected === at, 'sw--over': over === at && drag !== at, 'sw--close': closeAt.has(at) }" role="listitem" draggable="true" @dragstart="drag = at" @dragend="drag = over = -1" @dragover.prevent="over = at" @drop.prevent="drop(at)">
              <button type="button" class="sw__color" :style="{ background: color, color: textOn(color) }" :aria-label="`Color ${at + 1}, ${color}`" :aria-pressed="selected === at" @click="selected = selected === at ? -1 : at">{{ at + 1 }}</button>
              <button v-if="palette.length > LIMIT.minItems" type="button" class="sw__x" :aria-label="`Remove color ${at + 1}`" @click.stop="remove(at)">×</button>
            </div>
            <button v-if="palette.length < LIMIT.maxItems" type="button" class="sw__add" aria-label="Add a color" title="Add a color that is far from the others" @click="add">+</button>
          </div>

          <div v-if="selected >= 0 && selected < palette.length" class="line line--selected">
            <span class="hint">Color {{ selected + 1 }}</span>
            <input :value="palette[selected]" type="color" class="color" :aria-label="`Color ${selected + 1}`" @input="setAt(selected, ($event.target as HTMLInputElement).value)" />
            <input :value="palette[selected]" type="text" maxlength="7" spellcheck="false" class="hex" :aria-label="`Color ${selected + 1} as hex`" @change="typedAt($event, selected)" />
            <v-btn icon="mdi-arrow-left" size="x-small" density="comfortable" variant="text" :disabled="selected === 0" aria-label="Move earlier" title="Move earlier" @click="move(selected, -1)" />
            <v-btn icon="mdi-arrow-right" size="x-small" density="comfortable" variant="text" :disabled="selected === palette.length - 1" aria-label="Move later" title="Move later" @click="move(selected, 1)" />
          </div>
          <div v-else class="hint">Click a color to change it.</div>
        </section>

        <section class="block">
          <div class="block__head">
            <b>Paste colors</b>
            <span class="hint">hex codes, one per line or separated by spaces or commas</span>
          </div>
          <textarea v-model="pasted" rows="3" spellcheck="false" class="paste" placeholder="#c29ed7 #214b25 #ee9813" aria-label="Colors to paste" />
          <div class="line">
            <v-btn size="small" color="primary" variant="flat" :disabled="!pasted.trim()" @click="apply(true)">Replace palette</v-btn>
            <v-btn size="small" variant="outlined" :disabled="!pasted.trim()" @click="apply(false)">Add to palette</v-btn>
          </div>
          <div v-if="report" class="report" :class="{ 'report--bad': report.bad }">{{ report.text }}</div>
        </section>
      </div>

      <div class="editor__right">
        <section class="block">
          <div class="block__head">
            <b>Live preview</b>
            <span class="hint">the host and {{ people.length }} others</span>
          </div>
          <svg viewBox="0 0 300 190" class="scene" role="img" aria-label="A model with the host and six others in the colors of the palette">
            <rect x="0" y="0" width="300" height="190" fill="#fff" />
            <rect x="1" y="1" width="298" height="188" fill="none" :stroke="bar" stroke-width="2" />
            <rect x="30" y="70" width="120" height="60" fill="#fff" :stroke="host" stroke-width="3" />
            <text x="90" y="104" text-anchor="middle" class="scene__text">Customer</text>
            <circle cx="150" cy="70" r="9" :fill="host" />
            <rect x="146" y="69" width="8" height="6" rx="1" fill="#fff" />
            <path d="M147.5 69 V67 a2.5 2.5 0 0 1 5 0 V69" fill="none" stroke="#fff" stroke-width="1.5" />
            <g v-for="(person, at) in people.slice(0, 6)" :key="at">
              <circle :cx="30 + at * 17" cy="70" r="9" :fill="person.color" />
              <text :x="30 + at * 17" y="70" text-anchor="middle" dominant-baseline="central" class="scene__mark">{{ person.name.charAt(0) }}</text>
            </g>
            <g transform="translate(40 120)">
              <circle cx="0" cy="0" r="7" fill="#fff" />
              <circle cx="0" cy="0" r="4.75" :fill="palette[2] ?? host" :stroke="palette[3] ?? host" stroke-width="2.5" />
            </g>
            <g v-for="(pointer, at) in pointers" :key="at" :transform="`translate(${pointer.x} ${pointer.y})`">
              <path d="M1 1 L1 15 L5 11.5 L8 17 L10.5 16 L7.5 10.5 L13 10.5 Z" :fill="pointer.color" stroke="#fff" stroke-width="1" />
              <rect x="12" y="14" width="34" height="17" rx="4" :fill="pointer.color" />
              <text x="29" y="22.5" text-anchor="middle" dominant-baseline="central" class="scene__name" :fill="textOn(pointer.color)">{{ pointer.name }}</text>
            </g>
          </svg>
          <div class="people">
            <span class="person" :style="{ background: host, color: textOn(host) }">Ann · host</span>
            <span v-for="person in people" :key="person.name" class="person" :style="{ background: person.color, color: textOn(person.color) }">{{ person.name }}</span>
          </div>
        </section>

        <section class="block check" :class="{ 'check--bad': Boolean(problem), 'check--warn': !problem && closePairs.length > 0 }">
          <template v-if="problem">
            <b>Not allowed</b>
            <span>{{ problem }}</span>
          </template>
          <template v-else-if="closePairs.length > 0">
            <b>{{ closePairs.length }} {{ closePairs.length === 1 ? 'hint' : 'hints' }}</b>
            <span v-for="pair in closePairs.slice(0, 3)" :key="pair">{{ pair }}</span>
            <span v-if="closePairs.length > 3">and {{ closePairs.length - 3 }} more.</span>
          </template>
          <template v-else>
            <b>All colors are clear</b>
            <span>The host and the {{ palette.length }} others can be told apart.</span>
          </template>
        </section>

        <section class="block">
          <div class="block__head">
            <b>Ready palettes</b>
          </div>
          <div class="line">
            <v-btn size="small" :variant="isPreset(LIMIT.default) ? 'tonal' : 'outlined'" @click="useColors([...LIMIT.default])">Default palette</v-btn>
            <v-btn size="small" :variant="isPreset(COLOR_BLIND_SAFE) ? 'tonal' : 'outlined'" @click="useColors([...COLOR_BLIND_SAFE])">Color-blind safe</v-btn>
          </div>
          <div class="hint">Color-blind safe: {{ COLOR_BLIND_SAFE.length }} colors that stay apart under red-green and blue-yellow color blindness. More people than colors share a color.</div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { COLLAB_LIMITS } from '@/collab/settings/collabSettings'
import { colorDistance, hexOf, textOn } from '@/collab/settings/colorMath'

/** The host color and the palette as the form shows them; the other colors are only read for the preview. */
const props = defineProps<{ colors: Record<string, unknown>; problem: string | undefined; changed: (key: 'hostColor' | 'palette') => boolean }>()
const emit = defineEmits<{ update: [key: 'hostColor' | 'palette', value: string | string[]] }>()

const LIMIT = COLLAB_LIMITS.colors.palette
const HOST_DEFAULT = COLLAB_LIMITS.colors.hostColor.default
/**
 * Eight colors picked from the Okabe-Ito and Tol palettes: simulated for protan, deutan and tritan vision they lie at least
 * 14 apart in Lab (CIE76), in normal vision at least 19, and none is closer than 25 to the default host color.
 */
const COLOR_BLIND_SAFE = ['#e69f00', '#56b4e9', '#4b0092', '#882255', '#ddcc77', '#0072b2', '#cc79a7', '#194b78']
/** Below this distance the tab warns without blocking saving (as in CollabSettings.vue). */
const CLOSE = 15

const colorOf = (key: string, fallback: string) => {
  const value = props.colors[key]
  return typeof value === 'string' && hexOf(value) ? value : fallback
}
const host = computed(() => colorOf('hostColor', HOST_DEFAULT))
const bar = computed(() => colorOf('barColor', COLLAB_LIMITS.colors.barColor.default))
const palette = computed(() => (Array.isArray(props.colors.palette) ? (props.colors.palette as string[]) : [...LIMIT.default]))

const NAMES = ['Ben', 'Cem', 'Dana', 'Eli', 'Fay', 'Gus']
const people = computed(() => NAMES.slice(0, Math.max(1, Math.min(NAMES.length, palette.value.length))).map((name, at) => ({ name, color: palette.value[at] })))
const pointers = computed(() => [
  { x: 190, y: 40, ...people.value[0] },
  { x: 200, y: 120, ...people.value[Math.min(1, people.value.length - 1)] }
])

// Pairs that are hard to tell apart; the swatches of such a pair get a mark.
const closePairs = computed(() => {
  const all = [host.value, ...palette.value]
  const pairs: string[] = []
  for (const [at, color] of all.entries()) for (const [later, other] of all.entries()) if (later > at && colorDistance(color, other) < CLOSE) pairs.push(`${at === 0 ? 'The host' : `Color ${at}`} and ${later === 0 ? 'the host' : `color ${later}`} are hard to tell apart.`)
  return pairs
})
const closeAt = computed(() => {
  const marked = new Set<number>()
  const all = [host.value, ...palette.value]
  for (const [at, color] of all.entries()) for (const [later, other] of all.entries()) if (later > at && colorDistance(color, other) < CLOSE) [at, later].forEach((one) => one > 0 && marked.add(one - 1))
  return marked
})

// Any change but the one of a paste makes the message about the last paste obsolete.
const send = (next: string[]) => {
  report.value = null
  emit('update', 'palette', next)
}
const selected = ref(-1)
const drag = ref(-1)
const over = ref(-1)

const typedHost = (event: Event) => {
  const input = event.target as HTMLInputElement
  const hex = hexOf(input.value)
  if (hex) emit('update', 'hostColor', hex)
  input.value = hex ?? host.value
}
const setAt = (at: number, color: string) => send(palette.value.map((one, index) => (index === at ? color : one)))
const typedAt = (event: Event, at: number) => {
  const input = event.target as HTMLInputElement
  const hex = hexOf(input.value)
  if (hex) setAt(at, hex)
  input.value = hex ?? palette.value[at]
}
const move = (at: number, step: number) => {
  const next = [...palette.value]
  const [one] = next.splice(at, 1)
  next.splice(at + step, 0, one)
  send(next)
  selected.value = at + step
}
const drop = (to: number) => {
  const from = drag.value
  drag.value = over.value = -1
  if (from < 0 || from === to) return
  const next = [...palette.value]
  const [one] = next.splice(from, 1)
  next.splice(to, 0, one)
  send(next)
  selected.value = to
}
const remove = (at: number) => {
  send(palette.value.filter((_, index) => index !== at))
  selected.value = -1
}
/** A new color: of many random ones, the one that lies farthest from all the others. */
const add = () => {
  const others = [host.value, ...palette.value]
  let best = '#808080'
  let far = -1
  for (let tries = 0; tries < 80; tries += 1) {
    const color = `#${Math.floor(Math.random() * 0x1000000)
      .toString(16)
      .padStart(6, '0')}`
    const gap = Math.min(...others.map((other) => colorDistance(color, other)))
    if (gap > far) [best, far] = [color, gap]
  }
  send([...palette.value, best])
  // The form is the same reactive object, so the new color is already the last one.
  selected.value = palette.value.length - 1
}

const useColors = (colors: string[]) => {
  selected.value = -1
  send(colors)
}
const isPreset = (colors: readonly string[]) => colors.length === palette.value.length && colors.every((color, at) => color.toLowerCase() === palette.value[at].toLowerCase())

// Pasting: every word must be a hex color; what is not, a repeat or the host color is told, nothing goes unnoticed.
const pasted = ref('')
const report = ref<{ text: string; bad: boolean } | null>(null)
const apply = (replace: boolean) => {
  const words = pasted.value.split(/[\s,;]+/).filter(Boolean)
  const found: string[] = []
  const ignored: string[] = []
  let repeats = 0
  for (const word of words) {
    const hex = hexOf(word.replace(/^["']|["']$/g, ''))
    if (!hex) ignored.push(word)
    else if (found.includes(hex) || (!replace && palette.value.some((color) => color.toLowerCase() === hex))) repeats += 1
    else found.push(hex)
  }
  const withoutHost = found.filter((color) => color !== host.value.toLowerCase())
  const skippedHost = found.length - withoutHost.length
  const room = replace ? LIMIT.maxItems : LIMIT.maxItems - palette.value.length
  const taken = withoutHost.slice(0, room)
  const notes = [ignored.length ? `not a hex color: ${ignored.slice(0, 3).join(', ')}${ignored.length > 3 ? ' …' : ''}` : '', repeats ? `${repeats} repeated` : '', skippedHost ? 'the host color is not allowed' : '', withoutHost.length > room ? `${withoutHost.length - room} over the limit of ${LIMIT.maxItems}` : ''].filter(Boolean)
  if (replace && taken.length < LIMIT.minItems) {
    report.value = { text: `At least ${LIMIT.minItems} colors are needed, found ${taken.length}. The palette is unchanged.${notes.length ? ` Skipped: ${notes.join('; ')}.` : ''}`, bad: true }
    return
  }
  send(replace ? taken : [...palette.value, ...taken])
  selected.value = -1
  pasted.value = ''
  report.value = { text: `${replace ? 'Palette replaced with' : 'Added'} ${taken.length} ${taken.length === 1 ? 'color' : 'colors'}.${notes.length ? ` Skipped: ${notes.join('; ')}.` : ''}`, bad: notes.length > 0 }
}
</script>

<style scoped>
.editor {
  padding: 10px 12px;
  background: rgb(var(--v-theme-surface));
  font-size: 13px;
  container-type: inline-size;
}

.editor__grid {
  display: grid;
  gap: 16px;
}

.editor__left,
.editor__right {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

/* Where there is room, the editor stands beside its preview. */
@container (min-width: 760px) {
  .editor__grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 320px);
  }
}

.block {
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.block__head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px 8px;
  margin-bottom: 6px;
}

.hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.65);
}

.dot {
  align-self: center;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgb(var(--v-theme-warning));
}

.line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin-top: 6px;
}

.line:first-of-type {
  margin-top: 0;
}

.color {
  width: 36px;
  height: 24px;
  padding: 0;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  background: none;
  cursor: pointer;
}

.hex {
  width: 78px;
  padding: 2px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  color: rgb(var(--v-theme-on-surface));
}

.strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sw {
  position: relative;
  padding-bottom: 5px;
  border-bottom: 3px solid transparent;
}

.sw--close {
  border-bottom-color: rgb(var(--v-theme-warning));
}

.sw--over .sw__color {
  outline: 2px dashed rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.sw--selected .sw__color {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}

.sw__color {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: grab;
}

.sw__x {
  position: absolute;
  top: -6px;
  right: -6px;
  display: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 0 0 1px rgba(var(--v-theme-on-surface), 0.4);
  font-size: 12px;
  line-height: 16px;
}

.sw:hover .sw__x,
.sw:focus-within .sw__x {
  display: block;
}

.sw__add {
  width: 34px;
  height: 34px;
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.45);
  border-radius: 6px;
  font-size: 18px;
}

.paste {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  background: rgb(var(--v-theme-surface));
  font-family: ui-monospace, monospace;
  font-size: 12px;
  color: rgb(var(--v-theme-on-surface));
  resize: vertical;
}

.report {
  margin-top: 6px;
  font-size: 12px;
  color: rgb(var(--v-theme-success));
}

.report--bad {
  color: rgb(var(--v-theme-error));
}

.scene {
  display: block;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.15);
}

.scene__text {
  font-size: 12px;
  fill: #000;
}

.scene__mark {
  font-size: 10px;
  font-weight: 500;
  fill: #fff;
}

.scene__name {
  font-size: 11px;
}

.people {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.person {
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 11px;
}

.check {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-color: rgb(var(--v-theme-success));
  font-size: 12px;
}

.check b {
  color: rgb(var(--v-theme-success));
}

.check--warn {
  border-color: rgb(var(--v-theme-warning));
}

.check--warn b {
  color: rgb(var(--v-theme-warning));
}

.check--bad {
  border-color: rgb(var(--v-theme-error));
}

.check--bad b {
  color: rgb(var(--v-theme-error));
}
</style>
