<template>
  <div class="collab-settings">
    <p class="about mb-3">These settings apply to every shared model and group room. A change reaches everyone connected at once, and the backend at its next look at the shares.</p>
    <div class="shell">
      <div class="shell__head">
        <v-icon icon="mdi-cog-outline" size="20" />
        <span class="shell__title">Collab settings</span>
        <v-chip v-if="unsavedCount" size="small" color="warning" variant="tonal">{{ unsavedCount }} unsaved</v-chip>
        <v-spacer />
        <v-btn variant="outlined" :disabled="!unsavedCount || busy !== null" @click="discard">Discard</v-btn>
        <v-btn color="primary" variant="flat" :disabled="!loaded || !unsavedCount || blocked || busy !== null" :loading="busy === 'all'" @click="saveAll">Save all</v-btn>
      </div>
      <div class="shell__tools">
        <v-text-field v-model="query" density="compact" variant="outlined" hide-details clearable prepend-inner-icon="mdi-magnify" placeholder="Search settings" aria-label="Search settings" class="search" :disabled="!loaded" />
        <v-btn-toggle v-model="filter" mandatory density="compact" variant="outlined" divided color="primary" aria-label="Filter settings">
          <v-btn value="all" size="small">All</v-btn>
          <v-btn value="changed" size="small">Changed</v-btn>
          <v-btn value="advanced" size="small">Advanced</v-btn>
        </v-btn-toggle>
      </div>
      <v-tabs v-model="tab" density="compact" color="primary" class="shell__tabs" @update:model-value="clearSearch">
        <v-tab v-for="group in GROUPS" :key="group.id" :value="group.id" :prepend-icon="group.icon">
          {{ group.title }}
          <span v-if="group.areas.some((area) => changed(area))" class="tab-dot" title="Unsaved changes" />
        </v-tab>
      </v-tabs>
      <div class="shell__body">
        <p v-if="searching && visible.length === 0" class="about">No settings match.</p>
        <div v-for="entry in visible" :key="entry.section.area" class="card">
          <h3 v-if="searching || entry.section.title !== entry.group.title" class="title">{{ searching && entry.section.title !== entry.group.title ? `${entry.group.title} · ${entry.section.title}` : entry.section.title }}</h3>
          <p v-if="!searching" class="about mb-2">{{ entry.section.about }}</p>
          <div v-for="field in entry.fields" :key="field.key" class="row" :class="{ 'row--wide': isWide(entry.section.area, field.key) }">
            <div class="row__text">
              <div class="row__label">
                <span v-if="fieldChanged(entry.section.area, field.key)" class="row__dot" title="Unsaved change" />
                {{ field.label }}
              </div>
              <div class="row__hint">{{ hintOf(entry.section.area, field) }}</div>
              <div v-if="problemOf(entry.section.area, field.key)" class="row__hint text-error">{{ problemOf(entry.section.area, field.key) }}</div>
              <div v-else-if="warningOf(entry.section.area) && isWide(entry.section.area, field.key)" class="row__hint text-warning">{{ warningOf(entry.section.area) }}</div>
            </div>
            <div class="row__control">
              <v-select v-if="field.items" v-model="form[entry.section.area][field.key]" :items="field.items" item-title="title" item-value="value" density="compact" variant="outlined" hide-details :disabled="!loaded" :aria-label="field.label" />
              <v-switch v-else-if="typeof limitOf(entry.section.area, field.key).default === 'boolean'" v-model="form[entry.section.area][field.key]" color="primary" density="compact" inset hide-details :disabled="!loaded" :aria-label="field.label" />
              <span v-else-if="'color' in limitOf(entry.section.area, field.key)" class="swatch" :style="{ color: textOn(String(form[entry.section.area][field.key])) }">
                <input v-model="form[entry.section.area][field.key]" type="color" :disabled="!loaded" :aria-label="field.label" />
                <span class="swatch__text">H</span>
              </span>
              <div v-else-if="isWide(entry.section.area, field.key)" class="d-flex flex-wrap align-center ga-1">
                <span v-for="(color, at) in listOf(entry.section.area, field.key)" :key="at" class="swatch" :style="{ color: textOn(color) }">
                  <input :value="color" type="color" :disabled="!loaded" :aria-label="`${field.label} ${at + 1}`" @input="setColor(entry.section.area, field.key, at, $event)" />
                  <span class="swatch__text">{{ at + 1 }}</span>
                  <v-btn icon="mdi-close" size="x-small" density="compact" variant="flat" class="swatch__remove" :disabled="!loaded" :aria-label="`Remove color ${at + 1}`" @click="listOf(entry.section.area, field.key).splice(at, 1)" />
                </span>
                <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" class="ml-2" :disabled="!loaded" @click="listOf(entry.section.area, field.key).push(randomColor())">Add color</v-btn>
              </div>
              <v-text-field v-else v-model.number="form[entry.section.area][field.key]" type="number" :suffix="unitOf(field.key)" density="compact" variant="outlined" hide-details :error="Boolean(problemOf(entry.section.area, field.key))" :disabled="!loaded" :aria-label="field.label" />
            </div>
            <div class="row__reset">
              <v-btn v-if="nonDefault(entry.section.area, field.key)" icon="mdi-restore" size="x-small" density="comfortable" variant="text" :disabled="!loaded" :aria-label="`Reset ${field.label} to the default`" title="Reset to the default" @click="resetField(entry.section.area, field.key)" />
            </div>
          </div>
          <div v-if="!searching" class="d-flex align-center ga-2 mt-2">
            <v-btn v-if="entry.section.fields.some((field) => field.advanced)" variant="text" size="small" :append-icon="open[entry.section.area] ? 'mdi-chevron-up' : 'mdi-chevron-down'" @click="open[entry.section.area] = !open[entry.section.area]">Advanced ({{ entry.section.fields.filter((field) => field.advanced).length }})</v-btn>
            <v-spacer />
            <v-btn variant="text" size="small" :disabled="!loaded || busy !== null" :loading="busy === entry.section.area" @click="reset(entry.section)">Reset to defaults</v-btn>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { collabErrorMessage } from '@/collab/kit/collabKit'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'
