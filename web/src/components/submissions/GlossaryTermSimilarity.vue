<template>
  <div class="term-similarity">
    <div v-if="comparisons?.length" class="d-flex flex-wrap ga-1">
      <v-menu v-for="score in scores" :key="score.method" open-on-hover :open-on-click="false" :open-delay="80" :close-delay="120" location="bottom start" max-width="360">
        <template #activator="{ props: activator }">
          <span v-bind="activator" class="text-caption score-label" :class="tone(score)" tabindex="0">{{ compactSimilarityMethodLabel(score.method) }} <strong>{{ percent(score.minimum, score.maximum) }}</strong></span>
        </template>
        <v-card class="pa-2 score-panel" elevation="6">
          <div class="text-caption text-medium-emphasis">{{ similarityMethodLabel(score.method) }}</div>
          <div class="text-body-2">{{ score.referenceForm ?? score.referenceText }} ↔ {{ score.submissionForm ?? score.submissionText }}</div>
        </v-card>
      </v-menu>
    </div>
    <span v-else class="text-caption text-medium-emphasis">No saved text score</span>
    <div v-if="reasonTags.length" class="d-flex flex-wrap ga-1 mt-1">
      <v-menu v-for="tag in reasonTags" :key="tag.code" open-on-hover :open-on-click="false" :open-delay="80" :close-delay="120" location="bottom start" max-width="320">
        <template #activator="{ props: activator }">
          <span v-bind="activator" class="text-caption score-label font-weight-medium" :class="`reason-${tag.tone}`" tabindex="0">{{ tag.label }}<template v-if="reasonTags.length > 1"> · {{ tag.count }}</template></span>
        </template>
        <v-card class="pa-2 score-panel" elevation="6">
          <div class="text-caption text-medium-emphasis">{{ tag.count }} {{ tag.count === 1 ? 'case' : 'cases' }}</div>
          <div class="text-body-2">{{ tag.note }}</div>
        </v-card>
      </v-menu>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TermComparison, TextEvidence } from '@/services/synonymGlossary'
import { compactSimilarityMethodLabel, similarityMethodLabel } from '@/utils/analysisFeedback'
const props = withDefaults(defineProps<{ comparisons?: TermComparison[]; thresholds?: TextEvidence; reasons?: Record<string, number> }>(), {
  thresholds: () => ({ spelling: 0.85, meaning: 0.85, meaningFloor: 0.70 }),
  reasons: () => ({})
})
const reasonDetails: Record<string, { label: string; tone: 'accepted' | 'partial' | 'rejected' | 'neutral'; note: string }> = {
  identified_glossary: { label: 'Accepted in glossary', tone: 'accepted', note: 'An administrator accepted this term, and the evaluation could assign it uniquely.' },
  identified_text: { label: 'Text match', tone: 'accepted', note: 'The text reached a threshold and no other candidate competed for this element.' },
  identified_owner: { label: 'Parent confirmed', tone: 'accepted', note: 'The parent element was identified, and the text fits uniquely inside it.' },
  identified_structure: { label: 'Structure confirmed', tone: 'accepted', note: 'Recognized child elements or connections confirmed this assignment.' },
  identified_label: { label: 'Exact name', tone: 'accepted', note: 'The names are identical and uniquely assignable.' },
  counted_at_same_name: { label: 'Same name elsewhere', tone: 'accepted', note: 'The term was counted at another element with the same name in its own structure.' },
  owner_unresolved: { label: 'Parent unresolved', tone: 'partial', note: 'The term exists and fits this element, but its parent could not be identified. It is partially recognized and does not change the score.' },
  ambiguous_candidates: { label: 'Ambiguous', tone: 'rejected', note: 'Several candidates fit equally well, so no unique assignment was possible.' },
  owner_conflict: { label: 'Wrong parent', tone: 'rejected', note: 'The term sits in a structure that was identified as, or whose siblings point to, a different element.' },
  assigned_elsewhere: { label: 'Assigned elsewhere', tone: 'rejected', note: 'This term or this reference element already belongs to another assignment.' },
  label_structure_conflict: { label: 'Structure conflict', tone: 'rejected', note: 'The name fits, but children and neighbors point to another counterpart.' },
  no_unique_match: { label: 'No unique match', tone: 'rejected', note: 'The text fits, but the overall assignment could not be established uniquely.' },
  text_below_threshold: { label: 'Text below threshold', tone: 'rejected', note: 'Neither spelling nor meaning reached the acceptance threshold.' },
  glossary_rejected: { label: 'Rejected in glossary', tone: 'rejected', note: 'An administrator rejected this term for this element.' },
  digit_mismatch: { label: 'Numbers differ', tone: 'rejected', note: 'The names contain different numbers, so the text match was blocked.' },
  start_mismatch: { label: 'Different word start', tone: 'rejected', note: 'The names begin differently, so spelling similarity was not accepted.' },
  not_evaluated: { label: 'Not evaluated', tone: 'neutral', note: 'This element was not part of the semantic evaluation.' }
}
const reasonTags = computed(() => Object.entries(props.reasons)
  .map(([code, count]) => ({ code, count, ...(reasonDetails[code] ?? { label: code, tone: 'neutral' as const, note: 'Reason recorded by the matcher.' }) }))
  .sort((left, right) => right.count - left.count))
