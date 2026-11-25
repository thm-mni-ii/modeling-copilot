<template>
  <article class="analysis-detail text-caption" :aria-label="`Befund ${title}`">
    <header class="mb-2">
      <h4 class="text-body-2 font-weight-medium analysis-detail__title">{{ title }}</h4>
      <div class="d-flex align-center flex-wrap ga-2 mt-1">
        <v-chip size="x-small" label variant="tonal" :color="display.color"><v-icon start size="12">{{ display.icon }}</v-icon>{{ statusLabel }}</v-chip>
        <span class="text-medium-emphasis">{{ kindText }}</span>
      </div>
    </header>
    <slot name="student-questions">
      <section v-if="studentQuestions.length" class="analysis-detail__section" aria-label="Rückfrage an Studierende">
        <h5 class="analysis-detail__heading"><v-icon icon="mdi-information-outline" color="info" size="16" /> Rückfrage an Studierende</h5>
        <div v-for="question in studentQuestions" :key="question.id" class="mb-2">{{ question.text }}<div class="text-medium-emphasis">{{ question.reason }}</div></div>
        <p class="text-medium-emphasis">Dies ist ein Hinweis auf ein mögliches Gegenstück und zählt nicht als bestätigte Erkennung.</p>
      </section>
    </slot>

    <section class="analysis-detail__section" aria-label="Ergebnis">
      <ul class="agenda">
        <li v-for="(row, index) in agenda" :key="index"><v-icon size="16" :color="row.color" aria-hidden="true">{{ row.icon }}</v-icon><span>{{ row.text }}</span></li>
      </ul>
      <p v-if="targetNote" class="text-medium-emphasis mt-1 mb-0">{{ targetNote }}</p>
    </section>

    <section v-if="identity || annotation?.referenceId" class="analysis-detail__section" aria-label="Zuordnung und Identität">
      <h5 class="analysis-detail__heading">Zuordnung &amp; Identität</h5>
      <dl class="object-details mb-2">
        <template v-if="annotation?.referenceId"><dt>Gegenstück</dt><dd>{{ describe('reference', annotation.referenceId) }}</dd></template>
        <template v-if="annotation?.mappingReason || annotation?.match?.reason"><dt>Zuordnungsregel</dt><dd>{{ analysisReasonLabel(annotation.mappingReason ?? annotation.match?.reason ?? '') }}</dd></template>
        <template v-if="annotation?.match"><dt>Zuordnung (älteres Format)</dt><dd>{{ analysisValueLabel(annotation.match.status) }}</dd></template>
        <template v-if="annotation?.context"><dt>Strukturkontext</dt><dd>{{ describe('reference', annotation.context.referenceId) }} (abgeleitet, keine Zuordnung)</dd></template>
      </dl>
      <p v-if="explanation" class="mb-2">{{ explanation }}</p>
      <div v-for="group in criteriaGroups" :key="group.title" class="mb-2">
        <div class="font-weight-medium">{{ group.title }}</div>
        <ul class="agenda">
          <li v-for="criterion in group.items" :key="criterion.method">
            <v-icon size="16" :color="criterionColor(criterion.result)" aria-hidden="true">{{ criterionIcon(criterion.result) }}</v-icon>
            <span>{{ analysisIdentityMethodLabel(criterion.method) }}<br /><span class="text-medium-emphasis">{{ identityCriterionNote(criterion, describePair) }}</span></span>
          </li>
        </ul>
      </div>
      <div v-if="sameText.length" class="mb-1">
        <div class="font-weight-medium">Gleiche Beschriftung auch bei</div>
        <div v-for="pair in sameText" :key="`${pair.referenceId}:${pair.submissionId}`" class="text-medium-emphasis">
          {{ pair.submissionId === submissionId ? `Referenz „${pair.referenceLabel}“ (${pair.referenceId})` : `Abgabe „${pair.submissionLabel}“ (${pair.submissionId})` }}
        </div>
      </div>
    </section>

    <section v-if="decisions.length" class="analysis-detail__section" aria-label="Entscheidung je Textkandidat">
      <h5 class="analysis-detail__heading">Entscheidung je Textkandidat</h5>
      <ul class="agenda">
        <li v-for="row in decisions" :key="`${row.referenceId}:${row.studentId}`">
          <v-icon size="16" :color="decisionLook[row.decision].color" aria-hidden="true">{{ decisionLook[row.decision].icon }}</v-icon>
          <span>{{ annotation ? describe('reference', row.referenceId) : describe('submission', row.studentId) }}: {{ pairDecisionStatusLabels[row.decision] }}<br />
            <span class="text-medium-emphasis">{{ pairDecisionLabels[row.reason] ?? row.reason }}</span></span>
        </li>
      </ul>
    </section>

    <section v-if="evidence && isElement" class="analysis-detail__section" aria-label="Textähnlichkeit">
      <h5 class="analysis-detail__heading">Textähnlichkeit</h5>
      <SimilarityEvidence :evidence="evidence" :submission-id="submissionId" :reference-id="annotation?.referenceId ?? referenceHint?.referenceId" :verdict="textVerdict" />
    </section>

    <section v-if="factGroups.length || otherFactCount" class="analysis-detail__section" aria-label="Prüfungen">
      <h5 class="analysis-detail__heading">Prüfungen</h5>
      <div v-for="group in factGroups" :key="group.title" class="mb-2">
        <div class="font-weight-medium">{{ group.title }} ({{ group.items.length }})</div>
        <ul class="agenda">
          <li v-for="fact in group.items" :key="fact.id ?? fact.code">
            <v-icon size="16" :color="group.color" aria-hidden="true">{{ group.icon }}</v-icon>
            <span>{{ analysisFactLabel(fact.code) }}<br />
              <span class="text-medium-emphasis">{{ analysisFactEvidence(fact) }}</span>
              <template v-if="factOpenReason(fact, graphsComplete)"><br /><span>{{ factOpenReason(fact, graphsComplete) }}</span></template>
            </span>
          </li>
        </ul>
      </div>
      <p v-if="otherFactCount" class="text-medium-emphasis mb-0">{{ otherFactCount }} weitere Prüfungen nicht anwendbar oder nicht ausgewertet.</p>
      <dl v-if="annotation && !annotation.facts && annotation.checks" class="object-details">
        <template v-for="(status, check) in visibleChecks" :key="check"><dt>{{ checkLabels[check] ?? check }}{{ groupCheck(String(check)) ? ' (Gruppe)' : '' }}</dt><dd>{{ analysisValueLabel(status) }}</dd></template>
      </dl>
    </section>

    <section v-if="hasStructure" class="analysis-detail__section" aria-label="Struktur">
      <h5 class="analysis-detail__heading">Struktur</h5>
      <dl v-if="annotation?.owner || annotation?.containment" class="object-details mb-2">
        <template v-if="annotation.owner"><dt>Besitzer Referenz</dt><dd>{{ ownerText('reference', annotation.owner.referenceOwnerId) }}</dd><dt>Besitzer Abgabe</dt><dd>{{ ownerText('submission', annotation.owner.submissionOwnerId) }}</dd></template>
        <template v-if="annotation.containment"><dt>Parents Referenz</dt><dd>{{ parentText('reference', annotation.containment.referenceParents) }}</dd><dt>Parents Abgabe</dt><dd>{{ parentText('submission', annotation.containment.submissionParents) }}</dd></template>
      </dl>
      <div v-if="children" class="mb-2" aria-label="Kinderbefunde">
        <div class="font-weight-medium">{{ children.matched }} / {{ children.expected }} erwartete Kinder korrekt enthalten</div>
        <div v-if="children.moved.length">Erkannt, aber unter anderem Parent: {{ children.moved.map(id => describe('reference', id)).join(', ') }}</div>
        <div v-if="children.absent.length">Nachweisbar nicht realisiert: {{ children.absent.map(id => describe('reference', id)).join(', ') }}</div>
        <div v-if="children.unresolvedReference.length">Erwartet, aber nicht zuordenbar: {{ children.unresolvedReference.map(id => describe('reference', id)).join(', ') }}</div>
        <div v-if="children.unresolvedSubmission.length">Zusätzlich, nicht zuordenbar: {{ children.unresolvedSubmission.map(id => describe('submission', id)).join(', ') }}</div>
        <div v-if="children.foreign.length">Einem anderen Referenzkontext zugeordnet: {{ children.foreign.map(id => describe('submission', id)).join(', ') }}</div>
        <div v-if="children.roleDifferences.length">Abweichende Relationsrolle: {{ children.roleDifferences.map(id => describe('reference', id)).join(', ') }}</div>
      </div>
      <dl v-if="annotation?.connection" class="object-details mb-2">
        <template v-for="side in (['reference', 'submission'] as const)" :key="side">
          <dt>{{ side === 'reference' ? 'Referenzverbindung' : 'Abgabeverbindung' }}</dt>
          <dd v-if="annotation.connection[side]">{{ connectionText(side, annotation.connection[side]!) }}</dd>
          <dd v-else>Kein individuell zugeordnetes Gegenstück</dd>
        </template>
      </dl>
      <p v-if="annotation?.checks?.connectionScope === 'endpoint_group'">Richtung und Verbindungstyp gelten für die Endpunktgruppe und belegen keinen Fehler dieser einzelnen Verbindung.</p>
      <template v-for="(fieldLabel, field) in localFields" :key="field">
        <div v-if="annotation?.local?.[field]" class="mb-2">
          <div class="font-weight-medium">{{ fieldLabel }}</div>
          <dl class="object-details"><template v-for="(label, key) in localLabels" :key="key"><dt>{{ label }}</dt><dd>{{ annotation.local[field]![key] ?? 'nicht bestimmbar' }}</dd></template></dl>
        </div>
      </template>
      <div v-if="annotation?.local?.containmentRelations" class="mb-2">
        <div class="font-weight-medium">Lokale Containment-Prüfung</div>
        <div>{{ annotation.local.containmentRelations.recognized }} / {{ annotation.local.containmentRelations.expected ?? 'unbekannt' }} gestützt · {{ annotation.local.containmentRelations.deviating }} abweichend · {{ annotation.local.containmentRelations.unresolvedReference ?? 'unbekannt' }} ungeklärt</div>
        <div v-for="role in annotation.local.childRoles" :key="role.role ?? 'unknown'">{{ role.role ?? 'Rolle ungeklärt' }}: {{ role.recognized }} / {{ role.expected ?? 'unbekannt' }} gestützt · {{ role.observed }} beobachtet · {{ role.deviating }} abweichend</div>
      </div>
      <div v-for="relation in relations" :key="relation.id" class="mb-2">
        <div class="font-weight-medium">Containment-Beziehung · {{ analysisValueLabel(relation.status) }}</div>
        <div>Referenz: {{ describe('reference', relation.referenceChildId) }} in {{ describe('reference', relation.referenceParentId) }} ({{ relation.referenceRole ?? 'Rolle ungeklärt' }})</div>
        <div>Abgabe: {{ relation.submissionChildId ? describe('submission', relation.submissionChildId) : 'Kind ungeklärt' }} in {{ parentText('submission', relation.observedParents) }}</div>
        <div>Relationsrolle: {{ analysisValueLabel(relation.roleStatus) }}</div>
      </div>
      <div v-for="group in groups" :key="group.id" class="mb-2">
        <div class="font-weight-medium">Verbindungsgruppe (Gruppenaussage)</div>
        <div class="text-medium-emphasis">Gilt für alle Verbindungen zwischen denselben Endpunkten, nicht für jede einzelne.</div>
        <div>Referenz: {{ group.referenceIds.map(id => describe('reference', id)).join(', ') || 'keine' }}</div>
        <div>Abgabe: {{ group.submissionIds.map(id => describe('submission', id)).join(', ') || 'keine' }}</div>
        <ul v-if="group.facts" class="agenda mt-1">
          <li v-for="fact in group.facts" :key="fact.id ?? fact.code"><v-icon size="16" :color="criterionColor(fact.status)" aria-hidden="true">{{ criterionIcon(fact.status) }}</v-icon><span>{{ analysisFactLabel(fact.code) }}: {{ analysisValueLabel(fact.status) }}<br /><span class="text-medium-emphasis">{{ analysisFactEvidence(fact) }}</span></span></li>
        </ul>
        <dl v-else class="object-details"><template v-for="(status, check) in group.checks" :key="check"><dt>{{ checkLabels[check] ?? check }}</dt><dd>{{ analysisValueLabel(status) }}</dd></template></dl>
        <div v-if="group.referenceOnlyCount !== undefined">Ohne Gegenstück in der Gruppe: {{ group.referenceOnlyCount }} Referenz / {{ group.submissionOnlyCount }} Abgabe</div>
      </div>
      <div v-if="relatedHints.length">
        <div class="font-weight-medium">Musterlösungsobjekte, die hier verortet sind</div>
        <ul class="agenda">
          <li v-for="hint in relatedHints" :key="hint.referenceId"><v-icon size="16" :color="analysisDisplay.unresolved.color" aria-hidden="true">mdi-link-variant-off</v-icon><span>{{ hint.label ?? describe('reference', hint.referenceId) }}: {{ analysisHintText(hint) }}</span></li>
        </ul>
      </div>
    </section>

    <details class="analysis-detail__section">
      <summary>Technische Angaben</summary>
      <dl class="object-details mt-2">
        <dt>Original-ID</dt><dd>{{ submissionId ?? referenceHint?.referenceId }}</dd>
        <template v-if="annotation?.referenceId"><dt>Referenz-ID</dt><dd>{{ annotation.referenceId }}</dd></template>
        <template v-if="dependencies.length"><dt>Abhängige Zuordnungen</dt><dd><div v-for="dep in dependencies" :key="dep.submissionId">{{ dep.submissionId }} → {{ dep.referenceId }}</div></dd></template>
      </dl>
      <div v-for="diagnostic in diagnostics" :key="diagnostic.code" class="mt-1">Parser: {{ diagnostic.code }} · {{ diagnostic.message }}</div>
      <ul v-if="hints.length" class="pl-4 mt-1">
        <li v-for="(hint, index) in hints" :key="`${hint.code}:${index}`">{{ hint.code }}: {{ analysisHintText(hint) }}<div class="technical-parameters text-medium-emphasis">{{ analysisHintParameters(hint) }}</div></li>
      </ul>
    </details>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SimilarityEvidence from './SimilarityEvidence.vue'