import { applyCollabSettings, COLLAB_AREAS, COLLAB_LIMITS, collabSettings, loadCollabSettings, type CollabArea, type CollabLimit } from '@/collab/settings/collabSettings'
import { historyChoices } from '@/collab/sharing/shareChoices'
import { labOf, textOn } from '@/collab/settings/colorMath'

const props = defineProps<{ ck: CollabKitApi }>()

/** A field in the tab; with items a choice, otherwise by its default a switch or a number in seconds, with unit in ms or days. Technical ones are under "Advanced". */
interface Field {
  readonly key: string
  readonly label: string
  readonly hint: string
  readonly items?: readonly { readonly value: string; readonly title: string }[]
  readonly unit?: 'ms' | 'days' | 'px' | 'people' | 'tries' | 'requests' | 'items'
  readonly advanced?: boolean
}

interface Section {
  readonly area: CollabArea
  readonly title: string
  readonly about: string
  readonly fields: readonly Field[]
}

/** A panel of the tab: one or more areas of collab-kit that belong together. */
interface Group {
  readonly id: string
  readonly title: string
  readonly icon: string
  readonly areas: readonly CollabArea[]
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
      { key: 'followMs', label: 'Visitors fetch the room history every', hint: 'What a visitor takes along on leaving is at most this old.', advanced: true },
      { key: 'tabCheckMs', label: 'Other-tab check waits', hint: 'How long a new tab waits for an answer of another tab of this browser before it counts as the only one.', unit: 'ms', advanced: true },
      { key: 'roomPollMs', label: 'Room write check every', hint: 'How often collab-kit is asked whether it holds what was written, while the history goes into a room.', unit: 'ms', advanced: true },
      { key: 'roomWaitMs', label: 'Room write waits at most', hint: 'After this the write counts as failed.', advanced: true },
      { key: 'checkpointAttempts', label: 'Checkpoint tries', hint: 'How often a save asks whether collab-kit holds the own changes before it marks the checkpoint.', unit: 'tries', advanced: true },
      { key: 'checkpointPauseMs', label: 'Checkpoint pause between tries', hint: 'Together with the tries it makes how long a save waits for collab-kit.', unit: 'ms', advanced: true },
      { key: 'apiBatch', label: 'Requests at once', hint: 'Versions or changes read or written at once when sharing; higher is faster and loads the API more.', unit: 'requests', advanced: true },
      { key: 'apiPage', label: 'API page size', hint: 'How many models or versions are listed per request.', unit: 'items', advanced: true }
    ]
  },
  {
    area: 'presence',
    title: 'Presence',
    about: 'Applies to everyone working on a model together, shared or in a group room.',
    fields: [
      { key: 'idleMs', label: 'Idle until the selection is released', hint: 'With the selection go the locks on its elements.' },
      { key: 'marksShown', label: 'People shown on an element', hint: 'Others who selected the same element show as marks at its top left; the rest as "+n".', unit: 'people' },
      { key: 'cursorSendMs', label: 'Cursor sent at most every', hint: 'Shorter moves pointers more smoothly and sends more.', unit: 'ms', advanced: true },
      { key: 'lockHintMs', label: 'Locked-element notice at most every', hint: 'How often someone who tries to change a locked element is told who holds it.', advanced: true },
      { key: 'idleCheckMs', label: 'Idle check every', hint: 'How often a client looks whether it was idle long enough. Takes effect when a model is opened.', advanced: true },
      { key: 'authorMarkSize', label: 'Size of the author dot', hint: 'The dot that shows who made an element; it scales with the zoom.', unit: 'px', advanced: true },
      { key: 'authorMarkWaitMs', label: 'Author dots wait after a change', hint: 'Until collab-kit has stored the change, so several are read together.', unit: 'ms', advanced: true }
    ]
  },
  {
    area: 'shareDefaults',
    title: 'Share defaults',
    about: 'What the dialog has chosen when someone shares a model. The host can still change it there for each share.',
    fields: [
      { key: 'anonymous', label: 'Anonymous', hint: 'Others see a pseudonym instead of the name.' },
      { key: 'edit', label: 'May edit', hint: 'Visitors change the model together with the host.' },
      { key: 'task', label: 'Share the task', hint: 'A model with a task takes the task along.' },
      { key: 'history', label: 'Share history', hint: 'How much of the private history goes into the shared model.', items: historyChoices }
    ]
  },
  {
    area: 'colors',
    title: 'Colors',
    about: 'The colors of people in a shared model or group room: cursor, selection, locks and the marks of who made what. Everyone sees the same colors; a change reaches open models at once. The status colors are under Advanced.',
    fields: [
      { key: 'hostColor', label: 'Host', hint: 'Only the host wears it, so keep it apart from the colors of the others.' },
      { key: 'palette', label: 'Everyone else', hint: 'Handed out in this order, so the first ones should differ the most.' },
      { key: 'barColor', label: 'Bar while sharing', hint: 'The frame and the bar of a shared model; the presenter frame takes the color of the host.', advanced: true },
      { key: 'barAwayColor', label: 'Bar while the host is away', hint: 'The same bar, as long as the host is disconnected.', advanced: true },
      { key: 'conflictColor', label: 'Overwritten change', hint: 'The frame around your change that someone else overwrote.', advanced: true },
      { key: 'someoneColor', label: 'Someone unknown', hint: 'Changes that belong to no known person, in the event log and as frame.', advanced: true }
    ]
  },
  {
    area: 'log',
    title: 'Event log',
    about: 'How the event log in the sidebar of a shared model or group room groups and times its entries.',
    fields: [
      { key: 'mergeMs', label: 'Changes of one person merge for', hint: 'Changes of the same person within this time make one entry.' },
      { key: 'leaveMs', label: 'Away until "left" shows', hint: 'Background tabs report only about once a minute, so keep it above that.' },
      { key: 'releaseNoticeMs', label: 'Release notice stays', hint: 'How long the bar above the model shows a release by someone else.' },
      { key: 'settleMs', label: 'Settling after connecting', hint: 'People already there when you connect do not count as joined during this time.', advanced: true },
      { key: 'refreshMs', label: 'Relative times renewed every', hint: 'How often "2 min ago" updates while the log is shown. Takes effect when the log opens.', advanced: true }
    ]
  },
  {
    area: 'hints',
    title: 'Notices',
    about: 'How long short notices and frames stay.',
    fields: [
      { key: 'conflictFrameMs', label: 'Overwritten change framed for', hint: 'The frame around your change that someone else overwrote.' },
      { key: 'copiedMs', label: 'Link shows as copied for', hint: 'How long the share link says it was copied.', unit: 'ms' },
      { key: 'importDelayMs', label: 'Group import checks after', hint: 'How long the import waits for quiet before it checks the input.', unit: 'ms', advanced: true }
    ]
  },
  {
    area: 'archive',
    title: 'Archive',
    about: 'Archived workpieces, rooms and groups can be restored or deleted for good. Turned off, the Archive tab is hidden, but collab-kit still offers to archive rooms, groups and workpieces.',
    fields: [
      { key: 'enabled', label: 'Archive', hint: 'Shows the Archive tab here.' },
      { key: 'archiveOnShareClose', label: 'Archive ended shares', hint: 'The model and the task of a share go to the archive when the host ends it, instead of staying in collab-kit without a room. Only while the archive is on.' },
      { key: 'archiveUnusedAfterDays', label: 'Archive unused shared models after', hint: 'Models and tasks of ended shares that lie in no room and nobody has used for so long; the backend looks once a day at 03:00 UTC. 0 never archives. Only while the archive is on.', unit: 'days' }
    ]
  }
]

