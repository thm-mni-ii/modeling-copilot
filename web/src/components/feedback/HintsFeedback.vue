<template>
  <v-expansion-panels v-model="open" class="hints-feedback" :class="{ 'hints-feedback--focused': pulsing }" variant="accordion">
    <v-expansion-panel value="hints" elevation="0" class="hints-feedback__panel">
      <v-expansion-panel-title class="hints-feedback__title">
        <v-icon size="18" color="info" class="me-2" aria-hidden="true">mdi-lightbulb-on-outline</v-icon>
        <span class="text-body-2 font-weight-medium">Was meinst du damit?</span>
        <v-chip size="x-small" color="info" variant="tonal" label class="ms-2" :aria-label="`${hints.length} Hinweise`">{{ hints.length }}</v-chip>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <p v-if="!readonly" class="hints-feedback__meta">Erst zeigen, dann entscheiden.</p>
        <ul class="hints-feedback__list">
          <li v-for="hint in hints" :key="hint.id" ref="hintItems" :data-hint-id="hint.id" tabindex="-1" class="hints-feedback__item">
            <!-- An observation only reports what the evaluation found; there is nothing to replace or reject. -->
            <p v-if="hint.note" class="hints-feedback__text">{{ hint.note }}</p>
            <p v-else class="hints-feedback__text">
              <strong>„{{ hint.submissionLabel || 'Ohne Beschriftung' }}“</strong>:
              <template v-if="hint.suggestion">Meinst du damit „{{ hint.suggestion }}“?</template>
              <template v-else>Ist das der passende Begriff?</template>
            </p>
            <p v-if="!exists(hint)" class="hints-feedback__meta">Das Element wurde entfernt.</p>
            <p v-else-if="changed" class="hints-feedback__meta">Modell seit der Auswertung geändert. Prüfe, ob der Vorschlag noch passt.</p>
            <div class="d-flex flex-wrap ga-1 mt-1" aria-live="polite">
              <v-chip v-if="retained(hint)" size="x-small" color="success" variant="tonal" label>Ersetzt</v-chip>
              <v-chip v-else-if="states[hint.id] === 'dismissed'" size="x-small" variant="tonal" label>Abgelehnt</v-chip>
              <template v-else>
                <v-btn size="x-small" variant="text" prepend-icon="mdi-crosshairs-gps" :disabled="!exists(hint)" @click="show(hint)">Zeigen</v-btn>
                <v-btn v-if="hint.suggestion" size="x-small" variant="tonal" color="primary" prepend-icon="mdi-check" :disabled="!canDecide(hint) || !editable(hint)" @click="accept(hint)">Ersetzen</v-btn>
                <v-btn v-if="!hint.note" size="x-small" variant="text" prepend-icon="mdi-close" :disabled="!canDecide(hint)" @click="dismiss(hint)">Ablehnen</v-btn>
              </template>
            </div>
          </li>
        </ul>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, reactive, ref, watch, watchEffect } from 'vue'
import { EventObject, InternalEvent } from '@maxgraph/core'
import { createCellOutline } from '@/utils/analysisFeedbackGraph'
import { sanitizeLabelHtml } from '@/utils/htmlLabels'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { useFeedbackValidity } from '@/composables/useFeedbackValidity'
import { notifyWarning } from '@/composables/useNotifications'
import evaluationService from '@/services/evaluation/evaluation.service'
import type { ApiId } from '@/services/api/types/common'
import type { LabelHint, LabelHintAction } from '@/services/api/types/evaluation'

