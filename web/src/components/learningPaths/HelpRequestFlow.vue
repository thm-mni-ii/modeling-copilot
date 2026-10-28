<template>
  <section v-if="request.stage === 'marking'" class="help-marking-panel" aria-label="Problemstellen markieren">
    <div class="d-flex align-start ga-3 flex-wrap">
      <v-icon color="warning" class="mt-1">mdi-marker</v-icon>
      <div class="flex-grow-1">
        <h2 class="text-subtitle-1 font-weight-bold">Markiere, wo du gerade Hilfe brauchst</h2>
        <p class="text-body-2">Klicke auf Modellelemente oder Verbindungen. Wähle Text in der Aufgabenstellung aus und klicke auf „Textstelle markieren“. Erneutes Anklicken entfernt eine Modellmarkierung.</p>
        <p class="text-caption mt-1">{{ cellIds.length }} {{ cellIds.length === 1 ? 'Modellelement' : 'Modellelemente' }} · {{ textRanges.length }} {{ textRanges.length === 1 ? 'Textstelle' : 'Textstellen' }} markiert. Dein Modell wird dabei nicht verändert.</p>
      </div>
      <div class="d-flex ga-2 flex-wrap">
        <v-btn variant="text" :disabled="busy" @click="cancel">Abbrechen</v-btn>
        <v-btn color="primary" :loading="busy || snapshotLoading" :disabled="!cellIds.length && !textRanges.length || snapshotLoading || Boolean(snapshotError)" @click="submitMarkings">Markierungen abschicken</v-btn>
      </div>
    </div>
    <div v-if="textRanges.length" class="d-flex ga-2 flex-wrap mt-2">
      <v-chip v-for="(range, index) in textRanges" :key="`${range.start}:${range.end}`" closable :title="range.text" size="small" @click:close="emit('remove-text', index)">{{ range.text.length > 60 ? `${range.text.slice(0, 60)}…` : range.text }}</v-chip>
    </div>
    <v-alert v-if="error || snapshotError" type="error" density="compact" variant="tonal" class="mt-2">{{ error || snapshotError }}<v-btn v-if="snapshotError" size="small" variant="text" @click="emit('retry-snapshot')">Erneut laden</v-btn></v-alert>
  </section>
  <v-dialog v-else :model-value="request.stage !== 'cancelled'" persistent max-width="680" scrollable>
    <v-card class="help-flow-card">
      <v-card-title class="d-flex align-center ga-2"><v-icon color="warning">mdi-lifebuoy</v-icon>{{ title }}</v-card-title>
      <v-card-text>
        <v-alert v-if="error" type="error" variant="tonal" class="mb-3">{{ error }}<v-btn variant="text" @click="refresh">Erneut versuchen</v-btn></v-alert>
        <template v-if="request.stage === 'completed'">
          <p class="text-body-1 font-weight-medium mb-3">{{ request.nextAction }}</p>
          <p>{{ nextStep }}</p>
          <p class="text-caption text-medium-emphasis mt-4">Deine Angaben und die zugehörige Modellversion wurden gespeichert.</p>
        </template>
        <SurveyRenderer v-else-if="phase" :key="`${request.id}:${phase}`" ref="renderer" :survey-id="request.surveyIds[phase]" :activity="{ runId: request.runId, stepId: request.stepId, helpRequestId: request.id, helpPhase: phase }" @completed="refresh" />
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="request.stage !== 'completed'" variant="text" :disabled="busy || renderer?.saving" @click="cancel">Abbrechen</v-btn>
        <v-spacer />
        <v-btn v-if="request.stage === 'completed'" color="primary" variant="flat" @click="emit('close')">Weiter modellieren</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
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
  if (action.includes('Vorlesungsfolien')) return 'Öffne deine Vorlesungsfolien und suche nach dem Thema oder einem passenden Beispiel zu deiner Problemstelle.'
  if (action.includes('Lehrkraft')) return 'Wende dich an eine Lehrkraft und zeige ihr die Stelle, an der du nicht weiterkommst.'
  if (action.includes('Kommiliton')) return 'Tausche dich mit einer Kollegin, einem Kollegen oder anderen Studierenden aus und besprecht deine konkrete Problemstelle.'
  return 'Nutze eine andere Hilfequelle, die für dich gerade passt. Danach kannst du hier weiterarbeiten.'
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
  if (busy.value || renderer.value?.saving) return
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
.help-marking-panel { flex-shrink: 0; max-height: 35vh; overflow-y: auto; padding: 12px 16px; margin-bottom: 10px; border: 1px solid #c79b4b; border-radius: 10px; background: #fff8e9; color: #574224; }
.help-flow-card { border-top: 4px solid #b68b49; }
</style>
