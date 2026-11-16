<template>
  <div v-if="tab !== 'technical'" class="analysis-panel text-caption">
    <v-alert v-if="error" type="warning" density="compact" variant="tonal" class="my-2">{{ error }}</v-alert>

    <template v-else-if="analysis && tab === 'overview'">
      <section class="analysis-panel__section" aria-label="Befunde im Überblick">
        <h3 class="text-body-2 font-weight-medium mb-1">Befunde</h3>
        <v-list density="compact" class="pa-0" bg-color="transparent">
          <v-list-item v-for="group in groupCounts" :key="group.group" :title="group.title" class="analysis-panel__count" @click="showGroup(group.group)">
            <template #prepend><v-icon size="18" :color="group.color">{{ group.icon }}</v-icon></template>
            <template #append><span class="text-body-2 font-weight-medium">{{ group.count }}</span></template>
          </v-list-item>
        </v-list>
      </section>

      <section class="analysis-panel__section" aria-label="Konfiguration">
        <h3 class="text-body-2 font-weight-medium mb-1">Textähnlichkeit</h3>
        <template v-if="evidence">
          <div v-for="method in evidence.methods" :key="method.name" class="d-flex justify-space-between ga-2">
            <span>{{ similarityMethodLabel(method.name) }}</span>
            <span :class="method.threshold === null ? 'text-medium-emphasis' : 'font-weight-medium'">{{ method.threshold === null ? 'berechnet, ohne Schwelle' : `Schwelle ${number.format(method.threshold)}` }}</span>
          </div>
          <p class="text-medium-emphasis mt-1 mb-0">{{ evidence.configured ? 'Verfahren mit Schwelle können eine Zuordnung begründen; die übrigen Werte sind nur informativ.' : 'Keine Schwelle konfiguriert: Textähnlichkeit fließt nicht in die Zuordnung ein.' }}</p>
        </template>
        <p v-else class="text-medium-emphasis mb-0">Für diese Musterlösung liegen keine zusammengehörigen Kandidaten- und Vergleichsdaten vor.</p>
      </section>

      <section class="analysis-panel__section" aria-label="Datenqualität">
        <h3 class="text-body-2 font-weight-medium mb-1">Datenqualität</h3>
        <div v-for="model in models" :key="model.title" class="mb-2">
          <div class="d-flex justify-space-between ga-2">
            <span>{{ model.title }}</span>
            <span :class="model.graph?.interpretation === 'complete' ? '' : 'font-weight-medium'">{{ interpretationLabel(model.graph) }}</span>
          </div>
          <div v-for="diagnostic in model.graph?.diagnostics ?? []" :key="`${diagnostic.code}:${diagnostic.elementIds?.join()}`" class="text-medium-emphasis pl-2">
            {{ graphDiagnosticLabel(diagnostic) }}<template v-if="diagnostic.elementIds?.length"> · {{ diagnostic.elementIds.map(id => describe(model.side, id)).join(', ') }}</template>
          </div>
        </div>
        <p v-if="graphsComplete === false" class="text-medium-emphasis mb-1">Bei teilweise interpretierten Graphen bleiben Vollständigkeitsprüfungen offen, auch wenn die Anzahlen übereinstimmen.</p>
        <ul v-if="analysis.report.limitations?.length" class="pl-4 mb-1">
          <li v-for="hint in analysis.report.limitations" :key="hint.code">{{ analysisHintText(hint) }}</li>
        </ul>
        <p v-if="analysis.report.structuralContainers" class="text-medium-emphasis mb-0">
          Strukturelle Container: {{ analysis.report.structuralContainers.submissionCount }} in der Abgabe, {{ analysis.report.structuralContainers.referenceCount }} in der Musterlösung (zählen nicht zur Erkennung).
        </p>
      </section>
    </template>

    <template v-else-if="analysis">
      <v-alert v-if="stale" type="info" density="compact" variant="tonal" class="my-2">Das Diagramm weicht vom ausgewerteten Stand ab. Markierungen sind ausgeblendet; die Befunde gelten für den gespeicherten Stand.</v-alert>

      <template v-if="selected">
        <div class="d-flex align-center ga-1 my-1">
          <v-btn size="small" variant="text" prepend-icon="mdi-arrow-left" @click="selectedKey = null">Alle Befunde</v-btn>
          <v-spacer />
          <template v-if="selectedIndex >= 0">
            <v-btn icon size="x-small" variant="text" :disabled="selectedIndex === 0" aria-label="Vorheriger Befund" @click="step(-1)"><v-icon>mdi-chevron-up</v-icon></v-btn>
            <span class="text-medium-emphasis" aria-live="polite">{{ selectedIndex + 1 }} / {{ visibleFindings.length }}</span>
            <v-btn icon size="x-small" variant="text" :disabled="selectedIndex === visibleFindings.length - 1" aria-label="Nächster Befund" @click="step(1)"><v-icon>mdi-chevron-down</v-icon></v-btn>
          </template>
        </div>
        <AnalysisObjectDetail
          :key="selected.key"
          :annotation="selected.annotation"
          :reference-hint="selected.hint"
          :report="analysis.report"
          :node="selected.annotation ? submissionGraph?.nodes.get(selected.annotation.target.id) : referenceGraph?.nodes.get(selected.hint!.referenceId)"
          :evidence="evidence"
          :graphs-complete="graphsComplete"
          :diagnostics="selectedDiagnostics"
          :related-hints="selected.annotation ? analysis.report.referenceHints.filter(hint => hint.target.id === selected!.annotation!.target.id) : []"
          :target-note="targetNote"
          :describe="describe"
        />
      </template>

      <template v-else>
        <div class="d-flex flex-wrap ga-1 my-2" role="group" aria-label="Befunde filtern">
          <v-chip size="small" :variant="filter === 'all' ? 'flat' : 'outlined'" :color="filter === 'all' ? 'primary' : undefined" @click="filter = 'all'">Alle {{ findings.length }}</v-chip>
          <v-chip v-for="group in groupCounts" :key="group.group" size="small" :variant="filter === group.group ? 'flat' : 'outlined'" :color="filter === group.group ? 'primary' : undefined" @click="filter = group.group">
            <v-icon start size="14" :color="filter === group.group ? undefined : group.color">{{ group.icon }}</v-icon>{{ group.count }}
            <span class="d-sr-only">{{ group.title }}</span>
          </v-chip>
        </div>
        <v-text-field v-model="search" label="Beschriftung oder ID suchen" density="compact" variant="outlined" hide-details clearable prepend-inner-icon="mdi-magnify" class="mb-2" />
        <p v-if="!visibleFindings.length" class="text-medium-emphasis">Keine Befunde für diese Auswahl.</p>
        <v-list v-else density="compact" class="pa-0" bg-color="transparent">
          <template v-for="section in listSections" :key="section.group">
            <v-list-subheader class="analysis-panel__subheader">{{ section.title }} ({{ section.items.length }})</v-list-subheader>
            <v-list-item v-for="finding in section.items" :key="finding.key" class="analysis-panel__finding" @click="openFinding(finding)">
              <template #prepend><v-icon size="18" :color="finding.color" class="mr-2">{{ finding.icon }}</v-icon></template>
              <v-list-item-title class="text-body-2">{{ finding.title }}</v-list-item-title>
              <v-list-item-subtitle class="analysis-panel__reason">{{ finding.subtitle }}</v-list-item-subtitle>
            </v-list-item>
          </template>
        </v-list>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { GraphDataModel, InternalEvent, type Cell, type Graph } from '@maxgraph/core'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createModelSerializer, importModelFromXml } from '@/utils/modelPersistence'
