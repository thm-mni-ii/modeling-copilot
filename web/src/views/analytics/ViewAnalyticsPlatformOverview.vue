<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-progress-linear v-if="loading" indeterminate color="primary-dark" class="mb-4" />

    <template v-if="overview">
      <KpiTiles :tiles="kpis" class="mb-5" />

      <v-row>
        <v-col v-for="chart in weeklyCharts" :key="chart.title" cols="12" md="4">
          <v-sheet border rounded="lg" class="chart-card pa-4">
            <h2 class="text-subtitle-2 font-weight-medium">{{ chart.title }}<InfoTip :text="chart.tip" /></h2>
            <div class="bars" role="img" :aria-label="`${chart.title}: ${chart.series.map((point) => point.count).join(', ')}`">
              <div v-for="point in chart.series" :key="point.weekStart" class="bar-col" :title="`Week of ${weekLabel(point.weekStart)}: ${point.count}`">
                <div class="bar" :style="{ height: point.count ? `${Math.max(2, point.count / chart.max * 100)}%` : '0' }" />
              </div>
            </div>
            <div class="d-flex justify-space-between text-caption text-medium-emphasis">
              <span>{{ weekLabel(chart.series[0]?.weekStart) }}</span><span>max {{ chart.max }}/week</span><span>{{ weekLabel(chart.series[chart.series.length - 1]?.weekStart) }}</span>
            </div>
          </v-sheet>
        </v-col>
        <v-col cols="12" md="4">
          <v-sheet border rounded="lg" class="chart-card pa-4">
            <h2 class="text-subtitle-2 font-weight-medium">Models per user<InfoTip :text="histogramTip" /></h2>
            <div v-for="bin in overview.modelsPerUser" :key="bin.label" class="hist-row" :title="`${bin.users} users with ${bin.label} models`">
              <span class="hist-label text-caption">{{ bin.label }}</span>
              <span class="hist-track"><span class="hist-bar" :style="{ width: `${bin.users / histogramMax * 100}%` }" /></span>
              <span class="hist-count text-caption">{{ bin.users }}</span>
            </div>
          </v-sheet>
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import KpiTiles from '@/components/analytics/KpiTiles.vue'
import { usePlatformFilters } from '@/composables/usePlatformFilters'
import analytics, { type PlatformOverview } from '@/services/analytics'

const { period, includeStaff } = usePlatformFilters()
const overview = ref<PlatformOverview | null>(null)
const loading = ref(false)
const error = ref('')

const weekLabel = (value?: string) => value ? new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' }) : ''
const number = (value: number | null) => value === null ? '—' : value

const kpis = computed(() => {
  const kpi = overview.value?.kpis
  if (!kpi) return []
  const scope = 'created in the selected period'
  return [
    { label: 'Known users', value: kpi.knownUsers, hint: `${kpi.newUsers} new in period`, tip: 'People who opened the app at least once. New: first visit within the selected period (people seen before first-visit tracking was added are not counted as new). Not limited by the period.' },
    { label: 'Active, last 7 days', value: kpi.activeUsersWeek, tip: 'People whose last visit was within the last 7 days. Independent of the selected period.' },
    { label: 'Active, last 30 days', value: kpi.activeUsersMonth, tip: 'People whose last visit was within the last 30 days. Independent of the selected period.' },
    { label: 'Users with models', value: kpi.usersWithModels, tip: `People who own at least one model ${scope}.` },
    { label: 'Models', value: kpi.models, hint: `${kpi.modelsArchived} archived`, tip: `Models ${scope}, including archived ones (counted separately).` },
    { label: 'Models per user', value: `${number(kpi.avgModelsPerUser)} avg`, hint: `${number(kpi.medianModelsPerUser)} median`, tip: `Mean and median number of models per user, over users with at least one model ${scope}.` },
    { label: 'Versions', value: kpi.checkpoints + kpi.releases, hint: `${kpi.checkpoints} checkpoints, ${kpi.releases} releases`, tip: 'Model versions saved in the selected period, split by checkpoint and release.' }
  ]
})

const weeklyCharts = computed(() => {
  const value = overview.value
  if (!value) return []
  const chart = (title: string, tip: string, series: PlatformOverview['weeklyNewModels']) => ({ title, tip, series, max: Math.max(1, ...series.map((point) => point.count)) })
  return [
    chart('Active users per week', 'People with at least one editor session started in that calendar week (Monday to Sunday, UTC). The chart shows the period, but at least four weeks and at most 52 weeks.', value.weeklyActiveUsers),
    chart('New models per week', 'Models created in that calendar week (Monday to Sunday, UTC). The chart shows the period, but at least four weeks and at most 52 weeks.', value.weeklyNewModels)
  ]
})
const histogramTip = 'Number of users by how many models they created in the selected period. Users without a model are not shown.'
const histogramMax = computed(() => Math.max(1, ...(overview.value?.modelsPerUser.map((bin) => bin.users) ?? [])))

let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.platform(period.value, includeStaff.value)).data
    if (request === generation) overview.value = result
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
.chart-card { height: 100%; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.bars { display: flex; align-items: flex-end; gap: 2px; height: 120px; margin: 12px 0 6px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.2); }
.bar-col { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.bar { width: 100%; border-radius: 2px 2px 0 0; background: rgb(var(--v-theme-primary-dark)); }
.hist-row { display: grid; grid-template-columns: 48px 1fr 32px; align-items: center; gap: 8px; margin-top: 6px; }
.hist-label { text-align: right; }
.hist-track { height: 14px; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.06); overflow: hidden; }
.hist-bar { display: block; height: 100%; background: rgb(var(--v-theme-primary-dark)); }
.hist-count { font-variant-numeric: tabular-nums; }
</style>
