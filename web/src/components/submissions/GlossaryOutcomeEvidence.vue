<template>
  <div class="case-evidence">
    <div>
      <div class="text-caption text-medium-emphasis mb-2">{{ occurrence.usedForLearnerResult ? 'Used for learner result' : 'Selected sample solution' }}</div>
      <v-progress-linear v-if="loading" indeterminate aria-label="Loading decision evidence" />
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-2">
        {{ error }} <v-btn size="small" variant="text" @click="load">Retry</v-btn>
      </v-alert>
      <v-select v-if="explanations.length > 1" v-model="explanationIndex" :items="explanationItems" label="Term occurrence in this submission" density="compact" hide-details class="mb-3" />
      <section v-if="item" class="mb-2">
        <div class="text-subtitle-2">{{ item.submissionLabel }} → {{ referenceLabel || item.referenceLabel }}</div>
        <GlossaryTermSimilarity :comparisons="pairComparisons" />
        <div class="text-caption mt-2"><strong>{{ stateTitles[item.state] }}</strong> · {{ item.resultReason }}</div>
        <details class="text-caption">
          <summary class="text-medium-emphasis my-2">Technical details</summary>
        <template v-if="item.checks.length">
          <div class="text-subtitle-2">{{ item.evidenceScope === 'pair' ? 'Recorded checks for this pair' : item.evidenceScope === 'submission' ? 'Recorded checks across this element’s alternatives' : 'Context and glossary evidence' }}</div>
          <ul class="evidence-checks mb-3">
            <li v-for="(check, checkIndex) in item.checks" :key="`${check.method}:${checkIndex}`" class="my-2">
              <strong>{{ methodLabel(check.method) }}</strong> · {{ resultLabel(check.result) }}<span v-if="check.role === 'identity_anchor'"> · decisive identity evidence</span>
              <div class="text-caption">{{ check.note }}</div>
            </li>
          </ul>
        </template>
        <template v-if="item.similarities.length">
          <div class="text-subtitle-2">Text comparison</div>
          <p class="text-caption text-medium-emphasis mb-2">Scores and saved thresholds are shown separately. A score above a threshold supports text similarity; the complete match still needs a unique correspondence.</p>
          <v-table density="compact" class="mb-3">
            <thead><tr><th>Method</th><th>Score</th><th>Saved thresholds</th><th>Confirmation floor</th></tr></thead>
            <tbody>
              <tr v-for="score in item.similarities" :key="`${score.method}:${score.referenceText ?? ''}`">
                <td>{{ similarityMethodLabel(score.method) }}<div v-if="score.referenceText" class="text-caption">Approved source: {{ score.referenceText }}</div></td>
                <td>{{ score.score == null ? 'Not scored' : score.score.toFixed(3) }}</td>
                <td><div v-for="(threshold, tier) in score.thresholds" :key="tier">{{ tierLabel(tier) }} ≥ {{ threshold.toFixed(3) }}<span v-if="score.score != null"> · {{ score.score >= threshold ? 'reached' : 'below' }}</span></div><span v-if="!Object.keys(score.thresholds).length">Not recorded</span></td>
                <td><div v-for="(floor, tier) in score.confirmationFloors" :key="tier">{{ tierLabel(tier) }} ≥ {{ floor.toFixed(3) }}</div><span v-if="!Object.keys(score.confirmationFloors).length">Not recorded</span></td>
              </tr>
            </tbody>
          </v-table>
        </template>
        <details v-if="item.alternatives.length" class="mb-3">
          <summary class="text-body-2">Other compared pairs ({{ item.alternatives.length }})</summary>
          <ul class="evidence-checks text-caption mt-2"><li v-for="alternative in item.alternatives" :key="`${alternative.referenceElementId}:${alternative.submissionElementId}`">{{ alternative.submissionLabel }} → {{ alternative.referenceLabel }} · {{ alternative.counted ? 'confirmed in final feedback' : 'compared; no final recognition confirmed' }}<div class="text-medium-emphasis">Elements {{ alternative.submissionElementId }} → {{ alternative.referenceElementId }}</div></li></ul>
        </details>
        <v-alert v-if="item.limitations.length" type="info" variant="tonal" density="compact">
          <div class="font-weight-medium">Evidence limits</div>
          <ul class="evidence-checks text-caption"><li v-for="note in item.limitations" :key="note">{{ note }}</li></ul>
        </v-alert>
          <div class="text-medium-emphasis mt-3">Evaluation: {{ occurrence.evaluationId }}</div>
          <div class="text-medium-emphasis">Submission version: {{ occurrence.modelVersionId }}</div>
          <div v-if="occurrence.evidenceNote">{{ occurrence.evidenceNote }}</div>
        </details>
      </section>
      <p v-else-if="!loading && !error" class="text-body-2">The saved records do not contain an explanation for this case.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import GlossaryTermSimilarity from './GlossaryTermSimilarity.vue'
import { synonymGlossary, type OutcomeExplanation, type OutcomeOccurrence, type SolutionRef, type TermOutcome } from '@/services/synonymGlossary'
import { similarityMethodLabel } from '@/utils/analysisFeedback'

const props = defineProps<{ solution: SolutionRef; outcome: TermOutcome; occurrence: OutcomeOccurrence; replayId: string | null; referenceLabel?: string }>()
const explanations = ref<OutcomeExplanation[]>([])
const loading = ref(false)
const error = ref('')
const stateTitles = { counted: 'Counted', partial: 'Partially recognized', not_counted: 'Not counted', counted_elsewhere: 'Other element', unknown: 'No saved counting decision' }
const explanationIndex = ref(0)
const item = computed(() => explanations.value[explanationIndex.value])
const pairComparisons = computed(() => (item.value?.similarities ?? []).filter(score => score.score != null).map(score => ({
  referenceText: score.referenceText ?? item.value!.referenceLabel, submissionText: item.value!.submissionLabel,
  method: score.method, minimum: score.score!, maximum: score.score!
})))
const explanationItems = computed(() => explanations.value.map((explanation, index) => ({ title: `${explanation.submissionLabel} · ${stateTitles[explanation.state]} · Occurrence ${index + 1}`, value: index })))
const methodLabel = (method: string) => ({ exact_label: 'Exact label', type_compatibility: 'Type compatibility', independent_children: 'Recognized child elements', combined_children: 'Combined child structure', identified_owner: 'Recognized owner', connection_structure: 'Connection endpoints', text_similarity: 'Text matching', label_structure: 'Label / structure conflict', candidate_count: 'Supported alternatives', frozen_glossary: 'Glossary at evaluation time', suggestion_context: 'Glossary suggestion' }[method] ?? method)
const resultLabel = (result: string) => ({ satisfied: 'Satisfied', violated: 'Not satisfied', unresolved: 'Unresolved', not_evaluated: 'Not evaluated', not_applicable: 'Not applicable', informational: 'Information' }[result] ?? result)
const tierLabel = (tier: string) => ({ canonical: 'Canonical spelling', spelling: 'Spelling similarity', meaning: 'Meaning similarity', glossary: 'Glossary', minimumSimilarity: 'Minimum similarity' }[tier] ?? tier)
const load = async () => {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    explanations.value = (await synonymGlossary.explainOutcome(props.solution, props.outcome, props.occurrence, props.replayId)).data
  } catch (cause) {
    error.value = (cause as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Decision evidence could not be loaded.'
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.case-evidence summary { cursor: pointer; }
.evidence-checks { padding-left: 20px; }
</style>