const GROUPS: readonly Group[] = [
  { id: 'sharing', title: 'Sharing', icon: 'mdi-share-variant', areas: ['sharing', 'shareDefaults'] },
  { id: 'people', title: 'People', icon: 'mdi-account-group', areas: ['presence', 'colors'] },
  { id: 'activity', title: 'Activity and hints', icon: 'mdi-bell-outline', areas: ['log', 'hints'] },
  { id: 'archive', title: 'Archive', icon: 'mdi-archive-outline', areas: ['archive'] }
]
const sectionsOf = (group: Group) => SECTIONS.filter((section) => group.areas.includes(section.area))

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
const busy = ref<CollabArea | 'all' | null>(null)
const open = reactive<Partial<Record<CollabArea, boolean>>>({})
const tab = ref('sharing')
const query = ref<string | null>('')
const filter = ref<'all' | 'changed' | 'advanced'>('all')

/** A color list is too wide for the column of values; it gets a line of its own. */
const isWide = (area: CollabArea, key: string) => 'minItems' in limitOf(area, key)
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
  if (area === 'presence' && key === 'idleCheckMs' && typeof form.presence.idleMs === 'number' && value > form.presence.idleMs) return 'At most as long as until the selection is released.'
  if (area !== 'sharing' || typeof grace !== 'number') return undefined
  if (key === 'hostEndSeconds' && value < grace) return 'At least as long as until the room locks.'
  if (key === 'hostAwayMs' && value >= grace) return 'Shorter than until the room locks.'
  // If the sweep looks less often than someone may be away, the wait loses its effect.
  if (key === 'sweepSeconds' && typeof visitor === 'number' && value > Math.min(visitor, grace)) return 'At most as long as the shorter wait of a visitor or the host.'
  return undefined
}
/** Color distance in Lab (CIE76); the default colors are at least 18 apart, below 15 the tab warns without blocking saving. */
const warningOf = (area: CollabArea) => {
  if (area !== 'colors') return undefined
  const colors = [String(form.colors.hostColor), ...listOf('colors', 'palette')]
  const nameOf = (at: number) => (at === 0 ? 'The host' : `Color ${at}`)
  for (const [at, color] of colors.entries()) for (const [later, other] of colors.entries()) if (later > at && Math.hypot(...labOf(color).map((value, axis) => value - labOf(other)[axis])) < 15) return `${nameOf(at)} and ${nameOf(later).toLowerCase()} are hard to tell apart.`
  return undefined
}

