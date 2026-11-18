<template>
  <div class="evaluation-sidebar">
    <div class="evaluation-sidebar__toolbar">
      <v-btn v-if="view === 'detail'" icon size="x-small" variant="text" title="Zurück zur Liste" @click="view = 'list'">
        <v-icon size="18">mdi-arrow-left</v-icon>
      </v-btn>
      <span v-if="view === 'detail' && current" class="evaluation-sidebar__toolbar-title" :title="showServiceView ? current.name : feedbackTitle">{{ showServiceView ? current.name : feedbackTitle }}</span>
      <span v-else class="text-caption text-medium-emphasis">{{ evaluations.length ? `${evaluations.length} ${evaluations.length === 1 ? 'Auswertung' : 'Auswertungen'}` : '\u00A0' }}</span>
      <v-spacer />
      <v-btn icon size="x-small" variant="text" title="Aktualisieren" :loading="view === 'list' ? loading : detailLoading" @click="view === 'list' ? loadList() : reload()">
        <v-icon size="16">mdi-refresh</v-icon>
      </v-btn>
    </div>

    <div v-if="view === 'list'" class="evaluation-sidebar__body">
      <template v-if="loading && !evaluations.length">
        <v-skeleton-loader v-for="n in 3" :key="n" type="list-item-two-line" class="evaluation-skeleton" />
      </template>
      <v-alert v-else-if="listError" type="error" density="compact" variant="tonal" class="evaluation-load-error ma-3">
        {{ listError }}
        <template #append><v-btn size="x-small" variant="text" @click="loadList">Erneut versuchen</v-btn></template>
      </v-alert>
      <div v-else-if="!evaluations.length" class="evaluation-empty">
        <v-icon size="40" color="medium-emphasis">mdi-chart-timeline-variant-shimmer</v-icon>
        <p class="text-caption text-medium-emphasis mt-2 mb-0">Noch keine Auswertungen vorhanden.</p>
        <p class="text-caption text-medium-emphasis mb-0">{{ userStore.globalRole === 'ADMIN' ? 'Starte eine Auswertung über den Task-Header.' : 'Hier erscheint dein automatisch erzeugtes Feedback.' }}</p>
      </div>
      <v-list v-else density="compact" nav class="pa-0">
        <template v-for="({ evaluation, summary }, index) in navigationEntries" :key="evaluation.id">
          <v-list-item :active="selectedId === evaluation.id" class="evaluation-item" @click="openDetail(evaluation.id)">
            <template #prepend
              ><v-icon size="20" :color="evaluation.state === 'succeeded' && !showServiceView ? 'primary' : stateColor(evaluation.state)" aria-hidden="true">{{ evaluation.state === 'succeeded' && !showServiceView ? 'mdi-comment-text-outline' : stateIcon(evaluation.state) }}</v-icon></template
            >
            <template #title>
              <div class="d-flex align-center ga-2">
                <span class="evaluation-item__name" :title="showServiceView ? evaluation.workflow.name : feedbackTitle">{{ showServiceView ? evaluation.workflow.name : feedbackTitle }}</span>
                <span v-if="isPolling && selectedId === evaluation.id" class="live-dot" title="Wird live aktualisiert" />
              </div>
            </template>
            <template #subtitle>
              <span v-if="showServiceView || evaluation.state !== 'succeeded'" class="evaluation-item__status" :class="{ 'text-error': evaluation.state === 'failed', 'text-warning': evaluation.state === 'cancelled' }">{{ showServiceView ? stateLabel(evaluation.state) : studentStateLabel(evaluation.state) }}</span>
              <span v-if="evaluation.state === 'succeeded'" class="evaluation-item__summary">{{ summary }}</span>
              <span class="evaluation-item__meta" :title="absoluteTime(evaluation.startedAt)">{{ relativeTime(evaluation.startedAt) }}</span>
            </template>
          </v-list-item>
          <v-divider v-if="index < evaluations.length - 1" />
        </template>
      </v-list>
    </div>

    <div v-else class="evaluation-sidebar__body pa-2">
      <template v-if="detailLoading && !current">
        <v-skeleton-loader type="list-item-three-line" />
        <v-skeleton-loader type="list-item-three-line" class="mt-2" />
      </template>
      <v-alert v-else-if="detailError" type="error" density="compact" variant="tonal" class="evaluation-load-error">
        {{ detailError }}
        <template #append><v-btn size="x-small" variant="text" @click="reload">Erneut versuchen</v-btn></template>
      </v-alert>
      <template v-else-if="current">
        <v-btn-toggle v-if="canViewService" v-model="selectedPerspective" mandatory divided density="compact" variant="outlined" color="primary" class="evaluation-perspective mb-3" aria-label="Auswertungsansicht">
          <v-btn value="service" size="small">Service</v-btn>
          <v-btn value="student" size="small">Studierende</v-btn>
        </v-btn-toggle>

        <div class="d-flex flex-wrap align-center ga-2">
          <v-chip v-if="showServiceView" :color="stateColor(current.state)" size="small" variant="tonal" label class="evaluation-run-status" aria-label="Technischer Workflowstatus"
            ><v-icon start size="14">{{ stateIcon(current.state) }}</v-icon
            >{{ stateLabel(current.state) }}</v-chip
          >
          <span v-if="showServiceView && isPolling" class="live-dot" title="Wird live aktualisiert" />
          <v-spacer />
          <span class="text-caption text-medium-emphasis" :title="absoluteTime(current.startedAt)">{{ relativeTime(current.startedAt) }}</span>
        </div>

        <v-divider class="my-2" />

        <v-alert v-if="showServiceView && detail?.workflow.labels.phase === '4'" type="info" density="compact" variant="tonal" class="mb-2">
          Zwischenergebnisse bis Phase 4: Graphen, Elementinventare und semantische Kandidaten je Musterlösung.
        </v-alert>
        <v-alert v-else-if="showServiceView && detail?.workflow.labels.phase === '5'" type="info" density="compact" variant="tonal" class="mb-2">
          Vorläufiger Vergleich je Musterlösung. Eine vollständige strukturelle Bewertung liegt noch nicht vor.
        </v-alert>

        <div v-if="!terminal(current.state)" class="evaluation-progress mt-2">
          <div class="d-flex align-center justify-space-between text-caption text-medium-emphasis mb-1">
            <span>Durchlauffortschritt</span>
            <span v-if="showServiceView && detail">{{ doneStepCount }} / {{ detail.steps.length }} Schritte</span>
          </div>
          <v-progress-linear :model-value="progressPercent" :indeterminate="!showServiceView" height="6" rounded color="info" aria-label="Fortschritt des Auswertungsdurchlaufs" />
        </div>

        <v-select v-if="showServiceView && referenceOptions.length > 1" v-model="referenceKey" :items="referenceOptions" item-title="label" item-value="key" label="Musterlösung" density="compact" variant="outlined" hide-details class="mt-3" />

        <v-tabs v-if="showServiceView" v-model="serviceTab" density="compact" grow color="primary" class="evaluation-tabs mt-2">
          <v-tab value="overview">Überblick</v-tab>
          <v-tab value="findings">Befunde</v-tab>
          <v-tab value="feedback">Feedback</v-tab>
          <v-tab value="technical">Technik</v-tab>
        </v-tabs>

        <v-alert v-if="!showServiceView && feedback?.state !== 'succeeded'" :type="current.state === 'failed' ? 'error' : current.state === 'cancelled' ? 'warning' : 'info'" density="compact" variant="tonal" class="mt-3" :title="studentStateLabel(current.state)" aria-live="polite">
          <p class="text-caption text-medium-emphasis mb-0">{{ studentResultMessage }}</p>
        </v-alert>

        <!-- Learners see exactly what the completion check shows: percentages and, in learning paths, the thresholds. -->
        <section v-if="!showServiceView && feedback?.state === 'succeeded' && !hasCheckFeedback" class="my-3" aria-label="Dein Ergebnis" aria-live="polite">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <h3 class="text-body-2 font-weight-medium">Dein Ergebnis</h3>
            <v-spacer />
            <v-chip v-if="studentGate?.gated" :color="studentGate.passed ? 'success' : 'warning'" size="small" variant="tonal" label class="evaluation-result-status">{{ studentGate.passed ? 'Abgabebereit' : 'Noch nicht abgabebereit' }}</v-chip>
          </div>
          <CompletionGateBars v-if="studentGate" :result="studentGate" dense />
          <p v-else class="text-caption text-medium-emphasis">{{ studentResultMessage }}</p>
        </section>
        <section v-if="!showServiceView && feedback?.state === 'succeeded' && feedback.feedback?.length" class="my-3" aria-label="Dein Hilfe-Feedback">
          <h3 class="text-body-2 font-weight-medium mb-2">Dein Hilfe-Feedback</h3>
          <FeedbackView :entries="feedback.feedback" />
        </section>

        <section v-if="showServiceView && serviceTab === 'overview'" class="my-3" aria-label="Erkennungsübersicht" aria-live="polite">
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
          <p v-else class="text-caption text-medium-emphasis">Für diese Auswertung und Musterlösung ist noch keine Erkennungsübersicht verfügbar.</p>
        </section>

        <AnalyticalFeedbackPanel v-if="showServiceView && detail" v-model:reference-key="referenceKey" v-model:tab="serviceTab" :detail="detail" @feedback-object="id => catalogFocus = { id, seq: (catalogFocus?.seq ?? 0) + 1 }" />

        <FeedbackCatalogPanel v-if="showServiceView && detail && serviceTab === 'feedback'" :detail="detail" :reference-key="referenceKey" :focus="catalogFocus" />

        <div v-if="showServiceView && detail && serviceTab === 'technical'" class="mt-3">
        <p class="text-caption text-medium-emphasis mb-2">Auswertungsparameter: {{ parameterSummary }}</p>
        <v-timeline density="compact" side="end" truncate-line="both" class="evaluation-timeline">
          <v-timeline-item v-for="entry in timelineEntries" :key="entry.id" :dot-color="entry.color" size="x-small">
            <template #icon
              ><v-icon size="12" color="white">{{ entry.icon }}</v-icon></template
            >
            <div class="text-body-2 font-weight-medium">{{ entry.title }}</div>
            <div v-if="entry.resultSummary" class="result-summary mt-1">{{ entry.resultSummary }}</div>
            <div v-else-if="entry.description" class="text-caption text-medium-emphasis mt-1">{{ entry.description }}</div>
            <div v-if="entry.comparison" class="text-caption mt-1">
              <div>Vorläufige Anker: {{ entry.comparison.anchors }} / {{ entry.comparison.references }} ({{ entry.comparison.coverage }})</div>
              <div>Maximal zuordenbar: {{ entry.comparison.capacity }} / {{ entry.comparison.references }} ({{ entry.comparison.capacityBound }})</div>
              <div v-if="entry.comparison.owners">{{ entry.comparison.ownerLabel }}: {{ entry.comparison.owners }}</div>
              <div class="text-medium-emphasis">Keine bestätigte Modellübereinstimmung.</div>
            </div>
            <JsonResultViewer :data="entry.result ?? { title: entry.title, description: entry.description ?? null, resultSummary: entry.resultSummary ?? null }" class="mt-1">
              <template #actions>
                <SemanticComparisonViewer v-if="semanticComparisonResult(entry.result)" :result="semanticComparisonResult(entry.result)!" />
              </template>
            </JsonResultViewer>
            <v-btn
              v-if="terminal(detail.state) && entry.id === timelineEntries[timelineEntries.length - 1]?.id"
              class="mt-2"
              size="small"
              variant="tonal"
              prepend-icon="mdi-download"
              :loading="exporting"
              :disabled="exporting"
              @click="downloadRun"
            >Run als ZIP herunterladen</v-btn>
          </v-timeline-item>
        </v-timeline>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ApiId, JsonObject } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail, EvaluationFeedback, EvaluationOutcome } from '@/services/api/types/evaluation'
