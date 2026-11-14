<template>
  <section aria-label="Analytisches Feedback" class="my-3 text-caption">
    <h3 class="text-body-2 font-weight-medium mb-2">Analytisches Feedback</h3>
    <v-select v-model="referenceKey" :items="references" item-title="label" item-value="key" label="Musterlösung" density="compact" variant="outlined" hide-details class="mb-2" />
    <v-alert v-if="error" type="warning" density="compact" variant="tonal">{{ error }}</v-alert>
    <template v-else-if="analysis">
      <p>Alle Zuordnungen sind vorläufig. Erkennung bestätigt keine endgültige Korrektheit.</p>
      <dl class="recognition-counts">
        <template v-for="category in analysisCategories" :key="category">
          <dt>{{ categoryLabels[category] }}</dt>
          <dd>{{ recognitionText(analysis.report.summary[category]) }}<br /><span class="text-medium-emphasis">{{ analysisValueLabel(analysis.report.summary[category].evaluationStatus) }}</span></dd>
        </template>
      </dl>
      <v-alert v-if="stale" type="info" density="compact" variant="tonal" class="my-2">Das aktuelle Diagramm weicht vom ausgewerteten Stand ab. Markierungen sind ausgeblendet; die folgenden Befunde gelten für den gespeicherten Stand.</v-alert>
      <v-select v-model="selectedId" :items="objectOptions" item-title="label" item-value="id" label="Element oder Verbindung" density="compact" variant="outlined" hide-details class="my-3" @update:model-value="focusObject" />
      <template v-if="selected">
        <p class="d-flex align-center ga-1"><v-icon :color="display.color" size="18">{{ display.icon }}</v-icon>{{ display.label }}</p>
        <dl class="object-details">
          <dt>Original-ID</dt><dd>{{ selected.target.id }}</dd>
          <dt>Zuordnung</dt><dd>{{ analysisValueLabel(selected.match.status) }}</dd>
          <template v-if="selected.referenceId"><dt>Referenzgegenstück</dt><dd>{{ referenceLabel(selected.referenceId) }}</dd></template>
          <template v-if="selected.match.reason"><dt>Zuordnungsgrund</dt><dd>{{ analysisReasonLabel(selected.match.reason) }}</dd></template>
          <template v-if="selected.context"><dt>Strukturkontext</dt><dd>{{ referenceLabel(selected.context.referenceId) }} (abgeleitet, keine Zuordnung)</dd></template>
          <template v-for="(status, check) in selected.checks" :key="check"><dt>{{ checkLabels[check] ?? check }}{{ groupCheck(check) ? ' (Gruppe)' : '' }}</dt><dd>{{ analysisValueLabel(status) }}</dd></template>
        </dl>
        <p v-if="selected.checks.connectionScope === 'endpoint_group'">Richtung und Verbindungstyp gelten für die Endpunktgruppe. Sie beweisen keinen individuellen Fehler dieser Verbindung.</p>
        <div v-if="selected.match.dependsOn?.length" class="my-2">
          <strong>Abhängige Zuordnungen</strong>
          <div v-for="dep in selected.match.dependsOn" :key="dep.submissionId">{{ dep.submissionId }} → {{ referenceLabel(dep.referenceId) }}</div>
        </div>
        <template v-for="field in (['children', 'connections'] as const)" :key="field">
          <div v-if="selected.local?.[field]" class="my-2">
            <strong>{{ field === 'children' ? 'Enthaltene Elemente' : 'Angrenzende Verbindungen' }}</strong>
            <dl class="object-details">
              <template v-for="(label, key) in localLabels" :key="key"><dt>{{ label }}</dt><dd>{{ selected.local[field]![key] ?? 'nicht bestimmbar' }}</dd></template>
            </dl>
          </div>
        </template>
        <ul v-if="selected.hints.length" class="pl-4 my-2">
          <li v-for="(hint, index) in selected.hints" :key="`${hint.code}:${index}`" class="mb-2">{{ analysisHintText(hint) }}<div class="technical-parameters text-medium-emphasis">{{ analysisHintParameters(hint) }}</div></li>
        </ul>
      </template>
      <div v-if="visibleReferenceHints.length" class="my-3">
        <strong>Ungeklärte Referenzobjekte{{ selected ? ' am Anzeigeziel oder Modell' : '' }}</strong>
        <ul class="pl-4 mt-1">
          <li v-for="hint in visibleReferenceHints" :key="hint.referenceId" class="mb-2">{{ hint.label ?? referenceLabel(hint.referenceId) }}: {{ analysisHintText(hint) }}<div>{{ hint.reason === 'ambiguous_candidates' ? 'Mehrdeutige Kandidaten. ' : '' }}{{ hint.referenceId }}</div></li>
        </ul>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { InternalEvent, type Cell } from '@maxgraph/core'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createModelSerializer } from '@/utils/modelPersistence'
import { analysisCategories, analysisDisplay, analysisFromEvaluation, analysisHintParameters, analysisHintText, analysisReasonLabel, analysisStatus, analysisValueLabel, categoryLabels, checkLabels, type AdaptedAnalysis, type LocalCounts, type RecognitionCount } from '@/utils/analysisFeedback'
import { installAnalysisOverlays, referenceHintTarget } from '@/utils/analysisFeedbackGraph'