import {
  analysisDisplay, analysisFactLabel, analysisFromEvaluation, analysisHintText, analysisIdentityMethodLabel, analysisStatus, candidateEvidence, graphDiagnosticLabel,
  graphInfo, individualViolations, objectKindLabel, similarityMethodLabel, type AdaptedAnalysis, type AnalysisAnnotation, type GraphInfo, type ReferenceHint
} from '@/utils/analysisFeedback'
import { analysisTargetCell, installAnalysisOverlays, referenceHintTarget } from '@/utils/analysisFeedbackGraph'
import AnalysisObjectDetail from './AnalysisObjectDetail.vue'

type FindingGroup = 'warning' | 'unresolved' | 'supported' | 'reference' | 'recognized' | 'other'
interface Finding { key: string; group: FindingGroup; title: string; subtitle: string; icon: string; color: string; annotation?: AnalysisAnnotation; hint?: ReferenceHint }

const props = defineProps<{ detail: EvaluationDetail }>()
const referenceKey = defineModel<string>('referenceKey', { default: '' })
const tab = defineModel<'overview' | 'findings' | 'technical'>('tab', { default: 'overview' })
const graphContext = useGraphContextOptional()
const number = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
const selectedKey = ref<string | null>(null)
const filter = ref<FindingGroup | 'all'>('all')
const search = ref<string | null>('')
const stale = ref(false)
const analysis = shallowRef<AdaptedAnalysis | null>(null)
const error = ref('')