/** The values in effect as the form shows them, to tell what is not saved yet. */
const saved = computed(() => Object.fromEntries(COLLAB_AREAS.map((area) => [area, formOf(area)])) as Record<CollabArea, Record<string, FormValue>>)
const fieldChanged = (area: CollabArea, key: string) => JSON.stringify(form[area][key]) !== JSON.stringify(saved.value[area][key])
const changed = (area: CollabArea) => JSON.stringify(form[area]) !== JSON.stringify(saved.value[area])
const defaultOf = (area: CollabArea, key: string) => {
  const { default: value } = limitOf(area, key)
  return (typeof value === 'number' ? value / factorOf(key) : Array.isArray(value) ? [...value] : value) as FormValue
}
const nonDefault = (area: CollabArea, key: string) => JSON.stringify(form[area][key]) !== JSON.stringify(defaultOf(area, key))
const resetField = (area: CollabArea, key: string) => (form[area][key] = defaultOf(area, key))
const invalid = (section: Section) => section.fields.some((field) => problemOf(section.area, field.key))

/** Technical fields show when expanded, with an error that would otherwise block saving unseen, and when changed until saved. */
const shown = (area: CollabArea, field: Field) => !field.advanced || open[area] || Boolean(problemOf(area, field.key)) || fieldChanged(area, field.key)