import evaluationService from '@/services/evaluation/evaluation.service'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { useUserStore } from '@/stores/userStore'
import JsonResultViewer from './JsonResultViewer.vue'
import SemanticComparisonViewer from './SemanticComparisonViewer.vue'
import AnalyticalFeedbackPanel from './AnalyticalFeedbackPanel.vue'
import FeedbackView from '@/components/feedback/FeedbackView.vue'
import FeedbackCatalogPanel from './FeedbackCatalogPanel.vue'
import { semanticComparisonResult } from '@/utils/semanticComparison'
import CompletionGateBars from '@/components/learningPaths/CompletionGateBars.vue'
import { completionGate, type GateResult } from '@/utils/completionGate'
import { useModelFileContext } from '@/composables/useModelFileContext'
import { adaptRecognition, analysisCategories, analysisValueLabel, categoryLabels, recognitionReportsFromEvaluation, type RecognitionCount } from '@/utils/analysisFeedback'

const props = defineProps<{ modelId: ApiId | null; openEvaluationId?: ApiId | null; evaluationPerspective?: 'service' | 'student' }>()
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationOutcome]; 'service-detail-opened': [] }>()
const userStore = useUserStore()
const selectedPerspective = ref<'service' | 'student'>('service')
const canViewService = computed(() => userStore.globalRole === 'ADMIN' || userStore.globalRole === 'MODERATOR')
const showServiceView = computed(() => canViewService.value && selectedPerspective.value === 'service')
const view = ref<'list' | 'detail'>('list')
const evaluations = ref<Evaluation[]>([])
// Service view: full run (moderators/admins only). Student view: the learner feedback endpoint, exactly what learners receive.
const detail = ref<EvaluationDetail | null>(null)
const feedback = ref<EvaluationFeedback | null>(null)
const current = computed(() => showServiceView.value
  ? detail.value && { state: detail.value.state, startedAt: detail.value.startedAt, name: detail.value.workflow.name }
  : feedback.value && { state: feedback.value.state, startedAt: feedback.value.startedAt, name: feedback.value.workflowName })