const props = withDefaults(defineProps<{ evaluationId: ApiId; hints: LabelHint[]; snapshotXml?: string | null; readonly?: boolean; active?: boolean; expanded?: boolean; focus?: { cellId?: string; seq: number } | null }>(), { active: true })
const open = ref<string | null>(props.expanded ? 'hints' : null)
const focusedHintId = ref<string | null>(null)
const hintItems = ref<HTMLElement[]>([])
const pulsing = ref(false)
let pulseTimer: ReturnType<typeof setTimeout> | undefined
onBeforeUnmount(() => clearTimeout(pulseTimer))
const states = reactive<Record<string, LabelHint['state']>>({})
const acceptedIds = reactive(new Set<string>())
const graphRevision = ref(0)
const reportedRetention = new Map<string, LabelHintAction>()
// Decisions belong to a single evaluation, even when the next run returns the same hint IDs.
watch([() => props.evaluationId, () => props.hints], ([evaluationId, hints], [previousId]) => {
  if (evaluationId !== previousId) {
    for (const id of Object.keys(states)) delete states[id]
    acceptedIds.clear()
    reportedRetention.clear()
    open.value = props.expanded ? 'hints' : null
    focusedHintId.value = null
  }
  for (const hint of hints) {
    states[hint.id] ??= hint.state
    if (hint.state === 'accepted' || hint.retention) acceptedIds.add(hint.id)
  }
}, { immediate: true })
const { changed } = useFeedbackValidity(() => props.snapshotXml)
const graphContext = useGraphContextOptional()
const cellOf = (hint: LabelHint) => {
  void graphRevision.value
  return graphContext?.graph.value?.getDataModel().getCell(hint.submissionId) ?? null
}
const exists = (hint: LabelHint) => Boolean(cellOf(hint))
const retained = (hint: LabelHint) => {
  const cell = cellOf(hint)
  if (!cell || !hint.suggestion || !acceptedIds.has(hint.id)) return false
  const label = document.createElement('div')
  label.innerHTML = sanitizeLabelHtml(String(cell.getValue() ?? ''))
  return label.textContent === hint.suggestion
}
const canDecide = (hint: LabelHint) => !props.readonly && props.active && open.value === 'hints' && focusedHintId.value === hint.id && exists(hint) && !retained(hint) && states[hint.id] !== 'dismissed'
const editable = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  return Boolean(graph && cell && graph.isEnabled() && graph.isCellEditable(cell))
}

const show = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  if (!graph || !cell) return notifyWarning('Das Element wurde entfernt.')
  graph.clearSelection()
  graph.scrollCellToVisible(cell)
  if (!graph.view.getState(cell)) return notifyWarning('Das Element ist im Diagramm aktuell nicht sichtbar.')
  focusedHintId.value = hint.id
}

// Navigating from an info icon opens the question; only an explicit Show unlocks a decision.
watch([() => props.focus, () => props.active, () => props.hints], async ([focus, active], _, onCleanup) => {
  if (!focus || !active) return
  const hint = props.hints.find(item => item.submissionId === focus.cellId) ?? props.hints[0]
  if (!hint) return
  let cancelled = false
  onCleanup(() => { cancelled = true })
  focusedHintId.value = null
  open.value = 'hints'
  await nextTick()
  clearTimeout(pulseTimer)
  pulsing.value = false
  await nextTick()
  if (cancelled || !props.active || props.focus !== focus) return
  const item = hintItems.value.find(item => item.dataset.hintId === hint.id)
  item?.scrollIntoView({ block: 'nearest' })
  item?.focus({ preventScroll: true })
  pulsing.value = true
  pulseTimer = setTimeout(() => { pulsing.value = false }, 1200)
}, { immediate: true })
watch([open, () => props.active], ([value, active]) => {
  if (value !== 'hints' || !active) focusedHintId.value = null
})

// Runtime-only frame: follows zoom/movement without changing the model or its undo history.
watchEffect(onCleanup => {
  const graph = graphContext?.graph.value
  const hint = props.hints.find(item => item.id === focusedHintId.value)
  if (!graph || !hint || !props.active || open.value !== 'hints' || !exists(hint)) return
  const cell = cellOf(hint)
  const state = cell && graph.view.getState(cell)
  if (!state) return
  const highlight = createCellOutline(graph, cell)
  onCleanup(() => highlight.destroy())
})

