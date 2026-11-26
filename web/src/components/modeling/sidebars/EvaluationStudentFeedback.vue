<template>
  <section aria-label="Studierendenfeedback">
    <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-3">
      {{ error }}<v-btn size="small" variant="text" @click="reload">Erneut versuchen</v-btn>
    </v-alert>
    <v-skeleton-loader v-if="loading && !feedback" type="list-item-three-line" />
    <template v-else-if="feedback">
      <v-progress-linear v-if="!['succeeded', 'failed', 'cancelled'].includes(feedback.state)" indeterminate height="6" rounded color="info" aria-label="Modell wird ausgewertet" />
      <v-alert v-if="feedback?.state !== 'succeeded'" :type="feedback.state === 'failed' ? 'error' : feedback.state === 'cancelled' ? 'warning' : 'info'" density="compact" variant="tonal" class="mt-3" :title="studentStateLabel(feedback.state)" aria-live="polite">
        <p class="text-caption text-medium-emphasis mb-0">{{ studentResultMessage }}</p>
      </v-alert>

      <!-- Hints are a separate, uncounted view (AP-10); accepting one renames the element in the editor (AP-11). -->
      <HintNotice v-if="feedback.state === 'succeeded' && !noticeViewed" :hints="feedback.hints ?? []" @open="viewHints" />
      <HintsFeedback v-if="feedback?.state === 'succeeded' && feedback.hints?.length" :evaluation-id="feedback.id" :hints="feedback.hints" :snapshot-xml="feedbackSnapshotXml" :readonly="historical" :focus="hintFocus" class="mt-3" />
      <!-- Learners see exactly what the completion check shows: percentages and, in learning paths, the thresholds.
           With help feedback, only a completion gate is shown here; help type "Prüfung" renders it itself. -->
      <section v-if="!historical && feedback?.state === 'succeeded' && (!feedback.feedback?.length || (studentGate && !hasCheckFeedback))" class="my-3" aria-label="Dein Ergebnis" aria-live="polite">
        <div class="d-flex flex-wrap align-center ga-2 mb-3">
          <h3 class="text-body-2 font-weight-medium">Dein Ergebnis</h3>
          <v-spacer />
          <v-chip v-if="studentGate?.gated" :color="studentGate.passed ? 'success' : 'warning'" size="small" variant="tonal" label class="evaluation-result-status">{{ studentGate.passed ? 'Abgabebereit' : 'Noch nicht abgabebereit' }}</v-chip>
        </div>
        <CompletionGateBars v-if="studentGate" :result="studentGate" dense />
        <p v-else class="text-caption text-medium-emphasis">{{ studentResultMessage }}</p>
      </section>
      <section v-if="feedback?.state === 'succeeded' && feedback.feedback?.length" class="my-3" aria-label="Dein Hilfe-Feedback">
        <h3 class="text-body-2 font-weight-medium mb-2">Dein Hilfe-Feedback</h3>
        <FeedbackView :entries="feedback.feedback" :snapshot-xml="feedbackSnapshotXml" />
      </section>

      <section v-if="historical" class="my-3" aria-label="Erkennungsübersicht" aria-live="polite">
        <h3 class="text-body-2 font-weight-medium mb-1">Erkennung</h3>
        <p class="text-caption text-medium-emphasis">Anteil der Musterlösungsobjekte mit eindeutig erkanntem Gegenstück. Keine Korrektheitsquote oder Note.</p>
        <p v-if="selectedRecognition?.recognition.buckets" class="text-caption text-medium-emphasis">Eine Zeile je Vergleichsgruppe bzw. nicht gruppiertem Typ der Musterlösung.</p>
        <v-alert v-if="recognitionState.error" type="warning" density="compact" variant="tonal">{{ recognitionState.error }}</v-alert>
        <template v-else-if="selectedRecognition">
          <div v-for="entry in recognitionRows" :key="entry.key" class="mb-3">
            <div class="d-flex justify-space-between ga-2 text-caption"><strong>{{ entry.label }}</strong><span>{{ entry.row.recognized }} von {{ entry.row.expected }} erkannt</span></div>
            <div class="d-flex justify-space-between ga-2 text-caption text-medium-emphasis"><span>{{ analysisValueLabel(entry.row.evaluationStatus) }}</span><span>{{ recognitionPercent(entry.row) }}</span></div>
            <v-progress-linear v-if="entry.row.percent !== null" :model-value="entry.row.percent" height="4" rounded color="primary" :aria-label="`${entry.label}: Erkennungsquote`" :aria-valuetext="`${entry.row.recognized} von ${entry.row.expected} erkannt`" />
          </div>
          <div class="mb-3">
            <div class="d-flex justify-space-between ga-2 text-caption"><strong>Abgabeobjekte ohne Zuordnung</strong><span>{{ unmatchedCount }}</span></div>
            <!-- Not a quota: always red, it only signals how many own objects found no counterpart. -->
            <v-progress-linear v-if="unmatchedCount" :model-value="100" height="4" rounded color="error" :aria-label="`${unmatchedCount} Abgabeobjekte ohne Zuordnung`" />
          </div>
        </template>
        <p v-else-if="historical && feedback?.scorePercent != null" class="text-body-2">Gespeichertes Ergebnis: {{ feedback.scorePercent }} %</p>
        <p v-else class="text-caption text-medium-emphasis">Für diese Auswertung und Musterlösung ist noch keine Erkennungsübersicht verfügbar.</p>
      </section>

    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApiId } from '@/services/api/types/common'
