<template>
  <div>
    <kpi-tiles :tiles="kpis" class="mb-4" />
    <LearningPathProgressStats :records="records" :template-id="templateId" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import KpiTiles from '@/components/analytics/KpiTiles.vue'
import LearningPathProgressStats from '@/components/learningPaths/LearningPathProgressStats.vue'
import type { PathAnalyticsDetail } from '@/services/analytics'
import type { PathProgressSummary } from '@/services/learningPaths'

const props = defineProps<{ templateId: string; summary: PathAnalyticsDetail; records: PathProgressSummary[] }>()
const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const duration = (seconds: number | null) => {
  if (seconds === null) return '—'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours} h ${minutes % 60} min`
  return `${Math.floor(hours / 24)} d ${hours % 24} h`
}
const kpis = computed(() => [
  { label: 'Participants', value: props.summary.participants, tip: 'People who started this path.' },
  { label: 'Completed', value: `${props.summary.completed} (${props.summary.completionRate}%)`, tip: 'Finished every active step.' },
  { label: 'Average progress', value: `${props.summary.avgProgress}%`, tip: 'Mean share of finished steps.' },
  { label: 'Median time to finish', value: duration(props.summary.medianSecondsToFinish), tip: 'From start to first completion.' },
  { label: 'Stalled', value: props.summary.stalled, tip: 'In progress, inactive for more than 7 days.' },
  { label: 'Last activity', value: date(props.summary.lastActivityAt), tip: 'Most recent recorded activity.' }
].map((kpi) => ({ ...kpi, hint: kpi.tip })))
</script>