const scores = computed(() => {
  const grouped = new Map<string, TermComparison>()
  for (const item of props.comparisons ?? []) {
    const prior = grouped.get(item.method)
    grouped.set(item.method, prior ? { ...prior, minimum: Math.min(prior.minimum, item.minimum), maximum: Math.max(prior.maximum, item.maximum), acceptance: prior.acceptance === item.acceptance ? prior.acceptance : null, floor: prior.floor === item.floor ? prior.floor : null } : { ...item })
  }
  return [...grouped.values()]
})
const boundaries =(score: TermComparison) => {
  const meaning = score.method === 'multilingual_expanded'
  const spelling = score.method === 'damerau_canonical'
  return {
    acceptance: score.acceptance ?? (meaning ? props.thresholds.meaning : spelling ? props.thresholds.spelling : null),
    floor: score.floor ?? (meaning ? props.thresholds.meaningFloor : spelling ? props.thresholds.spelling : null)
  }
}
const tone = (score: TermComparison) => {
  const { acceptance, floor } = boundaries(score)
  return acceptance != null && score.minimum >= acceptance ? 'score-accepted' : floor != null && score.maximum < floor ? 'score-rejected' : 'score-uncertain'
}
const percent = (minimum: number, maximum: number) => {
  const low = Math.round(100 * minimum), high = Math.round(100 * maximum)
  return low === high ? `${high}%` : `${low}–${high}%`
}
</script>

<style scoped>
.term-similarity { min-width: 160px; padding-block: 4px; }
.form-line { line-height: 1.3; }
.score-panel { overflow-wrap: anywhere; }
.score-label { cursor: default; border: 1px solid rgba(var(--v-theme-on-surface), 0.18); border-radius: 4px; padding: 1px 5px; }
.score-accepted { background: rgba(var(--v-theme-success), 0.09); }
.score-rejected { background: rgba(var(--v-theme-error), 0.07); }
.score-uncertain { background: rgba(var(--v-theme-on-surface), 0.05); }
.reason-accepted { background: rgba(var(--v-theme-success), 0.16); border-color: rgba(var(--v-theme-success), 0.55); }
.reason-partial { background: rgba(var(--v-theme-warning), 0.18); border-color: rgba(var(--v-theme-warning), 0.65); }
.reason-rejected { background: rgba(var(--v-theme-error), 0.12); border-color: rgba(var(--v-theme-error), 0.5); }
.reason-neutral { background: rgba(var(--v-theme-on-surface), 0.08); }
</style>