watch([() => props.detail, referenceKey], () => {
  analysis.value = null
  error.value = ''
  if (!referenceKey.value) { error.value = 'Für diese Auswertung liegen keine analytischen Daten vor.'; return }
  const step = props.detail.steps.find(step => step.id === `generate_analytical_feedback_${referenceKey.value}`)
  if (step?.status !== 'succeeded') { error.value = 'Analytisches Feedback ist noch nicht verfügbar.'; return }
  try { analysis.value = analysisFromEvaluation(props.detail, referenceKey.value) } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Analytisches Feedback konnte nicht gelesen werden.' }
}, { immediate: true })

const submissionGraph = computed(() => graphInfo(props.detail, 'submission'))
const referenceGraph = computed(() => referenceKey.value ? graphInfo(props.detail, referenceKey.value) : null)
const models = computed(() => [{ title: 'Abgabe', side: 'submission' as const, graph: submissionGraph.value }, { title: 'Musterlösung', side: 'reference' as const, graph: referenceGraph.value }])
const graphsComplete = computed(() => submissionGraph.value?.interpretation && referenceGraph.value?.interpretation
  ? submissionGraph.value.interpretation === 'complete' && referenceGraph.value.interpretation === 'complete' : null)
const interpretationLabel = (graph: GraphInfo | null | undefined) => !graph?.interpretation ? 'nicht bestimmbar'
  : graph.interpretation === 'complete' ? 'vollständig interpretiert' : `teilweise interpretiert (${graph.diagnostics.length} ${graph.diagnostics.length === 1 ? 'Hinweis' : 'Hinweise'})`
const evidence = computed(() => analysis.value ? candidateEvidence(props.detail, referenceKey.value) : null)

const duplicateLabels = (graph: GraphInfo | null) => {
  const seen = new Set<string>(), duplicates = new Set<string>()
  for (const node of graph?.nodes.values() ?? []) if (node.label) (seen.has(node.label) ? duplicates : seen).add(node.label)
  return duplicates
}
const duplicates = computed(() => ({ submission: duplicateLabels(submissionGraph.value), reference: duplicateLabels(referenceGraph.value) }))
// Labels repeat in real models, so a repeated label carries its ID to stay unambiguous.
const describe = (side: 'submission' | 'reference', id: string) => {
  const node = (side === 'submission' ? submissionGraph : referenceGraph).value?.nodes.get(id)
  if (!node?.label) return `${objectKindLabel(node?.kind)} ${id}`
  return duplicates.value[side].has(node.label) ? `„${node.label}“ (${id})` : `„${node.label}“`
}