import {
  analysisChildChecklist, analysisDisplay, analysisFactEvidence, analysisFactLabel, analysisHintParameters, analysisHintText, analysisIdentityLabel,
  analysisIdentityMethodLabel, analysisReasonLabel, analysisStatus, analysisOverviewAppearance, analysisStudentQuestions, analysisValueLabel, checkLabels, exactText, factOpenReason, graphDiagnosticLabel,
  identityCriterionNote, identityExplanation, individualViolations, objectKindLabel, pairDecisionLabels, pairDecisionStatusLabels,
  type AnalysisAnnotation, type AnalysisFeedback, type CandidateEvidence, type ConnectionValue, type GraphDiagnostic, type GraphNode, type LocalCounts, type ParentRelation, type ReferenceHint
} from '@/utils/analysisFeedback'

const props = defineProps<{
  annotation?: AnalysisAnnotation
  referenceHint?: ReferenceHint
  report: AnalysisFeedback
  node?: GraphNode
  evidence: CandidateEvidence | null
  graphsComplete: boolean | null
  diagnostics: GraphDiagnostic[]
  relatedHints: ReferenceHint[]
  targetNote?: string
  overviewMode?: boolean
  describe: (side: 'submission' | 'reference', id: string) => string
}>()

const submissionId = computed(() => props.annotation?.target.id)
const studentQuestions = computed(() => submissionId.value ? analysisStudentQuestions(props.report, submissionId.value) : [])
const kind = computed(() => props.annotation?.target.kind ?? props.referenceHint?.kind ?? null)
const isElement = computed(() => kind.value === 'modelElement')
const title = computed(() => props.annotation ? props.describe('submission', props.annotation.target.id) : props.referenceHint ? `Musterlösung: ${props.referenceHint.label ?? props.describe('reference', props.referenceHint.referenceId)}` : '')
const kindText = computed(() => [objectKindLabel(kind.value), props.node?.type].filter(Boolean).join(' · '))
const display = computed(() => props.annotation ? props.overviewMode ? analysisOverviewAppearance(props.annotation, studentQuestions.value.length > 0) : analysisDisplay[analysisStatus(props.annotation)]
  : props.referenceHint?.code === 'reference.missing' ? analysisDisplay.warning : props.referenceHint?.code === 'reference.not_evaluated' ? analysisDisplay.not_evaluated : analysisDisplay.unresolved)