const referenceKey = ref('')
const recognitionState = computed(() => {
  try {
    if (!showServiceView.value) return { reports: feedback.value?.recognitions.map(({ referenceKey, recognition }) => ({ referenceKey, recognition: adaptRecognition(recognition) })) ?? [], error: null }
    return { reports: detail.value ? recognitionReportsFromEvaluation(detail.value) : [], error: null }
  }
  catch { return { reports: [], error: 'Die Erkennungsübersicht hat ein ungültiges Format.' } }
})
const recognitionOptions = computed(() => recognitionState.value.reports.map((report, index) => ({ key: report.referenceKey, label: `Musterlösung ${index + 1}` })))
// Reference model names are only shown to roles that may see analysis data.
const analyticalOptions = computed(() => showServiceView.value && detail.value ? detail.value.steps.filter(step => step.id.startsWith('generate_analytical_feedback_')).map(step => ({
  key: step.id.slice('generate_analytical_feedback_'.length), label: step.label.replace(/^Analytisches Feedback:\s*/, '')
})) : [])
const referenceOptions = computed(() => analyticalOptions.value.length ? analyticalOptions.value : recognitionOptions.value)
watch([referenceOptions, () => detail.value?.id ?? feedback.value?.id],([options, evaluationId], [, previousId]) => {
  if (evaluationId !== previousId || !options.some(option => option.key === referenceKey.value)) referenceKey.value = options[0]?.key ?? ''
}, { immediate: true })
const catalogFocus = ref<{ id: string; seq: number } | null>(null)
const serviceTab = ref<'overview' | 'findings' | 'feedback' | 'technical'>('overview')
const selectedRecognition = computed(() => recognitionState.value.reports.find(report => report.referenceKey === referenceKey.value))
const recognitionRows = computed(() => selectedRecognition.value ? [
  { key: 'overall', label: 'Insgesamt', row: selectedRecognition.value.recognition.overall },
  ...(selectedRecognition.value.recognition.buckets?.map(row => ({ key: row.id, label: row.label, row })) ??
    analysisCategories.map(key => ({ key, label: categoryLabels[key], row: selectedRecognition.value!.recognition.categories![key] })))
] : [])
const files = useModelFileContext()
const feedbackTitle = computed(() => files?.completionGate.value?.minimumScorePercent != null ? 'Abgabeprüfung' : 'Modellfeedback')
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
const navigationEntries = computed(() => evaluations.value.map(evaluation => ({
  evaluation,
  summary: evaluation.feedback ? feedbackSummary(evaluation.feedback, gateFor(evaluation.feedback)) : 'Feedback öffnen'
})))
const unmatchedCount = computed(() => selectedRecognition.value?.recognition.unmatchedSubmission.length ?? 0)
const recognitionPercent = (row: RecognitionCount) => row.percent === null ? 'nicht bestimmbar' : `${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(row.percent)} %`
const selectedId = ref<ApiId | null>(null)
const loading = ref(false)
const detailLoading = ref(false)
const listError = ref<string | null>(null)
const detailError = ref<string | null>(null)
const isPolling = ref(false)
const exporting = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollingGeneration = 0

