<template>
  <div class="evaluation-sidebar">
    <div class="evaluation-sidebar__toolbar">
      <v-btn v-if="view === 'detail' && !historical" icon size="x-small" variant="text" title="Zurück zur Liste" @click="view = 'list'"><v-icon size="18">mdi-arrow-left</v-icon></v-btn>
      <span v-if="view === 'detail'" class="evaluation-sidebar__toolbar-title">{{ showServiceView ? current?.name ?? 'Auswertungsanalyse' : feedbackTitle }}</span>
      <span v-else class="text-caption text-medium-emphasis">{{ evaluations.length ? `${evaluations.length} ${evaluations.length === 1 ? 'Auswertung' : 'Auswertungen'}` : '\u00A0' }}</span>
      <v-spacer />
      <v-btn icon size="x-small" variant="text" title="Aktualisieren" :loading="view === 'list' ? loading : resultView?.loading" @click="view === 'list' ? loadList() : resultView?.reload()"><v-icon size="16">mdi-refresh</v-icon></v-btn>
    </div>
    <div v-if="userStore.loaded && canViewService" class="px-2 py-2 border-b flex-shrink-0">
      <v-btn-toggle v-model="perspective" mandatory divided rounded="lg" color="primary" variant="outlined" class="evaluation-perspectives" aria-label="Auswertungsansicht">
        <v-btn value="service" size="small" prepend-icon="mdi-magnify-scan">Analyse</v-btn>
        <v-btn value="student" size="small" prepend-icon="mdi-school-outline">Studenten</v-btn>
      </v-btn-toggle>
      <p class="text-caption text-medium-emphasis mt-2 mb-0">{{ showServiceView ? 'Geschützte Analyse für Administration und Moderation.' : 'Vorschau des regulären Studierendenfeedbacks.' }}</p>
    </div>
    <v-skeleton-loader v-if="!userStore.loaded" type="list-item-three-line" />
    <div v-else-if="view === 'list'" class="evaluation-sidebar__body">
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
      <template v-if="current && !historical && selectedId">
        <p class="text-caption mb-1">Feedback zum gespeicherten Modellstand · Auswertung vom {{ absoluteTime(current.startedAt) }}</p>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-timeline-clock-outline" class="mb-3" @click="historyDialog = true">Modellstand ansehen</v-btn>
      </template>
      <EvaluationAnalysis v-if="showServiceView && selectedId" :key="displayKey" ref="resultView" :evaluation-id="selectedId" @evaluation-updated="updateResult" />
      <EvaluationStudentFeedback v-else-if="selectedId" :key="displayKey" ref="resultView" :evaluation-id="selectedId" :historical="historical" :hint-request="hintRequest" @evaluation-updated="updateResult" />
    </div>
  </div>
  <ModelTimelineDialog v-if="userStore.loaded && !historical && historyDialog && current && selectedId" v-model="historyDialog" :target-version-id="current.submission.versionId" :target-evaluation-id="selectedId" :evaluation-perspective="selectedPerspective" />
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ApiId } from '@/services/api/types/common'
import type { Evaluation, EvaluationDetail, EvaluationFeedback, EvaluationOutcome } from '@/services/api/types/evaluation'
import evaluationService from '@/services/evaluation/evaluation.service'
import { useUserStore } from '@/stores/userStore'
import { useModelFileContext } from '@/composables/useModelFileContext'
import { completionGate, type GateResult } from '@/utils/completionGate'
import EvaluationStudentFeedback from './EvaluationStudentFeedback.vue'