const statusLabel = computed(() => props.annotation ? display.value.label
  : props.referenceHint?.code === 'reference.missing' ? 'Referenz fehlt' : props.referenceHint?.code === 'reference.not_evaluated' ? 'Nicht ausgewertet' : 'Referenz ohne Gegenstück')
const identity = computed(() => props.annotation?.identity ?? props.referenceHint?.identity)
// Only a mapped annotation's identity describes exactly the shown pair; other identities aggregate all candidates.
const textVerdict = computed(() => props.annotation?.referenceId ? props.annotation.identity?.criteria.find(item => item.method === 'text_similarity') : undefined)
const explanation = computed(() => props.annotation ? identityExplanation(props.annotation) : props.referenceHint ? analysisHintText(props.referenceHint) : null)
const facts = computed(() => (props.annotation?.facts ?? props.referenceHint?.facts ?? []).filter(fact => !fact.code.startsWith('identity.') && !fact.code.startsWith('label.')))
const hints = computed(() => (props.annotation?.hints ?? (props.referenceHint ? [props.referenceHint] : [])).filter(hint => hint.code !== 'label.different'))
// GM-40: how every text candidate of this object ended (identified, partially recognized or open) and why.
const decisionOrder = { identified: 0, partial: 1, open: 2 } as const
const decisions = computed(() => {
  const referenceId = props.annotation ? undefined : props.referenceHint?.referenceId
  return (props.evidence?.decisions ?? []).filter(row => submissionId.value !== undefined ? row.studentId === submissionId.value : row.referenceId === referenceId)
    .sort((a, b) => decisionOrder[a.decision] - decisionOrder[b.decision])
})
const decisionLook = {
  identified: { icon: 'mdi-check', color: analysisDisplay.recognized.color },
  partial: { icon: 'mdi-circle-half-full', color: analysisDisplay.supported.color },
  open: { icon: 'mdi-help', color: analysisDisplay.unresolved.color }
} as const
const visibleChecks = computed(() => Object.fromEntries(Object.entries(props.annotation?.checks ?? {}).filter(([check]) => check !== 'label')))