const props = defineProps<{ detail: EvaluationDetail }>()
const graphContext = useGraphContextOptional()
const referenceKey = ref('')
const selectedId = ref<string | null>(null)
const stale = ref(false)
const analysis = shallowRef<AdaptedAnalysis | null>(null)
const error = ref('')
const references = computed(() => props.detail.steps.filter(step => step.id.startsWith('generate_analytical_feedback_')).map(step => ({
  key: step.id.slice('generate_analytical_feedback_'.length), label: step.label.replace(/^Analytisches Feedback:\s*/, '')
})))
watch(references, items => { if (!items.some(item => item.key === referenceKey.value)) referenceKey.value = items[0]?.key ?? '' }, { immediate: true })
watch([() => props.detail, referenceKey], () => {
  analysis.value = null
  error.value = ''
  if (!referenceKey.value) { error.value = 'Für diese Auswertung liegen keine analytischen Daten vor.'; return }
  const step = props.detail.steps.find(step => step.id === `generate_analytical_feedback_${referenceKey.value}`)
  if (step?.status !== 'succeeded') { error.value = 'Analytisches Feedback ist noch nicht verfügbar.'; return }
  try { analysis.value = analysisFromEvaluation(props.detail, referenceKey.value) } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Analytisches Feedback konnte nicht gelesen werden.' }
}, { immediate: true })
const selected = computed(() => {
  if (!selectedId.value) return undefined
  for (const items of analysis.value?.annotations.values() ?? []) {
    const item = items.get(selectedId.value)
    if (item) return item
  }
  return undefined
})
const display = computed(() => analysisDisplay[selected.value ? analysisStatus(selected.value) : 'not_evaluated'])
const objects = (key: string) => {
  const result = props.detail.steps.find(step => step.result?.schema === 'graph-result/v1' && (step.result.source as { key?: string })?.key === key)?.result
  return (result?.graph as { nodes?: { id: string; label?: string }[] })?.nodes ?? []
}
const referenceLabel = (id: string) => { const label = objects(referenceKey.value).find(item => item.id === id)?.label; return label ? `${label} (${id})` : id }
const objectOptions = computed(() => {
  const labels = new Map(objects('submission').map(item => [item.id, item.label]))
  return analysis.value?.report.annotations.map(item => ({ id: item.target.id, label: `${labels.get(item.target.id) || item.target.kind || 'Objekt'} (${item.target.id})` })) ?? []
})
const percentFormat = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 })
const recognitionText = (row: RecognitionCount) => `${row.recognized ?? '–'} / ${row.expected ?? '–'} · ${row.percent === null ? 'nicht bestimmbar' : `${percentFormat.format(row.percent)} %`}`
const localLabels: Record<keyof LocalCounts, string> = { expected: 'Erwartet', observed: 'In der Abgabe', recognized: 'Vorläufig erkannt', recognizedAtTarget: 'Davon an diesem Ziel', unresolvedReference: 'Referenz ungeklärt', unresolvedSubmission: 'Abgabe ungeklärt', mappedFromOtherTargets: 'Anderem Kontext zugeordnet' }
const groupCheck = (check: string) => selected.value?.checks.connectionScope === 'endpoint_group' && ['direction', 'connectionType'].includes(check)
const visibleReferenceHints = computed(() => analysis.value?.report.referenceHints.filter(hint => {
  const graph = graphContext?.graph.value
  const target = graph && !stale.value ? referenceHintTarget(graph, hint) : null
  return !target || !selectedId.value || target.getId() === selectedId.value
}) ?? [])
const focusObject = (id: string | null) => {
  const graph = graphContext?.graph.value
  const cell = id && !stale.value ? graph?.getDataModel().getCell(id) : null
  if (cell) { graph!.setSelectionCell(cell); graph!.scrollCellToVisible(cell) }
}

// Compare XML independent of attribute order/indentation. No export helper that assigns IDs.
const canonicalXml = (xml: string) => {
  const document = new DOMParser().parseFromString(xml, 'application/xml')
  if (document.querySelector('parsererror')) return null
  const canonical = (element: Element): unknown => [element.tagName, [...element.attributes].map(attribute => [attribute.name, attribute.value]).sort(([a], [b]) => a.localeCompare(b)),
    [...element.childNodes].flatMap(node => node instanceof Element ? [canonical(node)] : node.textContent?.trim() ? [node.textContent] : [])]
  return JSON.stringify(canonical(document.documentElement))
}
watch([() => graphContext?.graph.value, analysis], ([graph, value], _, onCleanup) => {
  selectedId.value = null
  stale.value = false
  if (!graph || !value) return
  const data = props.detail.submissionSnapshot.data as { xml?: string } | undefined
  const expected = data?.xml ? canonicalXml(data.xml) : null
  const matchesSnapshot = () => expected !== null && canonicalXml(createModelSerializer(graph).export({ pretty: false })) === expected
  let removeOverlays = () => {}
  const refresh = () => {
    removeOverlays()
    stale.value = !matchesSnapshot()
    if (!stale.value) removeOverlays = installAnalysisOverlays(graph, value, id => { selectedId.value = id }).remove
  }
  const selectionChanged = () => { selectedId.value = (graph.getSelectionCell() as Cell | null)?.getId() ?? null }
  graph.getSelectionModel().addListener(InternalEvent.CHANGE, selectionChanged)
  graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
  refresh()
  selectionChanged()
  onCleanup(() => { removeOverlays(); graph.getSelectionModel().removeListener(selectionChanged); graph.getDataModel().removeListener(refresh) })
}, { immediate: true, flush: 'post' })
</script>

<style scoped>
.recognition-counts, .object-details { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 4px 8px; }
dd { margin: 0; overflow-wrap: anywhere; }
.technical-parameters { overflow-wrap: anywhere; font-size: 11px; }
</style>
