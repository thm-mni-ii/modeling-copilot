<template>
  <div class="collab-settings">
    <p class="about mb-3">These settings apply to every shared model and group room. A change reaches everyone connected at once, and the backend at its next look at the shares.</p>
    <div class="shell">
      <div class="shell__head">
        <v-icon icon="mdi-cog-outline" size="20" />
        <span class="shell__title">Collab settings</span>
        <v-chip v-if="unsavedCount" size="small" color="warning" variant="tonal">{{ unsavedCount }} unsaved</v-chip>
        <v-spacer />
        <v-btn-toggle v-model="filter" mandatory variant="outlined" divided color="primary" aria-label="Filter settings">
          <v-btn value="all">All</v-btn>
          <v-btn value="changed">Changed</v-btn>
        </v-btn-toggle>
        <v-btn variant="outlined" :disabled="!unsavedCount || busy !== null" @click="discard">Discard</v-btn>
        <v-btn color="primary" variant="flat" :disabled="!loaded || !unsavedCount || blocked || busy !== null" :loading="busy === 'all'" @click="saveAll">Save all</v-btn>
      </div>
      <v-tabs v-model="tab" density="compact" color="primary" class="shell__tabs">
        <v-tab v-for="group in GROUPS" :key="group.id" :value="group.id" :prepend-icon="group.icon">
          {{ group.title }}
          <span v-if="group.areas.some((area) => changed(area))" class="tab-dot" title="Unsaved changes" />
        </v-tab>
      </v-tabs>
      <div class="shell__body">
        <p v-if="filtering && visible.length === 0" class="about">No settings match.</p>
        <div v-for="entry in visible" :key="entry.section.area" class="card">
          <h3 v-if="filtering || entry.section.title !== entry.group.title" class="title">{{ filtering && entry.section.title !== entry.group.title ? `${entry.group.title} · ${entry.section.title}` : entry.section.title }}</h3>
          <div v-if="!filtering" class="callout callout--about">
            <span>{{ entry.section.about }}</span>
          </div>
          <div class="card__body" :class="{ 'card__body--split': !filtering && entry.section.area === 'shareDefaults' }">
            <div v-if="!filtering && entry.section.area === 'sharing'" class="sharing-wrap">
              <div class="sharing-top">
                <SharingTimeline :values="form.sharing" :resettable="WAIT_KEYS.some((key) => nonDefault('sharing', key))" @update="(key, seconds) => (form.sharing[key] = seconds)" @reset="WAIT_KEYS.forEach((key) => resetField('sharing', key))" />
                <SharingExplainer :values="form.sharing">
                  <template #field="{ fieldKey }">
                    <div class="stepfield">
                      <div class="stepfield__cap">
                        <span v-if="fieldChanged('sharing', fieldKey)" class="row__dot" title="Unsaved change" />
                        {{ labelOfKey('sharing', fieldKey) }}
                      </div>
                      <div class="stepfield__row">
                        <NumberControl v-model="form.sharing[fieldKey]" :label="labelOfKey('sharing', fieldKey)" :suffix="unitWordOf(fieldKey)" :sub="subOf('sharing', fieldKey)" :default-at="barAt('sharing', fieldKey, defaultOf('sharing', fieldKey))" :value-at="barAt('sharing', fieldKey, form.sharing[fieldKey])" :error="Boolean(problemOf('sharing', fieldKey))" :disabled="!loaded" />
                        <v-btn v-if="nonDefault('sharing', fieldKey)" icon="mdi-restore" size="x-small" density="comfortable" variant="text" :disabled="!loaded" :aria-label="`Reset ${labelOfKey('sharing', fieldKey)} to the default`" title="Reset to the default" @click="resetField('sharing', fieldKey)" />
                      </div>
                      <div v-if="problemOf('sharing', fieldKey)" class="stepfield__error">{{ problemOf('sharing', fieldKey) }}</div>
                    </div>
                  </template>
                </SharingExplainer>
              </div>
            </div>
            <PaletteEditor v-if="!filtering && entry.section.area === 'colors'" :colors="form.colors" :problem="problemOf('colors', 'palette')" :changed="(key) => fieldChanged('colors', key)" @update="(key, value) => (form.colors[key] = value)" />
            <PresenceCanvas v-if="!filtering && entry.section.area === 'presence'" class="mb-3" :presence="form.presence" :colors="form.colors" :changed="fieldChanged" :problem="problemOf" @update="(area, key, value) => (form[area][key] = value)" />
            <ActivityCanvas v-if="!filtering && (entry.section.area === 'log' || entry.section.area === 'hints')" :area="entry.section.area" class="mb-3" :values="form[entry.section.area]" :colors="form.colors" :changed="fieldChanged" :problem="problemOf" @update="(key, value) => (form[entry.section.area][key] = value)" />
            <ArchiveCanvas v-if="!filtering && entry.section.area === 'archive'" class="mb-3" :values="form.archive" :changed="(key) => fieldChanged('archive', key)" :problem="(key) => problemOf('archive', key)" @update="(key, value) => (form.archive[key] = value)" />
            <ShareDefaultsPreview v-if="!filtering && entry.section.area === 'shareDefaults'" :values="form.shareDefaults" :resettable="SHARE_KEYS.some((key) => nonDefault('shareDefaults', key))" @update="(key, value) => (form.shareDefaults[key] = value)" @reset="SHARE_KEYS.forEach((key) => resetField('shareDefaults', key))" />
            <div class="card__parts">
              <div v-for="part in partsOf(entry)" :key="String(part.advanced)" :class="part.advanced ? 'advanced' : 'part'">
                <div v-if="part.advanced" class="advanced__head">
                  <v-icon icon="mdi-wrench-outline" size="16" />
                  Advanced
                  <span>Technical settings. The defaults fit almost every case; change them only if you know why.</span>
                </div>
                <div :class="{ agroups: part.blocks.some((block) => block.name) }">
                  <div v-for="block in part.blocks" :key="block.name" :class="block.name ? ['agroup', `agroup--${groupInfoOf(block.name).tone}`] : []">
                    <div v-if="block.name" class="agroup__head">
                      <v-icon :icon="groupInfoOf(block.name).icon" class="agroup__icon" />
                      <div class="agroup__text">
                        <div class="agroup__title">
                          <b>{{ block.name }}</b>
                          <span class="agroup__chip">{{ effectOf(block.name) }}</span>
                        </div>
                        <div class="callout callout--small">
                          <v-icon icon="mdi-information-outline" size="16" />
                          <span>{{ groupInfoOf(block.name).about }}</span>
                        </div>
                      </div>
                    </div>
                    <div :class="{ agroup__body: block.name }">
                      <div :class="block.name ? 'agroup__rows' : 'rows'">
                        <div v-for="field in block.fields" :key="field.key" class="row" :class="{ 'row--wide': isWide(entry.section.area, field.key) }">
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
                            <NumberControl
                              v-else
                              v-model="form[entry.section.area][field.key]"
                              :label="field.label"
                              :suffix="unitWordOf(field.key)"
                              :sub="subOf(entry.section.area, field.key)"
                              :default-at="barAt(entry.section.area, field.key, defaultOf(entry.section.area, field.key))"
                              :value-at="barAt(entry.section.area, field.key, form[entry.section.area][field.key])"
                              :error="Boolean(problemOf(entry.section.area, field.key))"
                              :disabled="!loaded"
                            />
                          </div>
                          <div class="row__reset">
                            <v-btn v-if="nonDefault(entry.section.area, field.key)" icon="mdi-restore" size="x-small" density="comfortable" variant="text" :disabled="!loaded" :aria-label="`Reset ${field.label} to the default`" title="Reset to the default" @click="resetField(entry.section.area, field.key)" />
                          </div>
                        </div>
                      </div>
                      <div v-if="block.name === 'Who is away' || block.name === 'Saving to collab-kit'" class="agroup__diagram">
                        <SweepDiagram v-if="block.name === 'Who is away'" :seconds="numberOf('sweepSeconds')" />
                        <TriesDiagram v-else :tries="numberOf('checkpointAttempts')" :pause-ms="numberOf('checkpointPauseMs')" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!filtering" class="d-flex align-center ga-2 mt-2">
            <template v-if="advancedOf(entry.section).length > 0">
              <v-btn variant="tonal" color="info" prepend-icon="mdi-wrench-outline" :append-icon="open[entry.section.area] ? 'mdi-chevron-up' : 'mdi-chevron-down'" @click="open[entry.section.area] = !open[entry.section.area]">
                Advanced settings
                <span class="advanced-toggle__count">{{ advancedOf(entry.section).length }}</span>
              </v-btn>
              <span class="advanced-note">
                Technical settings
                <span v-if="advancedChanged(entry.section) > 0" class="advanced-note__badge">{{ advancedChanged(entry.section) }} changed</span>
              </span>
            </template>
            <v-spacer />
            <v-btn variant="outlined" size="small" prepend-icon="mdi-restore" :disabled="!loaded || busy !== null" :loading="busy === entry.section.area" @click="reset(entry.section)">Reset to defaults</v-btn>
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
import ActivityCanvas from '@/collab/settings/ActivityCanvas.vue'
import ArchiveCanvas from '@/collab/settings/ArchiveCanvas.vue'
import PaletteEditor from '@/collab/settings/PaletteEditor.vue'
import PresenceCanvas from '@/collab/settings/PresenceCanvas.vue'
import ShareDefaultsPreview from '@/collab/settings/ShareDefaultsPreview.vue'
import NumberControl from '@/collab/settings/NumberControl.vue'
import SharingExplainer from '@/collab/settings/SharingExplainer.vue'
import SharingTimeline from '@/collab/settings/SharingTimeline.vue'
import SweepDiagram from '@/collab/settings/SweepDiagram.vue'
import TriesDiagram from '@/collab/settings/TriesDiagram.vue'

