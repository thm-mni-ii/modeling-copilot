<template>
  <div v-show="tab === 'overview' || tab === 'findings' || tab === 'hints'" class="analysis-panel text-caption">
    <section v-show="tab === 'hints'" class="analysis-panel__section" aria-label="Hinweise">
      <v-alert v-if="hintError" type="warning" density="compact" variant="tonal" class="mb-2">
        Hinweise konnten nicht geladen werden.<v-btn size="small" variant="text" @click="reloadHints">Erneut versuchen</v-btn>
      </v-alert>
      <v-progress-linear v-if="hintsLoading" indeterminate color="info" aria-label="Hinweise werden geladen" />
      <HintsFeedback v-if="learnerFeedback?.hints?.length" :key="detail.id" :evaluation-id="detail.id" :hints="learnerFeedback.hints" :snapshot-xml="snapshotXml" :readonly="!ownsEvaluation" :active="tab === 'hints'" :focus="hintFocus" expanded />
      <p v-else-if="!hintsLoading && !hintError" class="text-medium-emphasis">Keine Hinweise für diese Auswertung.</p>
    </section>
    <v-alert v-if="tab !== 'hints' && error" type="warning" density="compact" variant="tonal" class="my-2">{{ error }}</v-alert>

    <template v-else-if="analysis && tab === 'overview'">
      <HintNotice v-if="!noticeViewed" :count="learnerFeedback?.hints?.length ?? 0" @open="noticeViewed = true; openHints()" />
      <section v-if="overviewMode" class="analysis-panel__section" aria-label="Evaluation result">
        <div class="d-flex align-center justify-space-between ga-3 mb-2">
          <div><h3 class="text-body-2 font-weight-medium">Erkennungsquote</h3><span class="text-caption text-medium-emphasis">Gewählte Musterlösung</span></div>
          <strong class="text-h4">{{ finalRecognition?.overall.percent == null ? '—' : `${number.format(finalRecognition.overall.percent)} %` }}</strong>
        </div>
        <v-progress-linear v-if="finalRecognition?.overall.percent != null" :model-value="finalRecognition.overall.percent" height="8" rounded color="info" aria-label="Eindeutig erkannte Musterlösungsobjekte" />
        <p v-if="finalRecognition" class="mt-2 mb-1">{{ finalRecognition.overall.recognized }} von {{ finalRecognition.overall.expected }} Musterlösungsobjekten eindeutig erkannt. {{ finalRecognition.unmatchedSubmission.length }} Abgabeobjekte ohne Zuordnung.</p>
        <p v-else class="text-medium-emphasis mt-2 mb-1">{{ recognitionError || 'Das finale Erkennungsergebnis liegt noch nicht vor.' }}</p>
        <p class="text-medium-emphasis mb-3">Erkennung ist keine Korrektheitsnote. Abweichungen und offene Prüfungen stehen separat darunter.</p>
        <div v-for="row in recognitionRows" :key="row.key" class="mb-2">
          <div class="d-flex justify-space-between ga-2"><span>{{ row.label }}</span><span>{{ row.count.recognized }} / {{ row.count.expected }} · {{ row.count.percent == null ? 'nicht ausgewertet' : `${number.format(row.count.percent)} %` }}</span></div>
          <v-progress-linear v-if="row.count.percent != null" :model-value="row.count.percent" height="3" color="info" :aria-label="row.label" />
        </div>
      </section>
      <section class="analysis-panel__section" aria-label="Befunde im Überblick">
        <h3 class="text-body-2 font-weight-medium mb-1">Befunde</h3>
        <p v-if="overviewMode" class="text-medium-emphasis mb-2">Eine andere Beschriftung allein ist keine Abweichung: bestätigte Synonyme bleiben grün. Ein blaues Infosymbol erscheint nur bei einer erzeugten Rückfrage. Kinder und Gruppenbefunde beeinflussen die Hakenfarbe nicht.</p>
        <v-list density="compact" class="pa-0" bg-color="transparent">
          <v-list-item v-for="group in groupCounts" :key="group.group" :title="group.title" class="analysis-panel__count" @click="showGroup(group.group)">
            <template #prepend><v-icon size="18" :color="group.color">{{ group.icon }}</v-icon></template>
            <template #append><span class="text-body-2 font-weight-medium">{{ group.count }}</span></template>
          </v-list-item>
        </v-list>
      </section>

      <section v-if="overviewMode" class="analysis-panel__section" aria-label="Differences and generated hints">
        <h3 class="text-body-2 font-weight-medium mb-2">Was fällt auf?</h3>
        <div class="d-flex flex-wrap ga-2 mb-3">
          <v-chip size="small" variant="tonal">{{ differenceCounts.properties }} Objekte mit lokalen Abweichungen</v-chip>
          <v-chip size="small" variant="tonal">{{ differenceCounts.open }} Objekte mit offenen Prüfungen</v-chip>
          <v-chip size="small" variant="tonal">{{ differenceCounts.type }} Typabweichungen</v-chip>
          <v-chip size="small" variant="tonal">{{ differenceCounts.partial }} teilweise konsistent</v-chip>
        </div>
        <h3 class="text-body-2 font-weight-medium mb-1">Erzeugte Analysehinweise ({{ overviewHints.length }})</h3>
        <p v-if="!overviewHints.length" class="text-medium-emphasis">Keine Analysehinweise für diese Musterlösung.</p>
        <v-list v-else density="compact" class="pa-0" bg-color="transparent">
          <v-list-item v-for="hint in overviewHints" :key="hint.key" :title="hint.text" :subtitle="hint.subject" :disabled="!hint.finding" @click="hint.finding && openFinding(hint.finding)"><template #prepend><v-icon icon="mdi-lightbulb-outline" size="18" class="mr-2" /></template></v-list-item>
        </v-list>
        <v-btn v-if="catalogAvailable !== false" size="small" variant="text" append-icon="mdi-arrow-right" @click="tab = 'feedback'">Alle Feedbackarten pro Element ansehen</v-btn>
      </section>

      <section v-if="!overviewMode" class="analysis-panel__section" aria-label="Konfiguration">
        <h3 class="text-body-2 font-weight-medium mb-1">Textähnlichkeit</h3>
        <template v-if="evidence">
          <div v-for="method in evidence.methods" :key="method.name" class="d-flex justify-space-between ga-2">
            <span>{{ similarityMethodLabel(method.name) }}</span>
            <span :class="method.threshold === null ? 'text-medium-emphasis' : 'font-weight-medium'">{{ method.threshold === null ? 'berechnet, ohne Schwelle' : method.stages.length ? method.stages.join(' · ') : `Schwelle ${number.format(method.threshold)}` }}</span>
          </div>
          <div v-for="method in evidence.methods.filter(item => item.floor !== null)" :key="`${method.name}-floor`" class="d-flex justify-space-between ga-2 text-medium-emphasis">
            <span>Graubereich {{ similarityMethodLabel(method.name) }}</span>
            <span>ab {{ number.format(method.floor ?? 0) }}, nur mit Bestätigung durch Nachbarn</span>
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
      </section>
    </template>

    <template v-else-if="analysis && tab === 'findings'">
      <v-alert v-if="stale" type="info" density="compact" variant="tonal" class="my-2">Das Modell wurde seit der Auswertung geändert. Markierungen bleiben für unveränderte Objekte und Abhängigkeiten erhalten. Die Befundtexte beziehen sich auf den ausgewerteten Stand.</v-alert>

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
          :overview-mode="overviewMode"
        >
          <template #student-questions />
        </AnalysisObjectDetail>
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
import { InternalEvent, type Cell } from '@maxgraph/core'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import { useUserStore } from '@/stores/userStore'
import { useEvaluationResult } from '@/composables/useEvaluationResult'
import evaluationService from '@/services/evaluation/evaluation.service'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createFeedbackValidity, currentAnalysis } from '@/utils/feedbackValidity'
import {
  analysisDisplay, analysisOverviewDisplay, analysisOverviewAppearance, analysisStudentQuestions, analysisFactLabel, analysisFromEvaluation, analysisHintText, analysisIdentityMethodLabel, analysisOverviewStatus, analysisStatus, candidateEvidence, graphDiagnosticLabel,
  analysisCategories, categoryLabels, recognitionReportsFromEvaluation,
  graphInfo, individualViolations, objectKindLabel, similarityMethodLabel, type AdaptedAnalysis, type AnalysisAnnotation, type GraphInfo, type ReferenceHint
} from '@/utils/analysisFeedback'
import { analysisTargetCell, createCellOutline, installAnalysisOverlays, referenceHintTarget } from '@/utils/analysisFeedbackGraph'
import AnalysisObjectDetail from './AnalysisObjectDetail.vue'
import HintsFeedback from '@/components/feedback/HintsFeedback.vue'
import HintNotice from '@/components/feedback/HintNotice.vue'

