<template>
  <span class="text-caption" :title="verdict.note"><v-icon :icon="verdict.icon" :color="verdict.color" size="small" /> {{ verdict.label }}</span>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { TermOutcome, OutcomeCounts } from '@/services/synonymGlossary'
const props = defineProps<{ outcome?: TermOutcome; counts?: OutcomeCounts; emptyText?: string }>()
const verdict = computed(() => {
  const c = props.counts ?? props.outcome?.counts
  const accepted = c?.counted ?? 0
  const partial = c?.partial ?? 0
  const sameName = c?.countedAtSameName ?? 0
  const rejected = (c?.notCounted ?? 0) + (c?.countedElsewhere ?? 0) - sameName
  if (accepted && (rejected || partial)) return { label: 'Mixed results', note: `${accepted} accepted; ${partial} partially recognized; ${rejected} not accepted as this element`, icon: 'mdi-swap-horizontal', color: 'warning' }
  if (accepted) return { label: 'Accepted', note: `${accepted} verified assignments to this element`, icon: 'mdi-check-circle-outline', color: 'success' }
  if (partial && rejected) return { label: 'Mixed results', note: `${partial} partially recognized; ${rejected} not accepted as this element`, icon: 'mdi-swap-horizontal', color: 'warning' }
  if (partial) return { label: 'Partially recognized', note: `${partial} evaluations found this term, but not its parent element. Partial recognition does not change the score.`, icon: 'mdi-circle-half-full', color: 'warning' }
  if (sameName && !rejected) return { label: 'Accepted at same-named element', note: `${sameName} evaluations counted this term at another element with the same name`, icon: 'mdi-check-circle-outline', color: 'success' }
  if (rejected) return { label: 'Not accepted', note: `${rejected} evaluations did not count this term as this element`, icon: 'mdi-close-circle-outline', color: 'error' }
  if (props.emptyText && !props.outcome) return { label: props.emptyText, note: 'These results contain no decision for this term and element.', icon: 'mdi-minus-circle-outline', color: undefined }
  return { label: 'Evaluation data missing', note: 'The original evaluation record is missing or incomplete. Text similarity does not prove acceptance.', icon: 'mdi-help-circle-outline', color: undefined }
})
</script>