const criterionIcon = (result: string) => result === 'satisfied' ? 'mdi-check' : result === 'violated' ? 'mdi-close' : result === 'unresolved' ? 'mdi-help' : 'mdi-minus'
const criterionColor = (result: string) => result === 'satisfied' ? analysisDisplay.recognized.color : result === 'violated' ? analysisDisplay.warning.color : result === 'unresolved' ? analysisDisplay.unresolved.color : analysisDisplay.not_evaluated.color
const describePair = (dependency: { referenceId: string; studentId: string }) => `${props.describe('submission', dependency.studentId)} ↔ ${props.describe('reference', dependency.referenceId)}`

const criteriaGroups = computed(() => {
  const criteria = identity.value?.criteria ?? []
  return [
    { title: 'Entscheidend', items: criteria.filter(criterion => criterion.role === 'identity_anchor') },
    { title: 'Spricht dafür', items: criteria.filter(criterion => criterion.role === 'support' && criterion.result === 'satisfied') },
    { title: 'Offen oder nicht erfüllt', items: criteria.filter(criterion => criterion.role === 'support' && criterion.result !== 'satisfied') },
    { title: 'Nur Zulässigkeit', items: criteria.filter(criterion => criterion.role === 'compatibility') }
  ].filter(group => group.items.length)
})
// Exact text ambiguity is the most common reason for an unresolved identity; show the other candidates carrying the same text.
const sameText = computed(() => {
  if (!props.evidence || !isElement.value) return []
  const referenceId = props.annotation?.referenceId ?? props.referenceHint?.referenceId
  return props.evidence.pairs.filter(pair => exactText(pair) && !(pair.submissionId === submissionId.value && pair.referenceId === referenceId) &&
    (submissionId.value !== undefined && pair.submissionId === submissionId.value || referenceId !== undefined && pair.referenceId === referenceId))
})

