<template>
  <v-dialog :model-value="Boolean(evaluationId)" max-width="1400" scrollable aria-label="Submitted model" @update:model-value="!$event && emit('close')">
    <v-card>
      <v-card-title class="d-flex align-center ga-2">
        <v-icon color="primary-dark" size="22">mdi-graph-outline</v-icon>
        <span class="text-h6">Submitted model<template v-if="result"> · {{ result.stepTitle }} · {{ date(result.startedAt) }}</template></span>
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" aria-label="Close model" @click="emit('close')" />
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" density="compact" class="mb-3">Read-only. Each time a model is opened here, the access is logged (who, which participant, which attempt, when).</v-alert>
        <v-progress-linear v-if="loading" indeterminate class="my-3" />
        <v-alert v-if="error" type="error" variant="tonal">{{ error }}<template #append><v-btn variant="text" @click="load">Try again</v-btn></template></v-alert>
        <div v-if="result" class="attempt-model">
          <ModelSnapshotPreview :data="modelData" :height="560" fit />
          <aside aria-label="Feedback the learner received">
            <h3 class="text-subtitle-1 font-weight-medium mb-2">Feedback the learner received</h3>
            <p v-if="!result.feedback" class="text-body-2 text-medium-emphasis">The learner has not opened the feedback of this attempt, or the evaluation has not finished.</p>
            <template v-else>
              <div class="d-flex flex-wrap align-center ga-2 mb-2">
                <v-chip size="small" variant="tonal" label>{{ result.feedback.state }}</v-chip>
                <span class="text-body-2">Score: {{ percentText(result.feedback.scorePercent === null ? null : Math.round(result.feedback.scorePercent)) }}</span>
              </div>
              <div v-for="item in recognitions" :key="item.referenceKey" class="text-body-2 mb-1">
                Recognition ({{ item.referenceKey }}): {{ item.recognized }} of {{ item.expected }} expected objects
              </div>
              <FeedbackView v-if="result.feedback.feedback?.length" :entries="result.feedback.feedback" :snapshot-xml="result.xml" class="mt-3" />
              <p v-else class="text-body-2 text-medium-emphasis mt-2">No help feedback was produced for this attempt.</p>
            </template>
          </aside>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import analytics, { type AttemptModel } from '@/services/analytics'
import FeedbackView from '@/components/feedback/FeedbackView.vue'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import { percentText } from '@/components/analytics/labels'

const props = defineProps<{ templateId: string; runId: string; evaluationId: string | null }>()
const emit = defineEmits<{ close: [] }>()
const result = ref<AttemptModel | null>(null)
const loading = ref(false)
const error = ref('')
let generation = 0
const date = (value: string) => new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' })
// Stable object: the preview reloads the graph whenever the prop identity changes.
const modelData = computed(() => (result.value ? { xml: result.value.xml } : null))
const recognitions = computed(() => (result.value?.feedback?.recognitions ?? []).flatMap(({ referenceKey, recognition }) => {
  const overall = recognition.overall as { recognized?: number; expected?: number } | undefined
  return typeof overall?.recognized === 'number' && typeof overall.expected === 'number' ? [{ referenceKey, recognized: overall.recognized, expected: overall.expected }] : []
}))
const load = async () => {
  const request = ++generation
  result.value = null
  error.value = ''
  if (!props.evaluationId) return
  loading.value = true
  try {
    const model = (await analytics.attemptModel(props.templateId, props.runId, props.evaluationId)).data
    if (request === generation) result.value = model
  } catch {
    if (request === generation) error.value = 'The model could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
watch(() => [props.templateId, props.runId, props.evaluationId], () => { void load() }, { immediate: true })
onUnmounted(() => { generation++ })
</script>

<style scoped>
.attempt-model { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 16px; align-items: start; }
@media (max-width: 960px) { .attempt-model { grid-template-columns: minmax(0, 1fr); } }
</style>
