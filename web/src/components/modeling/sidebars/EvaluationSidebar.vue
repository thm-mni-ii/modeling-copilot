<template>
  <div class="evaluation-sidebar">
    <div class="evaluation-sidebar__toolbar">
      <v-btn v-if="view === 'detail'" icon size="x-small" variant="text" title="Zurück zur Liste" @click="view = 'list'">
        <v-icon size="18">mdi-arrow-left</v-icon>
      </v-btn>
      <span v-if="view === 'detail' && detail" class="evaluation-sidebar__toolbar-title">{{ detail.workflow.name }}</span>
      <span v-else class="text-caption text-medium-emphasis">{{ evaluations.length ? `${evaluations.length} Auswertung(en)` : '\u00A0' }}</span>
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
        <template v-for="(evaluation, index) in evaluations" :key="evaluation.id">
          <v-list-item :active="selectedId === evaluation.id" class="evaluation-item" @click="openDetail(evaluation.id)">
            <template #prepend
              ><v-icon size="20" :color="stateColor(evaluation.state)">{{ stateIcon(evaluation.state) }}</v-icon></template
            >
            <template #title>
              <div class="d-flex align-center ga-2">
                <span class="evaluation-item__name">{{ evaluation.workflow.name }}</span>
                <span v-if="isPolling && selectedId === evaluation.id" class="live-dot" title="Wird live aktualisiert" />
              </div>
            </template>
            <template #subtitle>
              <span class="evaluation-item__meta" :title="absoluteTime(evaluation.startedAt)">{{ relativeTime(evaluation.startedAt) }}</span>
            </template>
          </v-list-item>
          <v-divider v-if="index < evaluations.length - 1" />
        </template>
      </v-list>
    </div>

    <div v-else class="evaluation-sidebar__body pa-2">
      <template v-if="detailLoading && !detail">
        <v-skeleton-loader type="list-item-three-line" />
        <v-skeleton-loader type="list-item-three-line" class="mt-2" />
      </template>
      <v-alert v-else-if="detailError" type="error" density="compact" variant="tonal" class="evaluation-load-error">
        {{ detailError }}
        <template #append><v-btn size="x-small" variant="text" @click="reload">Erneut versuchen</v-btn></template>
      </v-alert>
      <template v-else-if="detail">
        <v-btn-toggle v-if="canViewService" v-model="selectedPerspective" mandatory divided density="compact" variant="outlined" color="primary" class="evaluation-perspective mb-3" aria-label="Auswertungsansicht">
          <v-btn value="service" size="small">Service</v-btn>
          <v-btn value="student" size="small">Studierende</v-btn>
        </v-btn-toggle>

        <div class="d-flex align-center ga-2">
          <v-chip :color="stateColor(detail.state)" size="small" variant="tonal" label aria-label="Status des Auswertungsdurchlaufs"
            ><v-icon start size="14">{{ stateIcon(detail.state) }}</v-icon
            >{{ stateLabel(detail.state) }}</v-chip
          >
          <span v-if="isPolling" class="live-dot" title="Wird live aktualisiert" />
          <v-spacer />
          <span class="text-caption text-medium-emphasis" :title="absoluteTime(detail.startedAt)">{{ relativeTime(detail.startedAt) }}</span>
        </div>

        <v-divider class="my-2" />

        <v-alert v-if="showServiceView && detail.workflow.labels.phase === '4'" type="info" density="compact" variant="tonal" class="mb-2">
          Zwischenergebnisse bis Phase 4: Graphen, Elementinventare und semantische Kandidaten je Musterlösung.
        </v-alert>
        <v-alert v-else-if="showServiceView && detail.workflow.labels.phase === '5'" type="info" density="compact" variant="tonal" class="mb-2">
          Vorläufiger Vergleich je Musterlösung. Eine vollständige strukturelle Bewertung liegt noch nicht vor.
        </v-alert>

        <div class="evaluation-progress">
          <div class="d-flex align-center justify-space-between text-caption text-medium-emphasis mb-1">
            <span>Durchlauffortschritt</span>
            <span v-if="showServiceView">{{ doneStepCount }} / {{ detail.steps.length }} Schritte</span>
            <span v-else>{{ Math.round(progressPercent) }} %</span>
          </div>
          <v-progress-linear :model-value="progressPercent" height="6" rounded color="info" aria-label="Fortschritt des Auswertungsdurchlaufs" />
        </div>

        <v-divider class="my-2" />

        <section v-if="!showServiceView" aria-label="Ergebnis der Auswertung" aria-live="polite">
          <h3 class="text-body-2 font-weight-medium mb-2">Dein Ergebnis</h3>
          <p class="text-caption text-medium-emphasis mb-0">{{ studentResultMessage }}</p>
        </section>

        <v-timeline v-else density="compact" side="end" truncate-line="both" class="evaluation-timeline">
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
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ApiId, JsonObject } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail } from '@/services/api/types/evaluation'
import evaluationService from '@/services/evaluation/evaluation.service'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { useUserStore } from '@/stores/userStore'
import JsonResultViewer from './JsonResultViewer.vue'
import SemanticComparisonViewer from './SemanticComparisonViewer.vue'
import { semanticComparisonResult } from '@/utils/semanticComparison'

