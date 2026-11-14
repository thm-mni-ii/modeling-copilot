import type { EvaluationDetail } from '@/services/api/types/evaluation'

export const analysisCategories = ['nodes', 'attributes', 'connections', 'other'] as const
export type AnalysisCategory = typeof analysisCategories[number]
export type ObjectKind = 'modelElement' | 'structuralElement' | 'connection' | 'connectionLabel' | null
export interface AnalysisTarget { side: 'submission'; kind: ObjectKind | 'model'; id: string }
export type AnalysisStatus = 'provisional' | 'different' | 'ambiguous' | 'unresolved' | 'not_evaluated' | 'not_applicable'
export interface ObjectReference { side: 'submission' | 'reference'; kind: ObjectKind | 'model'; id: string }
export interface AnalysisHint { code: string; status?: AnalysisStatus; scope?: 'element' | 'relation' | 'group' | 'model'; parameters?: Record<string, unknown>; targets?: ObjectReference[]; [parameter: string]: unknown }
export interface AnalysisFact {
  id?: string; targets?: ObjectReference[]
  code: string; status: 'satisfied' | 'violated' | 'unresolved' | 'not_evaluated' | 'not_applicable'
  referenceIds: string[]; submissionIds: string[]
  evidence: { basis: 'direct_observation' | 'conditional_mapping' | 'independent_evidence'; reason: string; [key: string]: unknown }
}
export interface IdentityCriterion {
  method: string; role: 'compatibility' | 'support' | 'identity_anchor'; result: AnalysisFact['status']
  referenceIds: string[]; submissionIds: string[]; dependsOn: { referenceId: string; studentId: string }[]
  matched?: number; expected?: number; observed?: number; complete?: boolean
}
export interface AnalysisIdentity { status: 'uniquely_supported' | 'supported' | 'unresolved'; criteria: IdentityCriterion[]; supportingCandidateCount: number }
export interface LocalCounts {
  expected: number | null; observed: number; recognized: number | null; recognizedAtTarget: number | null
  unresolvedReference: number | null; unresolvedSubmission: number; mappedFromOtherTargets: number | null
  deviating?: number
  unresolvedChecks?: number
}
export interface ParentRelation { parentId: string; role: string | null }
export interface ConnectionValue { id: string; sourceId: string | null; targetId: string | null; directed: boolean | null; type: string | null }
export interface RelationCounts { expected: number | null; observed: number; recognized: number; deviating: number; unresolvedReference: number | null; evaluationStatus?: string }
export interface AnalysisAnnotation {
  target: AnalysisTarget
  referenceId?: string
  status?: AnalysisStatus
  category?: AnalysisCategory | null
  match: { status: 'provisional' | 'unresolved' | 'not_evaluated'; reason?: string; dependsOn?: { referenceId: string; submissionId: string }[] }
  context?: { referenceId: string; basis: string; status: string }
  checks: Record<string, string>
  hints: AnalysisHint[]
  facts?: AnalysisFact[]
  identity?: AnalysisIdentity
  consistency?: 'fully_consistent' | 'partial' | 'different' | 'unresolved' | 'not_evaluated'
  owner?: { referenceOwnerId: string | null; submissionOwnerId: string | null; status: string }
  containment?: { referenceParents: ParentRelation[] | null; submissionParents: ParentRelation[] }
  connection?: { reference: ConnectionValue | null; submission: ConnectionValue }
  groupIds?: string[]
  relationIds?: string[]
  local?: Partial<Record<'children' | 'directChildren' | 'connections' | 'incoming' | 'outgoing' | 'undirected' | 'unresolved', LocalCounts>> & {
    containmentRelations?: RelationCounts; childRoles?: (RelationCounts & { role: string | null })[]
  }
}
export interface ConnectionGroup { id: string; status: AnalysisStatus; referenceIds: string[]; submissionIds: string[]; referenceEndpointIds: string[]; submissionEndpointIds: string[]; checks: Record<string, string>; referenceOnlyCount: number; submissionOnlyCount: number; hints: AnalysisHint[] }
export interface ContainmentRelation { id: string; status: AnalysisStatus; scope: 'relation'; referenceChildId: string; referenceParentId: string; referenceRole: string | null; submissionChildId: string | null; submissionParentId: string | null; observedParents: ParentRelation[]; roleStatus: string; basis: string }
export interface RecognitionCount { recognized: number | null; expected: number | null; percent: number | null; evaluationStatus: string }
export interface ReferenceHint extends AnalysisHint { target: AnalysisTarget; referenceId: string; kind: ObjectKind; label?: string; facts?: AnalysisFact[] }
export interface AnalysisFeedback {
  schema: 'analysis-feedback/v1'; evaluationId: string; pair: { studentKey: 'submission'; referenceKey: string }
  contractVersion?: '1.1' | '1.2' | '1.3'
  status: 'provisional'; assessmentAvailable: false
  comparisonHash: string; analysisKey: string; analysisHash: string
  summary: Record<AnalysisCategory, RecognitionCount>; annotations: AnalysisAnnotation[]; referenceHints: ReferenceHint[]
  structuralContainers?: { referenceCount: number; submissionCount: number; contextCount: number; evaluationStatus: 'not_evaluated' }
  connectionGroups?: ConnectionGroup[]
  containmentRelations?: ContainmentRelation[]
  limitations?: AnalysisHint[]
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
const statuses: AnalysisStatus[] = ['provisional', 'different', 'ambiguous', 'unresolved', 'not_evaluated', 'not_applicable']

/** The detail API unwraps workflow-result/v1; raw saved stdout envelopes are accepted as well. */
export function adaptAnalysisFeedback(value: unknown, context: AnalysisContext): AdaptedAnalysis {
  requireValue(object(value))
  if (value.schema === 'workflow-result/v1') {
    requireValue(value.schemaVersion === 1 && value.status === 'ok' && value.capability === 'analytical-feedback')
    requireValue(object(value.result) && value.analysisKey === value.result.analysisKey)
    value = value.result
  }
  requireValue(object(value) && value.schema === 'analysis-feedback/v1' && value.status === 'provisional' && value.assessmentAvailable === false)
  requireValue(value.contractVersion === undefined || ['1.1', '1.2', '1.3'].includes(String(value.contractVersion)))
  const structured = value.contractVersion !== undefined
  const factual = ['1.2', '1.3'].includes(String(value.contractVersion))
  const identityAware = value.contractVersion === '1.3'
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
  const validReference = (target: unknown) => object(target) && id(target.id) && (target.side === 'submission' ? validTarget(target, true) :
    target.side === 'reference' && reference.has(target.id) && reference.get(target.id)!.kind === target.kind)
  const validFacts = (facts: unknown) => Array.isArray(facts) && facts.every(fact => object(fact) && id(fact.code) &&
    ['satisfied', 'violated', 'unresolved', 'not_evaluated', 'not_applicable'].includes(String(fact.status)) &&
    Array.isArray(fact.referenceIds) && fact.referenceIds.every(identity => id(identity) && reference.has(identity)) &&
    Array.isArray(fact.submissionIds) && fact.submissionIds.every(identity => id(identity) && submission.has(identity)) &&
    object(fact.evidence) && ['direct_observation', 'conditional_mapping', 'independent_evidence'].includes(String(fact.evidence.basis)) && id(fact.evidence.reason) &&
    (!identityAware || hash(fact.id) && Array.isArray(fact.targets) && fact.targets.every(validReference)))
  const validIdentity = (identity: unknown) => object(identity) && ['uniquely_supported', 'supported', 'unresolved'].includes(String(identity.status)) &&
    count(identity.supportingCandidateCount) && Array.isArray(identity.criteria) && identity.criteria.every(criterion => object(criterion) && id(criterion.method) &&
      ['compatibility', 'support', 'identity_anchor'].includes(String(criterion.role)) && ['satisfied', 'violated', 'unresolved', 'not_evaluated', 'not_applicable'].includes(String(criterion.result)) &&
      Array.isArray(criterion.referenceIds) && criterion.referenceIds.every(identity => id(identity) && reference.has(identity)) &&
      Array.isArray(criterion.submissionIds) && criterion.submissionIds.every(identity => id(identity) && submission.has(identity)) &&
      Array.isArray(criterion.dependsOn) && criterion.dependsOn.every(dep => object(dep) && id(dep.referenceId) && reference.has(dep.referenceId) && id(dep.studentId) && submission.has(dep.studentId)))
  const validHints = (hints: unknown) => Array.isArray(hints) && hints.every(hint => object(hint) && id(hint.code) && validHintParameters(hint) &&
    (!structured || statuses.includes(hint.status as AnalysisStatus) && ['element', 'relation', 'group', 'model'].includes(String(hint.scope)) &&
      object(hint.parameters) && validHintParameters(hint.parameters) && Array.isArray(hint.targets) && hint.targets.every(validReference)))
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
    if (factual) {
      requireValue(validFacts(item.facts) && ['fully_consistent', 'partial', 'different', 'unresolved', 'not_evaluated'].includes(String(item.consistency)))
      if (item.consistency === 'fully_consistent') requireValue(item.match.status === 'provisional' &&
        (item.facts as AnalysisFact[]).some(fact => fact.status === 'satisfied') &&
        (item.facts as AnalysisFact[]).every(fact => ['satisfied', 'not_applicable'].includes(fact.status)))
    }
    if (identityAware && ['modelElement', 'connection'].includes(String(item.target.kind))) {
      requireValue(validIdentity(item.identity))
      const identityFact = (item.facts as AnalysisFact[]).find(fact => fact.code.startsWith('identity.'))
      requireValue(identityFact && object(item.identity) && item.identity.status === identityFact.evidence.identityStatus &&
        JSON.stringify(item.identity.criteria) === JSON.stringify(identityFact.evidence.criteria))
      if (item.consistency === 'fully_consistent') requireValue(item.identity.status === 'uniquely_supported')
    }
    if (structured) {
      requireValue(statuses.includes(item.status as AnalysisStatus) && (item.category === null || analysisCategories.includes(item.category as AnalysisCategory)))
      requireValue(object(item.owner) && object(item.containment))
      for (const [side, catalog] of [['reference', reference], ['submission', submission]] as const) {
        const owner = item.owner[`${side}OwnerId`]
        requireValue(owner === null || id(owner) && catalog.has(owner))
        const parents = item.containment[`${side}Parents`]
        requireValue(side === 'reference' && parents === null || Array.isArray(parents) && parents.every(parent =>
          object(parent) && id(parent.parentId) && catalog.has(parent.parentId) && (parent.role === null || typeof parent.role === 'string')))
        if (item.connection !== undefined) {
          requireValue(object(item.connection))
          const descriptor = item.connection[side]
          if (side === 'reference' && descriptor === null) continue
          requireValue(object(descriptor) && id(descriptor.id) && catalog.get(descriptor.id)?.kind === 'connection')
          requireValue(['sourceId', 'targetId'].every(key => descriptor[key] === null || id(descriptor[key]) && catalog.has(descriptor[key] as string)))
          requireValue(descriptor.directed === null || typeof descriptor.directed === 'boolean')
          requireValue(descriptor.type === null || typeof descriptor.type === 'string')
        }
      }
    }
    if (item.context !== undefined) requireValue(object(item.context) && id(item.context.referenceId) && reference.has(item.context.referenceId) &&
      item.context.basis === 'structural_child_of_mapped_parent' && item.context.status === 'derived_context')
    if (item.local !== undefined) {
      requireValue(object(item.local))
      for (const key of ['children', 'connections', 'directChildren', 'incoming', 'outgoing', 'undirected', 'unresolved']) {
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
    requireValue(validHints([hint]))
    if (factual) requireValue(validFacts(hint.facts))
    referenceHints.add(hint.referenceId)
  }
  requireValue([...reference.values()].filter(item => ['modelElement', 'connection'].includes(item.kind ?? '') && !matchedReferences.has(item.id)).every(item => referenceHints.has(item.id)))
  if (structured) {
    requireValue([...reference.keys()].filter(id => !matchedReferences.has(id)).every(id => referenceHints.has(id)))
    requireValue(Array.isArray(value.connectionGroups) && Array.isArray(value.containmentRelations) && object(value.structuralContainers))
    const containers = value.structuralContainers
    requireValue(['referenceCount', 'submissionCount', 'contextCount'].every(key => count(containers[key])))
    const groupIds = new Set<string>(), relationIds = new Set<string>()
    requireValue(validHints(value.limitations))
    for (const group of value.connectionGroups) {
      if (factual) requireValue(object(group) && validFacts(group.facts))
      requireValue(object(group) && hash(group.id) && !groupIds.has(group.id as string) && statuses.includes(group.status as AnalysisStatus) && validHints(group.hints))
      for (const [side, catalog] of [['reference', reference], ['submission', submission]] as const) {
        requireValue(Array.isArray(group[`${side}Ids`]) && (group[`${side}Ids`] as unknown[]).every(id => typeof id === 'string' && catalog.get(id)?.kind === 'connection'))
        requireValue(Array.isArray(group[`${side}EndpointIds`]) && (group[`${side}EndpointIds`] as unknown[]).every(id => typeof id === 'string' && catalog.has(id)))
      }
      requireValue(object(group.checks) && Object.values(group.checks).every(status => ['equal', 'different', 'not_evaluated'].includes(String(status))) && count(group.referenceOnlyCount) && count(group.submissionOnlyCount))
      groupIds.add(group.id as string)
    }
    for (const relation of value.containmentRelations) {
      requireValue(object(relation) && hash(relation.id) && !relationIds.has(relation.id as string) && statuses.includes(relation.status as AnalysisStatus) && relation.scope === 'relation')
      for (const [side, catalog] of [['reference', reference], ['submission', submission]] as const) {
        for (const key of ['ChildId', 'ParentId']) requireValue(side === 'submission' && relation[side + key] === null || id(relation[side + key]) && catalog.has(relation[side + key] as string))
      }
      requireValue(Array.isArray(relation.observedParents) && relation.observedParents.every(parent => object(parent) && id(parent.parentId) && submission.has(parent.parentId)))
      relationIds.add(relation.id as string)
    }
    for (const item of value.annotations) {
      requireValue((item.groupIds === undefined || Array.isArray(item.groupIds) && item.groupIds.every((id: unknown) => typeof id === 'string' && groupIds.has(id))) &&
        (item.relationIds === undefined || Array.isArray(item.relationIds) && item.relationIds.every((id: unknown) => typeof id === 'string' && relationIds.has(id))))
    }
  }
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
  if (item.status) return ({ provisional: 'recognized', different: 'warning', ambiguous: 'unresolved', unresolved: 'unresolved', not_evaluated: 'not_evaluated', not_applicable: 'not_evaluated' } as const)[item.status] ?? 'not_evaluated'
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
export const checkLabels: Record<string, string> = { label: 'Beschriftung', type: 'Konkreter Typ', owner: 'Besitzer', containment: 'Containment', source: 'Source', target: 'Target', endpoints: 'Endpunkte', direction: 'Richtung', connectionType: 'Verbindungstyp', connectionScope: 'Prüfumfang', configuration: 'Konfiguration', counterpart: 'Gegenstück', children: 'Fachliche Kinder', direct_children: 'Unmittelbare Kinder', directChildren: 'Unmittelbare Kinder', connections: 'Angrenzende Verbindungen', incoming: 'Eingehende Verbindungen', outgoing: 'Ausgehende Verbindungen', undirected: 'Ungerichtete Verbindungen', connection_group: 'Verbindungsgruppe' }
export const analysisValueLabel = (value: string) => ({ provisional: 'Vorläufig', ambiguous: 'Mehrdeutig', unresolved: 'Ungeklärt', not_evaluated: 'Nicht ausgewertet', not_applicable: 'Nicht anwendbar', partial: 'Teilweise ausgewertet', exact: 'Gleich', equal: 'Gleich', different: 'Abweichend', same_type: 'Gleicher Typ', compatible_type_difference: 'Anderer Typ innerhalb der Vergleichsgruppe', satisfied: 'Erfüllt', violated: 'Verletzt', endpoint_group: 'Verbindungsgruppe', derived_context: 'Abgeleiteter Strukturkontext', fully_consistent: 'Implementierte lokale Prüfungen vollständig erfüllt (unter vorläufiger Zuordnung)', direct_observation: 'Direkt beobachtet', conditional_mapping: 'Unter vorläufiger Zuordnung', independent_evidence: 'Unabhängig gestützt' })[value] ?? value
export const analysisFactLabel = (code: string) => {
  const [prefix, dimension] = code.split('.')
  if (prefix === 'identity') return 'Identität'
  if (prefix === 'connection') return checkLabels[dimension] ?? dimension
  if (prefix === 'connection_group') return `Verbindungsgruppe: ${checkLabels[dimension] ?? (dimension === 'minimum_missing' ? 'Mindestfehlmenge' : dimension)}`
  return checkLabels[prefix] ?? code
}
export const analysisIdentityLabel = (status: string) => ({ uniquely_supported: 'Eindeutig erkannt', supported: 'Identität gestützt; Eindeutigkeit offen', unresolved: 'Identität ungeklärt' })[status] ?? status
export const analysisIdentityMethodLabel = (method: string) => ({ exact_label: 'Exakte Beschriftung', type_compatibility: 'Typkompatibilität', independent_children: 'Unabhängig erkannte Kinder', combined_children: 'Gemeinsame Kinderstruktur', identified_owner: 'Unabhängig erkannter Besitzer', connection_structure: 'Verbindungsstruktur', semantic_proposal: 'Vorhandene semantische Evidenz' })[method] ?? method
export const analysisIdentityRoleLabel = (role: string) => ({ compatibility: 'Vergleich zulässig', support: 'Positive Evidenz', identity_anchor: 'Identitätsanker nach Konkurrenzprüfung' })[role] ?? role
export const analysisPlacementLabel = (status: unknown) => typeof status === 'string' ? ({ correct_placement: 'Korrekt platziert', wrong_placement: 'Falsch platziert', placement_unresolved: 'Platzierung ungeklärt', unmatched_submission: 'Abgabegegenstück nicht zugeordnet', unmatched_reference: 'Referenzgegenstück nicht zugeordnet', proven_absent: 'Abwesenheit nachgewiesen' })[status] ?? status : ''
export const analysisFactEvidence = (fact: AnalysisFact) => {
  const evidence = fact.evidence
  const reasons: Record<string, string> = {
    evaluated_identity_evidence: 'Identität anhand der ausgewiesenen Evidenzmethoden geprüft',
    compared_labels: 'Beschriftungen verglichen', compared_concrete_types: 'Konkrete Typen verglichen',
    compared_owner: 'Fachliche Besitzer verglichen', compared_containment: 'Unmittelbare Container und Rollen verglichen',
    local_children_under_mapping: 'Lokale Kindstruktur geprüft', local_connections_under_mapping: 'Lokale Verbindungen geprüft',
    existing_correspondence: 'Vorhandenes Gegenstück', identity_unresolved: 'Gegenstück nicht eindeutig identifiziert',
    complete_submission_has_no_connections: 'Der vollständige Abgabegraph enthält keine Verbindung',
    unique_unassigned_child_class_absent: 'Kein freies kompatibles Gegenstück unter dieser Zuordnung',
    no_outgoing_connection_under_parent_mapping: 'Keine ausgehende Verbindung an diesem Parent',
    endpoint_group_count_deficit: 'Mindestfehlmenge in der Endpunktgruppe; einzelne Identitäten bleiben offen',
    endpoint_group_without_individual_identity: 'Endpunktgruppe verglichen; keine individuelle Identitätsaussage'
  }
  const reason = reasons[evidence.reason] ?? (evidence.reason.startsWith('compared_connection_') ? 'Verbindungseigenschaft anhand der Elementzuordnungen verglichen' : evidence.reason)
  const counts = typeof evidence.expected === 'number' ? ` · ${evidence.observed} / ${evidence.expected} vorhanden` : ''
  const missing = typeof evidence.minimumMissing === 'number' && evidence.minimumMissing > 0 ? ` · mindestens ${evidence.minimumMissing} lokal nicht realisiert` : ''
  const placement = evidence.placementStatus ? ` · ${analysisPlacementLabel(evidence.placementStatus)}` : ''
  return `${analysisValueLabel(evidence.basis)} · ${reason}${counts}${missing}${placement}`
}
export const analysisChildChecklist = (facts: AnalysisFact[] | undefined) => {
  const evidence = facts?.find(fact => fact.code === 'children.complete')?.evidence
  if (!evidence || typeof evidence.matched !== 'number' || typeof evidence.expected !== 'number') return null
  const ids = (key: string) => Array.isArray(evidence[key]) ? (evidence[key] as unknown[]).filter((id): id is string => typeof id === 'string') : []
  const absent = ids('provenAbsentReferenceIds')
  return { matched: evidence.matched, expected: evidence.expected, moved: ids('movedReferenceIds'), absent,
    unresolvedReference: ids('unmatchedReferenceIds').filter(id => !absent.includes(id)),
    unresolvedSubmission: ids('unmatchedSubmissionIds'), foreign: ids('mappedFromOtherTargets'), roleDifferences: ids('roleDifferenceReferenceIds') }
}
export const analysisReasonLabel = (reason: string) => ({ unique_exact_label: 'Eindeutige gleiche Beschriftung', unique_exact_after_reservations: 'Eindeutige gleiche Beschriftung nach bestehenden Zuordnungen', consistent_owner_anchor: 'Konsistenter zugeordneter Besitzer', independent_child_evidence: 'Unabhängige Evidenz enthaltener Elemente', supported_semantic_evidence: 'Semantisch gestützte Zuordnung', compatible_type_and_mapped_endpoints: 'Kompatibler Typ und zugeordnete Endpunkte', structural_child_of_mapped_parent: 'Kind eines zugeordneten Parents' })[reason] ?? `Zuordnungsregel: ${reason}`
const hintTexts: Record<string, string> = {
  'fact.violated': 'Die Einzelprüfung weist eine Abweichung nach.', 'fact.unresolved': 'Diese Einzelprüfung bleibt ungeklärt.',
  'fact.group_violated': 'Die Verbindungsgruppe weicht ab; einzelne Identitäten bleiben vorläufig.', 'fact.group_unresolved': 'Die Prüfung der Verbindungsgruppe bleibt ungeklärt.',
  'reference.missing': 'Das Referenzgegenstück ist nachweisbar nicht realisiert; die Beweisgrundlage steht im Einzelbefund.',
  'identity.unresolved': 'Identität ungeklärt; nicht als zusätzlich bestätigt.', 'identity.ambiguous': 'Mehrere Zuordnungskandidaten.',
  'label.different': 'Die Beschriftung weicht ab.', 'type.compatible_difference': 'Der konkrete Typ weicht innerhalb der Vergleichsgruppe ab; kein bestätigter fachlicher Fehler.',
  'owner.violated': 'Das Element ist einem anderen Besitzer zugeordnet.', 'owner.different': 'Der Besitzer weicht ab.', 'owner.unresolved': 'Der Besitzer ist ungeklärt.',
  'containment.violated': 'Die Zugehörigkeit zum Container ist verletzt.', 'connection.endpoints_different': 'Die Endpunkte weichen ab.',
  'connection.source_different': 'Source weicht ab.', 'connection.target_different': 'Target weicht ab.',
  'connection.direction_different': 'Die Richtung weicht ab.', 'connection.connectionType_different': 'Der konkrete Verbindungstyp weicht ab.',
  'connection.group_difference': 'Befund an der Verbindungsgruppe; kein individuell bewiesener Fehler dieser Verbindung.',
  'reference.unresolved': 'Referenzobjekt nicht identifiziert; nicht als fehlend bestätigt.',
  'reference.not_evaluated': 'Dieses Referenzobjekt wurde nicht eigenständig zugeordnet oder geprüft.',
  'input.category_metadata_unavailable': 'Die Sprachmetadaten deklarieren keine Elementkategorien. Nicht klassifizierte Elemente bleiben unter Sonstige.',
  'input.owner_evidence_unavailable': 'Es liegt keine Besitzerprüfung des Matchers vor.',
  'input.containment_evidence_unavailable': 'Es liegt keine Prüfung direkter Containment-Beziehungen des Matchers vor.',
  'input.connection_structure_unavailable': 'Es liegt kein Befund des Matchers zu Verbindungsgruppen vor.'
}
for (const [prefix, label] of [['children', 'Enthaltene Elemente'], ['connections', 'Angrenzende Verbindungen']]) {
  hintTexts[`${prefix}.unresolved_reference`] = `${label}: Referenzobjekte noch ungeklärt.`
  hintTexts[`${prefix}.unresolved_submission`] = `${label}: Abgabeobjekte noch ungeklärt; nicht als zusätzlich bestätigt.`
  hintTexts[`${prefix}.mapped_from_other_target`] = `${label}: Objekte sind vorläufig einem anderen Referenzkontext zugeordnet.`
  hintTexts[`${prefix}.outside_target`] = `${label}: Erkannte Objekte befinden sich außerhalb dieses Ziels; Zuordnung bleibt ungeklärt.`
}
export const analysisHintText = (hint: AnalysisHint) => Object.prototype.hasOwnProperty.call(hintTexts, hint.code) ? hintTexts[hint.code] : `Technischer Hinweis: ${hint.code}`
export const analysisHintParameters = (hint: AnalysisHint) => JSON.stringify(hint.parameters ?? Object.fromEntries(Object.entries(hint).filter(([key]) => !['code', 'target'].includes(key))))
