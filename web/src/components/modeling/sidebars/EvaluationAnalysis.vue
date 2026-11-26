<template>
  <section aria-label="Geschützte Auswertungsanalyse">
    <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-3">
      {{ error }}<v-btn size="small" variant="text" @click="reload">Erneut versuchen</v-btn>
    </v-alert>
    <v-skeleton-loader v-if="loading && !detail" type="list-item-three-line" />
    <template v-else-if="detail && canViewAnalysis">
      <div class="d-flex flex-wrap align-center ga-2 mb-2">
        <v-chip :color="stateColor(detail.state)" size="small" variant="tonal" label class="evaluation-run-status" aria-label="Technischer Workflowstatus"><v-icon start size="14">{{ stateIcon(detail.state) }}</v-icon>{{ stateLabel(detail.state) }}</v-chip>
        <span v-if="polling" class="text-caption text-medium-emphasis" role="status">Live-Aktualisierung</span>
      </div>
      <div v-if="!['succeeded', 'failed', 'cancelled'].includes(detail.state)" class="mt-2">
        <p class="text-caption text-medium-emphasis mb-1">Durchlauffortschritt · {{ doneStepCount }} / {{ detail.steps.length }} Schritte</p>
        <v-progress-linear :model-value="progressPercent" height="6" rounded color="info" aria-label="Fortschritt des Auswertungsdurchlaufs" />
      </div>
      <v-select v-if="(hasCatalog || serviceTab === 'overview' || serviceTab === 'findings') && referenceOptions.length > 1" v-model="referenceKey" :items="referenceOptions" item-title="label" item-value="key" label="Musterlösung" density="compact" variant="outlined" hide-details class="mt-3" />
      <v-tabs v-model="serviceTab" density="compact" grow color="primary" class="mt-2" aria-label="Analysebereich">
        <v-tab value="overview">Overview</v-tab>
        <v-tab value="findings">Findings</v-tab>
        <v-tab value="hints">Hinweise</v-tab>
        <v-tab v-if="hasCatalog" value="feedback">Alle Feedbackarten</v-tab>
        <v-tab value="technical">Ablaufverlauf</v-tab>
      </v-tabs>
      <AnalyticalFeedbackPanel v-model:reference-key="referenceKey" v-model:tab="serviceTab" :detail="detail" :catalog-available="hasCatalog" overview-mode @feedback-object="id => catalogFocus = { id, seq: (catalogFocus?.seq ?? 0) + 1 }" />
      <FeedbackCatalogPanel v-if="hasCatalog && serviceTab === 'feedback'" :detail="detail" :reference-key="referenceKey" :focus="catalogFocus" />
      <div v-if="serviceTab === 'technical'" class="mt-3">
        <p class="text-caption text-medium-emphasis mb-2">{{ detail.parameters?.textEvidence ? `Thresholds: spelling ${detail.parameters.textEvidence.spelling}, meaning ${detail.parameters.textEvidence.meaning}, floor ${detail.parameters.textEvidence.meaningFloor}` : 'Thresholds: workflow defaults' }}</p>
        <v-timeline density="compact" side="end" truncate-line="both" class="evaluation-timeline">
          <v-timeline-item v-for="entry in timelineEntries" :key="entry.id" :dot-color="entry.color" size="x-small">
            <template #icon
              ><v-icon size="12" color="white">{{ entry.icon }}</v-icon></template
            >
            <div class="text-body-2 font-weight-medium">{{ entry.title }}</div>
            <div class="text-caption text-medium-emphasis">{{ entry.status }}</div>
            <div v-if="entry.resultSummary" class="result-summary mt-1">{{ entry.resultSummary }}</div>
            <div v-else-if="entry.description" class="text-caption text-medium-emphasis mt-1">{{ entry.description }}</div>
          </v-timeline-item>
        </v-timeline>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApiId } from '@/services/api/types/common'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import evaluationService from '@/services/evaluation/evaluation.service'
import { useUserStore } from '@/stores/userStore'
import { useEvaluationResult } from '@/composables/useEvaluationResult'
import FeedbackCatalogPanel from './FeedbackCatalogPanel.vue'
import AnalyticalFeedbackPanel from './AnalyticalFeedbackPanel.vue'
import { recognitionReportsFromEvaluation } from '@/utils/analysisFeedback'

