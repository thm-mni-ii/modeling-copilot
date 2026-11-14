import type { EvaluationDetail } from '@/services/api/types/evaluation'

export const analysisCategories = ['nodes', 'attributes', 'connections', 'other'] as const
export type AnalysisCategory = typeof analysisCategories[number]
export type ObjectKind = 'modelElement' | 'structuralElement' | 'connection' | 'connectionLabel' | null
export interface AnalysisTarget { side: 'submission'; kind: ObjectKind | 'model'; id: string }
export interface AnalysisHint { code: string; [parameter: string]: unknown }
export interface LocalCounts {
  expected: number | null; observed: number; recognized: number | null; recognizedAtTarget: number | null
  unresolvedReference: number | null; unresolvedSubmission: number; mappedFromOtherTargets: number | null
}
export interface AnalysisAnnotation {
  target: AnalysisTarget
  referenceId?: string
  match: { status: 'provisional' | 'unresolved' | 'not_evaluated'; reason?: string; dependsOn?: { referenceId: string; submissionId: string }[] }
  context?: { referenceId: string; basis: string; status: string }
  checks: Record<string, string>
  hints: AnalysisHint[]
  local?: { children?: LocalCounts; connections?: LocalCounts }
}
export interface RecognitionCount { recognized: number | null; expected: number | null; percent: number | null; evaluationStatus: string }
export interface ReferenceHint extends AnalysisHint { target: AnalysisTarget; referenceId: string; kind: ObjectKind; label?: string }
export interface AnalysisFeedback {
  schema: 'analysis-feedback/v1'; evaluationId: string; pair: { studentKey: 'submission'; referenceKey: string }
  status: 'provisional'; assessmentAvailable: false
  comparisonHash: string; analysisKey: string; analysisHash: string
  summary: Record<AnalysisCategory, RecognitionCount>; annotations: AnalysisAnnotation[]; referenceHints: ReferenceHint[]
}
export interface AnalysisObject { id: string; kind: ObjectKind; label?: string }
export interface AnalysisContext {
  evaluationId: string; referenceKey: string; modelId: string
  submissionObjects: AnalysisObject[]; referenceObjects: AnalysisObject[]
}
export interface AdaptedAnalysis { report: AnalysisFeedback; annotations: Map<ObjectKind, Map<string, AnalysisAnnotation>> }

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const id = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
const count = (value: unknown) => Number.isInteger(value) && (value as number) >= 0
const hash = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
function requireValue(condition: unknown): asserts condition {
  if (!condition) throw new Error('Analytisches Feedback ist unvollständig oder gehört nicht zu dieser Auswertung.')
}
const kinds: ObjectKind[] = ['modelElement', 'structuralElement', 'connection', 'connectionLabel', null]

