<template>
  <section v-if="request.stage === 'marking'" class="help-marking-panel" aria-label="Problemstellen markieren">
    <div class="d-flex align-center ga-2">
      <v-icon color="warning" size="18">mdi-marker</v-icon>
      <h2 class="help-marking-title">Problemstellen markieren</h2>
    </div>
    <p class="help-marking-count" role="status">{{ cellIds.length }} {{ cellIds.length === 1 ? 'Element' : 'Elemente' }} · {{ textRanges.length }} {{ textRanges.length === 1 ? 'Textstelle' : 'Textstellen' }}</p>
    <details class="help-marking-details">
      <summary>So markierst du</summary>
      <p>Klicke Modellelemente oder Verbindungen an. Wähle im Aufgabentext Text aus und klicke auf „Textstelle markieren“. Erneutes Anklicken entfernt eine Modellmarkierung. Dein Modell bleibt unverändert.</p>
    </details>
    <p v-if="request.markingRequired === false" class="help-marking-optional">Markierungen sind optional.</p>
    <div class="help-marking-actions">
      <v-btn color="primary" size="small" variant="flat" :loading="busy || snapshotLoading" :disabled="request.markingRequired !== false && !cellIds.length && !textRanges.length || snapshotLoading || Boolean(snapshotError)" @click="submitMarkings">Weiter</v-btn>
    </div>
    <details v-if="textRanges.length" class="help-marking-details">
      <summary>Markierte Textstellen</summary>
      <div class="d-flex ga-1 flex-wrap mt-2">
        <v-chip v-for="(range, index) in textRanges" :key="`${range.start}:${range.end}`" closable :title="range.text" size="x-small" @click:close="emit('remove-text', index)">{{ range.text.length > 35 ? `${range.text.slice(0, 35)}…` : range.text }}</v-chip>
      </div>
    </details>
    <v-alert v-if="error || snapshotError" type="error" density="compact" variant="tonal" class="mt-2">{{ error || snapshotError }}<v-btn v-if="snapshotError" size="small" variant="text" @click="emit('retry-snapshot')">Erneut laden</v-btn></v-alert>
  </section>
  <section v-else-if="request.stage !== 'cancelled'" class="help-flow-card" :aria-label="title">
      <header class="d-flex align-center ga-2"><v-icon color="warning" size="18">mdi-lifebuoy</v-icon><h2 class="help-marking-title">{{ title }}</h2></header>
      <v-progress-linear v-if="busy" indeterminate height="2" class="mt-2" />
      <div class="help-flow-content">
        <div v-if="error" role="alert" class="help-flow-error">{{ error }}<v-btn size="small" variant="text" @click="refresh">Erneut versuchen</v-btn></div>
        <template v-if="request.stage === 'completed'">
          <p class="help-flow-choice">{{ request.nextAction }}</p>
          <p class="help-flow-next-step">{{ nextStep }}</p>
        </template>
        <SurveyRenderer v-else-if="phase" :key="`${request.id}:${phase}`" ref="renderer" compact :survey-id="request.surveyIds[phase]" :activity="{ runId: request.runId, stepId: request.stepId, helpRequestId: request.id, helpPhase: phase }" @completed="refresh" />
      </div>
      <div v-if="request.stage === 'topic' || request.stage === 'completed'" class="help-flow-actions">
        <v-btn v-if="request.stage === 'topic'" size="small" variant="text" :disabled="busy || renderer?.saving" @click="cancel">Abbrechen</v-btn>
        <v-btn v-else color="primary" size="small" variant="flat" @click="emit('close')">Weiter modellieren</v-btn>
      </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import paths, { type HelpRequest, type HelpSurveyPhase, type HelpTextRange } from '@/services/learningPaths'
import { surveyError } from '@/services/surveys'

