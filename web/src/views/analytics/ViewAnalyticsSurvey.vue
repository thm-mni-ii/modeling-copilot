<template>
  <div>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/analytics/surveys" class="mb-3">All surveys</v-btn>
    <div class="d-flex flex-wrap align-start ga-3 mb-4">
      <div class="flex-grow-1 survey-heading">
        <div class="d-flex flex-wrap align-center ga-2">
          <h2 class="text-h5">{{ summary?.title ?? 'Survey' }}</h2>
          <v-chip v-if="summary?.kind === 'help'" size="small" variant="tonal">Help flow</v-chip>
        </div>
      </div>
      <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>
    <v-sheet v-if="summary" border rounded="lg" class="filter-panel mb-4">
      <v-select v-model="release" :items="releaseItems" :disabled="!releaseItems.length" label="Release" placeholder="No release published" persistent-placeholder prepend-inner-icon="mdi-tag-outline" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details @update:model-value="load" />
      <v-select v-model="context" :items="contextItems" label="Context" prepend-inner-icon="mdi-filter-variant" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details @update:model-value="load" />
      <p class="text-caption text-medium-emphasis mb-0 context-note">
        Context shows where the questionnaire was answered: a learning path step, a pulse survey or the help flow. Other responses appear only under "All contexts".
      </p>
    </v-sheet>
    <kpi-tiles v-if="summary" :tiles="kpis" class="mb-4" />
    <v-sheet v-if="summary && !summary.release" border rounded="lg" class="pa-6">
      <p class="text-body-2 text-medium-emphasis mb-0">This survey has no published release yet, so there are no results.</p>
    </v-sheet>
    <v-sheet v-else-if="summary && !summary.submitted" border rounded="lg" class="pa-6">
      <p class="text-body-2 text-medium-emphasis mb-0">No submitted responses for this release and context yet.</p>
    </v-sheet>
    <div v-else-if="summary" class="question-grid">
      <question-card v-for="(question, index) in summary.questions" :key="question.name" :question="question" :number="index + 1" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import KpiTiles from '@/components/analytics/KpiTiles.vue'
import QuestionCard from '@/components/analytics/QuestionCard.vue'
import analytics, { type SurveyAnalyticsDetail, type SurveyContext } from '@/services/analytics'

const props = defineProps<{ surveyId: string }>()
const summary = ref<SurveyAnalyticsDetail | null>(null)
const release = ref<string | null>(null)
const context = ref<SurveyContext>('all')
const loading = ref(false)
const error = ref('')
let generation = 0

const CONTEXT_TITLES: Record<string, string> = { path: 'Learning path steps', pulse: 'Pulse surveys', help: 'Help flow' }
const date = (value: string | null) => value ? new Date(value).toLocaleDateString('en-GB', { dateStyle: 'short' }) : 'unreleased'
const releaseItems = computed(() => (summary.value?.releases ?? []).map((item) => ({
  title: `v${item.version}${item.active ? ' (active)' : ''} · ${item.submitted} submitted · ${date(item.releasedAt)}`, value: item.id
})))
const contextItems = computed(() => [
  { title: 'All contexts', value: 'all' },
  ...(summary.value?.contextCounts ?? []).map((item) => ({ title: `${CONTEXT_TITLES[item.key] ?? item.key} (${item.count})`, value: item.key }))
])
const kpis = computed(() => {
  const value = summary.value
  if (!value) return []
  return [
    { label: 'Responses, last 7 days', value: value.submittedLastWeek, tip: 'Submitted responses completed in the last 7 days, for the selected release and context. Test responses are excluded.' },
    { label: 'Responses, total', value: value.submitted, hint: `${value.skipped} skipped, ${value.draft} unfinished`, tip: 'Submitted responses of the selected release and context; the basis of all charts. Skipped and unfinished sessions carry no answers.' },
    { label: 'Completion', value: value.completionShare === null ? '–' : `${value.completionShare}%`, hint: `of ${value.responses} opened`, tip: 'Submitted share of all opened sessions (submitted, skipped and unfinished).' },
    { label: 'Last response', value: value.lastResponseAt ? date(value.lastResponseAt) : '–', tip: 'Completion date of the most recent submitted response.' }
  ]
})

const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  try {
    const result = (await analytics.survey(props.surveyId, release.value, context.value)).data
    if (request === generation) {
      summary.value = result
      release.value = result.release?.id ?? null
    }
  } catch (e) {
    if (request === generation) error.value = (e as { response?: { status?: number } }).response?.status === 404 ? 'This survey or release does not exist.' : 'Survey analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
watch(() => props.surveyId, () => {
  summary.value = null
  release.value = null
  context.value = 'all'
  void load()
}, { immediate: true })
onUnmounted(() => { generation++ })
</script>

<style scoped>
.survey-heading { min-width: 220px; }
.filter-panel { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr); gap: 12px; align-items: center; padding: 16px; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.context-note { grid-column: 1 / -1; }
.question-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: 12px; align-items: stretch; }
@media (max-width: 700px) {
  .filter-panel { grid-template-columns: 1fr; }
}
</style>
