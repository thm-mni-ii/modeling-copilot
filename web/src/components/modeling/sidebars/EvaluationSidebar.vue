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
      <v-alert v-else-if="listError" type="error" density="compact" variant="tonal" class="ma-3">
        {{ listError }}
        <template #append><v-btn size="x-small" variant="text" @click="loadList">Erneut versuchen</v-btn></template>
      </v-alert>
      <div v-else-if="!evaluations.length" class="evaluation-empty">
        <v-icon size="40" color="medium-emphasis">mdi-chart-timeline-variant-shimmer</v-icon>
        <p class="text-caption text-medium-emphasis mt-2 mb-0">Noch keine Auswertungen vorhanden.</p>
        <p class="text-caption text-medium-emphasis mb-0">Starte eine Auswertung über den Task-Header.</p>
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
      <v-alert v-else-if="detailError" type="error" density="compact" variant="tonal">
        {{ detailError }}
        <template #append><v-btn size="x-small" variant="text" @click="reload">Erneut versuchen</v-btn></template>
      </v-alert>
      <template v-else-if="detail">
        <div class="d-flex align-center ga-2">
          <v-chip :color="stateColor(detail.state)" size="small" variant="tonal" label
            ><v-icon start size="14">{{ stateIcon(detail.state) }}</v-icon
            >{{ stateLabel(detail.state) }}</v-chip
          >
          <span v-if="isPolling" class="live-dot" title="Wird live aktualisiert" />
          <v-spacer />
          <span class="text-caption text-medium-emphasis" :title="absoluteTime(detail.startedAt)">{{ relativeTime(detail.startedAt) }}</span>
        </div>

        <v-divider class="my-2" />

        <div class="evaluation-progress">
          <div class="d-flex align-center justify-space-between text-caption text-medium-emphasis mb-1">
            <span>Fortschritt</span>
            <span>{{ doneStepCount }} / {{ detail.steps.length }} Schritte</span>
          </div>
          <v-progress-linear :model-value="progressPercent" height="6" rounded :color="stateColor(detail.state) ?? 'primary'" />
        </div>

        <v-divider class="my-2" />

        <v-timeline density="compact" side="end" truncate-line="both" class="evaluation-timeline">
          <v-timeline-item v-for="entry in timelineEntries" :key="entry.id" :dot-color="entry.color" size="x-small">
            <template #icon
              ><v-icon size="12" color="white">{{ entry.icon }}</v-icon></template
            >
            <div class="text-body-2 font-weight-medium">{{ entry.title }}</div>
            <div v-if="entry.resultSummary" class="result-summary mt-1">{{ entry.resultSummary }}</div>
            <div v-else-if="entry.description" class="text-caption text-medium-emphasis mt-1">{{ entry.description }}</div>
            <JsonResultViewer v-if="entry.result" :data="entry.result" class="mt-1" />
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
import { notifySuccess } from '@/composables/useNotifications'
import JsonResultViewer from './JsonResultViewer.vue'

const props = defineProps<{ modelId: ApiId | null; openEvaluationId?: ApiId | null }>()
const view = ref<'list' | 'detail'>('list')
const evaluations = ref<Evaluation[]>([])
const detail = ref<EvaluationDetail | null>(null)
const selectedId = ref<ApiId | null>(null)
const loading = ref(false)
const detailLoading = ref(false)
const listError = ref<string | null>(null)
const detailError = ref<string | null>(null)
const isPolling = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
let pollingGeneration = 0

const terminal = (state: string) => ['succeeded', 'failed', 'cancelled'].includes(state)
const stateLabel = (state: string) => ({ queued: 'Wartet', running: 'Läuft', succeeded: 'Erfolgreich', failed: 'Fehlgeschlagen', cancelled: 'Abgebrochen', unknown: 'Status wird ermittelt' })[state] ?? state
const stateIcon = (state: string) => (state === 'succeeded' ? 'mdi-check-circle' : state === 'running' ? 'mdi-progress-clock' : state === 'failed' ? 'mdi-close-circle' : state === 'cancelled' ? 'mdi-cancel' : state === 'queued' ? 'mdi-clock-outline' : 'mdi-help-circle-outline')
const stateColor = (state: string) => (state === 'succeeded' ? 'success' : state === 'running' ? 'primary' : state === 'failed' ? 'error' : state === 'cancelled' ? 'warning' : undefined)

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
const progressPercent = computed(() => (detail.value && detail.value.steps.length ? (doneStepCount.value / detail.value.steps.length) * 100 : 0))

interface TimelineEntry {
  id: string
  icon: string
  color?: string
  title: string
  description?: string | null
  resultSummary?: string | null
  result?: JsonObject | null
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
    result: step.result
  }))
  if (detail.value.finalResult) {
    entries.push({ id: '__final__', icon: 'mdi-flag-checkered', color: 'success', title: 'Endergebnis', result: detail.value.finalResult })
  } else if (detail.value.state === 'failed' || detail.value.state === 'cancelled') {
    entries.push({ id: '__outcome__', icon: 'mdi-alert', color: 'error', title: detail.value.state === 'failed' ? 'Fehlgeschlagen' : 'Abgebrochen', description: 'Workflow wurde nicht erfolgreich abgeschlossen.' })
  }
  return entries
})

// Non-structural outcome: surface once via toast instead of a permanent panel.
const notifiedNoResultIds = new Set<ApiId>()
watch(detail, (value) => {
  if (value && value.state === 'succeeded' && !value.finalResult && !notifiedNoResultIds.has(value.id)) {
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
  if (!selectedId.value) return
  detail.value = (await evaluationService.get(selectedId.value)).data
  const index = evaluations.value.findIndex((item) => item.id === selectedId.value)
  if (index >= 0) evaluations.value[index] = { ...evaluations.value[index], state: detail.value.state }
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
  () => props.openEvaluationId,
  async (id) => {
    if (id) await openDetail(id)
  }
)
onMounted(() => window.addEventListener('beforeunload', stopPolling))
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
.evaluation-timeline :deep(.v-timeline-item__body) {
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
  background: rgb(var(--v-theme-primary));
  flex-shrink: 0;
  animation: evaluation-live-pulse 1.4s ease-in-out infinite;
}
@keyframes evaluation-live-pulse {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 0 0 rgba(var(--v-theme-primary), 0.5);
  }
  50% {
    opacity: 0.6;
    box-shadow: 0 0 0 4px rgba(var(--v-theme-primary), 0);
  }
}
</style>
