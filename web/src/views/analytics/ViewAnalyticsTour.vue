<template>
  <div>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/analytics/tours" class="mb-3">All tours</v-btn>
    <div class="d-flex flex-wrap align-start ga-3 mb-4">
      <div class="flex-grow-1 tour-heading">
        <div class="d-flex flex-wrap align-center ga-2">
          <h2 class="text-h5">{{ summary?.title ?? 'Tour' }}</h2>
          <v-chip v-if="summary" size="small" variant="tonal">Version {{ summary.version }}</v-chip>
        </div>
      </div>
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <section v-if="summary" class="kpis mb-4" aria-label="Key figures">
      <div v-for="kpi in kpis" :key="kpi.label" class="kpi">
        <span class="kpi-value">{{ kpi.value }}</span>
        <span class="kpi-label">{{ kpi.label }}</span>
        <span class="kpi-hint">{{ kpi.hint }}</span>
      </div>
    </section>
    <v-sheet v-if="summary" border rounded="lg" class="funnel-panel mb-4" aria-labelledby="tour-funnel-title">
      <div class="d-flex align-center ga-3 mb-4">
        <span class="section-icon"><v-icon size="21" color="info">mdi-filter-variant</v-icon></span>
        <div>
          <h2 id="tour-funnel-title" class="text-subtitle-1 font-weight-medium">Funnel by step</h2>
          <p class="text-caption text-medium-emphasis mb-0">How far people got. Bars show people who reached each step.</p>
        </div>
      </div>
      <div class="step-chart-list" tabindex="0" aria-label="Tour funnel, scroll for more steps">
        <div v-for="(step, index) in summary.steps" :key="step.id" class="step-row">
          <div class="step-label">
            <span class="step-number">{{ index + 1 }}</span>
            <span class="step-title text-body-2 font-weight-medium">{{ step.title }}</span>
            <v-chip v-if="step.biggestDropOff" size="x-small" color="warning" variant="tonal" prepend-icon="mdi-trending-down">Biggest drop-off</v-chip>
          </div>
          <div class="step-distribution">
            <div class="stat-bar" role="img" :aria-label="`${step.title}: ${step.reached} people reached this step`">
              <div class="stat-segment" :class="step.biggestDropOff ? 'stat-segment--drop' : 'stat-segment--reached'" :style="{ width: `${percent(step.reached)}%` }" />
            </div>
            <div class="text-caption text-medium-emphasis mt-1">{{ percent(step.reached) }}% of starters · left here: {{ step.leftHere }}</div>
          </div>
          <div class="step-finished"><span class="text-body-2 font-weight-medium">{{ step.reached }}</span><span class="text-caption text-medium-emphasis">reached</span></div>
        </div>
      </div>
      <p class="text-caption text-medium-emphasis mt-3 mb-0">Furthest step per person; completing the tour counts as reaching every step. "Left here" counts people who did not complete the tour and got no further than this step.</p>
    </v-sheet>
    <v-sheet v-if="summary" border rounded="lg" class="participants-panel">
      <div class="d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-account-group-outline</v-icon>
        <div class="flex-grow-1">
          <div class="d-flex flex-wrap align-center ga-2"><h2 class="text-subtitle-1 font-weight-medium">Participants</h2><v-chip size="x-small" color="primary-dark" variant="tonal" role="status">{{ filtered.length }} of {{ summary.participants.length }}</v-chip></div>
        </div>
      </div>
      <v-divider />
      <div class="filters pa-4">
        <v-text-field v-model="search" label="Search people" placeholder="Name or ID" prepend-inner-icon="mdi-magnify" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable />
        <v-select v-model="status" :items="statusOptions" label="Status" placeholder="All statuses" persistent-placeholder prepend-inner-icon="mdi-progress-check" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable />
      </div>
      <v-divider />
      <v-data-table v-model:sort-by="sortBy" :headers="headers" :items="filtered" :items-per-page="25" :items-per-page-options="[25, 50, 100]" hover class="participants-table" no-data-text="No people match these filters.">
        <template #[`item.userName`]="{ item }">
          <div class="py-2">{{ item.userName }}<div class="text-caption text-medium-emphasis">ID: {{ item.userId }}</div></div>
        </template>
        <template #[`item.status`]="{ item }">
          <v-chip size="small" variant="tonal" :color="statusColor[item.status]">{{ statusText(item.status) }}</v-chip>
        </template>
        <template #[`item.furthestStepId`]="{ item }">{{ stepLabel(item.furthestStepId) }}</template>
        <template #[`item.firstEventAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.lastEventAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Timeline of ${item.userName}`" @click="openTimeline(item)">Timeline</v-btn></template>
      </v-data-table>
    </v-sheet>
    <v-dialog v-model="timelineDialog" max-width="640" scrollable aria-label="Tour event timeline">
      <v-card>
        <v-card-title class="detail-heading d-flex align-center ga-2">
          <v-icon color="primary-dark" size="22">mdi-timeline-clock-outline</v-icon>
          <span class="text-h6">Event timeline</span><v-spacer />
          <v-btn icon="mdi-close" variant="text" aria-label="Close timeline" @click="timelineDialog = false" />
        </v-card-title>
        <v-card-text>
          <template v-if="selected">
            <h2 class="text-h6">{{ selected.userName }}</h2>
            <div class="text-caption text-medium-emphasis mb-3">ID: {{ selected.userId }}</div>
          </template>
          <v-progress-linear v-if="timelineLoading" indeterminate class="my-3" />
          <v-alert v-if="timelineError" type="error" variant="tonal" class="my-3">
            {{ timelineError }}<template #append><v-btn variant="text" @click="loadTimeline">Try again</v-btn></template>
          </v-alert>
          <v-timeline v-if="timeline.length" density="compact" side="end" align="start" class="mt-2">
            <v-timeline-item v-for="(item, index) in timeline" :key="index" size="x-small" dot-color="primary-dark">
              <div class="text-body-2 font-weight-medium">{{ eventText(item) }}</div>
              <div class="text-caption text-medium-emphasis">{{ date(item.at) }}</div>
            </v-timeline-item>
          </v-timeline>
          <p v-else-if="!timelineLoading && !timelineError" class="text-body-2 text-medium-emphasis">No events recorded.</p>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import analytics, { type TourAnalyticsDetail, type TourParticipant, type TourParticipantStatus, type TourTimelineEvent } from '@/services/analytics'

