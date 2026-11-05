<template>
  <div class="survey-renderer" :class="{ 'survey-renderer--compact': compact }" aria-live="polite">
    <v-progress-linear v-if="loading || saving" indeterminate />
    <v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert>
    <v-btn v-if="error && !model" @click="load">Erneut laden</v-btn>
    <v-alert v-if="mode !== 'use' && !compact" type="info" variant="tonal" class="mb-3">
      {{ mode === 'preview' ? 'Vorschau: Es werden keine Antworten gespeichert.' : 'Test: Antworten werden als Testdaten gespeichert.' }}
    </v-alert>
    <v-alert v-if="releaseChanged" type="info" variant="tonal" class="mb-3">Eine neue Version wurde veröffentlicht. Bitte fülle den aktuellen Fragebogen aus. Der bisherige Entwurf wird für diese Version nicht übernommen.</v-alert>
    <p v-if="activity && draftStatus && (!compact || draftFailed)" class="text-caption mb-2" role="status">{{ draftStatus }}</p>
    <p v-if="model && !completed && introduction" class="survey-introduction mb-5"><em>{{ introduction }}</em></p>
    <SurveyComponent v-if="model && !completed" :model="model" />
    <v-btn v-if="error && pendingAnswers && !completed" :loading="saving" @click="submit">Speichern erneut versuchen</v-btn>
    <template v-if="completed && !compact">
      <v-alert :type="skipped ? 'info' : 'success'">{{ skipped ? 'Fragebogen übersprungen. Es wurden keine Antworten abgegeben.' : mode === 'preview' ? 'Vorschau abgeschlossen. Diese Daten würden gespeichert:' : 'Vielen Dank! Die Antworten wurden gespeichert.' }}</v-alert>
      <pre v-if="mode === 'preview'" class="preview-data mt-3">{{ JSON.stringify(completed, null, 2) }}</pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, shallowRef, ref, watch } from 'vue'
import { Model, QuestionRankingModel, QuestionRatingModel, QuestionRadiogroupModel } from 'survey-core'
import { SurveyComponent } from 'survey-vue3-ui'
import 'survey-core/survey-core.css'
import 'survey-core/i18n/german'
import paths, { type SurveyPhase, type HelpSurveyPhase } from '@/services/learningPaths'
import surveys, { surveyError, type SurveyDefinition, type SurveyMode, type SurveyResponse } from '@/services/surveys'

const props = withDefaults(defineProps<{ surveyId: string; versionId?: string; mode?: SurveyMode; compact?: boolean; localDefinition?: SurveyDefinition; questionPerPage?: boolean; completeText?: string; activity?: { runId: string; stepId: string; phase?: SurveyPhase; helpRequestId?: string; helpPhase?: HelpSurveyPhase } }>(), { mode: 'use', compact: false })
const emit = defineEmits<{ completed: [response?: SurveyResponse] }>()
const model = shallowRef<Model | null>(null)
const loading = ref(false),
  saving = ref(false),
  error = ref('')