const factGroups = computed(() => [
  { title: 'Abweichend', icon: 'mdi-close', color: analysisDisplay.warning.color, items: facts.value.filter(fact => fact.status === 'violated') },
  { title: 'Offen', icon: 'mdi-help', color: analysisDisplay.unresolved.color, items: facts.value.filter(fact => fact.status === 'unresolved') },
  { title: 'Erfüllt', icon: 'mdi-check', color: analysisDisplay.recognized.color, items: facts.value.filter(fact => fact.status === 'satisfied') }
].filter(group => group.items.length))
const otherFactCount = computed(() => facts.value.filter(fact => fact.status === 'not_evaluated' || fact.status === 'not_applicable').length)

const agenda = computed(() => {
  const rows: { icon: string; color?: string; text: string }[] = []
  if (props.annotation) {
    rows.push(props.annotation.referenceId
      ? { icon: 'mdi-link-variant', text: `Gegenstück: ${props.describe('reference', props.annotation.referenceId)}` }
      : { icon: 'mdi-link-variant-off', color: analysisDisplay.unresolved.color, text: 'Kein Gegenstück zugeordnet' })
  } else if (props.referenceHint) {
    rows.push({ icon: 'mdi-link-variant-off', color: display.value.color, text: analysisHintText(props.referenceHint) })
  }
  if (identity.value) {
    const status = identity.value.status
    const look = status === 'uniquely_supported' ? analysisDisplay.recognized : status === 'supported' ? analysisDisplay.supported : analysisDisplay.unresolved
    rows.push({ icon: look.icon, color: look.color, text: analysisIdentityLabel(status) })
  }
  for (const fact of props.annotation ? individualViolations(props.annotation) : facts.value.filter(fact => fact.status === 'violated')) {
    rows.push({ icon: 'mdi-close-circle-outline', color: analysisDisplay.warning.color, text: `${analysisFactLabel(fact.code)}: abweichend` })
  }
  const open = facts.value.filter(fact => fact.status === 'unresolved').length
  const satisfied = facts.value.filter(fact => fact.status === 'satisfied').length
  if (open) rows.push({ icon: 'mdi-help-circle-outline', color: analysisDisplay.unresolved.color, text: `${open} ${open === 1 ? 'Prüfung' : 'Prüfungen'} offen` })
  if (satisfied) rows.push({ icon: 'mdi-check', color: analysisDisplay.recognized.color, text: `${satisfied} ${satisfied === 1 ? 'Prüfung' : 'Prüfungen'} erfüllt` })
  for (const diagnostic of props.diagnostics) rows.push({ icon: 'mdi-file-alert-outline', color: analysisDisplay.warning.color, text: `Parser: ${graphDiagnosticLabel(diagnostic)}` })
  return rows
})