const groupOrder: FindingGroup[] = ['warning', 'unresolved', 'supported', 'reference', 'recognized', 'other']
const groupMeta: Record<FindingGroup, { title: string; icon: string; color: string }> = {
  warning: { ...analysisDisplay.warning, title: 'Abweichungen' },
  unresolved: { ...analysisDisplay.unresolved, title: 'Ungeklärt' },
  supported: { ...analysisDisplay.supported, title: 'Gestützt, nicht eindeutig' },
  reference: { icon: 'mdi-link-variant-off', color: analysisDisplay.unresolved.color, title: 'Musterlösung ohne Gegenstück' },
  recognized: { ...analysisDisplay.recognized, title: 'Eindeutig erkannt' },
  other: { ...analysisDisplay.not_evaluated, title: 'Sonstige (Strukturobjekte, nicht ausgewertet)' }
}
const findingReason = (item: AnalysisAnnotation) => {
  const violations = individualViolations(item)
  if (violations.length) return `Abweichend: ${[...new Set(violations.map(fact => analysisFactLabel(fact.code)))].join(', ')}`
  const identity = item.identity
  if (!identity) return analysisDisplay[analysisStatus(item)].label
  const methods = (role: string) => [...new Set(identity.criteria.filter(criterion => criterion.role === role && criterion.result === 'satisfied').map(criterion => analysisIdentityMethodLabel(criterion.method)))].join(', ')
  if (identity.status === 'uniquely_supported') return `Eindeutig über ${methods('identity_anchor') || 'Identitätsanker'}`
  if (identity.status === 'supported') return `Gestützt durch ${methods('support')}`
  if (methods('support')) return 'Mehrdeutig: Konkurrenz mit ebenfalls positiver Evidenz'
  return item.referenceId ? 'Nur vorläufig zugeordnet' : 'Kein Gegenstück'
}
const findings = computed<Finding[]>(() => {
  const report = analysis.value?.report
  if (!report) return []
  const result: Finding[] = report.annotations.map(item => {
    const status = analysisStatus(item)
    const group: FindingGroup = status === 'warning' || status === 'unresolved' || status === 'supported' || status === 'recognized' ? status : 'other'
    const type = submissionGraph.value?.nodes.get(item.target.id)?.type
    return { key: `submission:${item.target.id}`, group, annotation: item, icon: analysisDisplay[status].icon, color: analysisDisplay[status].color,
      title: describe('submission', item.target.id), subtitle: [objectKindLabel(item.target.kind), type, findingReason(item)].filter(Boolean).join(' · ') }
  })
  for (const hint of report.referenceHints) {
    const missing = hint.code === 'reference.missing', notEvaluated = hint.code === 'reference.not_evaluated'
    const look = missing ? analysisDisplay.warning : notEvaluated ? analysisDisplay.not_evaluated : groupMeta.reference
    result.push({ key: `reference:${hint.referenceId}`, group: notEvaluated ? 'other' : 'reference', hint, icon: look.icon, color: look.color,
      title: referenceGraph.value?.nodes.get(hint.referenceId)?.label ? describe('reference', hint.referenceId) : hint.label ?? describe('reference', hint.referenceId),
      subtitle: `${objectKindLabel(hint.kind)} der Musterlösung · ${missing ? 'nachweisbar fehlend' : notEvaluated ? 'nicht ausgewertet' : 'kein Gegenstück identifiziert, nicht als fehlend belegt'}` })
  }
  return result.sort((left, right) => groupOrder.indexOf(left.group) - groupOrder.indexOf(right.group) || left.title.localeCompare(right.title, 'de'))
})
const groupCounts = computed(() => groupOrder.map(group => ({ group, ...groupMeta[group], count: findings.value.filter(item => item.group === group).length })).filter(group => group.count))
const visibleFindings = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('de')
  return findings.value.filter(item => (filter.value === 'all' || item.group === filter.value) &&
    (!query || item.title.toLocaleLowerCase('de').includes(query) || item.key.toLocaleLowerCase('de').includes(query)))
})
const listSections = computed(() => groupOrder.map(group => ({ group, title: groupMeta[group].title, items: visibleFindings.value.filter(item => item.group === group) })).filter(section => section.items.length))
const selected = computed(() => findings.value.find(item => item.key === selectedKey.value))
const selectedIndex = computed(() => visibleFindings.value.findIndex(item => item.key === selectedKey.value))
const selectedDiagnostics = computed(() => {
  const item = selected.value
  const graph = item?.annotation ? submissionGraph.value : referenceGraph.value
  const id = item?.annotation?.target.id ?? item?.hint?.referenceId
  return id ? graph?.diagnostics.filter(diagnostic => diagnostic.elementIds?.includes(id)) ?? [] : []
})