const props = defineProps<{ tourId: string }>()
const summary = ref<TourAnalyticsDetail | null>(null)
const loading = ref(false)
const error = ref('')
const search = ref('')
const status = ref<TourParticipantStatus | null>(null)
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastEventAt', order: 'desc' }])
const timelineDialog = ref(false)
const timelineLoading = ref(false)
const timelineError = ref('')
const selected = ref<TourParticipant | null>(null)
const timeline = ref<TourTimelineEvent[]>([])
let generation = 0
let timelineGeneration = 0
const statusOptions: { title: string; value: TourParticipantStatus }[] = [
  { title: 'Opened only', value: 'opened' }, { title: 'In progress', value: 'in_progress' },
  { title: 'Completed', value: 'completed' }, { title: 'Skipped', value: 'skipped' }
]
const statusColor: Record<TourParticipantStatus, string | undefined> = { opened: undefined, in_progress: 'info', completed: 'success', skipped: 'warning' }
const statusText = (value: TourParticipantStatus) => statusOptions.find((option) => option.value === value)?.title ?? value
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const funnelBase = computed(() => Math.max(summary.value?.startedUsers ?? 0, summary.value?.steps[0]?.reached ?? 0, 1))
const percent = (count: number) => Math.round(count / funnelBase.value * 100)
const stepLabel = (stepId: string | null) => {
  const index = summary.value?.steps.findIndex((step) => step.id === stepId) ?? -1
  return index < 0 ? '—' : `${index + 1}. ${summary.value?.steps[index]?.title}`
}
const eventText = (item: TourTimelineEvent) => {
  const where = item.stepTitle ? ` at "${item.stepTitle}"` : ''
  return { opened: 'Opened the tour menu', started: 'Started the tour', step: `Reached "${item.stepTitle}"`, completed: 'Completed the tour', skipped: `Skipped the tour${where}` }[item.event]
}
const kpis = computed(() => {
  const value = summary.value
  if (!value) return []
  return [
    { label: 'Opened', value: value.openedUsers, hint: 'People who opened the tour menu.' },
    { label: 'Started', value: value.startedUsers, hint: 'People who started the walkthrough.' },
    { label: 'Completed', value: value.completedUsers, hint: 'People who completed it at least once.' },
    { label: 'Skipped', value: value.skippedUsers, hint: 'Last outcome was skipping, never completed.' },
    { label: 'Completion rate', value: value.startedUsers ? `${value.completionRate}%` : '—', hint: 'Completed as a share of started.' },
    { label: 'Last activity', value: date(value.lastActivityAt), hint: 'Most recent tour event.' }
  ]
})
const filtered = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('en')
  return (summary.value?.participants ?? []).filter((row) => (!status.value || row.status === status.value) && `${row.userName} ${row.userId}`.toLocaleLowerCase('en').includes(query))
})
const headers = [
  { key: 'userName', title: 'Person', fixed: true, width: 180 }, { key: 'status', title: 'Status' },
  { key: 'furthestStepId', title: 'Furthest step', sortable: false }, { key: 'starts', title: 'Starts' },
  { key: 'opens', title: 'Menu opens' }, { key: 'firstEventAt', title: 'First event' },
  { key: 'lastEventAt', title: 'Last event' }, { key: 'actions', title: '', sortable: false }
]
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.tour(props.tourId)).data
    if (request === generation) summary.value = result
  } catch (e) {
    if (request === generation) error.value = (e as { response?: { status?: number } }).response?.status === 404 ? 'This tour does not exist.' : 'Tour analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
const loadTimeline = async () => {
  if (!selected.value) return
  const request = ++timelineGeneration
  timelineLoading.value = true
  timelineError.value = ''
  timeline.value = []
  try {
    const result = (await analytics.tourTimeline(props.tourId, selected.value.userId)).data
    if (request === timelineGeneration && timelineDialog.value) timeline.value = result
  } catch {
    if (request === timelineGeneration) timelineError.value = 'The event timeline could not be loaded.'
  } finally {
    if (request === timelineGeneration) timelineLoading.value = false
  }
}
const openTimeline = (row: TourParticipant) => {
  selected.value = row
  timelineDialog.value = true
  void loadTimeline()
}
watch(() => props.tourId, () => {
  summary.value = null
  search.value = ''
  status.value = null
  void load()
}, { immediate: true })
onUnmounted(() => { generation++; timelineGeneration++ })
</script>

<style scoped>
.tour-heading { min-width: 220px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.kpi { display: flex; flex-direction: column; padding: 14px 16px; border: 1px solid rgba(var(--v-theme-primary), 0.18); border-radius: 10px; background: rgba(var(--v-theme-primary), 0.04); }
.kpi-value { font-size: 1.5rem; line-height: 1.2; font-weight: 600; font-variant-numeric: tabular-nums; }
.kpi-label { font-size: 0.875rem; font-weight: 500; }
.kpi-hint { font-size: 0.75rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.funnel-panel { padding: 20px; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.section-icon { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: rgba(var(--v-theme-info), 0.08); flex-shrink: 0; }
.stat-bar { height: 12px; overflow: hidden; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.08); }
.stat-segment { height: 100%; }
.stat-segment--reached { background: rgb(var(--v-theme-info)); }
.stat-segment--drop { background: rgb(var(--v-theme-warning)); }
.step-chart-list { max-height: 420px; overflow: auto; }
.step-row { display: grid; grid-template-columns: minmax(200px, 1fr) minmax(0, 2fr) 70px; gap: 16px; align-items: center; padding: 12px 8px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06); }
.step-row:nth-child(even) { background: rgba(var(--v-theme-on-surface), 0.018); }
.step-label { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; min-width: 0; }
.step-number { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; flex-shrink: 0; border-radius: 7px; background: rgba(var(--v-theme-primary), 0.1); color: rgb(var(--v-theme-primary-dark)); font-size: 0.75rem; font-weight: 600; }
.step-title { min-width: 0; overflow-wrap: anywhere; }
.step-finished { display: flex; flex-direction: column; align-items: flex-end; font-variant-numeric: tabular-nums; }
.step-distribution { min-width: 0; }
.participants-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.filters { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; align-items: center; }
.participants-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
.participants-table :deep(th) { white-space: normal; }
.detail-heading { background: rgba(var(--v-theme-primary), 0.05); border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
@media (max-width: 700px) {
  .funnel-panel { padding: 16px; }
  .step-row { grid-template-columns: minmax(0, 1fr) 70px; gap: 8px 12px; }
  .step-distribution { grid-column: 1 / -1; grid-row: 2; }
  .filters { grid-template-columns: 1fr; }
}
</style>
