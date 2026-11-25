<template>
  <div v-if="outcome?.groups?.length" class="condition-groups">
    <section v-for="group in outcome.groups" :key="group.key" class="condition-group">
      <div class="d-flex flex-wrap align-center ga-1">
        <span v-for="label in conditionLabels(group)" :key="label" class="text-caption condition-label">{{ label }}</span>
        <span class="text-caption text-medium-emphasis">{{ group.cases }} {{ group.cases === 1 ? 'case' : 'cases' }}</span>
      </div>
      <div v-if="differentThresholds(group)" class="text-caption text-medium-emphasis">{{ thresholdLabel(group) }}</div>
      <div class="d-flex flex-wrap align-center ga-2">
        <GlossaryTermSimilarity :comparisons="group.comparisons" :reasons="groupReasons(group)" />
        <GlossaryOutcomeSummary :counts="group.counts" />
      </div>
    </section>
  </div>
  <div v-else>
    <GlossaryTermSimilarity :comparisons="comparisons" :reasons="outcome?.reasons" />
    <GlossaryOutcomeSummary :outcome="outcome" />
  </div>
</template>

<script setup lang="ts">
import type { OutcomeGroup, TermOutcome, TermComparison } from '@/services/synonymGlossary'
import { compactSimilarityMethodLabel } from '@/utils/analysisFeedback'
import GlossaryTermSimilarity from './GlossaryTermSimilarity.vue'
import GlossaryOutcomeSummary from './GlossaryOutcomeSummary.vue'

const props = defineProps<{ outcome?: TermOutcome; comparisons?: TermComparison[] }>()
const conditionNames: Record<string, string> = { parent: 'Parent', type: 'Type', children: 'Children', combined_children: 'Combined children', endpoints: 'Endpoints', context: 'Context', glossary: 'Glossary' }
const stateNames: Record<string, string> = { confirmed: 'confirmed', unresolved: 'unresolved', conflicting: 'conflicting', not_required: 'not required', not_evaluated: 'not evaluated', partial: 'partly confirmed', unknown: 'not recorded', incomplete: 'partly recorded', accepted: 'accepted', rejected: 'rejected', none: 'undecided' }
const conditionLabels = (group: OutcomeGroup) => Object.entries(group.conditions)
  .filter(([key, state]) => key === 'parent' || key === 'context' || !['not_required', 'not_evaluated'].includes(state))
  .sort(([left], [right]) => left === 'parent' ? -1 : right === 'parent' ? 1 : left.localeCompare(right))
  .map(([key, state]) => `${conditionNames[key] ?? key} ${stateNames[state] ?? state}`)
const signature = (group: OutcomeGroup) => JSON.stringify(Object.entries(group.conditions).sort(([a], [b]) => a.localeCompare(b)))
const differentThresholds = (group: OutcomeGroup) => props.outcome?.groups?.some(other => other.key !== group.key && signature(other) === signature(group))
const thresholdLabel = (group: OutcomeGroup) => group.comparisons.map(item => `${compactSimilarityMethodLabel(item.method)} ≥ ${item.acceptance == null ? '?' : Math.round(item.acceptance * 100) + '%'}${item.floor != null && item.floor !== item.acceptance ? ` · floor ${Math.round(item.floor * 100)}%` : ''}`).filter((item, index, items) => items.indexOf(item) === index).join(' / ')
const groupReasons = (group: OutcomeGroup) => Object.fromEntries(Object.entries(group.reasons).filter(([reason]) => !group.conditions.parent || !['identified_owner', 'owner_unresolved', 'owner_conflict'].includes(reason)))
</script>

<style scoped>
.condition-groups { min-width: 260px; }
.condition-group { padding-block: 6px; }
.condition-group + .condition-group { border-top: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.condition-label { border-radius: 3px; padding: 1px 5px; background: rgba(var(--v-theme-on-surface), 0.05); }
</style>
