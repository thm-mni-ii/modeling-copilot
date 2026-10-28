<template>
  <div aria-live="polite">
    <v-progress-linear v-if="loading || saving" indeterminate />
    <v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert>
    <v-btn v-if="error && !model" @click="load">Erneut laden</v-btn>
    <v-alert v-if="mode !== 'use'" type="info" variant="tonal" class="mb-3">
      {{ mode === 'preview' ? 'Vorschau: Es werden keine Antworten gespeichert.' : 'Test: Antworten werden als Testdaten gespeichert.' }}
    </v-alert>
    <v-alert v-if="releaseChanged" type="info" variant="tonal" class="mb-3">Eine neue Version wurde veröffentlicht. Bitte fülle den aktuellen Fragebogen aus. Der bisherige Entwurf wird für diese Version nicht übernommen.</v-alert>
    <p v-if="activity && draftStatus" class="text-caption mb-2" role="status">{{ draftStatus }}</p>
    <SurveyComponent v-if="model && !completed" :model="model" />
    <v-btn v-if="error && pendingAnswers && !completed" :loading="saving" @click="submit">Speichern erneut versuchen</v-btn>
    <template v-if="completed">
      <v-alert :type="skipped ? 'info' : 'success'">{{ skipped ? 'Fragebogen übersprungen. Es wurden keine Antworten abgegeben.' : mode === 'preview' ? 'Vorschau abgeschlossen. Diese Daten würden gespeichert:' : 'Vielen Dank! Die Antworten wurden gespeichert.' }}</v-alert>
      <pre v-if="mode === 'preview'" class="preview-data mt-3">{{ JSON.stringify(completed, null, 2) }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, shallowRef, ref, watch } from 'vue'
import { Model } from 'survey-core'
import { SurveyComponent } from 'survey-vue3-ui'
import 'survey-core/survey-core.css'
import 'survey-core/i18n/german'
import paths, { type SurveyPhase, type HelpSurveyPhase } from '@/services/learningPaths'
import surveys, { surveyError, type SurveyMode, type SurveyResponse } from '@/services/surveys'

const props = withDefaults(defineProps<{ surveyId: string; versionId?: string; mode?: SurveyMode; activity?: { runId: string; stepId: string; phase?: SurveyPhase; helpRequestId?: string; helpPhase?: HelpSurveyPhase } }>(), { mode: 'use' })
const emit = defineEmits<{ completed: [response?: SurveyResponse] }>()
const model = shallowRef<Model | null>(null)
const loading = ref(false),
  saving = ref(false),
  error = ref('')
const completed = ref<SurveyResponse | Record<string, unknown> | null>(null)
const skipped = ref(false)
const draftStatus = ref('')
const releaseChanged = ref(false)
let loadedSessionId = ''
let revision = 0,
  draftKey = '',
  draftQueue: Promise<void> = Promise.resolve(),
  draftFailed = false
let lastAnswers: Record<string, unknown> = {}
let inFlightAnswers: Record<string, unknown> | null = null
const storeLocal = (answers: Record<string, unknown>) => {
  try {
    localStorage.setItem(draftKey, JSON.stringify({ answers, revision, inFlightAnswers }))
  } catch {
    error.value = 'Der lokale Entwurf konnte nicht gesichert werden. Bitte vor dem Verlassen speichern.'
  }
}
let draftTimer: ReturnType<typeof setTimeout> | undefined
let savedAnswers = '{}'
const appendDraft = () => {
  clearTimeout(draftTimer)
  const activity = props.activity
  if (!activity || !draftKey) return
  draftQueue = draftQueue.then(async () => {
    if (draftFailed) return
    const answers = lastAnswers
    const serialized = JSON.stringify(answers)
    if (serialized === savedAnswers) return
    try {
      inFlightAnswers = answers
      storeLocal(lastAnswers)
      const result = (await (activity.helpRequestId && activity.helpPhase
        ? paths.saveHelpSurveyDraft(activity.runId, activity.stepId, activity.helpRequestId, activity.helpPhase, answers, revision, loadedSessionId)
        : paths.saveSurveyDraft(activity.runId, activity.stepId, answers, revision, loadedSessionId, activity.phase))).data
      revision = result.revision
      savedAnswers = serialized
      inFlightAnswers = null
      storeLocal(lastAnswers)
      draftStatus.value = answers === lastAnswers ? 'Entwurf gespeichert' : 'Entwurf wird gespeichert ...'
    } catch (e) {
      draftFailed = true
      error.value = surveyError(e)
      draftStatus.value = 'Entwurf nur lokal gespeichert. Bitte erneut versuchen.'
    }
  })
}
const queueDraft = (answers: Record<string, unknown>) => {
  lastAnswers = answers
  storeLocal(answers)
  draftStatus.value = 'Entwurf wird gespeichert ...'
  clearTimeout(draftTimer)
  draftTimer = setTimeout(appendDraft, 500)
}
async function saveDraft() {
  appendDraft()
  await draftQueue
  if (draftFailed) {
    draftFailed = false
    appendDraft()
    await draftQueue
  }
  return !draftFailed
}