const props = defineProps<{ ck: CollabKitApi }>()

/** A field in the tab; with items a choice, otherwise by its default a switch or a number in seconds, with unit in ms or days. Technical ones are under "Advanced". */
interface Field {
  readonly key: string
  readonly label: string
  readonly hint: string
  readonly items?: readonly { readonly value: string; readonly title: string }[]
  readonly unit?: 'ms' | 'days' | 'px' | 'people' | 'tries' | 'requests' | 'items'
  readonly advanced?: boolean
  /** Technical fields are listed in groups under "Advanced"; the first field of a group shows its name. */
  readonly group?: string
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

/** What the tab shows of an area: its fields as they pass the filter, or the ones that are not hidden under Advanced. */
interface Entry {
  readonly section: Section
  readonly group: Group
  readonly fields: readonly Field[]
}

type FormValue = number | string | boolean | string[]

/** One section per area in collab-kit; limits and defaults are in collabSettings.ts. */
const SECTIONS: readonly Section[] = [
  {
    area: 'sharing',
    title: 'Sharing',
    about: 'The host is the person who shares their model. This decides what happens when the host or a visitor of a shared model loses the connection: when visitors are told, when the room locks and when people are removed.',
    fields: [
      { key: 'visitorGraceSeconds', label: 'Visitor away until they leave', hint: 'The visitor leaves the room, and their working copy is deleted.' },
      { key: 'hostGraceSeconds', label: 'Host away until the room locks', hint: 'Nobody can edit or join until the host is back.' },
      { key: 'hostEndSeconds', label: 'Host away until all visitors leave', hint: 'The model stays for the host.' },
      { key: 'hostAwayMs', label: 'Host away until visitors are told', hint: 'Visitors see "The host is disconnected."' },
      { key: 'sweepSeconds', label: 'Look for absent people every', hint: 'Shorter: more exact timing, more load. Longer: less load, but locking and removing can come later, by up to this time.', advanced: true, group: 'Who is away' },
      { key: 'followMs', label: 'Visitors copy the room history every', hint: 'Visitors regularly copy what happened in the room. When they leave they take this copy along, so it is at most this old.', advanced: true, group: 'Who is away' },
      { key: 'roomPollMs', label: 'Ask whether data arrived every', hint: 'How often the Copilot asks while a history is written. Shorter: faster, more requests.', unit: 'ms', advanced: true, group: 'Saving to collab-kit' },
      { key: 'roomWaitMs', label: 'Give up after', hint: 'After this time the write counts as failed. Longer: more patience on a slow connection.', advanced: true, group: 'Saving to collab-kit' },
      { key: 'checkpointAttempts', label: 'Asks before a checkpoint', hint: 'Before a checkpoint is saved, the Copilot asks up to this many times whether collab-kit already holds your latest changes.', unit: 'tries', advanced: true, group: 'Saving to collab-kit' },
      { key: 'checkpointPauseMs', label: 'Pause between asks', hint: 'Asks times pause is the longest a save waits.', unit: 'ms', advanced: true, group: 'Saving to collab-kit' },
      { key: 'apiBatch', label: 'Parallel requests', hint: 'Versions or changes loaded or written at the same time while sharing. More: faster, but the server is loaded more.', unit: 'requests', advanced: true, group: 'Load on the server' },
      { key: 'apiPage', label: 'Entries per request', hint: 'How many models or versions one request brings back. More: fewer requests, bigger answers.', unit: 'items', advanced: true, group: 'Load on the server' },
      { key: 'tabCheckMs', label: 'Wait for other tabs', hint: 'A new tab asks the other tabs of this browser whether the model is already open, and waits this long for an answer. Longer: safer on slow computers, but opening takes longer.', unit: 'ms', advanced: true, group: 'Several tabs' }
    ]
  },
  {
    area: 'presence',
    title: 'Presence',
    about: 'How people see each other while they work on a model together: shared with a link or in a group room.',
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
      { key: 'task', label: 'Share the task', hint: 'A model with a task takes the task along. The dialog has no switch for it.' },
      { key: 'history', label: 'Share history', hint: 'How much of the private history goes into the shared model.', items: historyChoices }
    ]
  },
  {
    area: 'colors',
    title: 'Colors',
    about: 'Every person in a model gets a color, so others can see who is who: pointer, selection, lock and the dots that show who made what. Everyone sees the same colors, and changes apply in open models right away.',
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
    about: 'Archived workpieces, rooms and groups can be restored or deleted for good. Turned off, there is no archive: no tab, no buttons to archive, and nothing is archived by itself. The collab-kit server must allow it too (ARCHIVE_ENABLED=true).',
    fields: [
      { key: 'enabled', label: 'Use the archive', hint: 'Shows the Archive tab and the buttons to archive, and lets ended shares be archived. collab-kit also needs ARCHIVE_ENABLED=true on the server.' },
      { key: 'archiveOnShareClose', label: 'Archive ended shares', hint: 'The model and the task of a share go to the archive when the host ends it, instead of staying in collab-kit without a room. Only while the archive is on.' },
      { key: 'allowDelete', label: 'Delete for good', hint: 'The Archive tab offers deleting archived items for good, after a confirmation. collab-kit also needs ARCHIVE_DELETE=true on the server. Only while the archive is on.' },
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
const UNIT_WORDS: Record<string, string> = { s: 'seconds', ms: 'milliseconds', days: 'days', px: 'pixels', people: 'people', tries: 'tries', requests: 'requests', items: 'items' }
/** The unit as a word in the field, as "s" alone says little. */
const unitWordOf = (key: string) => UNIT_WORDS[unitOf(key)] ?? unitOf(key)
const factorOf = (key: string) => (key.endsWith('Ms') && !UNITS.has(key) ? 1000 : 1)
const limitOf = (area: CollabArea, key: string) => (COLLAB_LIMITS[area] as Record<string, CollabLimit>)[key]
/** A value in the unit of its field, in short words: "2 min", "1.5 s", "50 ms". */
const plain = (key: string, value: number) => {
  const unit = unitOf(key)
  if (unit === 's') return value >= 3600 && value % 3600 === 0 ? `${value / 3600} h` : value >= 60 && value % 60 === 0 ? `${value / 60} min` : `${value} s`
  if (unit === 'ms') return value >= 1000 && value % 1000 === 0 ? `${value / 1000} s` : `${value} ms`
  return `${value} ${unit}`
}
/** What a long value comes to in bigger units, such as 135 seconds as "2 min 15 s"; nothing for a short one. */
const humanOf = (key: string, value: number) => {
  const unit = unitOf(key)
  if (unit === 'ms' && value >= 1000) return `${Math.round(value / 100) / 10} s`
  if (unit !== 's' || value < 60) return ''
  const [hours, minutes, seconds] = [Math.floor(value / 3600), Math.floor((value % 3600) / 60), value % 60]
  return [hours && `${hours} h`, minutes && `${minutes} min`, seconds && `${seconds} s`].filter(Boolean).join(' ')
}
const hintOf = (area: CollabArea, field: Field) => {
  const limit = limitOf(area, field.key)
  if ('options' in limit) return `${field.hint} Default: ${field.items?.find((item) => item.value === limit.default)?.title ?? limit.default}.`
  if ('color' in limit) return `${field.hint} Default ${limit.default}.`
  if ('minItems' in limit) return `${field.hint} Default ${limit.default.length} colors, allowed ${limit.minItems}–${limit.maxItems}.`
  if (!('min' in limit)) return `${field.hint} Default: ${limit.default ? 'on' : 'off'}.`
  return `${field.hint} Default ${plain(field.key, limit.default / factorOf(field.key))}.`
}
/** The allowed range in words; a count names its unit once, a time in each end. */
const rangeOf = (key: string, low: number, high: number) => (['s', 'ms'].includes(unitOf(key)) ? `Range: ${plain(key, low)} to ${plain(key, high)}` : `Range: ${low} to ${high} ${unitOf(key)}`)
/** Under a number field: what the value comes to in bigger units, and the range that is allowed. */
const subOf = (area: CollabArea, key: string) => {
  const limit = limitOf(area, key)
  if (!('min' in limit)) return ''
  const factor = factorOf(key)
  const value = form[area][key]
  const human = typeof value === 'number' && Number.isFinite(value) ? humanOf(key, value) : ''
  return [human && `= ${human}`, rangeOf(key, limit.min / factor, limit.max / factor)].filter(Boolean).join(' · ')
}
/** Where a value lies in the allowed range, in percent; a wide range is drawn in a log scale, so small values stay visible. */
const barAt = (area: CollabArea, key: string, value: FormValue) => {
  const limit = limitOf(area, key)
  if (!('min' in limit)) return '0%'
  const [low, high] = [limit.min / factorOf(key), limit.max / factorOf(key)]
  const clamped = Math.min(Math.max(Number(value) || low, low), high)
  const share = low > 0 && high / low > 20 ? Math.log(clamped / low) / Math.log(high / low) : (clamped - low) / (high - low)
  return `${Math.round(share * 100)}%`
}
const numberOf = (key: string) => Number(form.sharing[key]) || 0

/** The technical groups: what they are for, how they look, and what the current values come to. */
const GROUP_INFO: Record<string, { icon: string; tone: 'info' | 'warning' | 'success' | 'neutral'; about: string }> = {
  'Who is away': { icon: 'mdi-timer-outline', tone: 'info', about: 'The backend does not watch all the time. It looks at regular intervals who is away, and only then locks the room or removes people. So the waiting times above are not exact to the second.' },
  'Saving to collab-kit': { icon: 'mdi-repeat', tone: 'warning', about: 'Collab-kit stores changes with a delay. After writing, the Copilot asks repeatedly whether the data has arrived, and gives up after a while.' },
  'Load on the server': { icon: 'mdi-database-outline', tone: 'success', about: 'How many requests run at the same time while sharing, and how many entries one request brings back.' },
  'Several tabs': { icon: 'mdi-web', tone: 'neutral', about: 'What a tab of this browser does before it opens a shared model.' }
}
const groupInfoOf = (group: string) => GROUP_INFO[group] ?? { icon: 'mdi-cog-outline', tone: 'neutral' as const, about: '' }
const effectOf = (group: string) => {
  const [sweep, tries, pause, batch, page, tab] = ['sweepSeconds', 'checkpointAttempts', 'checkpointPauseMs', 'apiBatch', 'apiPage', 'tabCheckMs'].map(numberOf)
  if (group === 'Who is away') return `checks every ${plain('sweepSeconds', sweep)}`
  if (group === 'Saving to collab-kit') return `${tries} asks × ${pause} ms = waits up to ${plain('checkpointPauseMs', tries * pause)}`
  if (group === 'Load on the server') return `${batch} parallel · ${page} per request`
  return `waits ${plain('tabCheckMs', tab)}`
}
// Lists as a copy: the form must not change the values in effect before saving.
const formOf = (area: CollabArea): Record<string, FormValue> => Object.fromEntries(Object.entries(collabSettings[area]).map(([key, value]) => [key, typeof value === 'number' ? value / factorOf(key) : Array.isArray(value) ? [...value] : value]))

const form = reactive(Object.fromEntries(COLLAB_AREAS.map((area) => [area, formOf(area)])) as Record<CollabArea, Record<string, FormValue>>)
const loaded = ref(false)
const busy = ref<CollabArea | 'all' | null>(null)
const open = reactive<Partial<Record<CollabArea, boolean>>>({})
const tab = ref('sharing')
const filter = ref<'all' | 'changed'>('all')

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
/** The settings the timeline and the dialog preview show, so they can be reset from there. */
/** The canvases of the presence, log, hints and archive settings and the palette editor hold every field of these areas, so they are no rows. */
const onCanvas = (area: CollabArea) => ['presence', 'colors', 'log', 'hints', 'archive'].includes(area)
const WAIT_KEYS = ['hostAwayMs', 'hostGraceSeconds', 'hostEndSeconds', 'visitorGraceSeconds']
const SHARE_KEYS = ['anonymous', 'edit', 'task', 'history']
const labelOfKey = (area: CollabArea, key: string) => SECTIONS.find((section) => section.area === area)?.fields.find((field) => field.key === key)?.label ?? key
const resetField = (area: CollabArea, key: string) => (form[area][key] = defaultOf(area, key))
const invalid = (section: Section) => section.fields.some((field) => problemOf(section.area, field.key))

/** Technical fields show when expanded, with an error that would otherwise block saving unseen, and when changed until saved. */
const shown = (area: CollabArea, field: Field) => !field.advanced || open[area] || Boolean(problemOf(area, field.key)) || fieldChanged(area, field.key)

/** With a filter the tab lists the matching fields of all areas, else the sections of the open tab. */
const filtering = computed(() => filter.value !== 'all')
const passes = (area: CollabArea, field: Field) => filter.value === 'all' || nonDefault(area, field.key) || fieldChanged(area, field.key)
const visible = computed<Entry[]>(() => {
  const groupOf = (area: CollabArea) => GROUPS.find((group) => group.areas.includes(area)) as Group
  if (filtering.value) return SECTIONS.map((section) => ({ section, group: groupOf(section.area), fields: section.fields.filter((field) => passes(section.area, field)) })).filter((entry) => entry.fields.length > 0)
  const group = GROUPS.find((entry) => entry.id === tab.value) as Group
  // The four waits of the sharing area stand in the cards of the explainer, not as rows.
  return sectionsOf(group).map((section) => ({ section, group, fields: section.fields.filter((field) => shown(section.area, field) && !onCanvas(section.area) && !(section.area === 'sharing' && WAIT_KEYS.includes(field.key))) }))
})
/** The fields of an entry in two parts: the usual ones, and the technical ones in a panel of their own; a filter lists them all together. */
const partsOf = (entry: Entry) => {
  if (filtering.value) return [{ advanced: false, blocks: [{ name: '', fields: [...entry.fields] }] }]
  const parts = [
    { advanced: false, fields: entry.fields.filter((field) => !field.advanced) },
    { advanced: true, fields: entry.fields.filter((field) => field.advanced) }
  ].filter((part) => part.fields.length > 0)
  return parts.map((part) => ({ advanced: part.advanced, blocks: part.advanced ? blocksOf(part.fields) : [{ name: '', fields: part.fields }] }))
}
/** The technical fields in blocks by their group, in the order they come; those without a group share one block without a name. */
const blocksOf = (fields: readonly Field[]) => {
  const blocks: { name: string; fields: Field[] }[] = []
  for (const field of fields) {
    const name = field.group ?? ''
    const last = blocks[blocks.length - 1]
    if (last && last.name === name) last.fields.push(field)
    else blocks.push({ name, fields: [field] })
  }
  return blocks
}
/** The technical fields of a section, and how many of them differ from the default or are not saved yet. */
const advancedOf = (section: Section) => section.fields.filter((field) => field.advanced && !onCanvas(section.area))
const advancedChanged = (section: Section) => advancedOf(section).filter((field) => nonDefault(section.area, field.key) || fieldChanged(section.area, field.key)).length

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

/* The sentence under a heading that says what the settings below do: in a tinted field with an icon, so it does not get lost. */
.callout {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  margin: 0 0 8px;
  border-left: 3px solid rgb(var(--v-theme-info));
  border-radius: 8px;
  background: rgba(var(--v-theme-info), 0.1);
  font-size: 14px;
  line-height: 1.55;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.callout .v-icon {
  flex: none;
  margin-top: 2px;
  color: rgb(var(--v-theme-info));
}

/* In a group card it is lighter and takes the color of the group. */
.callout--small {
  padding: 6px 10px;
  margin: 6px 0 0;
  border-left-width: 0;
  background: rgba(var(--agroup-color), 0.1);
  font-size: 13px;
  line-height: 1.5;
}

.callout--small .v-icon {
  margin-top: 1px;
  color: rgb(var(--agroup-color));
}

/* The frame: head with the actions, search, tabs and the sections as cards. */
.shell {
  overflow: hidden;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 12px;
}
/* Under a heading: grey with a green bar, in the style of the grey part cards. */
.callout--about {
  border: 1px solid rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-on-surface), 0.04);
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.7);
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

/* The timeline, the try-it part and the steps: one below the other, and where the area is wide, the steps beside the other two. */
.sharing-wrap {
  container-type: inline-size;
}

.sharing-top {
  display: grid;
  grid-template-areas:
    'timeline'
    'try'
    'steps';
  grid-template-columns: minmax(0, 1fr);
  gap: 16px 32px;
  margin-bottom: 8px;
}

.sharing-top > :first-child {
  grid-area: timeline;
  min-width: 0;
}

/* The same two columns as the rows below, so the edges line up. */
@container (min-width: 1152px) {
  .sharing-top {
    grid-template-areas:
      'timeline steps'
      'try steps';
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }
}

/* The rows run in two columns where the card is wide enough; a split card puts the dialog beside them. */
.card__body--split {
  display: flex;
  flex-wrap: wrap;
  gap: 24px;
  align-items: flex-start;
}

.card__parts {
  flex: 1 1 420px;
  min-width: 0;
}

.rows {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(max(560px, calc((100% - 32px) / 2)), 1fr));
  column-gap: 32px;
}

.rows > .advanced__head,
.rows > .row--wide {
  grid-column: 1 / -1;
}

.advanced-toggle__count {
  padding: 0 8px;
  margin-left: 8px;
  border-radius: 10px;
  background: rgb(var(--v-theme-surface));
  font-size: 12px;
  font-weight: 500;
}

.advanced-note {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.advanced-note__badge {
  padding: 2px 8px;
  margin-left: 4px;
  border-radius: 8px;
  background: rgba(var(--v-theme-warning), 0.2);
  font-weight: 500;
  color: rgb(var(--v-theme-warning));
}

/* The technical settings sit in a tinted panel, so they stand apart from the ones for everyday use. */
.advanced {
  padding: 4px 14px 8px;
  margin-top: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.advanced__head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 2px;
  font-size: 13px;
  font-weight: 600;
}

.advanced__head span {
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* The name of a group of technical settings under "Advanced". */
/* The technical settings in cards, one per group: the head, the rows and, where there is one, the picture beside the rows. */
.agroups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 760px), 1fr));
  gap: 12px;
  margin-top: 8px;
}

