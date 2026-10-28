<template>
  <v-container max-width="1100" class="py-8">
    <div class="d-flex align-center ga-3 mb-5">
      <h1 class="text-h4">Fragebögen</h1>
      <v-spacer />
      <v-btn color="primary" to="/surveys/edit">Fragebogen erstellen</v-btn>
      <v-btn :loading="loading" @click="load">Aktualisieren</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate />
    <v-card v-for="survey in items" :key="survey.id" variant="outlined" class="mb-3 pa-4">
      <div class="d-flex align-center flex-wrap ga-3">
        <strong>{{ survey.title }}</strong
        ><v-chip size="small">{{ survey.latestKind === 'checkpoint' ? 'Checkpoint' : 'Release' }} {{ survey.version }}</v-chip
        ><v-chip size="small" :color="survey.activeReleaseId ? 'success' : undefined">{{ survey.activeReleaseVersion ? `Aktiv: Release ${survey.activeReleaseVersion}` : 'Nicht veröffentlicht' }}</v-chip
        ><v-spacer />
        <v-btn v-if="survey.managedBy === 'learning-path-help'" :to="`/learning-path-templates/${survey.templateId}/edit`">Im Lernpfad bearbeiten</v-btn>
        <v-btn v-else :to="`/surveys/${survey.id}/edit`">Bearbeiten</v-btn>
        <v-btn @click="open(survey, 'preview')">Entwurfsvorschau</v-btn>
        <v-btn v-if="!survey.managedBy" @click="open(survey, 'test')">Entwurf testen</v-btn>
        <v-btn v-if="survey.activeReleaseId && !survey.managedBy" @click="open(survey, 'use')">Aktiven Release ausfüllen</v-btn>
        <v-btn v-if="!survey.managedBy" color="error" @click="deleting = survey">Löschen</v-btn>
      </div>
      <p class="text-caption mt-2">{{ survey.definition.elements.length }} Fragen · Geändert: {{ new Date(survey.updatedAt).toLocaleString('de-DE') }}</p>
    </v-card>
    <v-alert v-if="!loading && !items.length" type="info">Noch keine Fragebögen vorhanden.</v-alert>
    <v-dialog :model-value="!!selected" max-width="960" scrollable @update:model-value="!$event && (selected = null)">
      <v-card v-if="selected">
        <v-card-title>{{ mode === 'preview' ? 'Entwurfsvorschau' : mode === 'test' ? 'Entwurf testen' : `Aktiver Release ${selected.activeReleaseVersion}` }}</v-card-title>
        <v-card-text><SurveyRenderer :survey-id="selected.id" :mode="mode" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="selected = null">Schließen</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog :model-value="!!deleting" max-width="500" :persistent="busy" @update:model-value="!$event && (deleting = null)">
      <v-card>
        <v-card-title>Fragebogen löschen?</v-card-title>
        <v-card-text
          >„{{ deleting?.title }}“ wird aus der Verwaltung entfernt. Bestehende Antworten und ihre Fragebogenversionen bleiben erhalten.
          <v-alert v-if="deleteError" type="error" class="mt-3">{{ deleteError }}</v-alert>
        </v-card-text>
        <v-card-actions><v-btn :disabled="busy" @click="deleting = null">Abbrechen</v-btn><v-spacer /><v-btn color="error" :loading="busy" @click="remove">Löschen</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import surveys, { surveyError, type Survey, type SurveyMode } from '@/services/surveys'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
const items = ref<Survey[]>([]),
  selected = ref<Survey | null>(null),
  deleting = ref<Survey | null>(null)
const mode = ref<SurveyMode>('preview'),
  loading = ref(false),
  busy = ref(false),
  error = ref(''),
  deleteError = ref('')
function open(survey: Survey, value: SurveyMode) {
  mode.value = value
  selected.value = survey
}
async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const all: Survey[] = []
    for (let skip = 0; ; ) {
      const page = (await surveys.list(skip)).data
      all.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    items.value = all
  } catch (e) {
    error.value = surveyError(e)
  } finally {
    loading.value = false
  }
}
async function remove() {
  if (!deleting.value || busy.value) return
  busy.value = true
  deleteError.value = ''
  try {
    await surveys.remove(deleting.value.id)
    items.value = items.value.filter((item) => item.id !== deleting.value?.id)
    deleting.value = null
  } catch (e) {
    deleteError.value = surveyError(e)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
