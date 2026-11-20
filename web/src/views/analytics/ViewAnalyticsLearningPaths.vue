<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-sheet border rounded="lg" class="overview-panel">
      <div class="d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-map-marker-path</v-icon>
        <div class="flex-grow-1">
          <h2 class="text-subtitle-1 font-weight-medium">Learning paths</h2>
          <div class="text-caption text-medium-emphasis">One row per template, including paths without participants.</div>
        </div>
        <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
      </div>
      <v-divider />
      <v-data-table v-model:sort-by="sortBy" :headers="headers" :items="rows" :loading="loading" :items-per-page="25" hover class="overview-table" loading-text="Loading learning paths …" no-data-text="No learning path templates yet.">
        <template #[`item.name`]="{ item }">
          <router-link :to="`/analytics/learning-paths/${item.id}`" class="path-link font-weight-medium">{{ item.name }}</router-link>
        </template>
        <template #[`item.visibility`]="{ item }"><v-chip size="small" variant="tonal">{{ pathVisibilityLabel(item.visibility) }}</v-chip></template>
        <template #[`item.status`]="{ item }">
          <div v-if="item.participants" class="status-bar" role="img" :aria-label="`${item.notStarted} not started, ${item.inProgress} in progress, ${item.completed} completed`">
            <div v-for="segment in segments" :key="segment.key" :class="`segment segment--${segment.key}`" :style="{ width: `${item[segment.key] / item.participants * 100}%` }" :title="`${segment.label}: ${item[segment.key]}`" />
          </div>
          <span v-else class="text-medium-emphasis">—</span>
        </template>
        <template #[`item.avgProgress`]="{ item }">{{ item.participants ? `${item.avgProgress}%` : '—' }}</template>
        <template #[`item.completionRate`]="{ item }">{{ item.participants ? `${item.completionRate}%` : '—' }}</template>
        <template #[`item.lastActivityAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Progress of ${item.name}`" :to="`/analytics/learning-paths/${item.id}`">Open</v-btn></template>
      </v-data-table>
    </v-sheet>
    <div class="d-flex flex-wrap ga-4 text-caption mt-3">
      <span v-for="segment in segments" :key="segment.key" class="d-inline-flex align-center ga-1"><span :class="`legend-swatch segment--${segment.key}`" aria-hidden="true" />{{ segment.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import analytics, { type PathAnalytics } from '@/services/analytics'
import { pathVisibilityLabel } from '@/services/learningPaths'

const rows = ref<PathAnalytics[]>([])
const loading = ref(false)
const error = ref('')
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastActivityAt', order: 'desc' }])
const segments = [
  { key: 'notStarted', label: 'Not started' },
  { key: 'inProgress', label: 'In progress' },
  { key: 'completed', label: 'Completed' }
] as const
const headers = [
  { key: 'name', title: 'Learning path' }, { key: 'visibility', title: 'Visibility' },
  { key: 'participants', title: 'Participants' }, { key: 'status', title: 'Status', sortable: false, width: 200 },
  { key: 'avgProgress', title: 'Avg. progress' }, { key: 'completionRate', title: 'Completion rate' },
  { key: 'lastActivityAt', title: 'Last activity' }, { key: 'actions', title: '', sortable: false }
]
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.paths()).data
    if (request === generation) rows.value = result
  } catch {
    if (request === generation) error.value = 'Learning path analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
onMounted(load)
onUnmounted(() => { generation++ })
</script>

<style scoped>
.overview-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.overview-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
.path-link { color: rgb(var(--v-theme-primary-dark)); text-decoration: none; }
.path-link:hover { text-decoration: underline; }
.status-bar { display: flex; height: 12px; max-width: 200px; overflow: hidden; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.08); }
.segment { height: 100%; }
.segment--notStarted { background: rgba(var(--v-theme-on-surface), 0.35); }
.segment--inProgress { background: rgb(var(--v-theme-info)); }
.segment--completed { background: rgb(var(--v-theme-success)); }
.legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
</style>