const localLabels: Record<keyof LocalCounts, string> = { expected: 'Erwartet', observed: 'In der Abgabe', recognized: 'Vorläufig erkannt', recognizedAtTarget: 'Davon an diesem Ziel', unresolvedReference: 'Referenz ungeklärt', unresolvedSubmission: 'Abgabegegenstück ungeklärt', mappedFromOtherTargets: 'Anderem Kontext zugeordnet', deviating: 'Individuell abweichend', unresolvedChecks: 'Mit ungeklärten Einzelprüfungen' }
const localFields = { children: 'Fachliche Kinder einschließlich Zwischencontainern', directChildren: 'Unmittelbare Kinder', connections: 'Angrenzende Verbindungen', incoming: 'Eingehend', outgoing: 'Ausgehend', undirected: 'Ungerichtet', unresolved: 'Richtung ungeklärt' } as const
const ownerText = (side: 'submission' | 'reference', id: string | null) => id === null ? 'keiner oder ungeklärt' : props.describe(side, id)
const parentText = (side: 'submission' | 'reference', parents: ParentRelation[] | null) => parents === null ? 'nicht ausgewertet'
  : parents.map(parent => `${props.describe(side, parent.parentId)} (${parent.role ?? 'Rolle ungeklärt'})`).join(', ') || 'keine'
