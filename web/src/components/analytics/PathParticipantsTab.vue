<template>
  <div>
    <v-alert v-if="exportError" type="error" variant="tonal" class="mb-4">{{ exportError }}</v-alert>
    <v-sheet border rounded="lg" class="participants-panel">
      <div class="participants-toolbar d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-account-group-outline</v-icon>
        <div class="flex-grow-1">
          <div class="d-flex flex-wrap align-center ga-2"><h2 class="text-subtitle-1 font-weight-medium">Participants</h2><v-chip size="x-small" color="primary-dark" variant="tonal" role="status">{{ filtered.length }} of {{ rows.length }}</v-chip></div>
          <div class="text-caption text-medium-emphasis mt-1">Export includes all {{ filtered.length }} matching participations and their steps, across all pages.</div>
        </div>
        <v-btn color="primary-dark" variant="flat" prepend-icon="mdi-download" :loading="exporting" :disabled="loading || exporting || !filtered.length" @click="exportCsv">Export CSV ({{ filtered.length }})</v-btn>
      </div>
      <v-divider />
      <div class="progress-filters pa-4">
        <v-text-field v-model="search" label="Search people" placeholder="Name or ID" prepend-inner-icon="mdi-magnify" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable :disabled="exporting" />
        <v-select v-model="status" :items="statusOptions" label="Completion status" placeholder="All statuses" persistent-placeholder prepend-inner-icon="mdi-progress-check" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable :disabled="exporting" />
        <v-switch v-model="stalledOnly" color="primary-dark" density="compact" hide-details inset :disabled="exporting" label="Stalled only (in progress, inactive for more than 7 days)" />
      </div>
      <v-divider />
      <v-data-table v-model:page="page" v-model:sort-by="sortBy" :headers="headers" :items="filtered" :loading="loading" :items-per-page="25" :items-per-page-options="[25, 50, 100]" items-per-page-text="Records per page" loading-text="Loading progress …" hover class="progress-table">
        <template #[`item.learnerName`]="{ item }">
          <div class="d-flex align-center ga-2 py-2"><span class="person-icon"><v-icon size="17">mdi-account-outline</v-icon></span><div>{{ item.learnerName }}<div class="text-caption text-medium-emphasis">ID: {{ item.learnerId }}</div></div></div>
        </template>
        <template #[`item.completedTasks`]="{ item }"><span class="font-weight-medium">{{ item.completedTasks }}</span><span class="text-medium-emphasis"> / {{ item.totalTasks }}</span></template>
        <template #[`item.completed`]="{ item }">
          <div>{{ item.completed }} / {{ item.total }}</div><div v-if="item.skipped" class="text-caption text-medium-emphasis">{{ item.skipped }} skipped</div>
          <v-progress-linear :model-value="item.progress" :color="item.status === 'completed' ? 'success' : 'info'" height="4" rounded class="table-progress mt-1" :aria-label="`${item.progress}% of steps finished`" />
        </template>
        <template #[`item.status`]="{ item }">
          <v-chip size="small" variant="tonal" :color="item.status === 'completed' ? 'success' : item.status === 'in_progress' ? 'info' : undefined"><v-icon start size="14">{{ item.status === 'completed' ? 'mdi-check-circle-outline' : item.status === 'in_progress' ? 'mdi-progress-clock' : 'mdi-clock-outline' }}</v-icon>{{ statusText(item.status) }}</v-chip>
          <v-chip v-if="isStalled(item)" size="small" variant="tonal" color="warning" class="ml-1">Stalled</v-chip>
        </template>
        <template #[`item.workSeconds`]="{ item }">
          <template v-if="runActivity(item.id)">{{ durationText(runActivity(item.id)!.grossSeconds) }}<div class="text-caption text-medium-emphasis">{{ durationText(runActivity(item.id)!.activeSeconds) }} active · {{ runActivity(item.id)!.sessions }} sessions</div></template>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #[`item.windowSwitches`]="{ item }">
          <template v-if="runActivity(item.id)">{{ runActivity(item.id)!.tabHidden + runActivity(item.id)!.focusLost }}<div class="text-caption text-medium-emphasis">{{ runActivity(item.id)!.tabHidden }} tab · {{ runActivity(item.id)!.focusLost }} focus</div></template>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #[`item.createdAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.lastActivityAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Details for ${item.learnerName}`" @click="openDetail(item)">Details</v-btn></template>
        <template #no-data><p class="pa-5 text-body-2 text-medium-emphasis">{{ rows.length ? 'No participation records match these filters.' : `Nobody has started this learning path yet.${hiddenStaffRuns ? ` ${hiddenStaffRuns} staff runs are hidden.` : ''}` }}</p></template>
      </v-data-table>
    </v-sheet>
    <p class="text-caption text-medium-emphasis mt-3">Progress reflects the current learning path template. Archived steps are excluded. Skipped optional questionnaires count towards path completion.</p>
    <v-dialog v-model="detailDialog" max-width="1100" scrollable aria-label="Learning path progress details">
      <v-card>
        <v-card-title class="detail-heading d-flex align-center ga-2">
          <v-icon color="primary-dark" size="22">mdi-account-details-outline</v-icon>
          <span class="text-h6">Participation details</span><v-spacer />
          <v-btn icon="mdi-close" variant="text" aria-label="Close details" @click="detailDialog = false" />
        </v-card-title>
        <v-card-text>
          <template v-if="selected">
            <h2 class="text-h6">{{ selected.learnerName }}</h2>
            <div class="text-caption text-medium-emphasis mb-3">ID: {{ selected.learnerId }}</div>
            <h3 class="text-subtitle-1 font-weight-medium">{{ selected.name }}</h3>
          </template>
          <v-progress-linear v-if="detailLoading" indeterminate class="my-3" />
          <v-alert v-if="detailError" type="error" variant="tonal" class="my-3">
            {{ detailError }}<template #append><v-btn variant="text" @click="loadDetail">Try again</v-btn></template>
          </v-alert>
          <template v-if="detail">
            <p v-if="detail.description" class="text-body-2 text-medium-emphasis mt-1 mb-3">{{ detail.description }}</p>
            <div class="d-flex flex-wrap ga-4 text-body-2 my-3">
              <span>{{ statusText(detail.status) }}</span>
              <span>Tasks: {{ detail.completedTasks }} / {{ detail.totalTasks }}</span>
              <span>Steps: {{ detail.completed }} / {{ detail.total }} completed<span v-if="detail.skipped">, {{ detail.skipped }} skipped</span></span>
            </div>
            <div class="text-caption text-medium-emphasis mb-3">Created: {{ date(detail.createdAt) }} · Last recorded activity: {{ date(detail.lastActivityAt) }}<span v-if="detail.firstFinishedAt"> · First completed: {{ date(detail.firstFinishedAt) }}</span></div>
            <v-data-table :headers="stepHeaders" :items="detail.steps" :items-per-page="-1" density="compact" no-data-text="No steps available.">
              <template #[`item.title`]="{ item }"><div class="py-2">{{ item.title }}<div v-if="item.archived" class="text-caption text-medium-emphasis">Archived · excluded from progress</div></div></template>
              <template #[`item.type`]="{ value }">{{ value === 'task' ? 'Task' : 'Questionnaire' }}</template>
              <template #[`item.status`]="{ item }">
                <div>{{ stepStatusText(item.status) }}</div>
                <div v-for="reason in item.reasons" :key="reason" class="text-caption text-medium-emphasis">{{ reason }}</div>
                <div v-if="item.availableAt" class="text-caption text-medium-emphasis">Available from {{ date(item.availableAt) }}</div>
              </template>
              <template #[`item.openedAt`]="{ value }">{{ date(value) }}</template>
              <template #[`item.completedAt`]="{ value }">{{ date(value) }}</template>
              <template #bottom />
            </v-data-table>
          </template>
          <section v-if="selectedActivity" aria-label="Activity per task">
            <h3 class="text-subtitle-1 font-weight-medium mt-4 mb-2">Activity per task<InfoTip text="Editor sessions, work time and window switches of this person per task step. Approximations from browser events: idle detection and tab behaviour (also on mobile) are not exact." /></h3>
            <v-table density="compact" class="mini-table">
              <thead><tr><th>Task</th><th class="text-end">Sessions</th><th class="text-end">Work time</th><th class="text-end">Active time</th><th class="text-end">Tab switches</th><th class="text-end">Focus losses</th></tr></thead>
              <tbody>
                <tr v-for="step in selectedActivity.steps" :key="step.stepId"><td>{{ stepTitles.get(step.stepId) ?? step.stepId }}</td><td class="text-end">{{ step.sessions }}</td><td class="text-end">{{ durationText(step.grossSeconds) }}</td><td class="text-end">{{ durationText(step.activeSeconds) }}</td><td class="text-end">{{ step.tabHidden }}</td><td class="text-end">{{ step.focusLost }}</td></tr>
              </tbody>
            </v-table>
          </section>
          <AttemptTimeline v-if="selected" :template-id="templateId" :run-id="selected.id" />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import type { PathActivity } from '@/services/analytics'