const EvaluationAnalysis = defineAsyncComponent(() => import('./EvaluationAnalysis.vue'))
const ModelTimelineDialog = defineAsyncComponent(() => import('../versions/ModelTimelineDialog.vue'))
const props = defineProps<{ modelId: ApiId | null; openEvaluationId?: ApiId | null; evaluationPerspective?: 'service' | 'student'; historical?: boolean; hintRequest?: { evaluationId: string; cellId?: string; seq: number; noticeViewed?: boolean } | null }>()
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationOutcome]; 'service-detail-opened': [] }>()
const userStore = useUserStore()
const canViewService = computed(() => userStore.globalRole === 'ADMIN' || userStore.globalRole === 'MODERATOR')
const perspective = ref<'service' | 'student'>(props.evaluationPerspective ?? 'service')
const selectedPerspective = computed(() => canViewService.value ? perspective.value : 'student')
const showServiceView = computed(() => selectedPerspective.value === 'service')
const view = ref<'list' | 'detail'>('list')
const selectedId = ref<ApiId | null>(null)
const evaluations = ref<Evaluation[]>([])
// Navigation retains only common metadata; each dedicated display owns its result and requests.
const current = ref<(EvaluationOutcome & { startedAt: string; name: string }) | null>(null)
const resultView = ref<{ loading: boolean; reload: () => Promise<void> } | null>(null)
const displayKey = computed(() => `${props.modelId}:${userStore.userId}:${userStore.globalRole}:${selectedId.value}:${selectedPerspective.value}`)
const historyDialog = ref(false)
const loading = ref(false)
const listError = ref<string | null>(null)
const files = useModelFileContext()
const feedbackTitle = computed(() => files?.completionGate.value?.minimumScorePercent != null ? 'Abgabeprüfung' : 'Modellfeedback')
const gateFor = (value: EvaluationFeedback | null | undefined) => {
  try { return value ? completionGate(files?.completionGate.value ?? null, value) : null }
  catch { return null }
}
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
const updateResult = (value: EvaluationDetail | EvaluationFeedback) => {
  if (!userStore.loaded || value.id !== selectedId.value) return
  current.value = { id: value.id, state: value.state, submission: value.submission, scorePercent: value.scorePercent,
    startedAt: value.startedAt, name: 'workflow' in value ? value.workflow.name : feedbackTitle.value }
  const index = evaluations.value.findIndex(item => item.id === value.id)
  if (index >= 0) evaluations.value[index] = { ...evaluations.value[index], state: value.state,
    ...('recognitions' in value ? { feedback: value } : {}) }
  emit('evaluation-updated', value)
}
const openDetail = (id: ApiId) => {
  if (selectedId.value !== id) current.value = null
  selectedId.value = id
  view.value = 'detail'
}
watch(() => props.hintRequest, request => {
  if (!request || request.noticeViewed === false) return
  perspective.value = 'student'
  openDetail(request.evaluationId)
}, { immediate: true, flush: 'post' })
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

let listRequestToken = 0
const loadList = async () => {
  const token = ++listRequestToken
  const modelId = props.modelId, viewer = userStore.userId, role = userStore.globalRole
  if (!modelId || props.historical || !userStore.loaded) return
  loading.value = true
  listError.value = null
  try {
    const result = await evaluationService.listAll(modelId)
    if (token === listRequestToken && props.modelId === modelId && userStore.userId === viewer && userStore.globalRole === role) evaluations.value = result
  } catch {
    if (token === listRequestToken) listError.value = 'Auswertungen konnten nicht geladen werden.'
  } finally {
    if (token === listRequestToken) loading.value = false
  }
}
watch([() => props.modelId, () => props.openEvaluationId, canViewService, () => userStore.userId, () => userStore.loaded, () => props.evaluationPerspective],
  ([modelId, requestedId, service, viewer, ready, preferred], previous) => {
    listRequestToken++
    const movedModel = previous && modelId !== previous[0]
    const changedViewer = previous && viewer !== previous[3]
    const changedContext = !previous || movedModel || changedViewer || service !== previous[2] || ready !== previous[4]
    const wanted = (movedModel || changedViewer) && requestedId === previous?.[1]
      ? null : requestedId !== previous?.[1] ? requestedId : selectedId.value ?? requestedId
    if (changedContext) {
      evaluations.value = []
      selectedId.value = null
      current.value = null
      historyDialog.value = false
      view.value = 'list'
    }
    if (changedContext || requestedId !== previous?.[1] || preferred !== previous?.[5]) perspective.value = preferred ?? 'service'
    if (wanted) openDetail(wanted)
    void loadList()
  }, { immediate: true, flush: 'sync' })
watch([selectedPerspective, () => userStore.loaded], () => { current.value = null; historyDialog.value = false }, { flush: 'sync' })
watch(() => view.value === 'detail' && showServiceView.value && selectedId.value, opened => { if (opened) emit('service-detail-opened') }, { immediate: true })
onMounted(() => { void userStore.ensureGlobalRole() })
onBeforeUnmount(() => { listRequestToken++ })
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
.evaluation-perspectives { display: flex; width: 100%; }
.evaluation-perspectives.v-btn-group { height: 28px; }
.evaluation-perspectives :deep(.v-btn) { flex: 1; min-width: 0; }
</style>
