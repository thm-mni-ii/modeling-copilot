<template>
  <div class="collab-settings">
    <p class="about mb-4">These settings apply to every shared model and group room. A change reaches everyone connected at once, and the backend at its next look at the shares.</p>
    <v-sheet v-for="section in SECTIONS" :key="section.area" border rounded="lg" class="pa-4 mb-4">
      <h3 class="title">{{ section.title }}</h3>
      <p class="about mb-4">{{ section.about }}</p>
      <div class="fields">
        <div v-for="field in section.fields" v-show="shown(section.area, field)" :key="field.key">
          <v-select v-if="field.items" v-model="form[section.area][field.key]" :items="field.items" item-title="title" item-value="value" :label="field.label" density="compact" :disabled="!loaded" :hint="hintOf(section.area, field)" persistent-hint />
          <v-switch v-else-if="typeof limitOf(section.area, field.key).default === 'boolean'" v-model="form[section.area][field.key]" :label="field.label" color="primary" density="compact" inset :disabled="!loaded" :hint="hintOf(section.area, field)" persistent-hint />
          <div v-else-if="'color' in limitOf(section.area, field.key)" class="colors">
            <div class="colors__label">{{ field.label }}</div>
            <span class="swatch" :style="{ color: textOn(String(form[section.area][field.key])) }">
              <input v-model="form[section.area][field.key]" type="color" :disabled="!loaded" :aria-label="field.label" />
              <span class="swatch__text">H</span>
            </span>
            <div class="colors__hint">{{ hintOf(section.area, field) }}</div>
          </div>
          <div v-else-if="'minItems' in limitOf(section.area, field.key)" class="colors">
            <div class="colors__label">{{ field.label }}</div>
            <div class="d-flex flex-wrap align-center ga-1">
              <span v-for="(color, at) in listOf(section.area, field.key)" :key="at" class="swatch" :style="{ color: textOn(color) }">
                <input :value="color" type="color" :disabled="!loaded" :aria-label="`${field.label} ${at + 1}`" @input="setColor(section.area, field.key, at, $event)" />
                <span class="swatch__text">{{ at + 1 }}</span>
                <v-btn icon="mdi-close" size="x-small" density="compact" variant="flat" class="swatch__remove" :disabled="!loaded" :aria-label="`Remove color ${at + 1}`" @click="listOf(section.area, field.key).splice(at, 1)" />
              </span>
              <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" class="ml-2" :disabled="!loaded" @click="listOf(section.area, field.key).push(randomColor())">Add color</v-btn>
            </div>
            <div v-if="problemOf(section.area, field.key)" class="colors__hint text-error">{{ problemOf(section.area, field.key) }}</div>
            <div v-else-if="warningOf(section.area)" class="colors__hint text-warning">{{ warningOf(section.area) }}</div>
            <div v-else class="colors__hint">{{ hintOf(section.area, field) }}</div>
          </div>
          <v-text-field v-else v-model.number="form[section.area][field.key]" type="number" :label="field.label" :suffix="unitOf(field.key)" density="compact" :disabled="!loaded" :hint="hintOf(section.area, field)" persistent-hint :error-messages="problemOf(section.area, field.key)" />
        </div>
      </div>
      <v-btn v-if="section.fields.some((field) => field.advanced)" variant="text" size="small" class="mt-2" :append-icon="open[section.area] ? 'mdi-chevron-up' : 'mdi-chevron-down'" @click="open[section.area] = !open[section.area]">Advanced</v-btn>
      <div class="d-flex ga-2 mt-4">
        <v-btn color="primary" variant="flat" :disabled="!loaded || !changed(section.area) || invalid(section) || busy !== null" :loading="busy === section.area" @click="save(section)">Save</v-btn>
        <v-btn variant="text" :disabled="!loaded || busy !== null" @click="reset(section)">Reset to defaults</v-btn>
      </div>
    </v-sheet>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { collabErrorMessage } from '@/collab/kit/collabKit'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'
import { applyCollabSettings, COLLAB_AREAS, COLLAB_LIMITS, collabSettings, loadCollabSettings, type CollabArea, type CollabLimit } from '@/collab/connection/collabSettings'
import { historyChoices } from '@/collab/sharing/shareModel'
import { textOn } from '@/collab/presence/cursors'

