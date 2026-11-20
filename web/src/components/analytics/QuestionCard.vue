<template>
  <v-sheet border rounded="lg" class="question-card">
    <div class="d-flex align-start ga-2 mb-3">
      <span class="question-number">{{ number }}</span>
      <h3 class="text-subtitle-2 font-weight-medium flex-grow-1 question-title">{{ question.title }}</h3>
    </div>
    <question-chart :question="question" />
    <div class="d-flex flex-wrap align-center ga-2 mt-3">
      <v-chip size="x-small" variant="tonal">{{ TYPE_TITLES[question.type] ?? question.type }}</v-chip>
      <v-chip size="x-small" color="primary-dark" variant="tonal">n = {{ question.responses }}</v-chip>
      <v-chip v-if="question.responses < LOW_N" size="x-small" color="warning" variant="tonal" prepend-icon="mdi-alert-outline">
        Low n
        <v-tooltip activator="parent" location="top">Fewer than {{ LOW_N }} responses; read the result with care.</v-tooltip>
      </v-chip>
    </div>
    <div v-if="trend" class="trend">
      <span class="text-caption text-medium-emphasis">{{ question.kind === 'rating' ? 'Weekly mean' : 'Responses per week' }}</span>
      <div class="spark" role="img" :aria-label="trend.label">
        <span v-for="point in trend.points" :key="point.week" class="spark-column" :title="point.text">
          <span class="spark-fill" :style="{ height: `${point.height}%` }" />
        </span>
      </div>
      <span class="text-caption text-medium-emphasis">{{ trend.first }} to {{ trend.last }}</span>
    </div>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import QuestionChart from '@/components/analytics/QuestionChart.vue'
import type { SurveyQuestionStats } from '@/services/analytics'

const LOW_N = 5
const TYPE_TITLES: Record<string, string> = { radiogroup: 'Single choice', dropdown: 'Single choice', checkbox: 'Multiple choice', boolean: 'Yes / no', rating: 'Rating', comment: 'Free text', matrix: 'Matrix', ranking: 'Ranking' }

const props = defineProps<{ question: SurveyQuestionStats; number: number }>()

const week = (value: string) => new Date(value).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', timeZone: 'UTC' })
// Mini columns per calendar week: mean rating (over the scale, from its minimum) or number of responses.
const trend = computed(() => {
  const { question } = props
  if (question.trend.length < 2 || question.kind === 'other') return null
  const rating = question.kind === 'rating'
  const low = rating ? question.scaleMin ?? 0 : 0
  const high = rating ? question.scaleMax ?? 1 : Math.max(1, ...question.trend.map((point) => point.responses))
  const points = question.trend.map((point) => {
    const value = rating ? point.mean : point.responses
    return {
      week: point.weekStart,
      height: value === null ? 0 : Math.max(4, (value - low) / (high - low || 1) * 100),
      text: `Week of ${week(point.weekStart)}: ${rating ? `mean ${point.mean ?? 'n/a'}, ` : ''}${point.responses} responses`
    }
  })
  return { points, first: week(question.trend[0].weekStart), last: week(question.trend[question.trend.length - 1].weekStart), label: `${question.title}, weekly trend: ${points.map((point) => point.text).join('; ')}` }
})
</script>

<style scoped>
.question-card { padding: 16px; border-color: rgba(var(--v-theme-on-surface), 0.12); display: flex; flex-direction: column; }
.question-number { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; flex-shrink: 0; border-radius: 7px; background: rgba(var(--v-theme-primary), 0.1); color: rgb(var(--v-theme-primary-dark)); font-size: 0.75rem; font-weight: 600; }
.question-title { min-width: 0; overflow-wrap: anywhere; line-height: 1.35; }
.trend { display: flex; flex-direction: column; gap: 2px; margin-top: auto; padding-top: 12px; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.spark { display: flex; align-items: flex-end; gap: 2px; height: 28px; }
.spark-column { flex: 1 1 0; max-width: 14px; height: 100%; display: flex; align-items: flex-end; }
.spark-fill { display: block; width: 100%; border-radius: 2px 2px 0 0; background: rgba(var(--v-theme-primary-dark), 0.55); }
</style>
