<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <div class="d-flex flex-wrap align-center ga-4 mb-4">
      <v-switch v-model="includeStaff" color="primary-dark" label="Include staff" density="compact" hide-details />
      <span class="text-caption text-medium-emphasis flex-grow-1">Counts are people, not events, for the current tour version. Staff are administrators and moderators.</span>
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
    </div>

    <template v-if="overview">
      <KpiTiles :tiles="kpis" class="mb-5" />
      <v-sheet border rounded="lg" class="chart-card pa-4 mb-5">
        <h2 class="text-subtitle-2 font-weight-medium">Tour starts and completions per week<InfoTip :text="weeklyTip" /></h2>
        <div class="bars" role="img" :aria-label="`Starts per week: ${overview.weekly.map((week) => week.starts).join(', ')}. Completions per week: ${overview.weekly.map((week) => week.completions).join(', ')}`">
          <div v-for="week in overview.weekly" :key="week.weekStart" class="bar-col" :title="`Week of ${weekLabel(week.weekStart)}: ${week.starts} started, ${week.completions} completed`">
            <div class="bar bar-start" :style="{ height: barHeight(week.starts) }" />
            <div class="bar bar-complete" :style="{ height: barHeight(week.completions) }" />
          </div>
        </div>
        <div class="d-flex flex-wrap justify-space-between ga-3 text-caption text-medium-emphasis">
          <span>{{ weekLabel(overview.weekly[0]?.weekStart) }}</span>
          <span><span class="swatch bar-start" /> Started <span class="swatch bar-complete ml-2" /> Completed (max {{ weeklyMax }}/week)</span>
          <span>{{ weekLabel(overview.weekly[overview.weekly.length - 1]?.weekStart) }}</span>
        </div>
      </v-sheet>
    </template>

    <v-sheet border rounded="lg" class="overview-panel">
      <div class="d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-help-circle-outline</v-icon>
        <h2 class="text-subtitle-1 font-weight-medium">Guided tours</h2>
      </div>
      <v-divider />
      <v-data-table v-model:sort-by="sortBy" :headers="headers" :items="rows" :loading="loading" :items-per-page="25" hover class="overview-table" loading-text="Loading tours …" no-data-text="No tours available.">
        <template #[`item.title`]="{ item }">
          <router-link :to="`/analytics/tours/${item.id}`" class="tour-link font-weight-medium">{{ item.title }}</router-link>
        </template>
        <template #[`item.version`]="{ value }">v{{ value }}</template>
        <template #[`item.completionRate`]="{ item }">{{ item.startedUsers ? `${item.completionRate}%` : '—' }}</template>
        <template #[`item.lastActivityAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Details of ${item.title}`" :to="`/analytics/tours/${item.id}`">Open</v-btn></template>
      </v-data-table>
    </v-sheet>
    <p class="text-caption text-medium-emphasis mt-3">Opened: opened the tour menu. Started: started the walkthrough. Skipped: last outcome was skipping or aborting, without ever completing. Completion rate: completed people as a share of people who started.</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import KpiTiles from '@/components/analytics/KpiTiles.vue'
import { usePlatformFilters } from '@/composables/usePlatformFilters'
import analytics, { type TourOverview } from '@/services/analytics'

const { includeStaff } = usePlatformFilters()
const overview = ref<TourOverview | null>(null)
const rows = computed(() => overview.value?.tours ?? [])
const loading = ref(false)
const error = ref('')
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastActivityAt', order: 'desc' }])
const headers = [
  { key: 'title', title: 'Tour' }, { key: 'version', title: 'Version' },
  { key: 'openedUsers', title: 'Opened' }, { key: 'startedUsers', title: 'Started' },
  { key: 'completedUsers', title: 'Completed' }, { key: 'skippedUsers', title: 'Skipped' },
  { key: 'completionRate', title: 'Completion rate' }, { key: 'lastActivityAt', title: 'Last activity' },
  { key: 'actions', title: '', sortable: false }
]
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const weekLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }) : ''

const kpis = computed(() => {
  const summary = overview.value?.summary
  if (!summary) return []
  const people = 'Distinct people across all tours (current version), not events.'
  return [
    { label: 'Tours', value: summary.tours, tip: 'Number of guided tours available.' },
    { label: 'Opened the menu', value: summary.openedUsers, tip: `${people} Opened the tour menu at least once.` },
    { label: 'Started', value: summary.startedUsers, tip: `${people} Started a walkthrough at least once.` },
    { label: 'Completed', value: summary.completedUsers, tip: `${people} Completed a tour at least once.` },
    { label: 'Skipped', value: summary.skippedUsers, tip: `${people} Last outcome of a tour was skipping or aborting, without ever completing it.` },
    { label: 'Completion rate', value: summary.startedUsers ? `${summary.completionRate}%` : '—', tip: 'People who completed a tour as a share of people who started one.' },
    { label: 'Coverage', value: summary.knownUsers ? `${summary.coverage}%` : '—', hint: `${summary.startedUsers} of ${summary.knownUsers} known users`, tip: 'People who started any tour as a share of known users (people who opened the app at least once, without staff unless included).' }
  ]
})

const weeklyTip = 'People who started / completed any tour in that calendar week (Monday to Sunday, UTC), distinct per week. Shows the last 12 weeks.'
const weeklyMax = computed(() => Math.max(1, ...(overview.value?.weekly.flatMap((week) => [week.starts, week.completions]) ?? [])))
const barHeight = (count: number) => count ? `${Math.max(2, count / weeklyMax.value * 100)}%` : '0'

let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.tours(includeStaff.value)).data
    if (request === generation) overview.value = result
  } catch {
    if (request === generation) error.value = 'Tour analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
watch(includeStaff, load)
onMounted(load)
onUnmounted(() => { generation++ })
</script>

<style scoped>
.overview-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.overview-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
.tour-link { color: rgb(var(--v-theme-primary-dark)); text-decoration: none; }
.tour-link:hover { text-decoration: underline; }
.chart-card { border-color: rgba(var(--v-theme-on-surface), 0.12); }
.bars { display: flex; align-items: flex-end; gap: 6px; height: 120px; margin: 12px 0 6px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.2); }
.bar-col { flex: 1; height: 100%; display: flex; align-items: flex-end; gap: 2px; }
.bar { flex: 1; border-radius: 2px 2px 0 0; }
.bar-start { background: rgb(var(--v-theme-primary-dark)); }
.bar-complete { background: rgb(var(--v-theme-secondary-darken-1)); }
.swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; vertical-align: baseline; }
</style>
