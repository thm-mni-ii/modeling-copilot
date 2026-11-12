<template>
  <v-container max-width="1440" class="py-8">
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/learning-path-runs" class="mb-3">Learning Paths</v-btn>
    <div class="d-flex flex-wrap align-start ga-3 mb-5">
      <span class="page-icon"><v-icon size="26" color="primary-dark">mdi-map-marker-path</v-icon></span>
      <div class="flex-grow-1 page-heading">
        <h1 class="text-h4">Learning path progress</h1>
        <p class="text-body-2 text-medium-emphasis mt-2">Track participation, compare progress and export the filtered results.</p>
      </div>
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" :disabled="exporting" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="exportError" type="error" variant="tonal" class="mb-4">{{ exportError }}</v-alert>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-sheet border rounded="lg" class="filter-panel pa-4 mb-4">
      <div class="d-flex align-center flex-wrap ga-2 mb-3">
        <v-icon color="primary-dark" size="20">mdi-filter-outline</v-icon>
        <h2 class="text-subtitle-1 font-weight-medium">Filter participants</h2>
        <v-chip v-if="hasFilters" size="x-small" color="primary-dark" variant="tonal">Filters applied</v-chip>
        <v-spacer />
        <v-btn size="small" variant="text" :disabled="!hasFilters || exporting" @click="clearFilters">Clear filters</v-btn>
      </div>
      <div class="progress-filters">
        <v-autocomplete v-model="templateId" :items="templates" item-title="name" item-value="id" label="Learning path" placeholder="All learning paths" persistent-placeholder prepend-inner-icon="mdi-map-marker-path" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable :disabled="exporting" no-data-text="No learning paths found" />
        <v-select v-model="status" :items="statusOptions" label="Completion status" placeholder="All statuses" persistent-placeholder prepend-inner-icon="mdi-progress-check" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable :disabled="exporting" />
        <v-text-field v-model="search" label="Search people or learning paths" placeholder="Name, ID or learning path" prepend-inner-icon="mdi-magnify" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details clearable :disabled="exporting" />
      </div>
    </v-sheet>
    <LearningPathProgressStats v-if="!loading && !error" :records="filtered" :template-id="templateId" />
    <v-sheet border rounded="lg" class="participants-panel">
      <div class="participants-toolbar d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-account-group-outline</v-icon>
        <div class="flex-grow-1">
          <div class="d-flex flex-wrap align-center ga-2"><h2 class="text-subtitle-1 font-weight-medium">Participants</h2><v-chip size="x-small" color="primary-dark" variant="tonal" role="status">{{ filtered.length }} of {{ rows.length }}</v-chip></div>
          <div class="text-caption text-medium-emphasis mt-1">Export includes all {{ filtered.length }} matching participations and their steps, across all pages.</div>
        </div>
        <v-btn color="primary-dark" variant="flat" prepend-icon="mdi-download" :loading="exporting" :disabled="loading || exporting || !filtered.length || !!error" @click="exportCsv">Export CSV ({{ filtered.length }})</v-btn>
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
        <template #[`item.status`]="{ item }"><v-chip size="small" variant="tonal" :color="item.status === 'completed' ? 'success' : item.status === 'in_progress' ? 'info' : undefined"><v-icon start size="14">{{ item.status === 'completed' ? 'mdi-check-circle-outline' : item.status === 'in_progress' ? 'mdi-progress-clock' : 'mdi-clock-outline' }}</v-icon>{{ statusText(item.status) }}</v-chip></template>
        <template #[`item.createdAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.lastActivityAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Details for ${item.learnerName} – ${item.name}`" @click="openDetail(item)">Details</v-btn></template>
        <template #no-data><p class="pa-5 text-body-2 text-medium-emphasis">{{ rows.length ? 'No participation records match these filters.' : 'No learning path participation records yet.' }}</p></template>
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
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import paths, { type PathProgressDetail, type PathProgressSummary, type StepRun } from '@/services/learningPaths'
import LearningPathProgressStats from '@/components/learningPaths/LearningPathProgressStats.vue'