type FindingGroup = 'warning' | 'unresolved' | 'supported' | 'reference' | 'recognized' | 'other'
interface Finding { key: string; group: FindingGroup; title: string; subtitle: string; icon: string; color: string; annotation?: AnalysisAnnotation; hint?: ReferenceHint }

const props = defineProps<{ detail: EvaluationDetail; overviewMode?: boolean; catalogAvailable?: boolean }>()
const user = useUserStore()
const ownsEvaluation = computed(() => user.userId === props.detail.ownerId)
const snapshotXml = computed(() => (props.detail.submissionSnapshot.data as { xml?: string } | undefined)?.xml)
// Both analysis hosts use the published learner hints and their persisted decisions.
const { result: learnerFeedback, loading: hintsLoading, error: hintError, reload: reloadHints } = useEvaluationResult(
  () => props.detail.id, id => evaluationService.getFeedback(id), () => props.detail.state === 'succeeded')
const hintFocus = ref<{ cellId: string; seq: number } | null>(null)
const noticeViewed = ref(false)
watch(() => props.detail.id, () => { hintFocus.value = null; noticeViewed.value = false })
const openHints = (cellId = learnerFeedback.value?.hints?.[0]?.submissionId) => {
  if (!cellId) return
  hintFocus.value = { cellId, seq: (hintFocus.value?.seq ?? 0) + 1 }
  tab.value = 'hints'
}
// In the feedback tab a diagram click stays there; the catalog shows the object instead of the findings.
const emit = defineEmits<{ 'feedback-object': [id: string] }>()
const referenceKey = defineModel<string>('referenceKey', { default: '' })
const tab = defineModel<'overview' | 'findings' | 'hints' | 'feedback' | 'technical'>('tab', { default: 'overview' })
const graphContext = useGraphContextOptional()
const number = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 3 })
const selectedKey = ref<string | null>(null)
const filter = ref<FindingGroup | 'all'>('all')
const search = ref<string | null>('')
const stale = ref(false)
const currentFindingKeys = shallowRef(new Set<string>())
const analysis = shallowRef<AdaptedAnalysis | null>(null)
const error = ref('')
const displayStatus = (item: AnalysisAnnotation) => props.overviewMode ? analysisOverviewStatus(item) : analysisStatus(item)
const recognitionState = computed(() => {
  try { return { value: recognitionReportsFromEvaluation(props.detail).find(item => item.referenceKey === referenceKey.value)?.recognition, error: '' } }
  catch { return { value: undefined, error: 'Das finale Erkennungsergebnis konnte nicht verifiziert werden.' } }
})
const finalRecognition = computed(() => recognitionState.value.value)
const recognitionError = computed(() => recognitionState.value.error)
const recognitionRows = computed(() => finalRecognition.value?.buckets?.map(row => ({ key: row.id, label: row.label, count: row })) ??
  (finalRecognition.value?.categories ? analysisCategories.map(key => ({ key, label: categoryLabels[key], count: finalRecognition.value!.categories![key] })) : []))
