<template>
  <v-expansion-panel :value="survey.id" class="survey-panel">
    <v-expansion-panel-title>
      <div class="survey-title">
        <div class="d-flex flex-wrap align-center ga-2">
          <span class="text-subtitle-1 font-weight-medium">{{ survey.title }}</span>
          <v-chip v-for="usage in survey.usages" :key="usage" size="x-small" variant="tonal">{{ usage }}</v-chip>
          <v-chip v-if="!survey.usages.length" size="x-small" variant="tonal" color="warning">No longer used in this path</v-chip>
        </div>
        <div class="text-body-2 text-medium-emphasis mt-1 d-flex flex-wrap align-center ga-x-3">
          <span>Last 7 days: <strong>{{ survey.submittedLastWeek }}</strong> {{ survey.submittedLastWeek === 1 ? 'response' : 'responses' }}</span>
          <span v-if="change !== null" class="d-inline-flex align-center">
            <v-icon size="14" class="mr-1">{{ change > 0 ? 'mdi-arrow-up' : change < 0 ? 'mdi-arrow-down' : 'mdi-minus' }}</v-icon>{{ changeText }} vs previous 7 days
          </span>
          <span v-for="rating in summaryRatings" :key="rating.name" class="rating-summary" :title="rating.title">
            {{ shorten(rating.title) }}: <strong>{{ mean(rating.meanLastWeek) }}</strong> <span>(overall {{ mean(rating.meanOverall) }})</span>
          </span>
          <span v-if="extraRatings">+{{ extraRatings }} more rating {{ extraRatings === 1 ? 'question' : 'questions' }}</span>
        </div>
      </div>
    </v-expansion-panel-title>
    <v-expansion-panel-text>
      <p v-if="!survey.releases.length" class="text-body-2 text-medium-emphasis mb-0">
        Nobody in this path has answered this survey yet.<span v-if="survey.responses"> {{ survey.responses }} unfinished or skipped.</span>
      </p>
      <template v-else>
        <div class="d-flex flex-wrap align-center ga-4 mb-3">
          <v-select v-if="survey.releases.length > 1" v-model="releaseId" :items="releaseItems" label="Release" prepend-inner-icon="mdi-tag-outline" color="primary-dark" bg-color="surface" variant="outlined" density="compact" hide-details class="release-select" />
          <span v-else class="text-body-2 text-medium-emphasis">Release v{{ release?.version }}</span>
          <span class="text-body-2 text-medium-emphasis">
            {{ survey.submitted }} submitted in total · completion {{ survey.completionShare === null ? '–' : `${survey.completionShare}%` }} of {{ survey.responses }} opened · last response {{ date(survey.lastResponseAt) }}
          </span>
        </div>
        <div v-if="release" class="question-grid">
          <question-card v-for="(question, index) in release.questions" :key="question.name" :question="question" :number="index + 1" />
        </div>
      </template>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import QuestionCard from '@/components/analytics/QuestionCard.vue'
import type { PathSurvey } from '@/services/analytics'

const SUMMARY_RATINGS = 2
const props = defineProps<{ survey: PathSurvey }>()
const releaseId = ref<string | null>(null)
// Releases come newest first; the newest answered one is shown until another is chosen.
const release = computed(() => props.survey.releases.find((item) => item.id === releaseId.value) ?? props.survey.releases[0])
const change = computed(() => props.survey.submittedLastWeek || props.survey.submittedPreviousWeek ? props.survey.submittedLastWeek - props.survey.submittedPreviousWeek : null)
const changeText = computed(() => `${change.value! > 0 ? '+' : change.value! < 0 ? '−' : '±'}${Math.abs(change.value!)}`)
const ratings = computed(() => props.survey.releases[0]?.ratings ?? [])
const summaryRatings = computed(() => ratings.value.slice(0, SUMMARY_RATINGS))
const extraRatings = computed(() => Math.max(ratings.value.length - SUMMARY_RATINGS, 0))
const date = (value: string | null) => value ? new Date(value).toLocaleDateString('en-GB', { dateStyle: 'short' }) : '–'
const mean = (value: number | null) => value === null ? '–' : value.toFixed(2)
const shorten = (title: string) => title.length > 40 ? `${title.slice(0, 39)}…` : title
const releaseItems = computed(() => props.survey.releases.map((item) => ({
  title: `v${item.version}${item.active ? ' (active)' : ''} · ${item.submitted} submitted · ${date(item.releasedAt)}`, value: item.id
})))
</script>

<style scoped>
.survey-panel { border: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.survey-title { min-width: 0; }
.release-select { max-width: 380px; min-width: 240px; }
.question-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr)); gap: 12px; align-items: stretch; }
</style>