const terminal = (state: string) => ['succeeded', 'failed', 'cancelled'].includes(state)
const stateLabel = (state: string) => ({ queued: 'Workflow wartet auf Start', running: 'Workflow läuft', succeeded: 'Workflow erfolgreich durchgelaufen', failed: 'Workflow fehlgeschlagen', cancelled: 'Workflow abgebrochen', unknown: 'Workflowstatus unklar' })[state] ?? state
const studentStateLabel = (state: string) => ({ queued: 'Auswertung wartet auf Start', running: 'Modell wird ausgewertet', failed: 'Auswertung fehlgeschlagen', cancelled: 'Auswertung abgebrochen', unknown: 'Status der Auswertung unklar' })[state] ?? state
const stateIcon = (state: string) => (state === 'succeeded' ? 'mdi-check-circle' : state === 'running' ? 'mdi-progress-clock' : state === 'failed' ? 'mdi-close-circle' : state === 'cancelled' ? 'mdi-cancel' : state === 'queued' ? 'mdi-clock-outline' : 'mdi-help-circle-outline')
const stateColor = (state: string) => (state === 'succeeded' ? 'success' : state === 'running' ? 'info' : state === 'failed' ? 'error' : state === 'cancelled' ? 'warning' : undefined)

const rtf = new Intl.RelativeTimeFormat('de', { numeric: 'auto' })
const relativeTime = (iso: string) => {
  const diffMinutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000)
  if (Math.abs(diffMinutes) < 60) return rtf.format(diffMinutes, 'minute')
  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, 'hour')
  return rtf.format(Math.round(diffHours / 24), 'day')
}
const absoluteTime = (iso: string) => new Date(iso).toLocaleString()