const targetCell = (finding: Finding) => {
  const graph = graphContext?.graph.value
  if (!graph || stale.value) return null
  return finding.annotation ? analysisTargetCell(graph, finding.annotation.target) : finding.hint ? referenceHintTarget(graph, finding.hint) : null
}
const targetNote = computed(() => {
  const item = selected.value
  if (!item || !graphContext?.graph.value || stale.value) return undefined
  if (targetCell(item)) return undefined
  return item.hint ? 'Im Diagramm nicht verortbar: Es gibt keinen identifizierten Parent oder Endpunkt.' : 'Für dieses Objekt ist kein Diagrammziel darstellbar.'
})
// Our own focus must not be read back as a user selection (a reference hint focuses its parent cell).
let focusing = false
const openFinding = (finding: Finding) => {
  selectedKey.value = finding.key
  tab.value = 'findings'
  const graph = graphContext?.graph.value
  const cell = targetCell(finding)
  if (!graph || !cell) return
  focusing = true
  try { graph.setSelectionCell(cell); graph.scrollCellToVisible(cell) } finally { focusing = false }
}
const openSubmission = (id: string) => {
  const finding = findings.value.find(item => item.key === `submission:${id}`)
  if (finding) openFinding(finding)
}
const step = (delta: number) => {
  const next = visibleFindings.value[selectedIndex.value + delta]
  if (next) openFinding(next)
}
const showGroup = (group: FindingGroup) => {
  filter.value = group
  selectedKey.value = null
  tab.value = 'findings'
}

// Layer visibility is editor view state; element visibility remains part of the snapshot.
const canonicalXml = (xml: string) => {
  const document = new DOMParser().parseFromString(xml, 'application/xml')
  if (document.querySelector('parsererror')) return null
  const cells = [...document.querySelectorAll('GraphDataModel > root > Cell')]
  const rootId = cells.find(cell => !cell.hasAttribute('parent'))?.getAttribute('id')
  for (const cell of cells) if (rootId && cell.getAttribute('parent') === rootId) cell.removeAttribute('visible')
  const canonical = (element: Element): unknown => [element.tagName, [...element.attributes].map(attribute => [attribute.name, attribute.value]).sort(([a], [b]) => a.localeCompare(b)),
    [...element.childNodes].flatMap(node => node instanceof Element ? [canonical(node)] : node.textContent?.trim() ? [node.textContent] : [])]
  return JSON.stringify(canonical(document.documentElement))
}
watch(analysis, () => { selectedKey.value = null; filter.value = 'all' })
watch([() => graphContext?.graph.value, analysis], ([graph, value], _, onCleanup) => {
  stale.value = false
  if (!graph || !value) return
  const data = props.detail.submissionSnapshot.data as { xml?: string } | undefined
  let expected: string | null = null
  if (data?.xml) {
    // Use the same import/export path as the canvas to normalize codec defaults
    // and historical fields, without changing the live graph or assigning IDs.
    const snapshotModel = new GraphDataModel()
    const snapshotGraph = { getDataModel: () => snapshotModel } as Graph
    try {
      importModelFromXml(snapshotGraph, data.xml)
      expected = canonicalXml(createModelSerializer(snapshotGraph).export({ pretty: false }))
    } catch {
      // An unreadable snapshot cannot safely authorize diagram overlays.
    }
  }
  const matchesSnapshot = () => expected !== null && canonicalXml(createModelSerializer(graph).export({ pretty: false })) === expected
  let removeOverlays = () => {}
  const refresh = () => {
    removeOverlays()
    stale.value = !matchesSnapshot()
    if (!stale.value) removeOverlays = installAnalysisOverlays(graph, value, openSubmission).remove
  }
  // Selecting an analysed cell in the diagram opens its findings; other selections leave the panel as it is.
  const selectionChanged = () => {
    const id = (graph.getSelectionCell() as Cell | null)?.getId()
    if (!focusing && id && !stale.value) openSubmission(id)
  }
  graph.getSelectionModel().addListener(InternalEvent.CHANGE, selectionChanged)
  graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
  refresh()
  onCleanup(() => { removeOverlays(); graph.getSelectionModel().removeListener(selectionChanged); graph.getDataModel().removeListener(refresh) })
}, { immediate: true, flush: 'post' })
</script>

<style scoped>
.analysis-panel__section {
  padding-block: 10px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.12);
}
.analysis-panel__section:first-child {
  border-top: 0;
}
.analysis-panel__count {
  min-height: 32px;
}
.analysis-panel__subheader {
  min-height: 28px;
  padding-inline-start: 4px !important;
  font-size: 0.75rem;
}
.analysis-panel__finding {
  min-height: 40px;
  padding-inline: 4px !important;
}
.analysis-panel__reason {
  white-space: normal;
  -webkit-line-clamp: 2;
  font-size: 0.7rem;
}
</style>