const connectionText = (side: 'submission' | 'reference', value: ConnectionValue) =>
  `${value.sourceId ? props.describe(side, value.sourceId) : 'ungeklärt'} → ${value.targetId ? props.describe(side, value.targetId) : 'ungeklärt'} · ${value.directed === null ? 'Richtung ungeklärt' : value.directed ? 'gerichtet' : 'ungerichtet'} · ${value.type ?? 'Typ ungeklärt'}`
const groupCheck = (check: string) => props.annotation?.checks?.connectionScope === 'endpoint_group' && ['direction', 'connectionType'].includes(check)
const children = computed(() => analysisChildChecklist(props.annotation?.facts))
const relations = computed(() => props.report.containmentRelations?.filter(relation => props.annotation?.relationIds?.includes(relation.id)) ?? [])
const groups = computed(() => props.report.connectionGroups?.filter(group => props.annotation?.groupIds?.includes(group.id) || !!submissionId.value && group.submissionEndpointIds.includes(submissionId.value)) ?? [])
const dependencies = computed(() => props.annotation?.dependencies?.map(dep => ({ referenceId: dep.referenceId, submissionId: dep.studentId })) ?? props.annotation?.match?.dependsOn ?? [])
const hasStructure = computed(() => !!(props.annotation?.owner || props.annotation?.containment || children.value || props.annotation?.connection || props.annotation?.local ||
  relations.value.length || groups.value.length || props.relatedHints.length))
</script>

<style scoped>
.analysis-detail__title {
  overflow-wrap: anywhere;
}
.analysis-detail__section {
  padding-block: 8px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.12);
}
.analysis-detail__heading {
  font-size: 0.8125rem;
  font-weight: 600;
  margin-bottom: 6px;
}
.agenda {
  list-style: none;
  padding: 0;
  margin: 0;
}
.agenda > li {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 6px;
  align-items: start;
  padding-block: 2px;
  overflow-wrap: anywhere;
}
.object-details {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
  gap: 4px 8px;
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
}
.technical-parameters {
  overflow-wrap: anywhere;
  font-size: 11px;
}
</style>
