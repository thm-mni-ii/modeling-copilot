<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-sheet border rounded="lg" class="overview-panel">
      <div class="d-flex flex-wrap align-center ga-3 pa-4">
        <v-icon color="primary-dark" size="22">mdi-clipboard-text-outline</v-icon>
        <div class="flex-grow-1">
          <h2 class="text-subtitle-1 font-weight-medium">Surveys</h2>
          <div class="text-caption text-medium-emphasis">Aggregated results only; test responses are excluded and no individual answers are shown.</div>
        </div>
        <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
      </div>
      <v-divider />
      <v-data-table v-model:sort-by="sortBy" :headers="headers" :items="rows" :loading="loading" :items-per-page="25" hover class="overview-table" loading-text="Loading surveys …" no-data-text="No surveys available.">
        <template #[`item.title`]="{ item }">
          <router-link :to="`/analytics/surveys/${item.id}`" class="survey-link font-weight-medium">{{ item.title }}</router-link>
          <v-chip v-if="item.kind === 'help'" size="x-small" variant="tonal" class="ml-2">Help flow</v-chip>
        </template>
        <template #[`item.activeReleaseVersion`]="{ value }">{{ value === null ? 'None' : `v${value}` }}</template>
        <template #[`item.submitted`]="{ item }">{{ shareText(item.submitted, item.submittedShare) }}</template>
        <template #[`item.skipped`]="{ item }">{{ shareText(item.skipped, item.skippedShare) }}</template>
        <template #[`item.draft`]="{ item }">{{ shareText(item.draft, item.draftShare) }}</template>
        <template #[`item.lastResponseAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.actions`]="{ item }"><v-btn size="small" color="primary-dark" variant="text" append-icon="mdi-chevron-right" :aria-label="`Results of ${item.title}`" :to="`/analytics/surveys/${item.id}`">Results</v-btn></template>
      </v-data-table>
    </v-sheet>
    <p class="text-caption text-medium-emphasis mt-3">Responses: all non-test sessions across every release. Submitted: completed questionnaires. Skipped: closed without answering. Draft: opened but not finished. Shares refer to all responses of the survey.</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import analytics, { type SurveyAnalytics } from '@/services/analytics'

const rows = ref<SurveyAnalytics[]>([])
const loading = ref(false)
const error = ref('')
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastResponseAt', order: 'desc' }])
const headers = [
  { key: 'title', title: 'Survey' }, { key: 'activeReleaseVersion', title: 'Active release' },
  { key: 'responses', title: 'Responses' }, { key: 'submitted', title: 'Submitted' },
  { key: 'skipped', title: 'Skipped' }, { key: 'draft', title: 'Draft' },
  { key: 'lastResponseAt', title: 'Last response' }, { key: 'actions', title: '', sortable: false }
]
const shareText = (count: number, share: number | null) => share === null ? '—' : `${count} (${share}%)`
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.surveys()).data
    if (request === generation) rows.value = result
  } catch {
    if (request === generation) error.value = 'Survey analytics could not be loaded.'
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
.survey-link { color: rgb(var(--v-theme-primary-dark)); text-decoration: none; }
.survey-link:hover { text-decoration: underline; }
</style>