/** The detail API unwraps workflow-result/v1; raw saved stdout envelopes are accepted as well. */
export function adaptAnalysisFeedback(value: unknown, context: AnalysisContext): AdaptedAnalysis {
  requireValue(object(value))
  if (value.schema === 'workflow-result/v1') {
    requireValue(value.schemaVersion === 1 && value.status === 'ok' && value.capability === 'analytical-feedback')
    requireValue(object(value.result) && value.analysisKey === value.result.analysisKey)
    value = value.result
  }
  requireValue(object(value) && value.schema === 'analysis-feedback/v1' && value.status === 'provisional' && value.assessmentAvailable === false)
  requireValue(value.evaluationId === context.evaluationId && object(value.pair) && value.pair.studentKey === 'submission' && value.pair.referenceKey === context.referenceKey)
  requireValue(hash(value.comparisonHash) && hash(value.analysisKey) && hash(value.analysisHash))
  requireValue(Array.isArray(value.annotations) && Array.isArray(value.referenceHints) && object(value.summary))
  const submission = new Map(context.submissionObjects.map(item => [item.id, item]))
  const reference = new Map(context.referenceObjects.map(item => [item.id, item]))
  requireValue(submission.size === context.submissionObjects.length && reference.size === context.referenceObjects.length)
  requireValue([...submission.values(), ...reference.values()].every(item => id(item.id) && kinds.includes(item.kind)))
  const validTarget = (target: unknown, allowModel = false): target is AnalysisTarget => object(target) && target.side === 'submission' && id(target.id) &&
    (allowModel && target.kind === 'model' ? target.id === context.modelId : submission.has(target.id) && submission.get(target.id)!.kind === target.kind)
  const validHintParameters = (hint: Record<string, unknown>) => {
    for (const [prefix, catalog] of [['reference', reference], ['submission', submission]] as const) {
      for (const field of [`${prefix}Id`, `${prefix}OwnerId`, `${prefix}ParentId`]) {
        if (hint[field] !== undefined && hint[field] !== null && (!id(hint[field]) || !catalog.has(hint[field] as string))) return false
      }
      for (const field of [`${prefix}Ids`, `${prefix}ParentIds`]) {
        if (hint[field] !== undefined && (!Array.isArray(hint[field]) || !(hint[field] as unknown[]).every(value => id(value) && catalog.has(value)))) return false
      }
    }
    return true
  }
  const validHints = (hints: unknown) => Array.isArray(hints) && hints.every(hint => object(hint) && id(hint.code) && validHintParameters(hint))
  const annotations = new Map<ObjectKind, Map<string, AnalysisAnnotation>>()
  const seen = new Set<string>()
  const matchedReferences = new Set<string>()
  for (const item of value.annotations) {
    requireValue(object(item) && validTarget(item.target) && kinds.includes(item.target.kind as ObjectKind) && !seen.has(item.target.id))
    requireValue(object(item.match) && ['provisional', 'unresolved', 'not_evaluated'].includes(String(item.match.status)))
    requireValue((item.match.status === 'provisional') === (item.referenceId !== undefined))
    if (item.referenceId !== undefined) {
      requireValue(id(item.referenceId) && reference.get(item.referenceId)?.kind === item.target.kind && !matchedReferences.has(item.referenceId))
      matchedReferences.add(item.referenceId)
    }
    requireValue(item.match.reason === undefined || id(item.match.reason))
    if (item.match.dependsOn !== undefined) requireValue(Array.isArray(item.match.dependsOn) && item.match.dependsOn.every(dep =>
      object(dep) && id(dep.submissionId) && submission.has(dep.submissionId) && id(dep.referenceId) && reference.has(dep.referenceId)))
    requireValue(object(item.checks) && Object.values(item.checks).every(id) && validHints(item.hints))
    if (item.context !== undefined) requireValue(object(item.context) && id(item.context.referenceId) && reference.has(item.context.referenceId) &&
      item.context.basis === 'structural_child_of_mapped_parent' && item.context.status === 'derived_context')
    if (item.local !== undefined) {
      requireValue(object(item.local))
      for (const key of ['children', 'connections']) {
        const local = item.local[key]
        if (local === undefined) continue
        requireValue(object(local) && count(local.observed) && count(local.unresolvedSubmission))
        for (const field of ['expected', 'recognized', 'recognizedAtTarget', 'unresolvedReference', 'mappedFromOtherTargets']) requireValue(local[field] === null || count(local[field]))
      }
    }
    seen.add(item.target.id)
    const kind = item.target.kind as ObjectKind
    if (!annotations.has(kind)) annotations.set(kind, new Map())
    annotations.get(kind)!.set(item.target.id, item as unknown as AnalysisAnnotation)
  }
  requireValue(seen.size === submission.size)
  for (const item of value.annotations as unknown as AnalysisAnnotation[]) {
    for (const dep of item.match.dependsOn ?? []) requireValue(value.annotations.some((candidate: unknown) =>
      object(candidate) && object(candidate.target) && candidate.target.id === dep.submissionId && candidate.referenceId === dep.referenceId))
  }
  const referenceHints = new Set<string>()
  for (const hint of value.referenceHints) {
    requireValue(object(hint) && validTarget(hint.target, true) && id(hint.code) && id(hint.referenceId) && reference.has(hint.referenceId) &&
      reference.get(hint.referenceId)!.kind === hint.kind && !matchedReferences.has(hint.referenceId) && !referenceHints.has(hint.referenceId))
    requireValue(hint.label === undefined || typeof hint.label === 'string')
    referenceHints.add(hint.referenceId)
  }
  requireValue([...reference.values()].filter(item => ['modelElement', 'connection'].includes(item.kind ?? '') && !matchedReferences.has(item.id)).every(item => referenceHints.has(item.id)))
  const summary = {} as Record<AnalysisCategory, RecognitionCount>
  for (const category of analysisCategories) {
    const row = value.summary[category]
    if (row === undefined) {
      summary[category] = { recognized: null, expected: null, percent: null, evaluationStatus: 'not_evaluated' }
      continue
    }
    requireValue(object(row) && count(row.recognized) && count(row.expected) && (row.recognized as number) <= (row.expected as number) && id(row.evaluationStatus))
    requireValue(row.percent === null || typeof row.percent === 'number' && Number.isFinite(row.percent) && row.percent >= 0 && row.percent <= 100 &&
      (row.expected as number) > 0 && Math.abs(row.percent - 100 * (row.recognized as number) / (row.expected as number)) < 0.001)
    requireValue(!['not_applicable', 'not_evaluated'].includes(row.evaluationStatus) || row.percent === null)
    summary[category] = row as unknown as RecognitionCount
  }
  return { report: { ...value, summary } as unknown as AnalysisFeedback, annotations }
}

