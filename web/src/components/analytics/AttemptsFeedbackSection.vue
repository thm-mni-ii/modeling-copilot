<template>
  <v-sheet border rounded="lg" class="analytics-panel mb-4" aria-labelledby="attempts-title">
    <div class="d-flex align-center ga-3 pa-4">
      <v-icon color="primary-dark" size="22">mdi-chart-timeline-variant</v-icon>
      <div>
        <h2 id="attempts-title" class="text-subtitle-1 font-weight-medium">Attempts &amp; feedback<InfoTip :text="intro" /></h2>
        <div class="text-caption text-medium-emphasis">Evaluations of the models in each task step, and the help learners requested.</div>
      </div>
    </div>
    <v-divider />
    <p v-if="!steps.length" class="pa-5 text-body-2 text-medium-emphasis mb-0">This learning path has no task steps.</p>
    <v-expansion-panels v-else v-model="open" multiple variant="accordion" elevation="0">
      <v-expansion-panel v-for="step in steps" :key="step.stepId" :value="step.stepId">
        <v-expansion-panel-title>
          <div class="d-flex flex-wrap align-center ga-2">
            <span class="font-weight-medium">{{ step.title }}</span>
            <v-chip size="x-small" variant="tonal">{{ step.attemptPersons }} of {{ step.persons }} started have an attempt</v-chip>
            <v-chip v-if="step.minimumScorePercent !== null" size="x-small" variant="tonal" color="info">Gate {{ step.minimumScorePercent }}%</v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <section class="tiles mb-4" :aria-label="`Key figures for ${step.title}`">
            <div v-for="tile in tiles(step)" :key="tile.label" class="tile" tabindex="0">
              <span class="tile-value">{{ tile.value }}</span>
              <span class="tile-label">{{ tile.label }}</span>
              <v-tooltip activator="parent" location="bottom" max-width="320">{{ tile.tip }}</v-tooltip>
            </div>
          </section>
          <div class="charts">
            <div>
              <h3 class="text-body-2 font-weight-medium">Attempts per person<InfoTip text="Number of evaluations per person for this task, counting people with at least one attempt. Failed and cancelled evaluations are not attempts." /></h3>
              <BarRows :rows="step.attemptDistribution.map((bin) => ({ label: bin.label, value: bin.users }))" />
            </div>
            <div>
              <h3 class="text-body-2 font-weight-medium">Best score per person<InfoTip text="Each person is counted once, in the band of their best score. Only people with a scored attempt are included." /></h3>
              <BarRows :rows="step.scoreBands.map((bin) => ({ label: bin.label, value: bin.users }))" />
            </div>
            <div>
              <h3 class="text-body-2 font-weight-medium">Score by attempt number<InfoTip text="Average score of the 1st, 2nd, ... attempt across people (first 10 attempts). n is the number of scored attempts behind each average." /></h3>
              <BarRows v-if="step.scoreCurve.length" :max="100" :rows="step.scoreCurve.map((point) => ({ label: `Attempt ${point.attempt}`, value: point.avgScore ?? 0, text: `${percentText(point.avgScore)} (n=${point.scored})` }))" />
              <p v-else class="text-caption text-medium-emphasis mt-2 mb-0">No scored attempts yet.</p>
            </div>
          </div>
          <div class="charts mt-4">
            <div>
              <h3 class="text-body-2 font-weight-medium">Help kinds used<InfoTip text="Help requests per kind chosen in the help flow. Persons are distinct learners; requests include requests without a delivered result." /></h3>
              <v-table density="compact" class="mini-table">
                <thead><tr><th>Kind</th><th class="text-end">Persons</th><th class="text-end">Requests</th></tr></thead>
                <tbody>
                  <tr v-for="use in step.support" :key="use.kind"><td>{{ supportKindLabel(use.kind) }}</td><td class="text-end">{{ use.persons }}</td><td class="text-end">{{ use.requests }}</td></tr>
                </tbody>
              </v-table>
            </div>
            <div>
              <h3 class="text-body-2 font-weight-medium">Exhausted limits<InfoTip text="People who received as many delivered example or solution results as the task allows, as a share of all people who started the task. The limit comes from the help configuration of the task; no limit means nobody can exhaust it." /></h3>
              <v-table density="compact" class="mini-table">
                <thead><tr><th>Kind</th><th class="text-end">Limit</th><th class="text-end">Exhausted</th></tr></thead>
                <tbody>
                  <tr v-for="limit in step.limits" :key="limit.kind">
                    <td>{{ supportKindLabel(limit.kind) }}</td>
                    <td class="text-end">{{ limit.limit ?? 'None' }}</td>
                    <td class="text-end">{{ limit.exhausted === null ? '—' : `${limit.exhausted} (${percentText(limit.share)})` }}</td>
                  </tr>
                </tbody>
              </v-table>
            </div>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-sheet>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { StepFeedback } from '@/services/analytics'
import BarRows from '@/components/analytics/BarRows.vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import { percentText, supportKindLabel } from '@/components/analytics/labels'

const props = defineProps<{ steps: StepFeedback[] }>()
const open = ref<string[]>(props.steps.slice(0, 1).map((step) => step.stepId))
const intro = 'An attempt is an evaluation of the model a learner built in the task step. Scores are the best overall recognition across the sample solutions and are only known once the learner has opened the feedback.'
const tiles = (step: StepFeedback) => [
  { label: 'Started', value: step.persons, tip: 'People who started this task.' },
  { label: 'With attempt', value: step.attemptPersons, tip: 'People with at least one attempt.' },
  { label: 'Avg attempts', value: step.avgAttempts ?? '—', tip: 'Mean number of attempts per person with at least one attempt.' },
  { label: 'Avg first score', value: percentText(step.avgFirstScore), tip: `Mean score of the first scored attempt of each person (${step.scoredPersons} people with a score).` },
  { label: 'Avg best score', value: percentText(step.avgBestScore), tip: `Mean of the best score of each person (${step.scoredPersons} people with a score).` },
  ...(step.minimumScorePercent === null ? [] : [{
    label: 'Passed gate', value: `${step.passedPersons ?? 0} (${percentText(step.passedShare)})`,
    tip: `People with an attempt that met the completion gate (minimum ${step.minimumScorePercent}%, plus any category minimums), as a share of people with an attempt.`
  }])
]
</script>

<style scoped>
.analytics-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.tile { display: flex; flex-direction: column; padding: 10px 14px; border: 1px solid rgba(var(--v-theme-primary), 0.18); border-radius: 10px; background: rgba(var(--v-theme-primary), 0.04); }
.tile-value { font-size: 1.25rem; line-height: 1.2; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile-label { font-size: 0.8125rem; font-weight: 500; }
.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; }
.mini-table { background: transparent; }
</style>
