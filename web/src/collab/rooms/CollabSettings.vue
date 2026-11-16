<template>
  <div class="collab-settings">
    <p class="about mb-4">These settings apply to every shared model and group room. A change reaches everyone connected at once; the backend takes it at its next look at the shares, at most 30 s later.</p>
    <v-sheet v-for="section in SECTIONS" :key="section.area" border rounded="lg" class="pa-4 mb-4">
      <h3 class="title">{{ section.title }}</h3>
      <p class="about mb-4">{{ section.about }}</p>
      <div class="fields">
        <v-text-field
          v-for="field in section.fields"
          :key="field.key"
          v-model.number="form[section.area][field.key]"
          type="number"
          :label="field.label"
          suffix="s"
          :min="boundsOf(section.area, field.key).min"
          :max="boundsOf(section.area, field.key).max"
          density="compact"
          :disabled="!loaded"
          :hint="`${field.hint} Default ${boundsOf(section.area, field.key).default} s, allowed ${boundsOf(section.area, field.key).min}–${boundsOf(section.area, field.key).max} s.`"
          persistent-hint
          :error-messages="problemOf(section.area, field.key)"
        />
      </div>
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

const props = defineProps<{ ck: CollabKitApi }>()

interface Section {
  readonly area: CollabArea
  readonly title: string
  readonly about: string
  readonly fields: readonly { readonly key: string; readonly label: string; readonly hint: string }[]
}

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
      { key: 'hostAwayMs', label: 'Host away until visitors are told', hint: 'Visitors see "The host is disconnected."' }
    ]
  },
  {
    area: 'presence',
    title: 'Presence',
    about: 'Applies to everyone working on a model together, shared or in a group room.',
    fields: [{ key: 'idleMs', label: 'Idle until the selection is released', hint: 'With the selection go the locks on its elements.' }]
  }
]

/** Im Formular stehen Sekunden; Schlüssel auf Ms speichert collab-kit in Millisekunden. */
const factorOf = (key: string) => (key.endsWith('Ms') ? 1000 : 1)
const boundsOf = (area: CollabArea, key: string) => {
  const limit = (COLLAB_LIMITS[area] as Record<string, CollabLimit>)[key]
  const factor = factorOf(key)
  return { default: limit.default / factor, min: limit.min / factor, max: limit.max / factor }
}
const formOf = (area: CollabArea): Record<string, number | string> => Object.fromEntries(Object.entries(collabSettings[area]).map(([key, value]) => [key, value / factorOf(key)]))

const form = reactive<Record<CollabArea, Record<string, number | string>>>({ sharing: formOf('sharing'), presence: formOf('presence') })
const loaded = ref(false)
const busy = ref<CollabArea | null>(null)

/** Grenzen je Wert und die Abhängigkeiten im Bereich sharing; Sweep und Browser prüfen nur die Grenzen. */
const problemOf = (area: CollabArea, key: string): string | undefined => {
  const value = form[area][key]
  const { min, max } = boundsOf(area, key)
  if (typeof value !== 'number' || !Number.isInteger(value)) return 'Enter whole seconds.'
  if (value < min || value > max) return `Allowed are ${min}–${max} s.`
  const grace = form.sharing.hostGraceSeconds
  if (area !== 'sharing' || typeof grace !== 'number') return undefined
  if (key === 'hostEndSeconds' && value < grace) return 'At least as long as until the room locks.'
  if (key === 'hostAwayMs' && value >= grace) return 'Shorter than until the room locks.'
  return undefined
}
const invalid = (section: Section) => section.fields.some((field) => problemOf(section.area, field.key))
const changed = (area: CollabArea) => JSON.stringify(form[area]) !== JSON.stringify(formOf(area))

const save = async (section: Section) => {
  busy.value = section.area
  try {
    // PUT ersetzt den ganzen Bereich, also gehen immer alle seine Werte mit.
    const values = Object.fromEntries(Object.entries(form[section.area]).map(([key, value]) => [key, Number(value) * factorOf(key)]))
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