import paths, { type PathProgressDetail, type PathProgressSummary, type StepRun } from '@/services/learningPaths'
import AttemptTimeline from '@/components/analytics/AttemptTimeline.vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import { durationText } from '@/components/analytics/labels'

const props = defineProps<{ templateId: string; rows: PathProgressSummary[]; activity: PathActivity | null; loading: boolean; hiddenStaffRuns: number }>()
const STALLED_MS = 7 * 24 * 3600 * 1000
const exporting = ref(false)
const exportError = ref('')
const exportCsv = async () => {
  if (exporting.value || props.loading || !filtered.value.length) return
  exporting.value = true
  exportError.value = ''
  try {
    const { data } = await paths.exportProgressCsv(filtered.value.map((row) => row.id))
    const url = URL.createObjectURL(data)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = 'learning-path-progress.csv'
      document.body.appendChild(link)
      link.click()
      link.remove()
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch {
    exportError.value = 'The CSV export could not be created. Please try again.'
  } finally {
    exporting.value = false
  }
}
const search = ref('')
const status = ref<string | null>(null)
const stalledOnly = ref(false)
const page = ref(1)
watch([search, status, stalledOnly], () => { page.value = 1 })
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastActivityAt', order: 'desc' }])
const detailDialog = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selected = ref<PathProgressSummary | null>(null)
const detail = ref<PathProgressDetail | null>(null)
let detailGeneration = 0
const statusOptions = [{ title: 'Not started', value: 'not_started' }, { title: 'In progress', value: 'in_progress' }, { title: 'Completed', value: 'completed' }]
const statusText = (value: string) => statusOptions.find((option) => option.value === value)?.title ?? value
const stepStatusText = (value: StepRun['status']) => ({ locked: 'Locked', available: 'Available', in_progress: 'In progress', completed: 'Completed', skipped: 'Skipped' })[value]
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const isStalled = (row: PathProgressSummary) => row.status === 'in_progress' && Date.now() - Date.parse(row.lastActivityAt) > STALLED_MS
const filtered = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('en')
  return props.rows.filter((row) => (!status.value || row.status === status.value) && (!stalledOnly.value || isStalled(row)) && `${row.learnerName} ${row.learnerId}`.toLocaleLowerCase('en').includes(query))
})
const runActivities = computed(() => new Map((props.activity?.runs ?? []).map((run) => [run.runId, run])))
const runActivity = (runId: string) => runActivities.value.get(runId)
const stepTitles = computed(() => new Map((props.activity?.steps ?? []).map((step) => [step.stepId, step.title])))
const selectedActivity = computed(() => selected.value ? runActivity(selected.value.id) : undefined)
const headers = [
  { key: 'learnerName', title: 'Person', fixed: true, width: 180 },
  { key: 'completedTasks', title: 'Completed tasks' }, { key: 'completed', title: 'Completed steps' },
  { key: 'status', title: 'Status' },
  { key: 'workSeconds', title: 'Work time', value: (row: Record<string, unknown>) => runActivity(row.id as string)?.grossSeconds ?? 0 },
  { key: 'windowSwitches', title: 'Window switches', value: (row: Record<string, unknown>) => { const run = runActivity(row.id as string); return (run?.tabHidden ?? 0) + (run?.focusLost ?? 0) } },
  { key: 'createdAt', title: 'Created' },
  { key: 'lastActivityAt', title: 'Last recorded activity' }, { key: 'actions', title: '', sortable: false }
]
const stepHeaders = [{ key: 'title', title: 'Step' }, { key: 'type', title: 'Type' }, { key: 'status', title: 'Status' }, { key: 'openedAt', title: 'Started' }, { key: 'completedAt', title: 'Completed' }]
const loadDetail = async () => {
  if (!selected.value) return
  const request = ++detailGeneration
  detailLoading.value = true
  detailError.value = ''
  detail.value = null
  try {
    const result = (await paths.progressDetail(selected.value.id)).data
    if (request === detailGeneration && detailDialog.value) detail.value = result
  } catch {
    if (request === detailGeneration) detailError.value = 'Participation details could not be loaded.'
  } finally {
    if (request === detailGeneration) detailLoading.value = false
  }
}
const openDetail = (row: PathProgressSummary) => {
  selected.value = row
  detailDialog.value = true
  void loadDetail()
}
onUnmounted(() => { detailGeneration++ })
</script>

<style scoped>
.participants-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.participants-toolbar { background: rgba(var(--v-theme-primary), 0.025); }
.progress-filters { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 12px; align-items: center; }
.progress-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
.progress-table :deep(th) { white-space: normal; }
.progress-table :deep(td) { min-width: 120px; }
.person-icon { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 8px; color: rgb(var(--v-theme-primary-dark)); background: rgba(var(--v-theme-primary), 0.08); flex-shrink: 0; }
.table-progress { max-width: 90px; }
.mini-table { background: transparent; }
.detail-heading { background: rgba(var(--v-theme-primary), 0.05); border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
@media (max-width: 700px) { .progress-filters { grid-template-columns: 1fr; } }
</style>