const parameterSummary = computed(() => {
  const parameters = detail.value?.parameters as Record<string, unknown> | undefined
  // Runs started before the tier-only workflow recorded a Levenshtein threshold.
  if (parameters && 'levenshteinThreshold' in parameters) return 'Älterer Lauf mit früherem Textvergleich'
  const values = detail.value?.parameters?.textEvidence
  if (!values || typeof values !== 'object') return 'Evidenzstufen mit Standardwerten'
  const number = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 3 })
  return `Evidenzstufen: Schreibvariante ≥ ${number.format(values.spelling)}, Bedeutung ≥ ${number.format(values.meaning)}, Graubereich ab ${number.format(values.meaningFloor)}`
})
const doneStepCount = computed(() => (detail.value ? detail.value.steps.filter((step) => step.status === 'succeeded' || step.status === 'failed').length : 0))
const progressPercent = computed(() => {
  return detail.value && detail.value.steps.length ? (doneStepCount.value / detail.value.steps.length) * 100 : 0
})
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

interface TimelineEntry {
  id: string
  icon: string
  color?: string
  title: string
  description?: string | null
  resultSummary?: string | null
  result?: JsonObject | null
  comparison?: { anchors: number; references: number; coverage: string; capacity: number; capacityBound: string; owners?: string; ownerLabel?: string }
}
const jsonObject = (value: unknown): JsonObject | undefined =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : undefined
const percent = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value)
    ? new Intl.NumberFormat('de-DE', { style: 'percent', maximumFractionDigits: 1 }).format(value)
    : 'nicht bestimmbar'