/** With a search or a filter the tab lists the matching fields of all areas, else the sections of the open tab. */
const searching = computed(() => Boolean(query.value?.trim()) || filter.value !== 'all')
const matches = (section: Section, field: Field) => {
  const text = query.value?.trim().toLowerCase()
  return !text || [field.label, field.hint, field.key, section.title].some((part) => part.toLowerCase().includes(text))
}
const passes = (area: CollabArea, field: Field) => filter.value === 'all' || (filter.value === 'advanced' ? Boolean(field.advanced) : nonDefault(area, field.key) || fieldChanged(area, field.key))
const visible = computed(() => {
  const groupOf = (area: CollabArea) => GROUPS.find((group) => group.areas.includes(area)) as Group
  if (searching.value) return SECTIONS.map((section) => ({ section, group: groupOf(section.area), fields: section.fields.filter((field) => matches(section, field) && passes(section.area, field)) })).filter((entry) => entry.fields.length > 0)
  const group = GROUPS.find((entry) => entry.id === tab.value) as Group
  return sectionsOf(group).map((section) => ({ section, group, fields: section.fields.filter((field) => shown(section.area, field)) }))
})
const clearSearch = () => {
  query.value = ''
  filter.value = 'all'
}

const unsavedCount = computed(() => SECTIONS.reduce((sum, section) => sum + section.fields.filter((field) => fieldChanged(section.area, field.key)).length, 0))
/** Saving stops while a changed area holds an error. */
const blocked = computed(() => SECTIONS.some((section) => changed(section.area) && invalid(section)))
const discard = () => {
  for (const area of COLLAB_AREAS) form[area] = formOf(area)
}

const saveArea = async (area: CollabArea) => {
  // PUT replaces the whole area, so all its values always go along.
  const values = Object.fromEntries(Object.entries(form[area]).map(([key, value]) => [key, 'min' in limitOf(area, key) ? Number(value) * factorOf(key) : value]))
  applyCollabSettings(area, await props.ck.settings.set(area, values))
  form[area] = formOf(area)
}

/** Saves every changed area one after the other; one that fails does not stop the others. */
const saveAll = async () => {
  busy.value = 'all'
  const failed: string[] = []
  for (const section of SECTIONS) {
    if (!changed(section.area)) continue
    try {
      await saveArea(section.area)
    } catch (error) {
      failed.push(`${section.title}: ${collabErrorMessage(error)}`)
    }
  }
  busy.value = null
  if (failed.length) notifyError(`Could not be saved: ${failed.join('; ')}`)
  else notifySuccess('Settings saved.')
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
  max-width: 920px;
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

/* The frame: head with the actions, search, tabs and the sections as cards. */
.shell {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 12px;
}

.shell__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
}

.shell__title {
  font-size: 16px;
  font-weight: 600;
}

.shell__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 0 16px 10px;
}

.search {
  min-width: 200px;
  max-width: 320px;
}

.shell__tabs {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.shell__body {
  padding: 16px;
}

.card {
  padding: 12px 14px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
}

.card + .card {
  margin-top: 12px;
}

.tab-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-left: 6px;
  border-radius: 50%;
  background: rgb(var(--v-theme-warning));
}

/* A setting: name and explanation on the left, the value on the right, the reset arrow when it differs from the default. */
.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px 32px;
  gap: 4px 12px;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12);
}

.row__label {
  font-size: 14px;
  font-weight: 500;
}

.row__dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 6px;
  vertical-align: middle;
  border-radius: 50%;
  background: rgb(var(--v-theme-warning));
}

.row__hint {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.row__control {
  display: flex;
  justify-content: flex-end;
}

.row__control :deep(.v-input) {
  width: 100%;
}

.row__control :deep(.v-selection-control) {
  justify-content: flex-end;
}

.row__reset {
  display: flex;
  justify-content: center;
}

.row--wide {
  grid-template-columns: minmax(0, 1fr) 32px;
}

.row--wide .row__control {
  grid-row: 2;
  grid-column: 1 / -1;
  justify-content: flex-start;
}

.row--wide .row__reset {
  grid-row: 1;
  grid-column: 2;
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
</style>
