<template>
  <section aria-label="Attempt timeline">
    <h3 class="text-subtitle-1 font-weight-medium mt-4 mb-2">Attempts per task<InfoTip text="Evaluations of the model of the learner and help requests in time order. Evaluations started from a help request show its support kind and stage. Scores are only known once the learner has opened the feedback." /></h3>
    <v-progress-linear v-if="loading" indeterminate class="my-2" />
    <v-alert v-if="error" type="error" variant="tonal" class="my-2">{{ error }}<template #append><v-btn variant="text" @click="load">Try again</v-btn></template></v-alert>
    <p v-else-if="!loading && !steps.length" class="text-body-2 text-medium-emphasis">No evaluations or help requests yet.</p>
    <div v-for="step in steps" :key="step.stepId" class="mb-3">
      <div class="text-body-2 font-weight-medium">{{ step.title }}</div>
      <v-table density="compact" class="mini-table">
        <thead><tr><th>Time</th><th>Event</th><th>State</th><th class="text-end">Score</th><th>Support kind</th><th>Help request stage</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(event, index) in step.events" :key="index">
            <td>{{ date(event.at) }}</td>
            <td>{{ event.type === 'evaluation' ? 'Evaluation' : 'Help request' }}</td>
            <td>{{ event.state ?? '—' }}</td>
            <td class="text-end">{{ percentText(event.scorePercent === null ? null : Math.round(event.scorePercent)) }}<v-icon v-if="event.passed" size="14" color="success" class="ml-1" aria-label="Completion gate met">mdi-check-circle-outline</v-icon></td>
            <td>{{ supportKindLabel(event.supportKind) }}</td>
            <td>{{ helpStageLabel(event.helpStage) }}</td>
            <td class="text-end"><v-btn v-if="event.evaluationId" size="x-small" variant="tonal" prepend-icon="mdi-graph-outline" @click="modelEvaluationId = event.evaluationId">View submitted model</v-btn></td>
          </tr>
        </tbody>
      </v-table>
    </div>
    <AttemptModelDialog :template-id="templateId" :run-id="runId" :evaluation-id="modelEvaluationId" @close="modelEvaluationId = null" />
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import analytics, { type StepAttempts } from '@/services/analytics'
import AttemptModelDialog from '@/components/analytics/AttemptModelDialog.vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import { helpStageLabel, percentText, supportKindLabel } from '@/components/analytics/labels'

const props = defineProps<{ templateId: string; runId: string }>()
const steps = ref<StepAttempts[]>([])
const modelEvaluationId = ref<string | null>(null)
const loading = ref(false)
const error = ref('')
let generation = 0
const date = (value: string) => new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  steps.value = []
  modelEvaluationId.value = null
  try {
    const result = (await analytics.pathAttempts(props.templateId, props.runId)).data
    if (request === generation) steps.value = result
  } catch {
    if (request === generation) error.value = 'Attempts could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
watch(() => [props.templateId, props.runId], () => { void load() }, { immediate: true })
onUnmounted(() => { generation++ })
</script>

<style scoped>
.mini-table { background: transparent; }
</style>