const comparisonSummary = (result: JsonObject | null | undefined): TimelineEntry['comparison'] => {
  if (result?.schema !== 'reference-comparison/v1') return undefined
  const metrics = jsonObject(result.metrics)
  const overall = jsonObject(metrics?.overall)
  if (!overall || typeof overall.referenceCount !== 'number' || typeof overall.provisionalAnchorCount !== 'number' ||
      typeof overall.maximumAssignableCount !== 'number') return undefined
  const containment = jsonObject(metrics?.provisionalContainment)
  const containmentAgreement = jsonObject(containment?.agreement)
  const hasContainment = containment && containmentAgreement &&
    typeof containment.satisfied === 'number' && typeof containment.violated === 'number' &&
    typeof containment.unresolved === 'number' && typeof containment.referenceRelationCount === 'number'
  const owner = jsonObject(metrics?.provisionalOwnerConsistency)
  const ownerAgreement = jsonObject(owner?.agreement)
  const hasOwner = owner && ownerAgreement && typeof owner.satisfied === 'number' && typeof owner.expected === 'number'
  return {
    anchors: overall.provisionalAnchorCount,
    references: overall.referenceCount,
    coverage: percent(overall.anchorCoverage),
    capacity: overall.maximumAssignableCount,
    capacityBound: percent(overall.capacityUpperBound),
    owners: hasContainment
      ? `${percent(containmentAgreement.lower)} – ${percent(containmentAgreement.upper)} (${containment.satisfied} / ${containment.referenceRelationCount}, ${containment.violated} abweichend, ${containment.unresolved} offen)`
      : hasOwner
        ? `${percent(ownerAgreement.lower)} – ${percent(ownerAgreement.upper)} (${owner.satisfied} / ${owner.expected})`
        : undefined,
    ownerLabel: hasContainment ? 'Zugehörigkeitskonsistenz (vorläufig)' : 'Zugehörigkeitskonsistenz (nur zugeordnete Elemente)'
  }
}
const timelineEntries = computed<TimelineEntry[]>(() => {
  if (!detail.value) return []
  const entries: TimelineEntry[] = detail.value.steps.map((step) => ({
    id: step.id,
    icon: stateIcon(step.status),
    color: stateColor(step.status),
    title: step.label,
    description: step.description,
    resultSummary: step.resultSummary,
    result: step.result,
    comparison: comparisonSummary(step.result)
  }))
  if (detail.value.finalResult) {
    entries.push({ id: '__final__', icon: 'mdi-flag-checkered', color: 'info', title: detail.value.workflow.labels.phase === '4' ? 'Ergebnisübersicht bis Phase 4' : detail.value.workflow.labels.phase === '5' ? 'Vorläufige Ergebnisübersicht' : 'Endergebnis', result: detail.value.finalResult, comparison: comparisonSummary(detail.value.finalResult) })
  } else if (detail.value.state === 'failed' || detail.value.state === 'cancelled') {
    entries.push({ id: '__outcome__', icon: 'mdi-alert', color: 'error', title: detail.value.state === 'failed' ? 'Fehlgeschlagen' : 'Abgebrochen', description: 'Workflow wurde nicht erfolgreich abgeschlossen.' })
  }
  return entries
})

// Non-structural outcome: surface once via toast instead of a permanent panel.
const notifiedNoResultIds = new Set<ApiId>()
watch(detail, (value) => {
  if (showServiceView.value && value && value.state === 'succeeded' && !value.finalResult && !notifiedNoResultIds.has(value.id)) {
    notifiedNoResultIds.add(value.id)
    notifySuccess('Workflow erfolgreich durchgelaufen; es wurde kein strukturiertes Endergebnis geliefert.')
  }
})

const stopPolling = () => {
  pollingGeneration += 1
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
  isPolling.value = false
}

const loadList = async () => {
  if (!props.modelId) return
  loading.value = true
  listError.value = null
  try {
    evaluations.value = (await evaluationService.list(props.modelId)).data.items
  } catch {
    listError.value = 'Auswertungen konnten nicht geladen werden.'
  } finally {
    loading.value = false
  }
}

const refreshDetail = async () => {
  const id = selectedId.value
  if (!id) return
  const service = showServiceView.value
  const result = service ? (await evaluationService.get(id)).data : (await evaluationService.getFeedback(id)).data
  if (selectedId.value !== id || service !== showServiceView.value) return
  if (service) detail.value = result as EvaluationDetail
  else feedback.value = result as EvaluationFeedback
  const index = evaluations.value.findIndex((item) => item.id === id)
  if (index >= 0) evaluations.value[index] = {
    ...evaluations.value[index], state: result.state,
    feedback: service ? (result as EvaluationDetail).feedback ?? evaluations.value[index].feedback : result as EvaluationFeedback
  }
  emit('evaluation-updated', result)
}

const poll = async (generation: number) => {
  if (generation !== pollingGeneration) return
  try {
    await refreshDetail()
    detailError.value = null
  } catch {
    detailError.value = 'Auswertung konnte nicht aktualisiert werden.'
    stopPolling()
    return
  }
  if (generation === pollingGeneration) {
    if (current.value && !terminal(current.value.state)) pollTimer = setTimeout(() => void poll(generation), 2_000)
    else stopPolling()
  }
}

