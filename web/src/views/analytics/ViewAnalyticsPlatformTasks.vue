<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-progress-linear v-if="loading" indeterminate color="primary-dark" class="mb-4" />

    <template v-if="data">
      <KpiTiles :tiles="kpis" class="mb-5" />

      <v-sheet border rounded="lg" class="table-panel">
        <div class="pa-4">
          <h2 class="text-subtitle-1 font-weight-medium">Tasks</h2>
          <div class="text-caption text-medium-emphasis">Activity per task in the selected period; published tasks without activity are listed with zeros.</div>
        </div>
        <v-divider />
        <v-data-table v-model:sort-by="taskSort" :headers="taskHeaders" :items="data.tasks" :items-per-page="10" hover class="platform-table" no-data-text="No tasks yet.">
          <template #[`item.avgScore`]="{ value }">{{ value === null ? '—' : `${value}%` }}</template>
        </v-data-table>
      </v-sheet>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import KpiTiles from '@/components/analytics/KpiTiles.vue'
import { usePlatformFilters } from '@/composables/usePlatformFilters'
import analytics, { type PlatformTasks } from '@/services/analytics'

const { period, includeStaff } = usePlatformFilters()
const data = ref<PlatformTasks | null>(null)
const loading = ref(false)
const error = ref('')
const taskSort = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'models', order: 'desc' }])

const kpis = computed(() => {
  const kpi = data.value?.kpis
  if (!kpi) return []
  return [
    { label: 'Tasks', value: kpi.tasksPublished + kpi.tasksHidden + kpi.tasksArchived, hint: `${kpi.tasksPublished} published, ${kpi.tasksHidden} hidden, ${kpi.tasksArchived} archived`, tip: 'All tasks by catalog state: published, hidden (private, not archived) and archived. Independent of the period.' },
    { label: 'Evaluations', value: kpi.evaluations, hint: `${kpi.evaluationsLastWeek} in last 7 days`, items: kpi.evaluationsByState, tip: 'Evaluation runs started in the selected period, by state. The last-7-days count is independent of the period.' }
  ]
})

const taskHeaders = [
  { key: 'taskName', title: 'Task' },
  { key: 'persons', title: 'People', headerProps: { title: 'People who created at least one model for this task in the period.' } },
  { key: 'models', title: 'Models', headerProps: { title: 'Models created for this task in the period, including archived ones.' } },
  { key: 'evaluations', title: 'Evaluations', headerProps: { title: 'Evaluation runs for this task started in the period.' } },
  { key: 'avgScore', title: 'Avg. score', headerProps: { title: 'Mean score of the period’s evaluations that produced a score.' } }
]

let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.platformTasks(period.value, includeStaff.value)).data
    if (request === generation) data.value = result
  } catch {
    if (request === generation) error.value = 'Platform analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}

watch([period, includeStaff], load)
onMounted(load)
onUnmounted(() => { generation++ })
</script>

<style scoped>
.table-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.platform-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
</style>