export function analysisFromEvaluation(detail: EvaluationDetail, referenceKey: string): AdaptedAnalysis {
  const graphs = detail.steps.map(step => step.result).filter(result => result?.schema === 'graph-result/v1')
  const objects = (key: string): AnalysisObject[] => {
    const matches = graphs.filter(result => object(result?.source) && result.source.key === key)
    requireValue(matches.length === 1 && matches[0]?.evaluationId === detail.id && object(matches[0]?.graph) && Array.isArray(matches[0].graph.nodes))
    if (key === 'submission') requireValue(object(matches[0].source) && matches[0].source.modelId === detail.submission.modelId && matches[0].source.versionId === detail.submission.versionId)
    const nodes = matches[0].graph.nodes
    requireValue(nodes.every(node => object(node) && id(node.id) && kinds.includes(node.kind as ObjectKind)))
    return nodes as AnalysisObject[]
  }
  const step = detail.steps.find(step => step.id === `generate_analytical_feedback_${referenceKey}`)
  requireValue(step?.status === 'succeeded')
  const comparison = detail.steps.find(step => step.id === `match_graph_${referenceKey}`)?.result
  requireValue(comparison?.schema === 'reference-comparison/v1' && comparison.evaluationId === detail.id && object(comparison.pair) &&
    comparison.pair.studentKey === 'submission' && comparison.pair.referenceKey === referenceKey && object(comparison.mapping))
  requireValue(Array.isArray(comparison.mapping.provisionalElements) && Array.isArray(comparison.mapping.provisionalConnections))
  const adapted = adaptAnalysisFeedback(step.result, { evaluationId: detail.id, referenceKey, modelId: detail.submission.modelId,
    submissionObjects: objects('submission'), referenceObjects: objects(referenceKey) })
  requireValue(adapted.report.comparisonHash === comparison.comparisonHash)
  const pairs = new Map<string, string>()
  const referenceIds = new Set<string>()
  for (const pair of [...comparison.mapping.provisionalElements, ...comparison.mapping.provisionalConnections]) {
    requireValue(object(pair) && id(pair.studentId) && id(pair.referenceId) && !pairs.has(pair.studentId) && !referenceIds.has(pair.referenceId))
    pairs.set(pair.studentId, pair.referenceId)
    referenceIds.add(pair.referenceId)
  }
  requireValue(adapted.report.annotations.every(item => pairs.get(item.target.id) === item.referenceId) &&
    adapted.report.annotations.filter(item => item.referenceId !== undefined).length === pairs.size)
  return adapted
}