const props = defineProps<{ ck: CollabKitApi }>()

/** A field in the tab; with items a choice, otherwise by its default a switch or a number in seconds, with unit in ms or days. Technical ones are under "Advanced". */
interface Field {
  readonly key: string
  readonly label: string
  readonly hint: string
  readonly items?: readonly { readonly value: string; readonly title: string }[]
  readonly unit?: 'ms' | 'days'
  readonly advanced?: boolean
}

interface Section {
  readonly area: CollabArea
  readonly title: string
  readonly about: string
  readonly fields: readonly Field[]
}

type FormValue = number | string | boolean | string[]

/** One section per area in collab-kit; limits and defaults are in collabSettings.ts. */
const SECTIONS: readonly Section[] = [
  {
    area: 'sharing',
    title: 'Sharing',
    about: 'How long the host and the visitors of a shared model may be away. Reloading a page takes a few seconds and must not count.',
    fields: [
      { key: 'visitorGraceSeconds', label: 'Visitor away until they leave', hint: 'The visitor leaves the room, and their working copy is deleted.' },
      { key: 'hostGraceSeconds', label: 'Host away until the room locks', hint: 'Nobody can edit or join until the host is back.' },
      { key: 'hostEndSeconds', label: 'Host away until all visitors leave', hint: 'The model stays for the host.' },
      { key: 'hostAwayMs', label: 'Host away until visitors are told', hint: 'Visitors see "The host is disconnected."' },
      { key: 'sweepSeconds', label: 'Backend checks every', hint: 'How often the backend looks who is away. Shorter keeps the times above more exact and asks collab-kit more often.', advanced: true },
      { key: 'followMs', label: 'Visitors fetch the room history every', hint: 'What a visitor takes along on leaving is at most this old.', advanced: true }
    ]
  },
  {
    area: 'presence',
    title: 'Presence',
    about: 'Applies to everyone working on a model together, shared or in a group room.',
    fields: [
      { key: 'idleMs', label: 'Idle until the selection is released', hint: 'With the selection go the locks on its elements.' },
      { key: 'cursorSendMs', label: 'Cursor sent at most every', hint: 'Shorter moves pointers more smoothly and sends more.', unit: 'ms', advanced: true }
    ]
  },
  {
    area: 'shareDefaults',
    title: 'Share defaults',
    about: 'What the dialog has chosen when someone shares a model. The host can still change it there for each share.',
    fields: [
      { key: 'anonymous', label: 'Anonymous', hint: 'Others see a pseudonym instead of the name.' },
      { key: 'edit', label: 'May edit', hint: 'Visitors change the model together with the host.' },
      { key: 'history', label: 'Share history', hint: 'How much of the private history goes into the shared model.', items: historyChoices }
    ]
  },
  {
    area: 'colors',
    title: 'Colors',
    about: 'The colors of people in a shared model or group room: cursor, selection, locks and the marks of who made what. Everyone sees the same colors; a change reaches open models at once.',
    fields: [
      { key: 'hostColor', label: 'Host', hint: 'Only the host wears it, so keep it apart from the colors of the others.' },
      { key: 'palette', label: 'Everyone else', hint: 'Handed out in this order, so the first ones should differ the most.' }
    ]
  },
  {
    area: 'archive',
    title: 'Archive',
    about: 'Archived workpieces, rooms and groups can be restored or deleted for good. Turned off, the Archive tab is hidden, but collab-kit still offers to archive rooms, groups and workpieces.',
    fields: [
      { key: 'enabled', label: 'Archive', hint: 'Shows the Archive tab here.' },
      { key: 'archiveOnShareClose', label: 'Archive ended shares', hint: 'The model and the task of a share go to the archive when the host ends it, instead of staying in collab-kit without a room. Only while the archive is on.' },
      { key: 'archiveUnusedAfterDays', label: 'Archive unused shared models after', hint: 'Models and tasks of ended shares that lie in no room and nobody has used for so long; the backend looks every hour. 0 never archives. Only while the archive is on.', unit: 'days' }
    ]
  }
]

