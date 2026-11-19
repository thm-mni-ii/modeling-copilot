<template>
  <div class="similarity-evidence text-caption">
    <template v-for="section in sections" :key="section.title">
      <div class="font-weight-medium mb-1">{{ section.title }}</div>
      <p v-if="section.summary" class="mb-1">{{ section.summary }}</p>
      <p v-if="section.empty" class="text-medium-emphasis mb-2">{{ section.empty }}</p>
      <div v-for="row in section.rows" :key="row.key" class="mb-2">
        <div class="d-flex justify-space-between ga-2">
          <span class="text-truncate" :title="row.title">{{ row.title }}</span>
          <span class="flex-shrink-0" :class="row.pass ? 'font-weight-medium' : 'text-medium-emphasis'">{{ row.value }}</span>
        </div>
        <div v-if="row.score !== undefined" class="score-bar">
          <v-progress-linear :model-value="position(row.method, row.score)" :height="row.thin ? 4 : 8" rounded :color="row.pass ? 'primary' : 'grey'" :aria-label="`${row.title}: Ähnlichkeit`" :aria-valuetext="row.value" />
          <span v-if="row.method.floor !== null" class="score-bar__cut score-bar__cut--floor" :style="{ left: `${position(row.method, row.method.floor)}%` }" :title="`Graubereich ab ${number.format(row.method.floor)}`" aria-hidden="true" />
          <span v-if="row.method.threshold !== null" class="score-bar__cut" :style="{ left: `${position(row.method, row.method.threshold)}%` }" :title="`Schwelle ${number.format(row.method.threshold)}`" aria-hidden="true" />
        </div>
      </div>
    </template>
    <p class="text-medium-emphasis mb-0">{{ note }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { aboveThreshold, similarityMethodLabel, textVetoLabel, tierLabel, unavailableTextLabel, type CandidateEvidence, type CandidatePair, type IdentityCriterion, type SimilarityMethod } from '@/utils/analysisFeedback'

// verdict: the matcher's text_similarity criterion of this very pair; when present it replaces the re-derived thresholds.
const props = defineProps<{ evidence: CandidateEvidence; submissionId?: string; referenceId?: string; verdict?: IdentityCriterion }>()

interface Row { key: string; title: string; value: string; method: SimilarityMethod; score?: number; pass: boolean; thin?: boolean }
const number = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
// The bar spans the method's published score range; the tick marks its configured threshold.
const position = (method: SimilarityMethod, value: number) => Math.min(100, Math.max(0, 100 * (value - method.range[0]) / (method.range[1] - method.range[0])))
const scoreText = (method: SimilarityMethod, score: number | undefined) => score === undefined ? '–'
  : method.threshold === null ? number.format(score)
    : score < method.threshold && method.floor !== null && score >= method.floor ? `${number.format(score)} Graubereich`
      : `${number.format(score)} ${score >= method.threshold ? '≥' : '<'} ${number.format(method.threshold)}`

const pair = computed(() => props.evidence.pairs.find(item => item.submissionId === props.submissionId && item.referenceId === props.referenceId))
// Competition is ranked by the first configured method, else by the first computed one.
const primary = computed(() => props.evidence.methods.find(method => method.threshold !== null) ?? props.evidence.methods[0])
const sections = computed(() => {
  const result: { title: string; rows: Row[]; empty?: string; summary?: string }[] = []
  const current = pair.value
  const verdict = props.verdict?.scores ? props.verdict : undefined
  if (current) {
    result.push({
      title: `„${current.submissionLabel || '–'}“ ↔ „${current.referenceLabel || '–'}“`,
      summary: verdict && (verdict.veto ? `Vom Matcher verworfen: ${textVetoLabel(verdict.veto)}.`
        : verdict.tier ? `Vom Matcher erkannt in Stufe ${tierLabel(verdict.tier)}.` : 'Keine Stufe erreicht.'),
      empty: current.scores ? undefined : unavailableTextLabel(current.unavailableReason),
      rows: props.evidence.methods.flatMap(method => {
        const score = current.scores?.[method.name]
        if (score === undefined) return []
        if (!verdict) return [{ key: method.name, title: similarityMethodLabel(method.name), value: scoreText(method, score), method, score, pass: method.threshold !== null && score >= method.threshold }]
        // The applied threshold of the reached tier; a vetoed or unreached method never counts as passing.
        const applied = verdict.minimumSimilarity?.[method.name]
        const shown = applied === undefined ? method : { ...method, threshold: applied }
        return [{ key: method.name, title: similarityMethodLabel(method.name), method: shown, score,
          value: verdict.veto && method.threshold !== null && score >= method.threshold ? `${number.format(score)} · verworfen` : scoreText(shown, score),
          pass: applied !== undefined && score >= applied && !verdict.veto }]
      })
    })
  }
  const method = primary.value
  const own = (item: CandidatePair) => item.submissionId === props.submissionId && item.referenceId === props.referenceId
  const related = method ? props.evidence.pairs.filter(item => !own(item) &&
    (props.submissionId !== undefined && item.submissionId === props.submissionId || props.referenceId !== undefined && item.referenceId === props.referenceId)) : []
  if (method && related.length) {
    result.push({
      title: `${current ? 'Konkurrierende Kandidaten' : 'Stärkste Kandidaten'} · ${similarityMethodLabel(method.name)}`,
      rows: related
        .map(item => ({ key: `${item.referenceId}:${item.submissionId}`, method, score: item.scores?.[method.name], pass: aboveThreshold(item, props.evidence.methods), thin: true,
          title: item.submissionId === props.submissionId ? `Referenz „${item.referenceLabel || item.referenceId}“` : `Abgabe „${item.submissionLabel || item.submissionId}“`,
          value: scoreText(method, item.scores?.[method.name]) }))
        .sort((left, right) => (right.score ?? -Infinity) - (left.score ?? -Infinity))
        .slice(0, 3)
    })
  }
  if (!result.length) result.push({ title: 'Textähnlichkeit', rows: [], empty: 'Kein zulässiges Kandidatenpaar mit Textwerten.' })
  return result
})
const note = computed(() => props.evidence.configured
  ? 'Ein Verfahren über seiner eigenen Schwelle genügt; Verfahren werden nicht verrechnet. Entscheidend ist Textähnlichkeit nur, wenn genau ein offenes Paar über der Schwelle liegt.'
  : 'Keine Schwelle konfiguriert: Die Werte sind informativ und beeinflussen die Zuordnung nicht.')
</script>

<style scoped>
.score-bar {
  position: relative;
}
.score-bar__cut {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 2px;
  transform: translateX(-1px);
  background: rgb(var(--v-theme-on-surface));
}
.score-bar__cut--floor {
  opacity: 0.4;
}
</style>