const props = defineProps<{ modelId: ApiId | null; openEvaluationId?: ApiId | null; evaluationPerspective?: 'service' | 'student' }>()
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationDetail] }>()
const userStore = useUserStore()
const selectedPerspective = ref<'service' | 'student'>('service')
const canViewService = computed(() => userStore.globalRole === 'ADMIN' || userStore.globalRole === 'MODERATOR')
const showServiceView = computed(() => canViewService.value && selectedPerspective.value === 'service')
const view = ref<'list' | 'detail'>('list')
const evaluations = ref<Evaluation[]>([])
const detail = ref<EvaluationDetail | null>(null)
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
const stateLabel = (state: string) => ({ queued: 'Wartet', running: 'Läuft', succeeded: 'Abgeschlossen', failed: 'Fehlgeschlagen', cancelled: 'Abgebrochen', unknown: 'Status wird ermittelt' })[state] ?? state
const stateIcon = (state: string) => (state === 'succeeded' ? 'mdi-check-circle' : state === 'running' ? 'mdi-progress-clock' : state === 'failed' ? 'mdi-close-circle' : state === 'cancelled' ? 'mdi-cancel' : state === 'queued' ? 'mdi-clock-outline' : 'mdi-help-circle-outline')
const stateColor = (state: string) => (state === 'succeeded' || state === 'running' ? 'info' : state === 'failed' ? 'error' : state === 'cancelled' ? 'warning' : undefined)

const rtf = new Intl.RelativeTimeFormat('de', { numeric: 'auto' })
const relativeTime = (iso: string) => {
  const diffMinutes = Math.round((new Date(iso).getTime() - Date.now()) / 60_000)
  if (Math.abs(diffMinutes) < 60) return rtf.format(diffMinutes, 'minute')
  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) return rtf.format(diffHours, 'hour')
  return rtf.format(Math.round(diffHours / 24), 'day')
}
const absoluteTime = (iso: string) => new Date(iso).toLocaleString()

const doneStepCount = computed(() => (detail.value ? detail.value.steps.filter((step) => step.status === 'succeeded' || step.status === 'failed').length : 0))
const progressPercent = computed(() => {
  if (!showServiceView.value && detail.value?.state === 'succeeded') return 100
  return detail.value && detail.value.steps.length ? (doneStepCount.value / detail.value.steps.length) * 100 : 0
})
const studentResultMessage = computed(() => {
  switch (detail.value?.state) {
    case 'succeeded':
      if (detail.value.scorePercent != null) return `Dein Modell erreicht ${new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 }).format(detail.value.scorePercent)} %.`
      return 'Die Auswertung ist abgeschlossen. Eine Ergebnisanzeige für Studierende ist für diese Auswertung noch nicht eingerichtet.'
    case 'failed':
      return 'Die Auswertung ist fehlgeschlagen. Fordere erneut automatisch erzeugtes Feedback an oder versuche den Aufgabenabschluss erneut.'
    case 'cancelled':
      return 'Die Auswertung wurde abgebrochen. Fordere erneut automatisch erzeugtes Feedback an oder versuche den Aufgabenabschluss erneut.'
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
    notifySuccess('Workflow abgeschlossen; es wurde kein strukturiertes Endergebnis geliefert.')
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
  const result = (await evaluationService.get(id)).data
  if (selectedId.value !== id) return
  detail.value = result
  const index = evaluations.value.findIndex((item) => item.id === id)
  if (index >= 0) evaluations.value[index] = { ...evaluations.value[index], state: detail.value.state }
  emit('evaluation-updated', detail.value)
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
    if (detail.value && !terminal(detail.value.state)) pollTimer = setTimeout(() => void poll(generation), 2_000)
    else stopPolling()
  }
}

const open = async (id: ApiId) => {
  stopPolling()
  if (selectedId.value !== id) detail.value = null
  selectedId.value = id
  detailLoading.value = true
  detailError.value = null
  try {
    await refreshDetail()
    if (detail.value && !terminal(detail.value.state)) {
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
