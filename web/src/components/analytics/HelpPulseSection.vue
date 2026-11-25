<template>
  <v-sheet border rounded="lg" class="analytics-panel mb-4" aria-labelledby="help-pulse-title">
    <div class="d-flex align-center ga-3 pa-4">
      <v-icon color="primary-dark" size="22">mdi-lifebuoy</v-icon>
      <div>
        <h2 id="help-pulse-title" class="text-subtitle-1 font-weight-medium">Help &amp; pulse</h2>
        <div class="text-caption text-medium-emphasis">How learners use the help flow and respond to pulse questionnaires.</div>
      </div>
    </div>
    <v-divider />
    <div class="pa-4">
      <h3 class="text-subtitle-2 font-weight-medium">Help request funnel<InfoTip text="Each help request walks through the help flow: problem area question, reflection questions (and an optional marking), then the choice of help source. Counts are help requests that reached or passed a stage. Abort rate is the share of requests cancelled at the first question; open requests were neither completed nor cancelled." /></h3>
      <v-table density="compact" class="mini-table mt-2">
        <thead>
          <tr><th>Step</th><th class="text-end">Requests</th><th class="text-end">Problem area</th><th class="text-end">Reflection</th><th class="text-end">Completed</th><th class="text-end">Cancelled</th><th class="text-end">Open</th><th class="text-end">Abort rate</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in funnelRows" :key="row.key" :class="{ 'font-weight-medium': row.total }">
            <td>{{ row.title }}</td><td class="text-end">{{ row.help.requests }}</td><td class="text-end">{{ row.help.topicDone }}</td><td class="text-end">{{ row.help.reflectionDone }}</td>
            <td class="text-end">{{ row.help.completed }}</td><td class="text-end">{{ row.help.cancelled }}</td><td class="text-end">{{ row.help.open }}</td><td class="text-end">{{ percentText(row.help.abortRate) }}</td>
          </tr>
        </tbody>
      </v-table>
    </div>
    <v-divider />
    <div class="pa-4">
      <h3 class="text-subtitle-2 font-weight-medium">Help flow answers<InfoTip text="Answers of learners to the help questionnaire, counted per submitted phase. Only completed phases are counted; labels come from the questionnaire release the learner saw." /></h3>
      <p v-if="!feedback.help.requests" class="text-body-2 text-medium-emphasis mt-2 mb-0">No help requests yet.</p>
      <div v-else class="answers mt-2">
        <div v-for="question in feedback.helpAnswers" :key="question.name">
          <div class="text-body-2 font-weight-medium">{{ question.title }}</div>
          <div class="text-caption text-medium-emphasis">{{ question.responses }} answers</div>
          <BarRows :max="100" :rows="question.options.map((option) => ({ label: option.key, value: share(option.count, question.responses), text: `${option.count} (${share(option.count, question.responses)}%)` }))" />
        </div>
      </div>
    </div>
    <v-divider />
    <div class="pa-4">
      <h3 class="text-subtitle-2 font-weight-medium">Pulse questionnaires<InfoTip text="Pulse questionnaires are short surveys offered while learners work on a task. Rates are shares of all offers; opened includes answered, so the rates overlap. Pending offers have no reaction yet. A session is one browser session of a learner." /></h3>
      <p v-if="!pulse.offers" class="text-body-2 text-medium-emphasis mt-2 mb-0">No pulse questionnaires have been offered yet.</p>
      <template v-else>
        <section class="tiles my-3" aria-label="Pulse figures">
          <div v-for="tile in tiles" :key="tile.label" class="tile" tabindex="0">
            <span class="tile-value">{{ tile.value }}</span>
            <span class="tile-label">{{ tile.label }}</span>
            <v-tooltip activator="parent" location="bottom" max-width="320">{{ tile.tip }}</v-tooltip>
          </div>
        </section>
        <v-table density="compact" class="mini-table">
          <thead><tr><th>Pulse questionnaire</th><th class="text-end">Offered</th><th class="text-end">Answered</th><th class="text-end">Answer rate</th></tr></thead>
          <tbody>
            <tr v-for="survey in pulse.surveys" :key="survey.surveyId"><td>{{ survey.name }}</td><td class="text-end">{{ survey.offered }}</td><td class="text-end">{{ survey.answered }}</td><td class="text-end">{{ percentText(survey.answerRate) }}</td></tr>
          </tbody>
        </v-table>
      </template>
    </div>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PathFeedback } from '@/services/analytics'
import BarRows from '@/components/analytics/BarRows.vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import { percentText } from '@/components/analytics/labels'

const props = defineProps<{ feedback: PathFeedback }>()
const pulse = computed(() => props.feedback.pulse)
const share = (count: number, total: number) => total ? Math.round(count / total * 100) : 0
const funnelRows = computed(() => [
  ...props.feedback.steps.map((step) => ({ key: step.stepId, title: step.title, help: step.help, total: false })),
  { key: 'all', title: 'All steps', help: props.feedback.help, total: true }
])
const tiles = computed(() => [
  { label: 'Offers', value: pulse.value.offers, tip: 'Pulse questionnaires offered to learners.' },
  { label: 'Opened', value: percentText(pulse.value.openRate), tip: 'Offers the learner opened, including answered ones.' },
  { label: 'Answered', value: percentText(pulse.value.answerRate), tip: 'Offers whose questionnaire was submitted.' },
  { label: 'Dismissed', value: percentText(pulse.value.dismissRate), tip: 'Offers the learner dismissed.' },
  { label: 'Expired', value: percentText(pulse.value.expiredRate), tip: 'Offers that were not clicked in time.' },
  { label: 'Pending', value: pulse.value.pending, tip: 'Offers without a recorded reaction yet.' },
  { label: 'Offers per session', value: pulse.value.offersPerSession ?? '—', tip: `Mean offers per browser session (${pulse.value.sessions} sessions with an offer).` }
])
</script>

<style scoped>
.analytics-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
.tile { display: flex; flex-direction: column; padding: 10px 14px; border: 1px solid rgba(var(--v-theme-primary), 0.18); border-radius: 10px; background: rgba(var(--v-theme-primary), 0.04); }
.tile-value { font-size: 1.25rem; line-height: 1.2; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile-label { font-size: 0.8125rem; font-weight: 500; }
.answers { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 24px; }
.mini-table { background: transparent; }
</style>
