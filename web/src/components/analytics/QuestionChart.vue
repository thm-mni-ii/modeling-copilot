<template>
  <p v-if="question.kind === 'other'" class="text-body-2 text-medium-emphasis mb-0">No chart for this question type; only the response count is shown.</p>
  <p v-else-if="!question.responses" class="text-body-2 text-medium-emphasis mb-0">No responses yet.</p>
  <p v-else-if="question.kind === 'text'" class="text-body-2 mb-0">
    Average length <strong>{{ question.avgLength }}</strong> characters. Free-text answers are never displayed.
  </p>

  <div v-else-if="question.kind === 'rating'" role="img" :aria-label="ratingLabel">
    <div class="histogram">
      <div class="columns">
        <div v-for="bar in bars" :key="bar.key" class="column" :title="`${bar.key}: ${bar.count} (${bar.share}%)`">
          <span class="column-count text-caption">{{ bar.count || '' }}</span>
          <span class="column-fill" :style="{ height: `${bar.height}%` }" />
        </div>
        <span class="marker marker-mean" :style="{ left: `${position(question.mean)}%` }" />
        <span class="marker marker-median" :style="{ left: `${position(question.median)}%` }" />
      </div>
      <div class="axis text-caption">
        <span v-for="bar in bars" :key="bar.key" :class="{ 'axis-hidden': !bar.labelled }">{{ bar.key }}</span>
      </div>
    </div>
    <div v-if="question.minLabel || question.maxLabel" class="d-flex justify-space-between text-caption text-medium-emphasis mt-1">
      <span>{{ question.minLabel }}</span><span class="text-right">{{ question.maxLabel }}</span>
    </div>
    <div class="legend text-caption mt-2">
      <span><span class="swatch marker-mean" />Mean <strong>{{ question.mean }}</strong></span>
      <span><span class="swatch marker-median" />Median <strong>{{ question.median }}</strong></span>
    </div>
  </div>

  <div v-else-if="question.type === 'boolean'" role="img" :aria-label="booleanLabel">
    <div class="split">
      <span v-for="segment in segments" :key="segment.key" class="segment" :class="`segment-${segment.key}`" :style="{ flexGrow: segment.count }" />
    </div>
    <div class="legend text-caption mt-2">
      <span v-for="segment in segments" :key="segment.key"><span class="swatch" :class="`segment-${segment.key}`" />{{ segment.label }} <strong>{{ segment.count }}</strong> ({{ segment.share }}%)</span>
    </div>
  </div>

  <div v-else>
    <bar-rows :rows="rows" :max="question.responses" />
    <p v-if="question.type === 'checkbox'" class="text-caption text-medium-emphasis mt-2 mb-0">Share of respondents; several options can be selected, so shares can exceed 100% in total.</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BarRows from '@/components/analytics/BarRows.vue'
import type { SurveyQuestionStats } from '@/services/analytics'

const props = defineProps<{ question: SurveyQuestionStats }>()

const share = (count: number) => props.question.responses ? Math.round(count / props.question.responses * 100) : 0
const rows = computed(() => props.question.options.map((option) => ({ label: option.label, value: option.count, text: `${option.count} (${share(option.count)}%)` })))

const segments = computed(() => props.question.options.map((option) => ({ ...option, share: share(option.count) })))
const booleanLabel = computed(() => `${props.question.title}: ${segments.value.map((segment) => `${segment.label} ${segment.count} (${segment.share}%)`).join(', ')}`)

const bars = computed(() => {
  const top = Math.max(1, ...props.question.options.map((option) => option.count))
  const step = Math.ceil(props.question.options.length / 11)
  return props.question.options.map((option, index) => ({
    ...option, share: share(option.count), height: option.count / top * 100, labelled: index % step === 0 || index === props.question.options.length - 1
  }))
})
// Marker x position as percent of the histogram width: each scale value owns one equally wide column.
const position = (value: number | null) => {
  const { scaleMin, scaleMax } = props.question
  return value === null || scaleMin === null || scaleMax === null ? 0 : (value - scaleMin + 0.5) / (scaleMax - scaleMin + 1) * 100
}
const ratingLabel = computed(() => `${props.question.title}: mean ${props.question.mean}, median ${props.question.median}, scale ${props.question.scaleMin} to ${props.question.scaleMax}. ${bars.value.map((bar) => `${bar.key}: ${bar.count}`).join(', ')}`)
</script>

<style scoped>
.histogram { position: relative; }
.columns { position: relative; display: flex; align-items: flex-end; gap: 2px; height: 96px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.2); }
.column { flex: 1 1 0; min-width: 0; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: stretch; text-align: center; }
.column-count { line-height: 1.2; font-variant-numeric: tabular-nums; }
.column-fill { display: block; min-height: 2px; border-radius: 3px 3px 0 0; background: rgb(var(--v-theme-primary-dark)); }
.marker { position: absolute; top: 0; bottom: 0; width: 0; transform: translateX(-1px); pointer-events: none; }
.marker-mean { border-left: 2px solid rgb(var(--v-theme-dark-gray)); }
.marker-median { border-left: 2px dashed rgb(var(--v-theme-secondary-darken-1)); }
.axis { display: flex; gap: 2px; }
.axis span { flex: 1 1 0; min-width: 0; text-align: center; font-variant-numeric: tabular-nums; }
.axis-hidden { visibility: hidden; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: center; }
.swatch { display: inline-block; position: static; transform: none; width: 10px; height: 10px; margin-right: 6px; border-radius: 2px; vertical-align: -1px; }
.swatch.marker-mean { background: rgb(var(--v-theme-dark-gray)); border: 0; }
.swatch.marker-median { background: rgb(var(--v-theme-secondary-darken-1)); border: 0; }
.split { display: flex; height: 22px; gap: 2px; border-radius: 4px; overflow: hidden; background: rgba(var(--v-theme-on-surface), 0.06); }
.segment { flex-basis: 0; min-width: 0; }
.segment-true { background: rgb(var(--v-theme-primary-dark)); }
.segment-false { background: rgb(var(--v-theme-medium-gray)); }
</style>