/** The form shows seconds, except for fields with a unit of their own; keys ending in Ms without a unit are stored in milliseconds in collab-kit. */
const UNITS = new Map(SECTIONS.flatMap((section) => section.fields.flatMap((field) => (field.unit ? [[field.key, field.unit] as const] : []))))
const unitOf = (key: string) => UNITS.get(key) ?? 's'
const factorOf = (key: string) => (key.endsWith('Ms') && !UNITS.has(key) ? 1000 : 1)
const limitOf = (area: CollabArea, key: string) => (COLLAB_LIMITS[area] as Record<string, CollabLimit>)[key]
const hintOf = (area: CollabArea, field: Field) => {
  const limit = limitOf(area, field.key)
  if ('options' in limit) return `${field.hint} Default: ${field.items?.find((item) => item.value === limit.default)?.title ?? limit.default}.`
  if ('color' in limit) return `${field.hint} Default ${limit.default}.`
  if ('minItems' in limit) return `${field.hint} Default ${limit.default.length} colors, allowed ${limit.minItems}–${limit.maxItems}.`
  if (!('min' in limit)) return `${field.hint} Default: ${limit.default ? 'on' : 'off'}.`
  const [factor, unit] = [factorOf(field.key), unitOf(field.key)]
  return `${field.hint} Default ${limit.default / factor} ${unit}, allowed ${limit.min / factor}–${limit.max / factor} ${unit}.`
}
// Lists as a copy: the form must not change the values in effect before saving.
const formOf = (area: CollabArea): Record<string, FormValue> => Object.fromEntries(Object.entries(collabSettings[area]).map(([key, value]) => [key, typeof value === 'number' ? value / factorOf(key) : Array.isArray(value) ? [...value] : value]))

const form = reactive(Object.fromEntries(COLLAB_AREAS.map((area) => [area, formOf(area)])) as Record<CollabArea, Record<string, FormValue>>)
const loaded = ref(false)
const busy = ref<CollabArea | null>(null)
const open = reactive<Partial<Record<CollabArea, boolean>>>({})

const listOf = (area: CollabArea, key: string) => form[area][key] as string[]
const setColor = (area: CollabArea, key: string, at: number, event: Event) => (listOf(area, key)[at] = (event.target as HTMLInputElement).value)
const randomColor = () =>
  `#${Math.floor(Math.random() * 0x1000000)
    .toString(16)
    .padStart(6, '0')}`

/** Limits per number and color list, and the dependencies; switches, choices and a single color cannot hold anything wrong. */
const problemOf = (area: CollabArea, key: string): string | undefined => {
  const limit = limitOf(area, key)
  if ('minItems' in limit) {
    const colors = listOf(area, key).map((color) => color.toLowerCase())
    if (colors.length < limit.minItems || colors.length > limit.maxItems) return `Allowed are ${limit.minItems}–${limit.maxItems} colors.`
    if (new Set(colors).size < colors.length) return 'Each color only once.'
    if (colors.includes(String(form.colors.hostColor).toLowerCase())) return "The host's color must not be among them."
    return undefined
  }
  if (!('min' in limit)) return undefined
  const value = form[area][key]
  const factor = factorOf(key)
  const [min, max] = [limit.min / factor, limit.max / factor]
  if (typeof value !== 'number' || !Number.isInteger(value)) return 'Enter a whole number.'
  if (value < min || value > max) return `Allowed are ${min}–${max} ${unitOf(key)}.`
  const { visitorGraceSeconds: visitor, hostGraceSeconds: grace } = form.sharing
  if (area !== 'sharing' || typeof grace !== 'number') return undefined
  if (key === 'hostEndSeconds' && value < grace) return 'At least as long as until the room locks.'
  if (key === 'hostAwayMs' && value >= grace) return 'Shorter than until the room locks.'
  // If the sweep looks less often than someone may be away, the wait loses its effect.
  if (key === 'sweepSeconds' && typeof visitor === 'number' && value > Math.min(visitor, grace)) return 'At most as long as the shorter wait of a visitor or the host.'
  return undefined
}
/** Color distance in Lab (CIE76); the default colors are at least 18 apart, below 15 the tab warns without blocking saving. */
const labOf = (hex: string) => {
  const [red, green, blue] = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255).map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
  const [x, y, z] = [(0.4124 * red + 0.3576 * green + 0.1805 * blue) / 0.95047, 0.2126 * red + 0.7152 * green + 0.0722 * blue, (0.0193 * red + 0.1192 * green + 0.9505 * blue) / 1.08883].map((value) => (value > 0.008856 ? Math.cbrt(value) : 7.787 * value + 16 / 116))
  return [116 * y - 16, 500 * (x - y), 200 * (y - z)]
}
const warningOf = (area: CollabArea) => {
  if (area !== 'colors') return undefined
  const colors = [String(form.colors.hostColor), ...listOf('colors', 'palette')]
  const nameOf = (at: number) => (at === 0 ? 'The host' : `Color ${at}`)
  for (const [at, color] of colors.entries()) for (const [later, other] of colors.entries()) if (later > at && Math.hypot(...labOf(color).map((value, axis) => value - labOf(other)[axis])) < 15) return `${nameOf(at)} and ${nameOf(later).toLowerCase()} are hard to tell apart.`
  return undefined
}

