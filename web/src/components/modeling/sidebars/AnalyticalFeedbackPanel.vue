<template>
  <section aria-label="Analytisches Feedback" class="my-3 text-caption">
    <h3 class="text-body-2 font-weight-medium mb-2">Analytisches Feedback</h3>
    <v-select v-model="referenceKey" :items="references" item-title="label" item-value="key" label="Musterlösung" density="compact" variant="outlined" hide-details class="mb-2" />
    <v-alert v-if="error" type="warning" density="compact" variant="tonal">{{ error }}</v-alert>
    <template v-else-if="analysis">
      <p>Alle Zuordnungen sind vorläufig. Erkennung bestätigt keine endgültige Korrektheit.</p>
      <ul v-if="analysis.report.limitations?.length" class="pl-4 my-2 text-medium-emphasis"><li v-for="hint in analysis.report.limitations" :key="hint.code">{{ analysisHintText(hint) }}</li></ul>
      <p v-if="analysis.report.structuralContainers" class="text-medium-emphasis">Strukturelle Container: {{ analysis.report.structuralContainers.submissionCount }} in der Abgabe, {{ analysis.report.structuralContainers.referenceCount }} in der Referenz. Keine fachliche Knotenzählung.</p>
      <v-alert v-if="stale" type="info" density="compact" variant="tonal" class="my-2">Das aktuelle Diagramm weicht vom ausgewerteten Stand ab. Markierungen sind ausgeblendet; die folgenden Befunde gelten für den gespeicherten Stand.</v-alert>
      <v-select v-model="selectedId" :items="objectOptions" item-title="label" item-value="id" label="Element oder Verbindung" density="compact" variant="outlined" hide-details class="my-3" @update:model-value="focusObject" />
      <v-switch v-model="showDiagnostics" label="Details und Diagnosen anzeigen" density="compact" hide-details class="mb-2" />
      <template v-if="selected">
        <p class="d-flex align-center ga-1"><v-icon :color="display.color" size="18">{{ display.icon }}</v-icon>{{ display.label }}</p>
        <p v-if="selected.identity" class="text-body-2 font-weight-medium my-2">{{ analysisIdentityLabel(selected.identity.status) }}</p>
        <dl class="object-details">
          <dt>Original-ID</dt><dd>{{ selected.target.id }}</dd>
          <template v-if="selected.match"><dt>Historische Zuordnung</dt><dd>{{ analysisValueLabel(selected.match.status) }}</dd></template>
          <template v-if="selected.referenceId"><dt>Referenzgegenstück</dt><dd>{{ referenceLabel(selected.referenceId) }}</dd></template>
          <template v-if="selected.mappingReason || selected.match?.reason"><dt>Zuordnungsgrund</dt><dd>{{ analysisReasonLabel(selected.mappingReason ?? selected.match?.reason ?? '') }}</dd></template>
          <template v-if="selected.context"><dt>Strukturkontext</dt><dd>{{ referenceLabel(selected.context.referenceId) }} (abgeleitet, keine Zuordnung)</dd></template>
          <template v-if="selected.owner"><dt>Besitzer (Referenz / Abgabe)</dt><dd>{{ selected.owner.referenceOwnerId ?? 'ungeklärt oder ohne Besitzer' }} / {{ selected.owner.submissionOwnerId ?? 'ungeklärt oder ohne Besitzer' }}</dd></template>
          <template v-if="selected.containment"><dt>Direkte Parents (Referenz / Abgabe)</dt><dd>{{ parentText(selected.containment.referenceParents) }} / {{ parentText(selected.containment.submissionParents) }}</dd></template>
          <template v-if="!selected.facts && selected.checks"><template v-for="(status, check) in selected.checks" :key="check"><dt>{{ checkLabels[check] ?? check }}{{ groupCheck(check) ? ' (Gruppe)' : '' }}</dt><dd>{{ analysisValueLabel(status) }}</dd></template></template>
        </dl>
        <strong v-if="selected.identity?.criteria.length">Identitätsevidenz</strong>
        <dl v-if="selected.identity?.criteria.length" class="object-details my-2" aria-label="Identitätsevidenz">
          <template v-for="criterion in selected.identity.criteria" :key="criterion.method">
            <dt>{{ analysisIdentityMethodLabel(criterion.method) }}</dt>
            <dd>{{ criterion.result === 'violated' ? 'Nicht erfüllt' : analysisValueLabel(criterion.result) }}<template v-if="criterion.expected !== undefined"> · {{ criterion.matched ?? 0 }} / {{ criterion.expected }}</template><br />
              <span class="text-medium-emphasis">{{ analysisIdentityRoleLabel(criterion.role) }}</span>
            </dd>
          </template>
        </dl>
        <div v-if="selectedChildren" class="my-2" aria-label="Kinderbefunde">
          <strong>{{ selectedChildren.matched }} / {{ selectedChildren.expected }} erwartete Kinder korrekt enthalten</strong>
          <div v-if="selectedChildren.moved.length">{{ selectedChildren.moved.length }} erkannt, unter anderem Parent: {{ selectedChildren.moved.map(referenceLabel).join(', ') }}</div>
          <div v-if="selectedChildren.absent.length">{{ selectedChildren.absent.length }} nachweisbar nicht realisiert: {{ selectedChildren.absent.map(referenceLabel).join(', ') }}</div>
          <div v-if="selectedChildren.unresolvedReference.length">{{ selectedChildren.unresolvedReference.length }} erwartete Kinder nicht zuordenbar: {{ selectedChildren.unresolvedReference.map(referenceLabel).join(', ') }}</div>
          <div v-if="selectedChildren.unresolvedSubmission.length">{{ selectedChildren.unresolvedSubmission.length }} zusätzliche, nicht zuordenbare Kinder: {{ selectedChildren.unresolvedSubmission.join(', ') }}</div>
          <div v-if="selectedChildren.foreign.length">{{ selectedChildren.foreign.length }} einem anderen Referenzkontext zugeordnete Kinder: {{ selectedChildren.foreign.join(', ') }}</div>
          <div v-if="selectedChildren.roleDifferences.length">Abweichende Relationsrollen: {{ selectedChildren.roleDifferences.map(referenceLabel).join(', ') }}</div>
        </div>
        <p v-if="selected.consistency" class="my-2">{{ analysisValueLabel(selected.consistency) }}</p>
        <dl v-if="selected.facts?.length" class="object-details my-2" aria-label="Einzelbefunde">
          <template v-for="fact in visibleFacts" :key="fact.code">
            <dt>{{ analysisFactLabel(fact.code) }}</dt>
            <dd>{{ analysisValueLabel(fact.status) }}<br /><span class="text-medium-emphasis">{{ analysisFactEvidence(fact) }}</span></dd>
          </template>
        </dl>
        <p v-if="selected && !stale && graphContext?.graph.value && !analysisTargetCell(graphContext.graph.value, selected.target)" class="text-medium-emphasis">Für dieses Objekt ist kein Diagrammziel darstellbar. Die Befunde bleiben hier über die Original-ID verfügbar.</p>
        <dl v-if="selected.connection" class="object-details my-2">
          <template v-for="side in (['reference', 'submission'] as const)" :key="side">
            <dt>{{ side === 'reference' ? 'Referenzverbindung' : 'Abgabeverbindung' }}</dt>
            <dd v-if="selected.connection[side]">Source: {{ selected.connection[side]!.sourceId ?? 'ungeklärt' }}<br />Target: {{ selected.connection[side]!.targetId ?? 'ungeklärt' }}<br />{{ selected.connection[side]!.directed === null ? 'Richtung ungeklärt' : selected.connection[side]!.directed ? 'Gerichtet' : 'Ungerichtet' }} · {{ selected.connection[side]!.type ?? 'Typ ungeklärt' }}</dd>
            <dd v-else>Kein individuell zugeordnetes Gegenstück</dd>
          </template>
        </dl>
        <p v-if="selected.checks?.connectionScope === 'endpoint_group'">Richtung und Verbindungstyp gelten für die Endpunktgruppe. Sie beweisen keinen individuellen Fehler dieser Verbindung.</p>
        <div v-if="showDiagnostics && selectedDependencies.length" class="my-2">
          <strong>Abhängige Zuordnungen</strong>
          <div v-for="dep in selectedDependencies" :key="dep.submissionId">{{ dep.submissionId }} → {{ referenceLabel(dep.referenceId) }}</div>
        </div>
        <template v-for="(fieldLabel, field) in localFields" :key="field">
          <div v-if="selected.local?.[field]" class="my-2">
            <strong>{{ fieldLabel }}</strong>
            <dl class="object-details">
              <template v-for="(label, key) in localLabels" :key="key"><dt>{{ label }}</dt><dd>{{ selected.local[field]![key] ?? 'nicht bestimmbar' }}</dd></template>
            </dl>
          </div>
        </template>
        <div v-if="selected.local?.containmentRelations" class="my-2">
          <strong>Lokale Containment-Prüfung</strong>
          <div>{{ selected.local.containmentRelations.recognized }} / {{ selected.local.containmentRelations.expected ?? 'unbekannt' }} Beziehungen gestützt · {{ selected.local.containmentRelations.deviating }} abweichend · {{ selected.local.containmentRelations.unresolvedReference ?? 'unbekannt' }} ungeklärt</div>
          <div v-for="role in selected.local.childRoles" :key="role.role ?? 'unknown'">{{ role.role ?? 'Rolle ungeklärt' }}: {{ role.recognized }} / {{ role.expected ?? 'unbekannt' }} gestützt · {{ role.observed }} beobachtet · {{ role.deviating }} abweichend · {{ role.unresolvedReference ?? 'unbekannt' }} ungeklärt</div>
        </div>
        <div v-for="relation in selectedRelations" :key="relation.id" class="my-2">
          <strong>Containment-Beziehung · {{ analysisValueLabel(relation.status) }}</strong>
          <div>Referenz: {{ relation.referenceChildId }} → {{ relation.referenceParentId }} ({{ relation.referenceRole ?? 'Rolle ungeklärt' }})</div>
          <div>Abgabe: {{ relation.submissionChildId ?? 'Kind ungeklärt' }} → {{ parentText(relation.observedParents) }}</div>
          <div>Relationsrolle: {{ analysisValueLabel(relation.roleStatus) }}</div>
        </div>
        <div v-for="group in selectedGroups" :key="group.id" class="my-2">
          <strong>Verbindungsgruppe</strong>
          <p>Dieser Befund gilt für die Gruppe und belegt keinen Fehler jeder einzelnen Verbindung.</p>
          <div>Referenz: {{ group.referenceIds.join(', ') || 'keine' }}<br />Abgabe: {{ group.submissionIds.join(', ') || 'keine' }}</div>
          <dl v-if="group.facts" class="object-details"><template v-for="fact in group.facts" :key="fact.id ?? fact.code"><dt>{{ analysisFactLabel(fact.code) }}</dt><dd>{{ analysisValueLabel(fact.status) }}<br /><span class="text-medium-emphasis">{{ analysisFactEvidence(fact) }}</span></dd></template></dl>
          <dl v-else class="object-details"><template v-for="(status, check) in group.checks" :key="check"><dt>{{ checkLabels[check] ?? check }}</dt><dd>{{ analysisValueLabel(status) }}</dd></template></dl>
          <div v-if="group.referenceOnlyCount !== undefined">Ohne Gegenstück in der Gruppe: {{ group.referenceOnlyCount }} Referenz / {{ group.submissionOnlyCount }} Abgabe. Individuelle Identitäten bleiben ungeklärt.</div>
        </div>
        <ul v-if="showDiagnostics && selected.hints.length" class="pl-4 my-2">
          <li v-for="(hint, index) in selected.hints" :key="`${hint.code}:${index}`" class="mb-2">{{ analysisHintText(hint) }}<div class="technical-parameters text-medium-emphasis">{{ analysisHintParameters(hint) }}</div></li>
        </ul>
      </template>
      <div v-if="visibleReferenceHints.length" class="my-3">
        <strong>Referenzbefunde{{ selected ? ' am Anzeigeziel oder Modell' : '' }}</strong>
        <ul class="pl-4 mt-1">
          <li v-for="hint in visibleReferenceHints" :key="hint.referenceId" class="mb-2">{{ hint.label ?? referenceLabel(hint.referenceId) }}: {{ analysisHintText(hint) }}<div>{{ hint.reason === 'ambiguous_candidates' ? 'Mehrdeutige Kandidaten. ' : '' }}{{ hint.referenceId }}</div>
            <div v-for="fact in hint.facts" :key="fact.code" class="mt-1">{{ analysisFactLabel(fact.code) }}: {{ analysisValueLabel(fact.status) }}<br /><span class="text-medium-emphasis">{{ analysisFactEvidence(fact) }}</span></div>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { GraphDataModel, InternalEvent, type Cell, type Graph } from '@maxgraph/core'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import { useGraphContextOptional } from '@/composables/useGraphContext'
