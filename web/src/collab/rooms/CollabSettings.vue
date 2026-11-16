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

const props = defineProps<{ ck: CollabKitApi }>()

/** Ein Feld im Reiter; mit items eine Auswahl, sonst je nach Standard ein Schalter oder eine Zahl in Sekunden, mit unit in ms. Technisches steht unter „Advanced“. */
interface Field {
  readonly key: string
  readonly label: string
  readonly hint: string
  readonly items?: readonly { readonly value: string; readonly title: string }[]
  readonly unit?: 'ms'
  readonly advanced?: boolean
}

interface Section {
  readonly area: CollabArea
  readonly title: string
  readonly about: string
  readonly fields: readonly Field[]
}

type FormValue = number | string | boolean

/** Ein Abschnitt je Bereich in collab-kit; Grenzen und Standards stehen in collabSettings.ts. */
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
  }
]

/** Im Formular stehen Sekunden, außer bei Feldern mit unit ms; Schlüssel auf Ms speichert collab-kit in Millisekunden. */
const MS_KEYS = new Set(SECTIONS.flatMap((section) => section.fields.filter((field) => field.unit === 'ms').map((field) => field.key)))
const unitOf = (key: string) => (MS_KEYS.has(key) ? 'ms' : 's')
const factorOf = (key: string) => (key.endsWith('Ms') && !MS_KEYS.has(key) ? 1000 : 1)
const limitOf = (area: CollabArea, key: string) => (COLLAB_LIMITS[area] as Record<string, CollabLimit>)[key]
const hintOf = (area: CollabArea, field: Field) => {
  const limit = limitOf(area, field.key)
  if ('options' in limit) return `${field.hint} Default: ${field.items?.find((item) => item.value === limit.default)?.title ?? limit.default}.`
  if (!('min' in limit)) return `${field.hint} Default: ${limit.default ? 'on' : 'off'}.`
  const [factor, unit] = [factorOf(field.key), unitOf(field.key)]
  return `${field.hint} Default ${limit.default / factor} ${unit}, allowed ${limit.min / factor}–${limit.max / factor} ${unit}.`
}
const formOf = (area: CollabArea): Record<string, FormValue> => Object.fromEntries(Object.entries(collabSettings[area]).map(([key, value]) => [key, typeof value === 'number' ? value / factorOf(key) : value]))

const form = reactive(Object.fromEntries(COLLAB_AREAS.map((area) => [area, formOf(area)])) as Record<CollabArea, Record<string, FormValue>>)
const loaded = ref(false)
const busy = ref<CollabArea | null>(null)
const open = reactive<Partial<Record<CollabArea, boolean>>>({})

/** Grenzen je Zahl und die Abhängigkeiten im Bereich sharing; Schalter und Auswahl können nichts Falsches enthalten. */
const problemOf = (area: CollabArea, key: string): string | undefined => {
  const limit = limitOf(area, key)
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
  // Sieht der Sweep seltener nach, als jemand fehlen darf, verliert die Wartezeit ihre Wirkung.
  if (key === 'sweepSeconds' && typeof visitor === 'number' && value > Math.min(visitor, grace)) return 'At most as long as the shorter wait of a visitor or the host.'
  return undefined
}
/** Technisches zeigt sich aufgeklappt, mit einem Fehler, der sonst unsichtbar das Speichern sperrte, und geändert bis zum Speichern. */
const shown = (area: CollabArea, field: Field) => !field.advanced || open[area] || Boolean(problemOf(area, field.key)) || form[area][field.key] !== formOf(area)[field.key]
const invalid = (section: Section) => section.fields.some((field) => problemOf(section.area, field.key))
const changed = (area: CollabArea) => JSON.stringify(form[area]) !== JSON.stringify(formOf(area))

const save = async (section: Section) => {
  busy.value = section.area
  try {
    // PUT ersetzt den ganzen Bereich, also gehen immer alle seine Werte mit.
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

/** Löscht den Bereich in collab-kit; ohne Dokument gelten überall die Standards. */
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

// Gespeicherte Werte außerhalb der Grenzen zeigt das Formular als Standard, so wie sie auch gelten.
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

.fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px 24px;
}
</style>