const props = defineProps<{ request: HelpRequest; cellIds: string[]; textRanges: HelpTextRange[]; snapshotLoading: boolean; snapshotError: string }>()
const emit = defineEmits<{ 'update:request': [request: HelpRequest]; close: []; 'remove-text': [index: number]; 'retry-snapshot': [] }>()
const renderer = ref<InstanceType<typeof SurveyRenderer> | null>(null)
const busy = ref(false)
const error = ref('')
const phase = computed<HelpSurveyPhase | null>(() => ['topic', 'reflection', 'action'].includes(props.request.stage) ? props.request.stage as HelpSurveyPhase : null)
const title = computed(() => ({ topic: 'Dein Problem', marking: 'Problemstellen markieren', reflection: 'Was du gerade brauchst', action: 'Dein nächster Schritt', completed: 'Dein nächster Schritt', cancelled: 'Hilfe abgebrochen' })[props.request.stage])
const nextStep = computed(() => {
  const action = props.request.nextAction ?? ''
  const id = props.request.nextActionId
  if (id) return 'Nutze die gewählte Hilfequelle. Danach kannst du hier weiterarbeiten.'
  if (action.includes('Vorlesungsfolien')) return 'Öffne deine Vorlesungsfolien und suche nach dem Thema oder einem passenden Beispiel zu deiner Problemstelle.'
  if (action.includes('Lehrkraft')) return 'Wende dich an eine Lehrkraft und zeige ihr die Stelle, an der du nicht weiterkommst.'
  if (action.includes('Kommiliton')) return 'Tausche dich mit einer Kollegin, einem Kollegen oder anderen Studierenden aus und besprecht deine konkrete Problemstelle.'
  return 'Nutze die gewählte Hilfequelle. Danach kannst du hier weiterarbeiten.'
})
const refresh = async () => {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { emit('update:request', (await paths.help(props.request.runId, props.request.stepId, props.request.id)).data) }
  catch (e) { error.value = surveyError(e) }
  finally { busy.value = false }
}
const submitMarkings = async () => {
  if (busy.value || props.snapshotLoading || props.snapshotError) return
  busy.value = true
  error.value = ''
  try {
    emit('update:request', (await paths.saveHelpMarkings(props.request.runId, props.request.stepId, props.request.id, { cellIds: props.cellIds, taskTextRanges: props.textRanges })).data)
  } catch (e) { error.value = surveyError(e) }
  finally { busy.value = false }
}
const cancel = async () => {
  if (props.request.stage !== 'topic' || busy.value || renderer.value?.saving) return
  busy.value = true
  error.value = ''
  try {
    if (renderer.value && !(await renderer.value.saveDraft())) return
    emit('update:request', (await paths.cancelHelp(props.request.runId, props.request.stepId, props.request.id)).data)
    emit('close')
  } catch (e) { error.value = surveyError(e) }
  finally { busy.value = false }
}
</script>

<style scoped>
.help-marking-panel { max-height: 35vh; overflow-y: auto; margin: 0 8px 8px; padding: 10px; border: 1px solid #ddbf88; border-radius: 10px; background: #fff8e9; color: #574224; user-select: text; }
.help-marking-title { font-size: 13px; font-weight: 700; line-height: 1.35; }
.help-marking-count { margin: 5px 0; font-size: 12px; }
.help-marking-details { font-size: 11px; line-height: 1.5; }
.help-marking-details summary { cursor: pointer; }
.help-marking-details p { margin-top: 5px; }
.help-marking-optional { margin-top: 4px; font-size: 11px; }
.help-marking-actions { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
.help-marking-actions :deep(.v-btn) { text-transform: none; letter-spacing: 0; }
.help-flow-card { display: flex; flex-direction: column; min-height: 0; margin: 0 8px 8px; padding: 10px; border: 1px solid #ddbf88; border-radius: 10px; background: #fffdf8; color: #574224; user-select: text; }
.help-flow-card > header, .help-flow-actions { flex-shrink: 0; }
.help-flow-content { min-height: 0; padding-top: 8px; }
.help-flow-choice { font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.help-flow-next-step, .help-flow-error { font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.help-flow-error { color: rgb(var(--v-theme-error)); margin-bottom: 8px; }
.help-flow-actions { margin-top: 6px; }
.help-flow-actions :deep(.v-btn) { text-transform: none; letter-spacing: 0; }
</style>
