<template>
  <v-expansion-panels v-model="open" class="hints-feedback" variant="accordion">
    <v-expansion-panel value="hints" elevation="0" class="hints-feedback__panel">
      <v-expansion-panel-title class="hints-feedback__title">
        <v-icon size="18" color="info" class="me-2" aria-hidden="true">mdi-lightbulb-on-outline</v-icon>
        <span class="text-body-2 font-weight-medium">Wir haben Hinweise für dich</span>
        <v-chip size="x-small" color="info" variant="tonal" label class="ms-2" :aria-label="`${visible.length} Hinweise`">{{ visible.length }}</v-chip>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <p class="hints-feedback__intro">Diese Elemente passen vermutlich zur Musterlösung, sind aber nicht sicher erkannt. Hinweise zählen nicht zum Ergebnis; nach einer Anpassung prüft die nächste Auswertung erneut.</p>
        <ul class="hints-feedback__list">
          <li v-for="hint in visible" :key="hint.id" class="hints-feedback__item">
            <p class="hints-feedback__text">
              <strong>„{{ hint.submissionLabel || 'Ohne Beschriftung' }}“</strong>:
              <template v-if="hint.suggestion">Meinst du „{{ hint.suggestion }}“?</template>
              <template v-else>Die Beschriftung weicht vermutlich vom erwarteten Begriff ab.</template>
            </p>
            <p class="hints-feedback__meta">{{ describe(hint) }}</p>
            <p v-if="!current(hint)" class="hints-feedback__meta">Das Element wurde seit der Auswertung geändert oder entfernt.</p>
            <div class="d-flex flex-wrap ga-1 mt-1">
              <v-chip v-if="states[hint.id] === 'accepted'" size="x-small" color="success" variant="tonal" label>Übernommen, die nächste Auswertung prüft erneut</v-chip>
              <template v-else>
                <v-btn size="x-small" variant="text" prepend-icon="mdi-crosshairs-gps" :disabled="!current(hint)" @click="show(hint)">Zeigen</v-btn>
                <v-btn v-if="hint.suggestion && !readonly" size="x-small" variant="tonal" color="primary" prepend-icon="mdi-check" :disabled="!editable(hint)" @click="accept(hint)">Übernehmen</v-btn>
                <v-btn size="x-small" variant="text" prepend-icon="mdi-close" @click="decide(hint, 'dismissed')">Verwerfen</v-btn>
              </template>
            </div>
          </li>
        </ul>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { EventObject } from '@maxgraph/core'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { useFeedbackValidity } from '@/composables/useFeedbackValidity'
import { notifyWarning } from '@/composables/useNotifications'
import evaluationService from '@/services/evaluation/evaluation.service'
import type { ApiId } from '@/services/api/types/common'
import type { LabelHint, LabelHintAction, LabelHintRelation, LabelHintSource } from '@/services/api/types/evaluation'

const props = defineProps<{ evaluationId: ApiId; hints: LabelHint[]; snapshotXml?: string | null; readonly?: boolean }>()
const open = ref<string | null>(null)
const states = reactive<Record<string, LabelHint['state']>>({})
watch(() => props.hints, hints => { for (const hint of hints) states[hint.id] ??= hint.state }, { immediate: true })
const visible = computed(() => props.hints.filter(hint => states[hint.id] !== 'dismissed'))
const { isCurrent } = useFeedbackValidity(() => props.snapshotXml)
const graphContext = useGraphContextOptional()
const current = (hint: LabelHint) => isCurrent.value(hint.submissionId)
const cellOf = (hint: LabelHint) => graphContext?.graph.value?.getDataModel().getCell(hint.submissionId) ?? null
const editable = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  return Boolean(graph && cell && current(hint) && graph.isEnabled() && graph.isCellEditable(cell))
}

const show = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  if (!graph || !cell || !current(hint)) return notifyWarning('Das Element fehlt oder wurde seit der Auswertung verändert.')
  graph.setSelectionCells([cell])
  graph.scrollCellToVisible(cell)
}

const relations: Record<LabelHintRelation, string> = {
  notation: 'gleiche Wortteile, andere Schreibweise', reordered: 'gleiche Wortteile in anderer Reihenfolge',
  head_form: 'kürzere oder längere Form desselben Begriffs', part_of_term: 'Teil eines längeren Begriffs',
  abbreviation: 'Abkürzung', same_stem: 'gleicher Wortanfang oder gleiches Wortende'
}
const sources: Record<LabelHintSource, string> = {
  text_band: 'ähnliche Schreibweise oder Bedeutung', neighbor_profile: 'gleiche Verbindungen zu erkannten Elementen',
  child_overlap: 'viele gleiche untergeordnete Elemente'
}
const describe = (hint: LabelHint) => {
  const reasons = hint.sources.map(source => sources[source]).filter(Boolean)
  const relation = hint.relation ? relations[hint.relation] : null
  return `Grund: ${reasons.join(', ')}${relation ? `; Wortvergleich: ${relation}` : ''}.`
}

// Probe measurement (AP-11): one event per hint and action; a failed report never blocks the learner.
const report = (hint: LabelHint, action: LabelHintAction) => evaluationService.recordHintEvent(props.evaluationId, hint.id, action).catch(() => undefined)
watch(open, value => {
  if (value !== 'hints') return
  for (const hint of visible.value) if (states[hint.id] === 'new') { states[hint.id] = 'shown'; void report(hint, 'shown') }
})
const decide = (hint: LabelHint, action: LabelHintAction) => { states[hint.id] = action; void report(hint, action) }

// Accepting renames the submission element through the editor, so the change is undoable and synchronized.
const accept = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  if (!graph || !cell || !hint.suggestion || !editable(hint)) {
    notifyWarning('Das Element fehlt, wurde seit der Auswertung verändert oder ist nicht bearbeitbar.')
    return
  }
  graph.labelChanged(cell, hint.suggestion, new EventObject('hintAccepted'))
  decide(hint, 'accepted')
}
</script>

<style scoped>
.hints-feedback__panel { border: 1px solid rgba(var(--v-theme-info), 0.4); }
.hints-feedback__title { min-height: 40px; padding: 6px 12px; }
.hints-feedback__intro, .hints-feedback__meta { font-size: 11px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); margin-bottom: 6px; }
.hints-feedback__list { list-style: none; padding: 0; margin: 0; }
.hints-feedback__item + .hints-feedback__item { border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); margin-top: 8px; padding-top: 8px; }
.hints-feedback__text { font-size: 12px; line-height: 1.5; margin-bottom: 2px; }
</style>