defineExpose({ saveDraft, saving, getSessionReference: () => ({ sessionId: loadedSessionId, revision, draftKey }) })
const pendingAnswers = ref<Record<string, unknown> | null>(null)
let generation = 0,
  loadedVersionId = ''
async function submit() {
  if (!pendingAnswers.value || saving.value) return
  const current = generation
  // Keep the submitted payload stable while the draft save is in flight.
  const answers = JSON.parse(JSON.stringify(pendingAnswers.value)) as Record<string, unknown>
  const activity = props.activity
  const surveyId = props.surveyId
  const mode = props.mode
  const versionId = loadedVersionId
  saving.value = true
  error.value = ''
  try {
    let result: SurveyResponse
    if (activity) {
      if (!(await saveDraft()) || current !== generation) return
      result = (await (activity.helpRequestId && activity.helpPhase
        ? paths.submitHelpSurvey(activity.runId, activity.stepId, activity.helpRequestId, activity.helpPhase, answers, revision, loadedSessionId)
        : paths.submitSurvey(activity.runId, activity.stepId, answers, revision, loadedSessionId, activity.phase))).data
      try {
        localStorage.removeItem(draftKey)
      } catch {
        /* Already stored on the server. */
      }
    } else result = (await surveys.submit(surveyId, versionId, answers, mode)).data
    if (current !== generation) return
    completed.value = result
    emit('completed', result)
  } catch (e) {
    if (current === generation) error.value = surveyError(e)
  } finally {
    if (current === generation) saving.value = false
  }
}
async function load() {
  const current = ++generation
  model.value?.dispose()
  model.value = null
  completed.value = null
  skipped.value = false
  pendingAnswers.value = null
  error.value = ''
  loading.value = true
  saving.value = false
  try {
    const activity = props.activity
    const session = activity ? (activity.helpRequestId && activity.helpPhase
      ? (await paths.openHelpSurvey(activity.runId, activity.stepId, activity.helpRequestId, activity.helpPhase)).data
      : activity.phase?.startsWith('pulse:') ? (await paths.openPulse(activity.runId, activity.phase.slice(6))).data : (await paths.openSurvey(activity.runId, activity.stepId, activity.phase)).data) : null
    const survey = session ? session.version : (await surveys.render(props.surveyId, props.mode, props.versionId)).data
    if (current !== generation) return
    releaseChanged.value = session?.releaseChanged ?? false
    loadedVersionId = survey.id
    const pulse = activity?.phase?.startsWith('pulse:')
    const instance = new Model({ ...survey.definition, title: pulse || activity?.helpRequestId ? '' : survey.title, ...(pulse || activity?.helpRequestId ? { completeText: activity?.helpPhase === 'action' ? 'Hilfe auswählen' : 'Weiter' } : {}), locale: 'de', showCompletedPage: false, textUpdateMode: 'onTyping' })
    if (session) {
      loadedSessionId = session.sessionId
      revision = session.revision
      draftFailed = false
      draftKey = `learning-path-survey:${session.sessionId}:${survey.id}`
      if (session.status === 'submitted' || session.status === 'skipped') {
        skipped.value = session.status === 'skipped'
        completed.value = session.answers
        draftStatus.value = session.status === 'skipped' ? 'Fragebogen übersprungen.' : 'Fragebogen bereits abgeschlossen.'
        instance.dispose()
        if (session.status === 'submitted') emit('completed')
        return
      }
      savedAnswers = JSON.stringify(session.answers)
      instance.data = session.answers
      try {
        const local = JSON.parse(localStorage.getItem(draftKey) ?? 'null')
        if (local && (local.revision === revision || (local.revision + 1 === revision && JSON.stringify(local.inFlightAnswers) === JSON.stringify(session.answers)))) instance.data = local.answers
      } catch {
        /* Server draft remains available. */
      }
      lastAnswers = JSON.parse(JSON.stringify(instance.data))
      instance.onValueChanged.add((sender) => queueDraft(JSON.parse(JSON.stringify(sender.data))))
      if (JSON.stringify(instance.data) !== JSON.stringify(session.answers)) queueDraft(lastAnswers)
    }
    instance.onComplete.add((sender) => {
      pendingAnswers.value = JSON.parse(JSON.stringify(sender.data))
      void submit()
    })
    model.value = instance
  } catch (e) {
    if (current === generation) error.value = surveyError(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
// Parent renders create a new activity object; reload only if its IDs change.
watch([() => props.surveyId, () => props.versionId, () => props.mode, () => props.activity?.runId, () => props.activity?.stepId, () => props.activity?.phase, () => props.activity?.helpRequestId, () => props.activity?.helpPhase], load, { immediate: true })
onBeforeUnmount(() => {
  clearTimeout(draftTimer)
  if (props.activity && !completed.value) appendDraft()
  generation++
  model.value?.dispose()
})
</script>

<style scoped>
.preview-data {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