const props = defineProps<{ evaluationId: ApiId }>()
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationDetail] }>()
const user = useUserStore()
const canViewAnalysis = computed(() => user.globalRole === 'ADMIN' || user.globalRole === 'MODERATOR')
// Full run data is requested only here; the API independently enforces the staff boundary.
const { result: detail, loading, polling, error, reload } = useEvaluationResult(() => props.evaluationId, id => evaluationService.get(id), () => canViewAnalysis.value)
watch(detail, value => { if (value) emit('evaluation-updated', value) })
defineExpose({ reload, loading })
const hasCatalog = computed(() => {
  if (!canViewAnalysis.value || !detail.value) return false
  if (detail.value.feedbackTypes?.length) return detail.value.feedbackTypes.includes('help.catalog')
  return detail.value.steps.some(step => step.result?.schema === 'feedback-report/v4' && Array.isArray(step.result.feedback) &&
    step.result.feedback.some(entry => entry && typeof entry === 'object' && !Array.isArray(entry) && entry.type === 'help.catalog'))
})
const referenceKey = ref('')
const referenceOptions = computed(() => {
  if (!detail.value) return []
  const analytical = detail.value.steps.filter(step => step.id.startsWith('generate_analytical_feedback_')).map(step => ({
    key: step.id.slice('generate_analytical_feedback_'.length), label: step.label.replace(/^Analytisches Feedback:\s*/, '')
  }))
  if (analytical.length) return analytical
  try { return recognitionReportsFromEvaluation(detail.value).map((report, index) => ({ key: report.referenceKey, label: `Musterlösung ${index + 1}` })) }
  catch { return [] }
})
watch(referenceOptions, options => {
  if (!options.some(option => option.key === referenceKey.value)) referenceKey.value = options[0]?.key ?? ''
}, { immediate: true })
const serviceTab = ref<'overview' | 'findings' | 'hints' | 'feedback' | 'technical'>('overview')
const catalogFocus = ref<{ id: string; seq: number } | null>(null)
watch(() => detail.value?.state, state => {
  if (state === 'failed' || state === 'cancelled') serviceTab.value = 'technical'
})
const stateLabel = (state: string) => ({ queued: 'Workflow wartet auf Start', running: 'Workflow läuft', succeeded: 'Workflow erfolgreich durchgelaufen', failed: 'Workflow fehlgeschlagen', cancelled: 'Workflow abgebrochen', unknown: 'Workflowstatus unklar' })[state] ?? state
const stateIcon = (state: string) => (state === 'succeeded' ? 'mdi-check-circle' : state === 'running' ? 'mdi-progress-clock' : state === 'failed' ? 'mdi-close-circle' : state === 'cancelled' ? 'mdi-cancel' : state === 'queued' ? 'mdi-clock-outline' : 'mdi-help-circle-outline')
const stateColor = (state: string) => (state === 'succeeded' ? 'success' : state === 'running' ? 'info' : state === 'failed' ? 'error' : state === 'cancelled' ? 'warning' : undefined)

const doneStepCount = computed(() => (detail.value ? detail.value.steps.filter((step) => ['succeeded', 'failed', 'cancelled'].includes(step.status)).length : 0))
const progressPercent = computed(() => {
  return detail.value && detail.value.steps.length ? (doneStepCount.value / detail.value.steps.length) * 100 : 0
})
interface TimelineEntry {
  id: string
  icon: string
  color?: string
  title: string
  status: string
  description?: string | null
  resultSummary?: string | null
}
const timelineEntries = computed<TimelineEntry[]>(() => {
  if (!detail.value) return []
  const entries: TimelineEntry[] = detail.value.steps.map((step) => ({
    id: step.id,
    icon: stateIcon(step.status),
    color: stateColor(step.status),
    title: step.label,
    status: stateLabel(step.status),
    description: step.description,
    resultSummary: step.status === 'failed' && !step.result ? step.resultSummary : null
  }))
  return entries
})

</script>

<style scoped>
.evaluation-run-status { height: auto; min-height: 26px; white-space: normal; }
.evaluation-run-status :deep(.v-chip__content) { white-space: normal; }
.evaluation-timeline.v-timeline { grid-template-columns: 0 min-content minmax(0, 1fr); }
.evaluation-timeline :deep(.v-timeline-item__body) { width: 100%; min-width: 0; overflow-wrap: anywhere; padding-block-end: 8px; }
.result-summary { white-space: pre-wrap; font-size: 0.75rem; }
</style>