const rows = ref<PathProgressSummary[]>([])
const loading = ref(false)
const error = ref('')
const exporting = ref(false)
const exportError = ref('')
const exportCsv = async () => {
  if (exporting.value || loading.value || !filtered.value.length || error.value) return
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
const templateId = ref<string | null>(null)
const status = ref<string | null>(null)
const page = ref(1)
const hasFilters = computed(() => !!templateId.value || !!status.value || !!search.value?.trim())
const clearFilters = () => {
  templateId.value = null
  status.value = null
  search.value = ''
}
watch([templateId, status, search], () => { page.value = 1 })
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastActivityAt', order: 'desc' }])
const detailDialog = ref(false)
const detailLoading = ref(false)
const detailError = ref('')
const selected = ref<PathProgressSummary | null>(null)
const detail = ref<PathProgressDetail | null>(null)
let generation = 0
let detailGeneration = 0
const statusOptions = [{ title: 'Not started', value: 'not_started' }, { title: 'In progress', value: 'in_progress' }, { title: 'Completed', value: 'completed' }]
const statusText = (value: string) => statusOptions.find((option) => option.value === value)?.title ?? value
const stepStatusText = (value: StepRun['status']) => ({ locked: 'Locked', available: 'Available', in_progress: 'In progress', completed: 'Completed', skipped: 'Skipped' })[value]
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const templates = computed(() => [...new Map(rows.value.map((row) => [row.templateId, { id: row.templateId, name: row.name }])).values()].sort((a, b) => a.name.localeCompare(b.name)))
const filtered = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('en')
  return rows.value.filter((row) => (!templateId.value || row.templateId === templateId.value) && (!status.value || row.status === status.value) && `${row.learnerName} ${row.learnerId} ${row.name}`.toLocaleLowerCase('en').includes(query))
})
const headers = [
  { key: 'learnerName', title: 'Person', fixed: true, width: 180 }, { key: 'name', title: 'Learning path' },
  { key: 'completedTasks', title: 'Completed tasks' }, { key: 'completed', title: 'Completed steps' },
  { key: 'status', title: 'Status' }, { key: 'createdAt', title: 'Created' },
  { key: 'lastActivityAt', title: 'Last recorded activity' }, { key: 'actions', title: '', sortable: false }
]
const stepHeaders = [{ key: 'title', title: 'Step' }, { key: 'type', title: 'Type' }, { key: 'status', title: 'Status' }, { key: 'openedAt', title: 'Started' }, { key: 'completedAt', title: 'Completed' }]
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result: PathProgressSummary[] = []
    for (let skip = 0; ; ) {
      const page = (await paths.progress(skip)).data
      if (request !== generation) return
      result.push(...page.items)
      skip += page.items.length
      if (!page.items.length || skip >= page.total) break
    }
    rows.value = result
  } catch {
    if (request === generation) error.value = 'Learning path progress could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
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
onMounted(load)
onUnmounted(() => { generation++; detailGeneration++ })
</script>

<style scoped>
.page-icon { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 12px; background: rgba(var(--v-theme-primary), 0.1); flex-shrink: 0; }
.page-heading { min-width: 220px; }
.filter-panel { background: rgba(var(--v-theme-primary), 0.035); border-color: rgba(var(--v-theme-primary), 0.25); }
.progress-filters { display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 12px; }
.participants-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.participants-toolbar { background: rgba(var(--v-theme-primary), 0.025); }
.progress-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
.progress-table :deep(th) { white-space: normal; }
.progress-table :deep(td) { min-width: 120px; }
.person-icon { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 8px; color: rgb(var(--v-theme-primary-dark)); background: rgba(var(--v-theme-primary), 0.08); flex-shrink: 0; }
.table-progress { max-width: 90px; }
.detail-heading { background: rgba(var(--v-theme-primary), 0.05); border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
@media (max-width: 700px) { .progress-filters { grid-template-columns: 1fr; } }
</style>