/** Technical fields show when expanded, with an error that would otherwise block saving unseen, and when changed until saved. */
const shown = (area: CollabArea, field: Field) => !field.advanced || open[area] || Boolean(problemOf(area, field.key)) || form[area][field.key] !== formOf(area)[field.key]
const invalid = (section: Section) => section.fields.some((field) => problemOf(section.area, field.key))
const changed = (area: CollabArea) => JSON.stringify(form[area]) !== JSON.stringify(formOf(area))

const save = async (section: Section) => {
  busy.value = section.area
  try {
    // PUT replaces the whole area, so all its values always go along.
    const values = Object.fromEntries(Object.entries(form[section.area]).map(([key, value]) => [key, 'min' in limitOf(section.area, key) ? Number(value) * factorOf(key) : value]))
    applyCollabSettings(section.area, await props.ck.settings.set(section.area, values))
    form[section.area] = formOf(section.area)
    notifySuccess(`${section.title} saved.`)
  } catch (error) {
    notifyError(`${section.title} could not be saved: ${collabErrorMessage(error)}`)
  } finally {
    busy.value = null
  }
}

/** Deletes the area in collab-kit; without a document the defaults apply everywhere. */
const reset = async (section: Section) => {
  busy.value = section.area
  try {
    await props.ck.settings.remove(section.area)
    applyCollabSettings(section.area, {})
    form[section.area] = formOf(section.area)
    notifySuccess(`${section.title} reset to defaults.`)
  } catch (error) {
    notifyError(`${section.title} could not be reset: ${collabErrorMessage(error)}`)
  } finally {
    busy.value = null
  }
}

// Stored values outside the limits show as the default in the form, as that is what applies.
onMounted(async () => {
  const failed = (await Promise.allSettled(COLLAB_AREAS.map((area) => loadCollabSettings(props.ck, area)))).some((result) => result.status === 'rejected')
  if (failed) notifyError('The collab settings could not be loaded; the form shows the defaults.')
  for (const area of COLLAB_AREAS) form[area] = formOf(area)
  loaded.value = true
})
</script>

<style scoped>
.collab-settings {
  max-width: 880px;
}

.title {
  font-size: 15px;
  font-weight: 600;
}

.about {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.colors__label {
  margin-bottom: 4px;
  font-size: 13px;
}

.colors__hint {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* A color field: the native field at full size, number and remove on top of it. */
.swatch {
  position: relative;
  display: inline-flex;
  width: 40px;
  height: 32px;
}

.swatch input {
  width: 100%;
  height: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
}

.swatch input::-webkit-color-swatch-wrapper {
  padding: 0;
}

.swatch input::-webkit-color-swatch {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.2);
  border-radius: 6px;
}

.swatch__text {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.swatch__remove {
  position: absolute;
  top: -8px;
  right: -8px;
  display: none;
}

.swatch:hover .swatch__remove {
  display: inline-flex;
}

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px 24px;
}
</style>