const differenceCounts = computed(() => {
  const items = (analysis.value?.report.annotations ?? []).filter(item => item.target.kind !== 'structuralElement')
  const differs = (item: AnalysisAnnotation, kind: string) => individualViolations(item).some(fact => fact.code.startsWith(`${kind}.`)) || item.hints.some(hint => hint.code.startsWith(`${kind}.`) && ['label.different', 'type.compatible_difference'].includes(hint.code))
  return { properties: items.filter(item => individualViolations(item).length).length,
    open: items.filter(item => item.facts?.some(fact => fact.status === 'unresolved' && !fact.code.startsWith('identity.') && !fact.code.startsWith('label.'))).length,
    type: items.filter(item => differs(item, 'type') || item.checks?.type === 'compatible_type_difference').length,
    partial: items.filter(item => item.consistency === 'partial').length }
})


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
  supported: { ...(props.overviewMode ? analysisOverviewDisplay.supported : analysisDisplay.supported), title: props.overviewMode ? 'Kandidaten, nicht eindeutig erkannt' : 'Gestützt, nicht eindeutig' },
  reference: { icon: 'mdi-link-variant-off', color: analysisDisplay.unresolved.color, title: 'Musterlösung ohne Gegenstück' },
  recognized: { ...(props.overviewMode ? { icon: 'mdi-check-circle-outline', color: '#414958' } : analysisDisplay.recognized), title: 'Eindeutig erkannt' },
  other: { ...analysisDisplay.not_evaluated, title: 'Nicht ausgewertet' }
}
const findingReason = (item: AnalysisAnnotation) => {
  const violations = individualViolations(item)
  if (violations.length) return `Abweichend: ${[...new Set(violations.map(fact => analysisFactLabel(fact.code)))].join(', ')}`
  if (props.overviewMode && item.consistency === 'partial' && displayStatus(item) !== 'recognized') return 'Teilweise konsistent: offene oder abweichende lokale Prüfungen'
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
  const result: Finding[] = report.annotations.filter(item => item.target.kind !== 'structuralElement').map(item => {
    const status = displayStatus(item)
    const group: FindingGroup = status === 'warning' || status === 'unresolved' || status === 'supported' || status === 'recognized' ? status : 'other'
    const type = submissionGraph.value?.nodes.get(item.target.id)?.type
    const display = props.overviewMode ? analysisOverviewAppearance(item, !!analysis.value && analysisStudentQuestions(analysis.value.report, item.target.id).length > 0) : analysisDisplay[status]
    return { key: `submission:${item.target.id}`, group, annotation: item, icon: display.icon, color: display.color,
      title: describe('submission', item.target.id), subtitle: [objectKindLabel(item.target.kind), type, findingReason(item)].filter(Boolean).join(' · ') }
  })
  for (const hint of report.referenceHints) {
    if (hint.kind === 'structuralElement') continue
    const missing = hint.code === 'reference.missing', notEvaluated = hint.code === 'reference.not_evaluated'
    const look = missing ? analysisDisplay.warning : notEvaluated ? analysisDisplay.not_evaluated : groupMeta.reference
    result.push({ key: `reference:${hint.referenceId}`, group: notEvaluated ? 'other' : 'reference', hint, icon: look.icon, color: look.color,
      title: referenceGraph.value?.nodes.get(hint.referenceId)?.label ? describe('reference', hint.referenceId) : hint.label ?? describe('reference', hint.referenceId),
      subtitle: `${objectKindLabel(hint.kind)} der Musterlösung · ${missing ? 'nachweisbar fehlend' : notEvaluated ? 'nicht ausgewertet' : 'kein Gegenstück identifiziert, nicht als fehlend belegt'}` })
  }
  return result.sort((left, right) => groupOrder.indexOf(left.group) - groupOrder.indexOf(right.group) || left.title.localeCompare(right.title, 'de'))
})
const groupCounts = computed(() => groupOrder.map(group => ({ group, ...groupMeta[group], count: findings.value.filter(item => item.group === group).length })).filter(group => group.count))
const overviewHints = computed(() => {
  const rows = findings.value.flatMap(finding => (finding.annotation?.hints ?? (finding.hint ? [finding.hint] : [])).filter(hint => hint.code !== 'label.different').map(hint => ({
    key: `${finding.key}:${hint.findingId ?? hint.code}`, text: analysisHintText(hint), subject: finding.title, finding: finding as Finding | undefined
  })))
  for (const hint of analysis.value?.report.limitations ?? []) rows.push({ key: `model:${hint.code}`, text: analysisHintText(hint), subject: 'Gesamtes Modell', finding: undefined })
  return [...new Map(rows.map(row => [row.key, row])).values()]
})
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
  if (!graph || !currentFindingKeys.value.has(finding.key)) return null
  return finding.annotation ? analysisTargetCell(graph, finding.annotation.target) : finding.hint ? referenceHintTarget(graph, finding.hint) : null
}
const targetNote = computed(() => {
  const item = selected.value
  if (!item || !graphContext?.graph.value) return undefined
  if (!currentFindingKeys.value.has(item.key)) return 'Dieses Feedback gilt für den ausgewerteten Stand. Das Objekt oder eine seiner Abhängigkeiten wurde inzwischen geändert.'
  if (targetCell(item)) return undefined
  return item.hint ? 'Im Diagramm nicht verortbar: Es gibt keinen identifizierten Parent oder Endpunkt.' : 'Für dieses Objekt ist kein Diagrammziel darstellbar.'
})
// Our own focus must not be read back as a user selection (a reference hint focuses its parent cell).
let focusing = false
const openFinding = (finding: Finding, focusDiagram = true) => {
  selectedKey.value = finding.key
  tab.value = 'findings'
  if (!focusDiagram) return
  const graph = graphContext?.graph.value
  const cell = targetCell(finding)
  if (!graph || !cell) return
  focusing = true
  try { graph.clearSelection(); graph.scrollCellToVisible(cell) } finally { focusing = false }
}
watch([selectedKey, () => graphContext?.graph.value, currentFindingKeys, tab], (_, __, onCleanup) => {
  const graph = graphContext?.graph.value
  const cell = selected.value && targetCell(selected.value)
  if (!graph || !cell || tab.value !== 'findings') return
  const highlight = createCellOutline(graph, cell)
  onCleanup(() => highlight.destroy())
})
const openSubmission = (id: string, showQuestion = false) => {
  if (showQuestion) {
    openHints(id)
    return
  }
  if (!showQuestion && tab.value === 'feedback') return emit('feedback-object', id)
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

watch(analysis, () => { selectedKey.value = null; filter.value = 'all' })
watch([() => graphContext?.graph.value, analysis], ([graph, value], _, onCleanup) => {
  stale.value = false
  currentFindingKeys.value = new Set()
  if (!graph || !value) return
  const data = props.detail.submissionSnapshot.data as { xml?: string } | undefined
  const evaluate = createFeedbackValidity(data?.xml)
  let removeOverlays = () => {}
  const refresh = () => {
    removeOverlays()
    const validity = evaluate(graph)
    stale.value = validity.changed
    const applicable = currentAnalysis(value, validity)
    currentFindingKeys.value = new Set([
      ...applicable.report.annotations.filter(item => item.target.kind !== 'structuralElement').map(item => `submission:${item.target.id}`),
      ...applicable.report.referenceHints.filter(item => item.kind !== 'structuralElement').map(item => `reference:${item.referenceId}`)
    ])
    removeOverlays = installAnalysisOverlays(graph, applicable, openSubmission, props.overviewMode).remove
  }
  // Selecting an analysed cell in the diagram opens its findings; other selections leave the panel as it is.
  const selectionChanged = () => {
    const id = (graph.getSelectionCell() as Cell | null)?.getId()
    if (focusing || !id || !currentFindingKeys.value.has(`submission:${id}`)) return
    if (tab.value === 'feedback') return emit('feedback-object', id)
    const finding = findings.value.find(item => item.key === `submission:${id}`)
    // Reflect the editor selection without clearing it or interrupting drag/label editing.
    if (finding) openFinding(finding, false)
  }
  graph.getSelectionModel().addListener(InternalEvent.CHANGE, selectionChanged)
  graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
  refresh()
  onCleanup(() => { removeOverlays(); graph.getSelectionModel().removeListener(selectionChanged); graph.getDataModel().removeListener(refresh) })
}, { immediate: true, flush: 'post' })
defineExpose({ openSubmission })
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