const completed = ref<SurveyResponse | Record<string, unknown> | null>(null)
const skipped = ref(false)
const introduction = ref('')
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
  introduction.value = ''
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
    const survey = props.localDefinition && props.mode === 'preview' ? { id: 'local-preview', title: '', definition: props.localDefinition } : session ? session.version : (await surveys.render(props.surveyId, props.mode, props.versionId)).data
    if (current !== generation) return
    releaseChanged.value = session?.releaseChanged ?? false
    loadedVersionId = survey.id
    const pulse = activity?.phase?.startsWith('pulse:')
    introduction.value = survey.definition.introduction ?? ''
    const displayQuestion = (q: SurveyDefinition['elements'][number]) => {
      const question = { ...q }
      delete question.page
      delete question.exclusiveChoices
      delete question.visibleWhen
      const notEqual = question.visibleIf?.match(/^\{([a-zA-Z][a-zA-Z0-9_-]{0,79})\} (?:!=|notcontains) /)
      if (notEqual) question.visibleIf = `(${question.visibleIf}) and {${notEqual[1]}} notempty`
      if (q.type === 'ranking' && q.choicesFromQuestion) {
        const multipleChoices = `{${q.choicesFromQuestion}.length} >= 2`
        question.visibleIf = question.visibleIf ? `(${question.visibleIf}) and (${multipleChoices})` : multipleChoices
      }
      return { ...question, ...(q.type === 'rating' ? { displayMode: 'buttons', rateDescriptionLocation: 'bottom' } : {}), ...(q.choices ? { choices: q.choices.map(value => ({ value, text: q.choiceLabels?.[value] ?? value, isExclusive: q.exclusiveChoices?.includes(value) ?? false })) } : {}) }
    }
    const { elements, pages, ...settings } = survey.definition
    delete settings.introduction
    const displayedDefinition = pages?.length
      ? { ...settings, pages: pages.filter(page => elements.some(q => q.page === page.name)).map(page => ({ ...page, elements: elements.filter(q => q.page === page.name).map(displayQuestion) })), showProgressBar: 'top', progressBarType: 'pages' }
      : { ...settings, elements: elements.map(displayQuestion) }
    const instance = new Model({ ...displayedDefinition, widthMode: 'responsive', title: pulse || activity?.helpRequestId ? '' : survey.title, ...(pulse || activity?.helpRequestId ? { completeText: activity?.helpPhase === 'action' ? 'Hilfe auswählen' : 'Weiter' } : {}), ...(props.completeText ? { completeText: props.completeText } : {}), locale: 'de', showCompletedPage: false, textUpdateMode: 'onTyping' })
    for (const question of instance.getAllQuestions()) {
      if (question instanceof QuestionRankingModel) {
        // Show positions before an answer exists without pre-filling a ranking.
        question.getNumberByIndex = (index: number) => String(index + 1)
      }
    }
    instance.onUpdateQuestionCssClasses.add((_sender, { question, cssClasses }) => {
      if (question instanceof QuestionRatingModel && question.visibleRateValues.length === 5) {
        cssClasses.mainRoot += ' survey-rating-five'
      }
      if (question instanceof QuestionRadiogroupModel && question.choices.length >= 5 &&
        question.choices.slice(0, 5).every((choice, index) => String(choice.value) === String(index + 1) && choice.text === String(index + 1))) {
        cssClasses.mainRoot += ' survey-radio-scale'
      }
    })
    if (props.questionPerPage || activity?.helpRequestId && activity.helpPhase === 'reflection') {
      instance.questionsOnPageMode = 'questionPerPage'
      instance.pageNextText = 'Weiter'
    }
    if (props.compact) {
      instance.widthMode = 'responsive'
      instance.showQuestionNumbers = 'off'
      instance.applyTheme({
        isPanelless: true,
        cssVariables: {
          '--sjs-font-size': '12px', '--sjs-base-unit': '4px', '--sjs-corner-radius': '5px',
          '--sjs-general-backcolor': '#fffdf8', '--sjs-general-backcolor-dim': '#fffdf8',
          '--sjs-primary-backcolor': '#81ba24', '--sjs-primary-forecolor': '#ffffff',
          '--sjs-shadow-small': 'none', '--sjs-shadow-medium': 'none'
        }
      })
    }
    if (session) {
      loadedSessionId = session.sessionId
      revision = session.revision
      draftFailed = false
      draftKey = `learning-path-survey:${session.sessionId}:${survey.id}${activity?.helpPhase ? `:${activity.helpPhase}` : ''}`
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
      if (props.localDefinition && props.mode === 'preview') {
        const response: SurveyResponse = { id: 'preview', surveyId: props.surveyId, version: 0, versionId: 'local-preview', userId: '', answers: JSON.parse(JSON.stringify(sender.data)), isTest: true, createdAt: new Date().toISOString() }
        completed.value = response
        emit('completed', response)
        return
      }
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
watch([() => props.surveyId, () => props.versionId, () => props.mode, () => props.localDefinition, () => props.activity?.runId, () => props.activity?.stepId, () => props.activity?.phase, () => props.activity?.helpRequestId, () => props.activity?.helpPhase], load, { immediate: true })
onBeforeUnmount(() => {
  clearTimeout(draftTimer)
  if (props.activity && !completed.value) appendDraft()
  generation++
  model.value?.dispose()
})
</script>

<style scoped>
.survey-renderer { width: 100%; min-width: 0; }
:deep(.sd-rating fieldset) { flex-wrap: wrap; }
:deep(.survey-rating-five .sd-rating.sd-rating--labels-bottom fieldset) {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px clamp(4px, 2vw, 24px);
  width: min(100%, 40rem);
  box-sizing: border-box;
  padding-bottom: 0;
}
:deep(.survey-rating-five .sd-rating--labels-bottom .sd-rating__item) {
  grid-row: 1;
  justify-self: center;
  min-width: 0;
  max-width: 100%;
}
:deep(.survey-rating-five .sd-rating.sd-rating--labels-bottom fieldset .sd-rating__min-text),
:deep(.survey-rating-five .sd-rating.sd-rating--labels-bottom fieldset .sd-rating__max-text) {
  position: static;
  grid-row: 2;
  white-space: normal;
  overflow-wrap: anywhere;
  min-width: 0;
}
:deep(.survey-rating-five .sd-rating--labels-bottom .sd-rating__min-text) { grid-column: 1 / 3; }
:deep(.survey-rating-five .sd-rating--labels-bottom .sd-rating__max-text) {
  grid-column: 4 / -1;
  text-align: right;
}
:deep(.survey-radio-scale .sd-selectbase) {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px clamp(4px, 2vw, 24px);
  width: min(100%, 40rem);
  min-width: 0;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5)) {
  width: min(100%, var(--sjs2-size-x600, 48px));
  min-width: 0;
  justify-self: center;
  padding: 0;
  margin: 0;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-selectbase__label) {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  width: 100%;
  aspect-ratio: 1;
  box-sizing: border-box;
  border: 0;
  box-shadow: var(--sjs2-border-effect-surface-default, inset 0 0 0 1px #ddd);
  border-radius: 50%;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-item__decorator) { display: none; }
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-item__control-label) {
  margin: 0;
  width: 100%;
  text-align: center;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-selectbase__label:has(input:checked)) {
  background: var(--sjs2-color-bg-brand-primary, #19b394);
  box-shadow: none;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-selectbase__label:has(input:checked) .sd-item__control-label) {
  color: var(--sjs2-color-fg-brand-on-primary, #fff);
  font-weight: 600;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(-n+5) .sd-selectbase__label:has(input:focus-visible)) {
  outline: 2px solid var(--sjs2-color-bg-brand-primary, #19b394);
  outline-offset: 3px;
}
:deep(.survey-radio-scale .sd-item:nth-of-type(n+6)) { grid-column: 1 / -1; }
.survey-introduction {
  line-height: 1.6;
  white-space: pre-line;
}
:deep(.sd-page__description) {
  white-space: pre-line;
}
.preview-data {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.survey-renderer--compact { min-width: 0; }
.survey-renderer--compact :deep(.sd-root-modern) { background: transparent; min-width: 0; }
.survey-renderer--compact :deep(.sd-container-modern),
.survey-renderer--compact :deep(.sd-body),
.survey-renderer--compact :deep(.sd-body--static),
.survey-renderer--compact :deep(.sd-page) { min-width: 0 !important; max-width: 100%; padding: 0 !important; background: transparent; row-gap: 0; }
.survey-renderer--compact :deep(.sd-body > .sv-components-column) { row-gap: 0; }
.survey-renderer--compact :deep(.sd-page__content),
.survey-renderer--compact :deep(.sd-question__container),
.survey-renderer--compact :deep(.sd-question__header-and-content-container) { padding: 0 !important; row-gap: 0; column-gap: 0; }
.survey-renderer--compact :deep(.sd-row) { margin-top: 12px; }
.survey-renderer--compact :deep(.sd-row:first-child) { margin-top: 0; }
.survey-renderer--compact :deep(.sd-question),
.survey-renderer--compact :deep(.sd-question__content),
.survey-renderer--compact :deep(.sd-element--with-frame) { min-width: 0; max-width: 100%; padding: 0; box-shadow: none; border: 0; background: transparent; }
.survey-renderer--compact :deep(.sd-question__header) { padding: 0; margin-bottom: 6px; }
.survey-renderer--compact :deep(.sd-question__title) { font-size: 12px; font-weight: 600; line-height: 1.45; }
.survey-renderer--compact :deep(.sd-item__control-label) { font-size: 12px; line-height: 1.4; }
.survey-renderer--compact :deep(.sd-item__control-label .sv-string-viewer) { overflow: visible; overflow-wrap: anywhere; }
.survey-renderer--compact :deep(.sd-selectbase__label) { padding-block: 5px; }
.survey-renderer--compact :deep(.sd-item) { padding: 0 !important; margin: 0; }
.survey-renderer--compact :deep(.sd-body__navigation) { padding: 8px 0 0; }
.survey-renderer--compact :deep(.sd-btn) { min-height: 30px; padding: 5px 12px; font-size: 12px; line-height: 1.4; box-shadow: none; }
.survey-renderer--compact :deep(.sd-input),
.survey-renderer--compact :deep(.sd-comment__input) { font-size: 12px; line-height: 1.4; }
.survey-renderer--compact :deep(.sd-comment__input) { min-height: 64px; }
</style>