const open = async (id: ApiId) => {
  stopPolling()
  if (selectedId.value !== id) {
    detail.value = null
    feedback.value = null
    serviceTab.value = 'overview'
  }
  selectedId.value = id
  detailLoading.value = true
  detailError.value = null
  try {
    await refreshDetail()
    if (current.value && !terminal(current.value.state)) {
      isPolling.value = true
      pollingGeneration += 1
      pollTimer = setTimeout(() => void poll(pollingGeneration), 2_000)
    }
  } catch {
    detailError.value = 'Auswertung konnte nicht geladen werden.'
  } finally {
    detailLoading.value = false
  }
}

const openDetail = async (id: ApiId) => {
  view.value = 'detail'
  await open(id)
}

const reload = async () => {
  if (selectedId.value) await open(selectedId.value)
}

const downloadRun = async () => {
  const evaluationId = detail.value?.id
  if (!evaluationId || exporting.value) return
  exporting.value = true
  try {
    const { data } = await evaluationService.downloadArchive(evaluationId)
    const url = URL.createObjectURL(data)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = `evaluation-${evaluationId}.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch {
    notifyError('Der Run konnte nicht als ZIP heruntergeladen werden. Bitte versuche es erneut.')
  } finally {
    exporting.value = false
  }
}

watch(
  () => props.modelId,
  async () => {
    stopPolling()
    detail.value = null
    feedback.value = null
    selectedId.value = null
    view.value = 'list'
    await loadList()
  },
  { immediate: true }
)
watch(
  () => [props.openEvaluationId, props.evaluationPerspective] as const,
  async ([id, perspective]) => {
    if (id) {
      selectedPerspective.value = perspective ?? 'service'
      await openDetail(id)
    }
  },
  { immediate: true }
)
// Each perspective loads from its own endpoint.
watch(showServiceView, () => { if (view.value === 'detail') void reload() })
// Widen once per opened admin detail; the user may shrink it again afterwards.
watch(() => view.value === 'detail' && showServiceView.value && selectedId.value, (opened) => { if (opened) emit('service-detail-opened') }, { immediate: true })
onMounted(() => {
  void userStore.ensureGlobalRole()
  window.addEventListener('beforeunload', stopPolling)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', stopPolling)
  stopPolling()
})
</script>

<style scoped>
.evaluation-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  /* The sidebar frame disables selection; findings must stay copyable. */
  user-select: text;
}
.evaluation-sidebar__toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
  flex-shrink: 0;
}
.evaluation-sidebar__toolbar-title {
  font-size: 0.75rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evaluation-sidebar__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.evaluation-perspective {
  display: flex;
  width: 100%;
}
.evaluation-perspective > .v-btn {
  flex: 1;
  min-width: 0;
}
.evaluation-load-error :deep(.v-alert__append) {
  grid-column: 2 / -1;
  grid-row: 2;
  margin-inline-start: 0;
  margin-top: 8px;
}
.evaluation-skeleton {
  margin: 4px 8px;
}
.evaluation-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 16px;
}
.evaluation-item {
  min-height: 40px;
  padding-top: 4px;
  padding-bottom: 4px;
}
.evaluation-item :deep(.v-list-item-subtitle) {
  -webkit-line-clamp: unset;
  opacity: 1;
}
.evaluation-item__status,
.evaluation-item__summary {
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
  font-size: 0.75rem;
  line-height: 1.5;
}
.evaluation-item__summary {
  color: rgb(var(--v-theme-on-surface));
}
.evaluation-run-status,
.evaluation-result-status {
  height: auto;
  min-height: 26px;
  white-space: normal;
}
.evaluation-run-status :deep(.v-chip__content),
.evaluation-result-status :deep(.v-chip__content) {
  white-space: normal;
}
.evaluation-item__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.evaluation-item__meta {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.7rem;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.evaluation-timeline.v-timeline {
  grid-template-columns: 0 min-content minmax(0, 1fr);
}
.evaluation-timeline :deep(.v-timeline-item__body) {
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  padding-block-end: 8px;
}
.result-summary {
  white-space: pre-wrap;
  font-size: 0.75rem;
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgb(var(--v-theme-info));
  flex-shrink: 0;
  animation: evaluation-live-pulse 1.4s ease-in-out infinite;
}
@keyframes evaluation-live-pulse {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 0 0 rgba(var(--v-theme-info), 0.5);
  }
  50% {
    opacity: 0.6;
    box-shadow: 0 0 0 4px rgba(var(--v-theme-info), 0);
  }
}
</style>