// Decision events and observed retention are serialized so undo cannot overtake the acceptance report.
let reportQueue = Promise.resolve()
const report = (hint: LabelHint, action: LabelHintAction) => {
  const evaluationId = props.evaluationId
  reportQueue = reportQueue.then(() => evaluationService.recordHintEvent(evaluationId, hint.id, action)).then(() => undefined).catch(() => {
    if (evaluationId === props.evaluationId && reportedRetention.get(hint.id) === action) reportedRetention.delete(hint.id)
    notifyWarning('Deine Hinweisentscheidung konnte nicht protokolliert werden. Die Modelländerung bleibt erhalten.')
  })
  return reportQueue
}
watch(() => graphContext?.graph.value, (graph, _, onCleanup) => {
  graphRevision.value++
  if (!graph) return
  const refresh = () => { graphRevision.value++ }
  graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
  onCleanup(() => graph.getDataModel().removeListener(refresh))
}, { immediate: true })
watch([graphRevision, () => props.hints, () => props.readonly, () => [...acceptedIds]], () => {
  if (props.readonly || !graphContext?.graph.value?.isEnabled()) return
  for (const hint of props.hints) if (acceptedIds.has(hint.id)) {
    const action = !exists(hint) ? 'removed' : retained(hint) ? 'retained' : 'reverted'
    if (reportedRetention.get(hint.id) === action) continue
    reportedRetention.set(hint.id, action)
    void report(hint, action)
  }
}, { immediate: true })
watch([open, () => props.active, () => props.hints], ([value, active]) => {
  if (value !== 'hints' || !active || props.readonly) return
  for (const hint of props.hints) if (states[hint.id] === 'new') { states[hint.id] = 'shown'; void report(hint, 'shown') }
}, { immediate: true })
const decide = (hint: LabelHint, action: 'accepted' | 'dismissed') => {
  if (props.readonly) return
  states[hint.id] = action
  if (action === 'accepted') acceptedIds.add(hint.id)
  focusedHintId.value = null
  void report(hint, action)
}
const dismiss = (hint: LabelHint) => { if (canDecide(hint)) decide(hint, 'dismissed') }

// Accepting renames the submission element through the editor, so the change is undoable and synchronized.
const accept = (hint: LabelHint) => {
  const graph = graphContext?.graph.value
  const cell = cellOf(hint)
  if (!canDecide(hint) || !graph || !cell || !hint.suggestion || !editable(hint)) {
    notifyWarning('Das Element fehlt, wurde seit der Auswertung verändert oder ist nicht bearbeitbar.')
    return
  }
  // Keep formatting that wraps the whole label (e.g. an underlined key); only the text is the suggestion.
  const label = String(cell.getValue() ?? '')
  const wrap = /^((?:<(?:b|strong|i|em|u)>)*)[^<]*((?:<\/(?:b|strong|i|em|u)>)*)$/i.exec(label)
  const tags = (text: string) => text.match(/</g)?.length ?? 0
  const [prefix, suffix] = wrap && tags(wrap[1]) === tags(wrap[2]) ? [wrap[1], wrap[2]] : ['', '']
  graph.labelChanged(cell, `${prefix}${hint.suggestion}${suffix}`, new EventObject('hintAccepted'))
  decide(hint, 'accepted')
}
</script>

<style scoped>
.hints-feedback--focused { animation: hint-focus 1.2s ease-out; }
@keyframes hint-focus { 50% { box-shadow: 0 0 0 4px rgba(var(--v-theme-info), 0.3); } }
@media (prefers-reduced-motion: reduce) { .hints-feedback--focused { animation: none; outline: 2px solid rgb(var(--v-theme-info)); } }
.hints-feedback__panel { border: 1px solid rgba(var(--v-theme-info), 0.4); }
.hints-feedback__title { min-height: 40px; padding: 6px 12px; }
.hints-feedback__meta { font-size: 11px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); margin-bottom: 6px; }
.hints-feedback__list { list-style: none; padding: 0; margin: 0; }
.hints-feedback__item + .hints-feedback__item { border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); margin-top: 8px; padding-top: 8px; }
.hints-feedback__text { font-size: 12px; line-height: 1.5; margin-bottom: 2px; }
</style>