import type { EvaluationFeedback } from '@/services/api/types/evaluation'
import evaluationService from '@/services/evaluation/evaluation.service'
import modelService from '@/services/model/model.service'
import { useEvaluationResult } from '@/composables/useEvaluationResult'
import { useModelFileContext } from '@/composables/useModelFileContext'
import FeedbackView from '@/components/feedback/FeedbackView.vue'
import HintsFeedback from '@/components/feedback/HintsFeedback.vue'
import HintNotice from '@/components/feedback/HintNotice.vue'
import CompletionGateBars from '@/components/learningPaths/CompletionGateBars.vue'
import { completionGate, type GateResult } from '@/utils/completionGate'
import { adaptRecognition, analysisCategories, analysisValueLabel, categoryLabels, type RecognitionCount } from '@/utils/analysisFeedback'

const props = defineProps<{ evaluationId: ApiId; historical?: boolean; hintRequest?: { evaluationId: string; cellId?: string; seq: number; noticeViewed?: boolean } | null }>()
const hintFocus = ref<{ cellId?: string; seq: number } | null>(null)
const noticeViewed = ref(false)
watch(() => props.evaluationId, () => { hintFocus.value = null; noticeViewed.value = false })
const openHints = (cellId?: string) => { hintFocus.value = { cellId, seq: (hintFocus.value?.seq ?? 0) + 1 } }
const viewHints = () => {
  noticeViewed.value = true
  const request = props.hintRequest
  openHints(request?.evaluationId === props.evaluationId ? request.cellId : undefined)
}
watch(() => props.hintRequest, request => {
  if (request?.evaluationId === props.evaluationId && request.noticeViewed !== false) {
    if (request.noticeViewed) noticeViewed.value = true
    openHints(request.cellId)
  }
}, { immediate: true })
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationFeedback] }>()
// This component never loads analytical run details, including in a staff preview.
const { result: feedback, loading, error, reload } = useEvaluationResult(() => props.evaluationId, id => evaluationService.getFeedback(id))
watch(feedback, value => { if (value) emit('evaluation-updated', value) })
defineExpose({ reload, loading })
const feedbackSnapshotXml = ref<string | null>(null)
const feedbackSnapshots = new Map<string, Promise<string | null>>()
watch(() => feedback.value ? `${feedback.value.submission.modelId}:${feedback.value.submission.versionId}` : null, async (key, _, onCleanup) => {
  feedbackSnapshotXml.value = null
  let active = true
  onCleanup(() => { active = false })
  const submission = feedback.value?.submission
  if (!key || !submission) return
  let snapshot = feedbackSnapshots.get(key)
  if (!snapshot) {
    snapshot = modelService.get(submission.modelId)
      .then(model => modelService.getVersion(model.data, submission.versionId))
      .then(version => typeof version.data.data.xml === 'string' ? version.data.data.xml : null)
      .catch(() => null)
    feedbackSnapshots.set(key, snapshot)
  }
  const xml = await snapshot
  if (active) feedbackSnapshotXml.value = xml
}, { immediate: true })
const referenceKey = ref('')
const recognitionState = computed(() => {
  try { return { reports: feedback.value?.recognitions.map(({ referenceKey, recognition }) => ({ referenceKey, recognition: adaptRecognition(recognition) })) ?? [], error: null } }
  catch { return { reports: [], error: 'Die Erkennungsübersicht hat ein ungültiges Format.' } }
})
watch(recognitionState, value => {
  if (!value.reports.some(report => report.referenceKey === referenceKey.value)) referenceKey.value = value.reports[0]?.referenceKey ?? ''
}, { immediate: true })
const selectedRecognition = computed(() => recognitionState.value.reports.find(report => report.referenceKey === referenceKey.value))
const recognitionRows = computed(() => selectedRecognition.value ? [
  { key: 'overall', label: 'Insgesamt', row: selectedRecognition.value.recognition.overall },
  ...(selectedRecognition.value.recognition.buckets?.map(row => ({ key: row.id, label: row.label, row })) ??
    analysisCategories.map(key => ({ key, label: categoryLabels[key], row: selectedRecognition.value!.recognition.categories![key] })))
] : [])
const files = useModelFileContext()
const gateFor = (value: EvaluationFeedback | null | undefined) => {
  try { return value ? completionGate(files?.completionGate.value ?? null, value) : null }
  catch { return null }
}
const studentGate = computed(() => gateFor(feedback.value))
// Help type "Prüfung" renders these bars itself.
const hasCheckFeedback = computed(() => Boolean(feedback.value?.feedback?.some(entry => entry.type === 'help.check')))
// A summary describes the published feedback, independently of technical run success.
const feedbackSummary = (value: EvaluationFeedback, gate: GateResult | null) => {
  if (gate) {
    const recognition = `${Math.floor(gate.overall.percent)} % erkannt`
    return gate.gated ? `${gate.passed ? 'Abgabebereit' : 'Noch nicht abgabebereit'} · ${recognition}` : recognition
  }
  if (value.scorePercent != null) return `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(value.scorePercent)} %${value.recognitions.length ? ' erkannt' : ' erreicht'}`
  return 'Für diese Auswertung liegt kein Feedback vor.'
}
const unmatchedCount = computed(() => selectedRecognition.value?.recognition.unmatchedSubmission.length ?? 0)
const recognitionPercent = (row: RecognitionCount) => row.percent === null ? 'nicht bestimmbar' : `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(row.percent)} %`
const studentStateLabel = (state: string) => ({ queued: 'Auswertung wartet auf Start', running: 'Modell wird ausgewertet', failed: 'Auswertung fehlgeschlagen', cancelled: 'Auswertung abgebrochen', unknown: 'Status der Auswertung unklar' })[state] ?? state
const studentResultMessage = computed(() => {
  switch (feedback.value?.state) {
    case 'succeeded':
      return feedbackSummary(feedback.value, studentGate.value)
    case 'failed':
      return 'Es konnte kein Feedback erstellt werden. Bitte versuche die Auswertung erneut.'
    case 'cancelled':
      return 'Es liegt kein vollständiges Feedback vor. Bitte versuche die Auswertung erneut.'
    case 'queued':
      return 'Deine Auswertung wartet auf den Start.'
    case 'running':
      return 'Dein Modell wird ausgewertet.'
    default:
      return 'Der Status deiner Auswertung wird ermittelt.'
  }
})

</script>

<style scoped>
.evaluation-result-status { height: auto; min-height: 26px; white-space: normal; }
.evaluation-result-status :deep(.v-chip__content) { white-space: normal; }
</style>