export type DisplayStatus = 'recognized' | 'warning' | 'unresolved' | 'not_evaluated'
export const analysisStatus = (item: AnalysisAnnotation): DisplayStatus => {
  // Group direction/type findings never prove an individual connection error.
  const individualDifference = Object.entries(item.checks).some(([check, status]) =>
    ['owner', 'containment', 'endpoints', 'direction', 'connectionType'].includes(check) && ['violated', 'different'].includes(status) &&
    !(item.checks.connectionScope === 'endpoint_group' && ['direction', 'connectionType'].includes(check)))
  if (individualDifference || item.hints.some(hint => ['owner.violated', 'owner.different', 'containment.violated', 'connection.endpoints_different'].includes(hint.code))) return 'warning'
  const groupDifference = item.checks.connectionScope === 'endpoint_group' && [item.checks.direction, item.checks.connectionType].includes('different')
  if (item.match.status === 'unresolved' || Object.values(item.checks).includes('unresolved') || groupDifference || item.hints.some(hint =>
    ['identity.unresolved', 'identity.ambiguous', 'owner.unresolved', 'connection.group_difference'].includes(hint.code) ||
    /^(children|connections)\.(unresolved_reference|unresolved_submission|outside_target|mapped_from_other_target)$/.test(hint.code))) return 'unresolved'
  return item.match.status === 'provisional' ? 'recognized' : 'not_evaluated'
}
export const analysisDisplay = {
  recognized: { icon: 'mdi-check', color: '#607D8B', label: 'Vorläufig erkannt, keine festgestellte strukturelle Abweichung' },
  warning: { icon: 'mdi-alert-outline', color: '#B26A00', label: 'Strukturelle Abweichung festgestellt' },
  unresolved: { icon: 'mdi-help-circle-outline', color: '#546E7A', label: 'Ungeklärt oder mehrdeutig' },
  not_evaluated: { icon: 'mdi-information-outline', color: '#757575', label: 'Nicht ausgewertet' }
} as const
export const categoryLabels: Record<AnalysisCategory, string> = { nodes: 'Knoten', attributes: 'Attribute', connections: 'Verbindungen', other: 'Sonstige' }
export const checkLabels: Record<string, string> = { label: 'Beschriftung', type: 'Konkreter Typ', owner: 'Besitzer', containment: 'Containment', endpoints: 'Endpunkte', direction: 'Richtung', connectionType: 'Verbindungstyp', connectionScope: 'Prüfumfang' }
export const analysisValueLabel = (value: string) => ({ provisional: 'Vorläufig', unresolved: 'Ungeklärt', not_evaluated: 'Nicht ausgewertet', not_applicable: 'Nicht anwendbar', partial: 'Teilweise ausgewertet', exact: 'Gleich', equal: 'Gleich', different: 'Abweichend', same_type: 'Gleicher Typ', compatible_type_difference: 'Anderer Typ innerhalb der Vergleichsgruppe', satisfied: 'Konsistent', violated: 'Verletzt', endpoint_group: 'Verbindungsgruppe', derived_context: 'Abgeleiteter Strukturkontext' })[value] ?? value
export const analysisReasonLabel = (reason: string) => ({ unique_exact_label: 'Eindeutige gleiche Beschriftung', unique_exact_after_reservations: 'Eindeutige gleiche Beschriftung nach bestehenden Zuordnungen', consistent_owner_anchor: 'Konsistenter zugeordneter Besitzer', independent_child_evidence: 'Unabhängige Evidenz enthaltener Elemente', supported_semantic_evidence: 'Semantisch gestützte Zuordnung', compatible_type_and_mapped_endpoints: 'Kompatibler Typ und zugeordnete Endpunkte', structural_child_of_mapped_parent: 'Kind eines zugeordneten Parents' })[reason] ?? `Zuordnungsregel: ${reason}`
const hintTexts: Record<string, string> = {
  'identity.unresolved': 'Identität ungeklärt; nicht als zusätzlich bestätigt.', 'identity.ambiguous': 'Mehrere Zuordnungskandidaten.',
  'label.different': 'Die Beschriftung weicht ab.', 'type.compatible_difference': 'Der konkrete Typ weicht innerhalb der Vergleichsgruppe ab; kein bestätigter fachlicher Fehler.',
  'owner.violated': 'Das Element ist einem anderen Besitzer zugeordnet.', 'owner.different': 'Der Besitzer weicht ab.', 'owner.unresolved': 'Der Besitzer ist ungeklärt.',
  'containment.violated': 'Die Zugehörigkeit zum Container ist verletzt.', 'connection.endpoints_different': 'Die Endpunkte weichen ab.',
  'connection.group_difference': 'Befund an der Verbindungsgruppe; kein individuell bewiesener Fehler dieser Verbindung.',
  'reference.unresolved': 'Referenzobjekt nicht identifiziert; nicht als fehlend bestätigt.'
}
for (const [prefix, label] of [['children', 'Enthaltene Elemente'], ['connections', 'Angrenzende Verbindungen']]) {
  hintTexts[`${prefix}.unresolved_reference`] = `${label}: Referenzobjekte noch ungeklärt.`
  hintTexts[`${prefix}.unresolved_submission`] = `${label}: Abgabeobjekte noch ungeklärt; nicht als zusätzlich bestätigt.`
  hintTexts[`${prefix}.mapped_from_other_target`] = `${label}: Objekte sind vorläufig einem anderen Referenzkontext zugeordnet.`
  hintTexts[`${prefix}.outside_target`] = `${label}: Erkannte Objekte befinden sich außerhalb dieses Ziels; Zuordnung bleibt ungeklärt.`
}
export const analysisHintText = (hint: AnalysisHint) => Object.prototype.hasOwnProperty.call(hintTexts, hint.code) ? hintTexts[hint.code] : `Technischer Hinweis: ${hint.code}`
export const analysisHintParameters = (hint: AnalysisHint) => JSON.stringify(Object.fromEntries(Object.entries(hint).filter(([key]) => !['code', 'target'].includes(key))))