import { createModelSerializer, importModelFromXml } from '@/utils/modelPersistence'
import { analysisChildChecklist, analysisDisplay, analysisFactEvidence, analysisFactLabel, analysisFromEvaluation, analysisHintParameters, analysisHintText, analysisIdentityLabel, analysisIdentityMethodLabel, analysisIdentityRoleLabel, analysisReasonLabel, analysisStatus, analysisValueLabel, checkLabels, type AdaptedAnalysis, type LocalCounts, type ParentRelation } from '@/utils/analysisFeedback'
import { analysisTargetCell, installAnalysisOverlays, referenceHintTarget } from '@/utils/analysisFeedbackGraph'

const props = defineProps<{ detail: EvaluationDetail }>()
const graphContext = useGraphContextOptional()
const referenceKey = defineModel<string>('referenceKey', { default: '' })
const showDiagnostics = ref(false)
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
const localLabels: Record<keyof LocalCounts, string> = { expected: 'Erwartet', observed: 'In der Abgabe', recognized: 'Vorläufig erkannt', recognizedAtTarget: 'Davon an diesem Ziel', unresolvedReference: 'Referenz ungeklärt', unresolvedSubmission: 'Abgabegegenstück ungeklärt', mappedFromOtherTargets: 'Anderem Kontext zugeordnet', deviating: 'Individuell abweichend', unresolvedChecks: 'Mit ungeklärten Einzelprüfungen' }
const localFields = { children: 'Fachliche Kinder einschließlich Zwischencontainern', directChildren: 'Unmittelbare Kinder', connections: 'Angrenzende Verbindungen', incoming: 'Eingehend', outgoing: 'Ausgehend', undirected: 'Ungerichtet', unresolved: 'Richtung ungeklärt' } as const
const parentText = (parents: ParentRelation[] | null) => parents === null ? 'nicht ausgewertet' : parents.map(parent => `${parent.parentId} (${parent.role ?? 'Rolle ungeklärt'})`).join(', ') || 'keine'
const selectedRelations = computed(() => analysis.value?.report.containmentRelations?.filter(relation => selected.value?.relationIds?.includes(relation.id)) ?? [])
const selectedGroups = computed(() => analysis.value?.report.connectionGroups?.filter(group => selected.value?.groupIds?.includes(group.id) || !!selectedId.value && group.submissionEndpointIds.includes(selectedId.value)) ?? [])
const groupCheck = (check: string) => selected.value?.checks?.connectionScope === 'endpoint_group' && ['direction', 'connectionType'].includes(check)
const visibleFacts = computed(() => selected.value?.facts?.filter(fact => showDiagnostics.value || fact.status === 'violated' || fact.status === 'unresolved' || /^(label|type|owner|containment|counterpart|connection)\./.test(fact.code)) ?? [])
const selectedDependencies = computed(() => selected.value?.dependencies?.map(dep => ({ referenceId: dep.referenceId, submissionId: dep.studentId })) ?? selected.value?.match?.dependsOn ?? [])
const selectedChildren = computed(() => analysisChildChecklist(selected.value?.facts))
const visibleReferenceHints = computed(() => analysis.value?.report.referenceHints.filter(hint => {
  const graph = graphContext?.graph.value
  const target = graph && !stale.value ? referenceHintTarget(graph, hint) : null
  return !target || !selectedId.value || target.getId() === selectedId.value
}) ?? [])
const focusObject = (id: string | null) => {
  const graph = graphContext?.graph.value
  const item = analysis.value?.report.annotations.find(item => item.target.id === id)
  const cell = graph && item && !stale.value ? analysisTargetCell(graph, item.target) : null
  if (cell) { graph!.setSelectionCell(cell); graph!.scrollCellToVisible(cell); selectedId.value = id }
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
watch([() => graphContext?.graph.value, analysis], ([graph, value], _, onCleanup) => {
  selectedId.value = null
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
.object-details { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr); gap: 4px 8px; }
dd { margin: 0; overflow-wrap: anywhere; }
.technical-parameters { overflow-wrap: anywhere; font-size: 11px; }
</style>