.agroup {
  --agroup-color: var(--v-theme-info);
  padding: 10px 14px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-left: 4px solid rgb(var(--agroup-color));
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.agroup--warning {
  --agroup-color: var(--v-theme-warning);
}

.agroup--success {
  --agroup-color: var(--v-theme-success);
}

.agroup--neutral {
  --agroup-color: 128, 128, 128;
}

.agroup__head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.agroup__icon {
  flex: none;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(var(--agroup-color), 0.16);
  color: rgb(var(--agroup-color));
}

.agroup__title {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  align-items: center;
}

.agroup__title b {
  font-size: 14px;
  font-weight: 600;
}

.agroup__chip {
  padding: 2px 10px;
  border-radius: 8px;
  background: rgba(var(--agroup-color), 0.16);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.agroup__body {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 20px;
  align-items: flex-start;
  margin-top: 6px;
}

.agroup__rows {
  flex: 1 1 560px;
  min-width: 0;
}

.agroup__diagram {
  flex: 0 0 200px;
  padding-top: 12px;
}

/* The number field of a step card: the name of the setting, the field and the check beside the reset arrow. */
.stepfield {
  margin: 2px 0;
}

.stepfield__cap {
  margin-bottom: 4px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.stepfield__row {
  display: flex;
  gap: 4px;
  align-items: flex-start;
}

.stepfield__error {
  margin-top: 4px;
  font-size: 12px;
  color: rgb(var(--v-theme-error));
}

/* A setting: name and explanation on the left, the value on the right, the reset arrow when it differs from the default. */
.row {
  display: grid;
  grid-template-columns: minmax(0, 520px) 200px 32px;
  justify-content: start;
  gap: 4px 12px;
  align-items: start;
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
  align-self: center;
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
  align-self: center;
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
