import type { EvaluationDetail } from '@/services/api/types/evaluation'

export const compactSimilarityMethodLabel = (method: string) => ({
  damerau_canonical: 'Spelling', levenshtein_canonical: 'Spelling', levenshtein: 'Spelling',
  multilingual_expanded: 'Meaning', multilingual: 'Meaning', jaro_winkler: 'Word form', char_trigram: 'Characters'
} as Record<string, string>)[method] ?? method

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
  referenceIds?: string[]; submissionIds?: string[]; dependsOn?: { referenceId: string; studentId: string }[]
  matched?: number; expected?: number; observed?: number; complete?: boolean
  // text_similarity only: the matcher's own verdict (reached tier with its thresholds, guard veto).
  scores?: Record<string, number>; tier?: string | null; minimumSimilarity?: Record<string, number>; veto?: string
}
export interface AnalysisIdentity { status: 'uniquely_supported' | 'supported' | 'unresolved'; criteria: IdentityCriterion[]; supportingCandidateCount?: number }
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
  match?: { status: 'provisional' | 'unresolved' | 'not_evaluated'; reason?: string; dependsOn?: { referenceId: string; submissionId: string }[] }
  mappingReason?: string
  dependencies?: { referenceId: string; studentId: string }[]
  context?: { referenceId: string; basis: string; status: string }
  checks?: Record<string, string>
  hints: AnalysisHint[]
  facts?: AnalysisFact[]
  identity?: AnalysisIdentity
  consistency?: 'fully_consistent' | 'partial' | 'different' | 'unresolved' | 'not_evaluated'
  owner?: { referenceOwnerId: string | null; submissionOwnerId: string | null; status?: string }
  containment?: { referenceParents: ParentRelation[] | null; submissionParents: ParentRelation[] }
  connection?: { reference: ConnectionValue | null; submission: ConnectionValue }
  groupIds?: string[]
  relationIds?: string[]
  local?: Partial<Record<'children' | 'directChildren' | 'connections' | 'incoming' | 'outgoing' | 'undirected' | 'unresolved', LocalCounts>> & {
    containmentRelations?: RelationCounts; childRoles?: (RelationCounts & { role: string | null })[]
  }
}
export interface ConnectionGroup { id: string; status?: AnalysisStatus; referenceIds: string[]; submissionIds: string[]; referenceEndpointIds: string[]; submissionEndpointIds: string[]; facts?: AnalysisFact[]; checks?: Record<string, string>; referenceOnlyCount?: number; submissionOnlyCount?: number; hints?: AnalysisHint[] }
export interface ContainmentRelation { id: string; status: AnalysisStatus; scope: 'relation'; referenceChildId: string; referenceParentId: string; referenceRole: string | null; submissionChildId: string | null; submissionParentId: string | null; observedParents: ParentRelation[]; roleStatus: string; basis: string }
export interface RecognitionCount { recognized: number | null; expected: number | null; percent: number | null; evaluationStatus: string }
export interface RecognitionBucket extends RecognitionCount { id: string; label: string; kind: ObjectKind; grouped: boolean }
export interface RecognitionReport { basis: 'uniquely_supported'; buckets?: RecognitionBucket[]; categories?: Record<AnalysisCategory, RecognitionCount>; overall: RecognitionCount; unmatchedSubmission: { id: string; kind: ObjectKind; category?: AnalysisCategory }[] }
export interface ReferenceHint extends AnalysisHint { target: AnalysisTarget; referenceId: string; kind: ObjectKind; label?: string; facts?: AnalysisFact[]; identity?: AnalysisIdentity }
export interface AnalysisFeedback {
  labelHints?: { id: string; submissionId: string; submissionLabel: string; suggestion: string | null; sources?: string[]; relation?: string | null }[]
  schema: 'analysis-feedback/v1' | 'analysis-feedback/v2' | 'analysis-feedback/v3'; evaluationId: string; pair: { studentKey: 'submission'; referenceKey: string }
  contractVersion?: '1.1' | '1.2' | '1.3'
  status: 'provisional'; assessmentAvailable: false
  comparisonHash: string; analysisKey: string; analysisHash: string
  summary?: Record<AnalysisCategory, RecognitionCount>; recognition?: RecognitionReport; annotations: AnalysisAnnotation[]; referenceHints: ReferenceHint[]
  structuralContainers?: { referenceCount: number; submissionCount: number; contextCount?: number; evaluationStatus?: 'not_evaluated' }
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
const factStatuses = ['satisfied', 'violated', 'unresolved', 'not_evaluated', 'not_applicable']
const identityStatuses = ['uniquely_supported', 'supported', 'unresolved']
const recognitionStatuses = ['evaluated', 'partial', 'not_evaluated', 'not_applicable']

/** Validate published counts; never infer recognition from provisional mappings. */
export function adaptRecognition(value: unknown): RecognitionReport {
  requireValue(object(value) && value.basis === 'uniquely_supported' && (Array.isArray(value.buckets) || object(value.categories) && Object.keys(value.categories).length === analysisCategories.length) && Array.isArray(value.unmatchedSubmission))
  const validRow = (row: unknown) => object(row) && count(row.recognized) && count(row.expected) &&
    (row.recognized as number) <= (row.expected as number) && recognitionStatuses.includes(String(row.evaluationStatus)) &&
    (row.percent === null ? ['not_evaluated', 'not_applicable'].includes(String(row.evaluationStatus)) :
      !['not_evaluated', 'not_applicable'].includes(String(row.evaluationStatus)) && typeof row.percent === 'number' && Number.isFinite(row.percent) &&
      (row.expected as number) > 0 && Math.abs(row.percent - 100 * (row.recognized as number) / (row.expected as number)) < 0.000001)
  const grouped = Array.isArray(value.buckets)
  const rows: unknown[] = grouped ? value.buckets as unknown[] : analysisCategories.map(category => (value.categories as Record<string, unknown>)[category])
  requireValue(validRow(value.overall) && rows.every(validRow))
  if (grouped) requireValue(rows.every(row => object(row) && hash(row.id) && id(row.label) && kinds.includes(row.kind as ObjectKind) && typeof row.grouped === 'boolean' && Number(row.expected) > 0) &&
    new Set(rows.map(row => (row as Record<string, unknown>).id)).size === rows.length)
  for (const key of ['recognized', 'expected']) requireValue((value.overall as Record<string, unknown>)[key] ===
    rows.reduce<number>((sum, row) => sum + Number((row as Record<string, unknown>)[key]), 0))
  requireValue(value.unmatchedSubmission.every(item => object(item) && id(item.id) && kinds.includes(item.kind as ObjectKind) && (grouped || analysisCategories.includes(item.category as AnalysisCategory))) &&
    new Set(value.unmatchedSubmission.map(item => (item as Record<string, unknown>).id)).size === value.unmatchedSubmission.length)
  return value as unknown as RecognitionReport
}

// v4 carries only the requested feedback types; v2/v3 carry the recognition directly.
const recognitionOfReport = (result: Record<string, unknown>): unknown => result.schema !== 'feedback-report/v4'
  ? result.recognition
  : Array.isArray(result.feedback) ? result.feedback.find(entry => object(entry) && entry.type === 'recognition')?.recognition : undefined

export function recognitionReportsFromEvaluation(detail: EvaluationDetail) {
  const reports = detail.steps.filter(step => step.status === 'succeeded' && ['feedback-report/v2', 'feedback-report/v3', 'feedback-report/v4'].includes(String(step.result?.schema)))
    .filter(step => recognitionOfReport(step.result!) !== undefined).map(step => {
      const result = step.result!
      requireValue(object(result.pair) && id(result.pair.referenceKey) && result.evaluationId === detail.id)
      return { referenceKey: result.pair.referenceKey, recognition: adaptRecognition(recognitionOfReport(result)) }
    })
  requireValue(new Set(reports.map(report => report.referenceKey)).size === reports.length)
  return reports
}

function adaptCurrentAnalysis(value: Record<string, unknown>, context: AnalysisContext): AdaptedAnalysis {
  requireValue(value.status === 'provisional' && value.assessmentAvailable === false && value.evaluationId === context.evaluationId &&
    object(value.pair) && value.pair.studentKey === 'submission' && value.pair.referenceKey === context.referenceKey &&
    hash(value.analysisKey) && hash(value.analysisHash) && hash(value.comparisonHash))
  adaptRecognition(value.recognition)
  const submission = new Map(context.submissionObjects.map(item => [item.id, item]))
  const reference = new Map(context.referenceObjects.map(item => [item.id, item]))
  requireValue(submission.size === context.submissionObjects.length && reference.size === context.referenceObjects.length)
  requireValue([...submission.values(), ...reference.values()].every(item => id(item.id) && kinds.includes(item.kind)))
  const validTarget = (target: unknown): target is ObjectReference => object(target) && id(target.id) &&
    (target.side === 'submission' ? target.kind === 'model' ? target.id === context.modelId : submission.get(target.id)?.kind === target.kind && submission.has(target.id) :
      target.side === 'reference' && reference.has(target.id) && reference.get(target.id)!.kind === target.kind)
  const validFacts = (facts: unknown) => Array.isArray(facts) && facts.every(fact => object(fact) && hash(fact.id) && id(fact.code) && factStatuses.includes(String(fact.status)) &&
    Array.isArray(fact.referenceIds) && fact.referenceIds.every(identity => id(identity) && reference.has(identity)) &&
    Array.isArray(fact.submissionIds) && fact.submissionIds.every(identity => id(identity) && submission.has(identity)) && object(fact.evidence) &&
    ['direct_observation', 'independent_evidence', 'conditional_mapping'].includes(String(fact.evidence.basis)) && id(fact.evidence.reason) &&
    !('criteria' in fact.evidence) && !('referenceObservation' in fact.evidence) && !('submissionObservation' in fact.evidence))
  const validIdentity = (identity: unknown) => object(identity) && identityStatuses.includes(String(identity.status)) && Array.isArray(identity.criteria) &&
    identity.criteria.every(item => object(item) && id(item.method) && ['compatibility', 'support', 'identity_anchor'].includes(String(item.role)) && factStatuses.includes(String(item.result)) &&
      (item.dependsOn === undefined || Array.isArray(item.dependsOn) && item.dependsOn.every(dep => object(dep) && id(dep.referenceId) && reference.has(dep.referenceId) && id(dep.studentId) && submission.has(dep.studentId))))
  const validHints = (hints: unknown) => Array.isArray(hints) && hints.every(hint => object(hint) && id(hint.code) &&
    ['element', 'relation', 'group', 'model'].includes(String(hint.scope)) && Array.isArray(hint.targets) && hint.targets.every(validTarget) &&
    (hint.factId === undefined || hash(hint.factId)) && (hint.findingId === undefined || hash(hint.findingId)))
  requireValue(Array.isArray(value.annotations) && Array.isArray(value.referenceHints) && Array.isArray(value.connectionGroups) && validHints(value.limitations))
  const annotations = new Map<ObjectKind, Map<string, AnalysisAnnotation>>()
  const seen = new Set<string>(), matched = new Set<string>()
  for (const item of value.annotations) {
    requireValue(object(item) && validTarget(item.target) && item.target.side === 'submission' && item.target.kind !== 'model' && !seen.has(item.target.id) &&
      (value.schema === 'analysis-feedback/v3' || item.category === null || analysisCategories.includes(item.category as AnalysisCategory)) && validFacts(item.facts) && validHints(item.hints) && !('checks' in item) && !('status' in item))
    if (item.referenceId !== undefined) {
      requireValue(id(item.referenceId) && reference.get(item.referenceId)?.kind === item.target.kind && !matched.has(item.referenceId))
      matched.add(item.referenceId)
    }
    if (['modelElement', 'connection'].includes(String(item.target.kind))) requireValue(validIdentity(item.identity))
    requireValue(item.dependencies === undefined || Array.isArray(item.dependencies) && item.dependencies.every(dep => object(dep) && id(dep.referenceId) && reference.has(dep.referenceId) && id(dep.studentId) && submission.has(dep.studentId)))
    seen.add(item.target.id)
    const kind = item.target.kind as ObjectKind
    if (!annotations.has(kind)) annotations.set(kind, new Map())
    annotations.get(kind)!.set(item.target.id, item as unknown as AnalysisAnnotation)
  }
  requireValue(seen.size === submission.size)
  const hinted = new Set<string>()
  for (const hint of value.referenceHints) {
    requireValue(object(hint) && id(hint.referenceId) && reference.get(hint.referenceId)?.kind === hint.kind && !matched.has(hint.referenceId) &&
      !hinted.has(hint.referenceId) && validTarget(hint.target) && hint.target.side === 'submission' && validFacts(hint.facts) && validHints([hint]))
    if (hint.identity !== undefined) requireValue(validIdentity(hint.identity))
    // Analyses before analytical-feedback 2.5.0 kept inline formatting tags in the reference label.
    if (typeof hint.label === 'string') hint.label = plainLabel(hint.label)
    hinted.add(hint.referenceId)
  }
  requireValue([...reference.keys()].every(identity => matched.has(identity) || hinted.has(identity)))
  const groups = new Set<string>()
  for (const group of value.connectionGroups) {
    requireValue(object(group) && hash(group.id) && !groups.has(group.id as string) && validFacts(group.facts) &&
      Array.isArray(group.referenceIds) && group.referenceIds.every(identity => id(identity) && reference.get(identity)?.kind === 'connection') &&
      Array.isArray(group.submissionIds) && group.submissionIds.every(identity => id(identity) && submission.get(identity)?.kind === 'connection') &&
      Array.isArray(group.referenceEndpointIds) && group.referenceEndpointIds.every(identity => id(identity) && reference.has(identity)) &&
      Array.isArray(group.submissionEndpointIds) && group.submissionEndpointIds.every(identity => id(identity) && submission.has(identity)))
    groups.add(group.id as string)
  }
  for (const item of value.annotations) requireValue(object(item) && (item.groupIds === undefined || Array.isArray(item.groupIds) && item.groupIds.every(identity => typeof identity === 'string' && groups.has(identity))))
  return { report: value as unknown as AnalysisFeedback, annotations }
}

/** The detail API unwraps workflow-result/v1; raw saved stdout envelopes are accepted as well. */
export function adaptAnalysisFeedback(value: unknown, context: AnalysisContext): AdaptedAnalysis {
  requireValue(object(value))
  if (value.schema === 'workflow-result/v1') {
    requireValue(value.schemaVersion === 1 && value.status === 'ok' && value.capability === 'analytical-feedback')
    requireValue(object(value.result) && value.analysisKey === value.result.analysisKey)
    value = value.result
  }
  if (object(value) && ['analysis-feedback/v2', 'analysis-feedback/v3'].includes(String(value.schema))) return adaptCurrentAnalysis(value, context)
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
    for (const dep of item.match?.dependsOn ?? []) requireValue(value.annotations.some((candidate: unknown) =>
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
  requireValue(['reference-comparison/v1', 'reference-comparison/v2'].includes(String(comparison?.schema)) && comparison?.evaluationId === detail.id && object(comparison.pair) &&
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

export type DisplayStatus = 'recognized' | 'supported' | 'provisional' | 'warning' | 'unresolved' | 'not_evaluated'
/** Most severe first; used for list order and for merging several findings into one diagram marker. */
export const displayStatusOrder: DisplayStatus[] = ['warning', 'unresolved', 'supported', 'recognized', 'provisional', 'not_evaluated']
export const individualViolations = (item: { facts?: AnalysisFact[] }) => item.facts?.filter(fact => !fact.code.startsWith('connection_group.') && !fact.code.startsWith('label.') && fact.status === 'violated') ?? []
export const analysisStatus = (item: AnalysisAnnotation): DisplayStatus => {
  if (item.identity) {
    if (individualViolations(item).length) return 'warning'
    return item.identity.status === 'uniquely_supported' ? 'recognized' : item.identity.status === 'supported' ? 'supported' : 'unresolved'
  }
  if (item.status) return ({ provisional: 'provisional', different: 'warning', ambiguous: 'unresolved', unresolved: 'unresolved', not_evaluated: 'not_evaluated', not_applicable: 'not_evaluated' } as const)[item.status] ?? 'not_evaluated'
  const checks = item.checks ?? {}
  // Group direction/type findings never prove an individual connection error.
  const individualDifference = Object.entries(checks).some(([check, status]) =>
    ['owner', 'containment', 'endpoints', 'direction', 'connectionType'].includes(check) && ['violated', 'different'].includes(status) &&
    !(checks.connectionScope === 'endpoint_group' && ['direction', 'connectionType'].includes(check)))
  if (individualDifference || item.hints.some(hint => ['owner.violated', 'owner.different', 'containment.violated', 'connection.endpoints_different'].includes(hint.code))) return 'warning'
  const groupDifference = checks.connectionScope === 'endpoint_group' && [checks.direction, checks.connectionType].includes('different')
  if (item.match?.status === 'unresolved' || Object.values(checks).includes('unresolved') || groupDifference || item.hints.some(hint =>
    ['identity.unresolved', 'identity.ambiguous', 'owner.unresolved', 'connection.group_difference'].includes(hint.code) ||
    /^(children|connections)\.(unresolved_reference|unresolved_submission|outside_target|mapped_from_other_target)$/.test(hint.code))) return 'unresolved'
  return item.match?.status === 'provisional' ? 'provisional' : 'not_evaluated'
}
// Recognition is not correctness, so "recognized" stays blue instead of success green.
/** Identity markers are independent of property and neighbourhood checks (GM-29/34/37). */
export const analysisOverviewStatus = (item: AnalysisAnnotation): DisplayStatus => {
  if (item.identity) return item.identity.status === 'uniquely_supported' ? 'recognized' : item.identity.status === 'supported' ? 'supported' : 'unresolved'
  if (item.match?.status === 'provisional') return 'provisional'
  if (item.match?.status === 'unresolved') return 'unresolved'
  return item.status === 'not_evaluated' || item.status === 'not_applicable' ? 'not_evaluated' : item.referenceId ? 'provisional' : 'unresolved'
}

export const analysisDisplay = {
  recognized: { icon: 'mdi-check-circle-outline', color: '#1E6FA8', label: 'Eindeutig erkannt' },
  supported: { icon: 'mdi-circle-half-full', color: '#607D8B', label: 'Gestützt, nicht eindeutig' },
  provisional: { icon: 'mdi-information-outline', color: '#607D8B', label: 'Vorläufige Zuordnung (älteres Format)' },
  warning: { icon: 'mdi-alert-outline', color: '#B26A00', label: 'Abweichung' },
  unresolved: { icon: 'mdi-help-circle-outline', color: '#6D4C9F', label: 'Ungeklärt' },
  not_evaluated: { icon: 'mdi-minus-circle-outline', color: '#757575', label: 'Nicht ausgewertet' }
} as const
export const analysisOverviewDisplay = {
  ...analysisDisplay,
  recognized: { icon: 'mdi-check-circle', color: '#4CAF50', label: 'Gegenstück eindeutig erkannt' },
  supported: { icon: 'mdi-circle-half-full', color: '#B26A00', label: 'Kandidat, noch nicht eindeutig erkannt' }
} as const
export const recognizedWithLocalIssuesDisplay = {
  icon: 'mdi-check-circle-outline', color: '#1F242E', label: 'Gegenstück erkannt; lokale Eigenschaft weicht ab'
} as const
export const studentQuestionDisplay = {
  icon: 'mdi-check-circle-outline', color: '#1F242E', label: 'Mögliche Zuordnung; Rückfrage an Studierende'
} as const
const hintSourceLabels: Record<string, string> = {
  text_band: 'ähnliche Schreibweise oder Bedeutung', neighbor_profile: 'gleiche Verbindungen zu erkannten Elementen', child_overlap: 'viele gleiche untergeordnete Elemente'
}
const hintRelationLabels: Record<string, string> = {
  notation: 'gleiche Wortteile, andere Schreibweise', reordered: 'gleiche Wortteile in anderer Reihenfolge', head_form: 'kürzere oder längere Form desselben Begriffs',
  part_of_term: 'Teil eines längeren Begriffs', abbreviation: 'Abkürzung', same_stem: 'gleicher Wortanfang oder gleiches Wortende'
}
/** Why a hint exists, shared by the learner hint list and the analysis view. */
export const labelHintReason = (sources: readonly string[], relation: string | null) => {
  const reasons = sources.map(source => hintSourceLabels[source] ?? source)
  return `Grund: ${reasons.join(', ') || 'nicht angegeben'}${relation ? `; Wortvergleich: ${hintRelationLabels[relation] ?? relation}` : ''}.`
}
export const analysisStudentQuestions = (report: AnalysisFeedback, submissionId?: string) =>
  (Array.isArray(report.labelHints) ? report.labelHints : []).filter(hint => hint && typeof hint.id === 'string' &&
    typeof hint.submissionId === 'string' && (submissionId === undefined || hint.submissionId === submissionId)).map(hint => ({
    id: hint.id, submissionId: hint.submissionId, reason: labelHintReason(hint.sources ?? [], hint.relation ?? null),
    text: typeof hint.suggestion === 'string' && hint.suggestion ? `Meinst du „${hint.suggestion}“?` : 'Die Beschriftung weicht vermutlich vom erwarteten Begriff ab.'
  }))

/** Only the object's own properties affect its checkmark, never children or group totals. */
export const analysisOverviewAppearance = (item: AnalysisAnnotation, hasStudentQuestion = false) => {
  if (hasStudentQuestion) return studentQuestionDisplay
  const status = analysisOverviewStatus(item)
  if (status !== 'recognized') return analysisOverviewDisplay[status]
  const differing = [...new Set((item.facts ?? []).filter(fact =>
    /^(type|formatting|owner|containment|connection)\./.test(fact.code) && fact.status === 'violated' &&
    fact.submissionIds.length === 1 && fact.submissionIds[0] === item.target.id).map(fact => analysisFactLabel(fact.code)))]
  return differing.length ? { ...recognizedWithLocalIssuesDisplay, label: `Gegenstück erkannt; abweichend: ${differing.join(', ')}` } : analysisOverviewDisplay.recognized
}
export const categoryLabels: Record<AnalysisCategory, string> = { nodes: 'Knoten', attributes: 'Attribute', connections: 'Verbindungen', other: 'Sonstige' }
export const checkLabels: Record<string, string> = { label: 'Beschriftung', type: 'Konkreter Typ', formatting: 'Textauszeichnung', owner: 'Besitzer', containment: 'Containment', source: 'Source', target: 'Target', endpoints: 'Endpunkte', direction: 'Richtung', connectionType: 'Verbindungstyp', connectionScope: 'Prüfumfang', configuration: 'Konfiguration', counterpart: 'Gegenstück', children: 'Fachliche Kinder', direct_children: 'Unmittelbare Kinder', directChildren: 'Unmittelbare Kinder', connections: 'Angrenzende Verbindungen', incoming: 'Eingehende Verbindungen', outgoing: 'Ausgehende Verbindungen', undirected: 'Ungerichtete Verbindungen', connection_group: 'Verbindungsgruppe' }
export const analysisValueLabel = (value: string) => ({ provisional: 'Vorläufig', evaluated: 'Ausgewertet', ambiguous: 'Mehrdeutig', unresolved: 'Ungeklärt', not_evaluated: 'Nicht ausgewertet', not_applicable: 'Nicht anwendbar', partial: 'Teilweise ausgewertet', exact: 'Gleich', equal: 'Gleich', different: 'Abweichend', same_type: 'Gleicher Typ', compatible_type_difference: 'Anderer Typ innerhalb der Vergleichsgruppe', satisfied: 'Erfüllt', violated: 'Verletzt', endpoint_group: 'Verbindungsgruppe', derived_context: 'Abgeleiteter Strukturkontext', fully_consistent: 'Implementierte lokale Prüfungen vollständig erfüllt (unter vorläufiger Zuordnung)', direct_observation: 'Direkt beobachtet', conditional_mapping: 'Unter vorläufiger Zuordnung', independent_evidence: 'Unabhängig gestützt' })[value] ?? value
export const analysisFactLabel = (code: string) => {
  const [prefix, dimension] = code.split('.')
  if (prefix === 'identity') return 'Identität'
  if (prefix === 'connection') return checkLabels[dimension] ?? dimension
  if (prefix === 'connection_group') return `Verbindungsgruppe: ${checkLabels[dimension] ?? (dimension === 'minimum_missing' ? 'Mindestfehlmenge' : dimension)}`
  return checkLabels[prefix] ?? code
}
export const analysisIdentityLabel = (status: string) => ({ uniquely_supported: 'Eindeutig erkannt', supported: 'Identität gestützt; Eindeutigkeit offen', unresolved: 'Identität ungeklärt' })[status] ?? status
export const analysisIdentityMethodLabel = (method: string) => ({ context_structure: 'Graphkontext entscheidet zwischen Textkandidaten', neighbor_structure: 'Übereinstimmende Nachbarstruktur', interchangeable_duplicate: 'Gleichwertige Kopie (GM-51)', exact_label: 'Exakte Beschriftung', type_compatibility: 'Typkompatibilität', independent_children: 'Unabhängig erkannte Kinder', combined_children: 'Gemeinsame Kinderstruktur', identified_owner: 'Unabhängig erkannter Besitzer', connection_structure: 'Verbindungsstruktur', text_similarity: 'Textähnlichkeit über Schwelle', label_structure: 'Beschriftung widerspricht Struktur (vermutlich vertauscht)', semantic_proposal: 'Vorhandene semantische Evidenz' })[method] ?? method
export const analysisIdentityRoleLabel = (role: string) => ({ compatibility: 'Vergleich zulässig', support: 'Positive Evidenz', identity_anchor: 'Identitätsanker nach Konkurrenzprüfung' })[role] ?? role
export const analysisPlacementLabel = (status: unknown) => typeof status === 'string' ? ({ correct_placement: 'Korrekt platziert', wrong_placement: 'Falsch platziert', placement_unresolved: 'Platzierung ungeklärt', unmatched_submission: 'Abgabegegenstück nicht zugeordnet', unmatched_reference: 'Referenzgegenstück nicht zugeordnet', proven_absent: 'Abwesenheit nachgewiesen' })[status] ?? status : ''
const formattingNames: Record<string, string> = { bold: 'fett', italic: 'kursiv', underline: 'unterstrichen' }
const factValue = (value: unknown): string => Array.isArray(value) ? value.map(item => formattingNames[String(item)] ?? String(item)).join(', ') || 'keine'
  : typeof value === 'boolean' ? (value ? 'ja' : 'nein') : value === null || value === undefined || value === '' ? '–' : String(value)
export const analysisFactEvidence = (fact: AnalysisFact) => {
  const evidence = fact.evidence
  const reasons: Record<string, string> = {
    evaluated_identity_evidence: 'Identität anhand der ausgewiesenen Evidenzmethoden geprüft',
    compared_labels: 'Beschriftungen verglichen', text_unavailable: 'Beschriftungsvergleich nicht auswertbar', compared_concrete_types: 'Konkrete Typen verglichen', compared_visible_formatting: 'Textauszeichnung verglichen', difference_explained_by_type: 'Abweichung folgt aus dem Elementtyp', no_formatting: 'Keine Seite ist ausgezeichnet',
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
  const unavailable = evidence.unavailableReason === 'missing_text' ? ' · Beschriftung fehlt' : evidence.unavailableReason === 'unsupported_text' ? ' · Beschriftungsformat nicht unterstützt' : ''
  const values = fact.code.startsWith('label.') || !('referenceValue' in evidence) ? ''
    : ` · Referenz: ${factValue(evidence.referenceValue)} · Abgabe: ${factValue(evidence.submissionValue)}`
  return `${analysisValueLabel(evidence.basis)} · ${reason}${counts}${missing}${placement}${unavailable}${values}`
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
export const analysisReasonLabel = (reason: string) => ({ context_disambiguated_text: 'Text mit passendem Graphkontext (GM-47)', neighbor_structure: 'Übereinstimmende Nachbarstruktur (GM-48)', loose_context_text: 'Text mit passendem Nachbarn trotz abweichender Kante (GM-51)', interchangeable_duplicate: 'Gleichwertige Kopie, beliebig zugeordnet (GM-51)', interchangeable_parallel_connections: 'Austauschbare parallele Verbindung (GM-46)', combined_child_structure: 'Gemeinsam unterscheidende Kinderstruktur', unique_mapped_endpoints: 'Eindeutig zugeordnete Endpunkte', unique_exact_connection_label: 'Eindeutige Verbindungsbeschriftung', unique_exact_label: 'Eindeutige gleiche Beschriftung', unique_exact_after_reservations: 'Eindeutige gleiche Beschriftung nach bestehenden Zuordnungen', consistent_owner_anchor: 'Konsistenter zugeordneter Besitzer', independent_child_evidence: 'Unabhängige Evidenz enthaltener Elemente', supported_semantic_evidence: 'Semantisch gestützte Zuordnung', neighbor_confirmed_semantic_evidence: 'Textähnlichkeit im Graubereich, durch zugeordnete Nachbarn bestätigt', compatible_type_and_mapped_endpoints: 'Kompatibler Typ und zugeordnete Endpunkte', structural_child_of_mapped_parent: 'Kind eines zugeordneten Parents' })[reason] ?? `Zuordnungsregel: ${reason}`
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

// --- Admin explanations: read-only views on artifacts the workflow already published ---

export const objectKindLabel = (kind: string | null | undefined) =>
  ({ modelElement: 'Element', structuralElement: 'Strukturcontainer', connection: 'Verbindung', connectionLabel: 'Verbindungsbeschriftung', model: 'Modell' } as Record<string, string>)[kind ?? ''] ?? 'Objekt'

export interface GraphNode { id: string; kind: ObjectKind; label?: string; type?: string }
export interface GraphDiagnostic { code: string; severity: string; message?: string; elementIds?: string[] }
export interface GraphInfo { nodes: Map<string, GraphNode>; interpretation: 'complete' | 'partial' | null; diagnostics: GraphDiagnostic[] }

/** Parser output of one model of this evaluation; null when absent or not bound to the evaluation. */
/** Same inline tags as the editor and model-label-extraction; breaks become spaces. */
export const plainLabel = (label: string) => label.replace(/<\/?(b|strong|i|em|u|br|div)\s*\/?>/gi, (tag) => /^<\/?(br|div)/i.test(tag) ? ' ' : '').split(/\s+/).filter(Boolean).join(' ')
export function graphInfo(detail: EvaluationDetail, key: string): GraphInfo | null {
  const result = detail.steps.find(step => step.result?.schema === 'graph-result/v1' && object(step.result.source) && step.result.source.key === key)?.result
  if (!result || result.evaluationId !== detail.id || !object(result.graph) || !Array.isArray(result.graph.nodes)) return null
  const nodes = (result.graph.nodes as unknown[]).filter((node): node is GraphNode => object(node) && id(node.id))
  const interpretation = object(result.completeness) ? result.completeness.interpretation : null
  return {
    // Inline formatting is layout (compared as its own check), so names in the analysis are plain text.
    nodes: new Map(nodes.map(node => [node.id, typeof node.label === 'string' ? { ...node, label: plainLabel(node.label) } : node])),
    interpretation: interpretation === 'complete' || interpretation === 'partial' ? interpretation : null,
    diagnostics: Array.isArray(result.diagnostics) ? (result.diagnostics as unknown[]).filter((item): item is GraphDiagnostic => object(item) && id(item.code)) : []
  }
}
export const graphDiagnosticLabel = (diagnostic: GraphDiagnostic) => ({
  AMBIGUOUS_COMPARISON_GROUP: 'Vergleichsgruppe nicht eindeutig', AMBIGUOUS_DEFINITION: 'Typdefinition mehrdeutig', AMBIGUOUS_LANGUAGE_ORIGIN: 'Sprachherkunft mehrdeutig',
  CONTAINMENT_CYCLE: 'Zyklische Verschachtelung', INVALID_COMPARISON_ROLE: 'Ungültige Vergleichsrolle', INVALID_CONNECTION_LABEL_OWNER: 'Verbindungsbeschriftung ohne gültige Verbindung',
  INVALID_LANGUAGE_REFERENCE: 'Ungültiger Sprachverweis', INVALID_OWNER: 'Ungültiger Besitzer', MULTIPLE_LANGUAGE_ORIGINS: 'Mehrere Sprachherkünfte',
  OPEN_ENDPOINT: 'Verbindung mit offenem Endpunkt', UNRESOLVED_CHILD_DEFINITION: 'Kinddefinition nicht auflösbar', UNRESOLVED_DEFINITION: 'Typdefinition nicht auflösbar',
  UNRESOLVED_DIRECTION: 'Verbindungsrichtung unbekannt', UNRESOLVED_LANGUAGE_ORIGIN: 'Sprachherkunft nicht auflösbar'
} as Record<string, string>)[diagnostic.code] ?? diagnostic.message ?? diagnostic.code

export interface SimilarityMethod { name: string; range: [number, number]; threshold: number | null; stages: string[]; floor: number | null }
export interface CandidatePair { referenceId: string; submissionId: string; referenceLabel: string; submissionLabel: string; scores: Record<string, number> | null; unavailableReason: string | null }
export interface PairDecision { referenceId: string; studentId: string; decision: 'identified' | 'partial' | 'open'; reason: string }
export interface CandidateEvidence { configured: boolean; methods: SimilarityMethod[]; pairs: CandidatePair[]; decisions: PairDecision[] }
export const pairDecisionLabels: Record<string, string> = {
  identified_glossary: 'Im Glossar akzeptiert und eindeutig', identified_owner: 'Eindeutig innerhalb des erkannten Besitzers', identified_structure: 'Durch Kinder, Verbindungen oder Kontext bestätigt',
  identified_text: 'Text über Schwelle, ohne Konkurrenz', identified_label: 'Gleiche Beschriftung, eindeutig', owner_unresolved: 'Begriff passt, Besitzer aber nicht identifiziert (Teilerkennung, zählt nicht)',
  ambiguous_candidates: 'Mehrere gleich gute Kandidaten', owner_conflict: 'Liegt unter einem anderen Besitzer als in der Musterlösung', assigned_elsewhere: 'Eine Seite ist bereits anderweitig zugeordnet',
  label_structure_conflict: 'Beschriftung widerspricht der Struktur', no_unique_match: 'Keine eindeutige Zuordnung möglich', glossary_rejected: 'Im Glossar abgelehnt',
  digit_mismatch: 'Abweichende Ziffern', start_mismatch: 'Abweichender Wortanfang'
}
export const pairDecisionStatusLabels: Record<PairDecision['decision'], string> = { identified: 'Erkannt', partial: 'Teilweise erkannt', open: 'Nicht zugeordnet' }
/** Prototype tier names from the workflow preset; unknown names are shown as configured. */
export const tierLabel = (name: string) => ({ glossary: 'Glossary', canonical: 'Kanonisch gleich', spelling: 'Schreibweise', meaning: 'Bedeutung' } as Record<string, string>)[name] ?? name
export const similarityMethodLabel = (name: string) => ({ levenshtein: 'Levenshtein', jaro_winkler: 'Jaro-Winkler', char_trigram: 'Zeichen-Trigramme', multilingual: 'Multilinguales Embedding', levenshtein_canonical: 'Levenshtein (kanonische Schreibweise)', damerau_canonical: 'Damerau-Levenshtein (kanonische Schreibweise)', multilingual_expanded: 'Multilinguales Embedding (ausgeschriebene Abkürzungen)' } as Record<string, string>)[name] ?? name
export const textVetoLabel = (veto: string) => ({ glossary_rejected: 'Rejected in the synonym glossary', digit_mismatch: 'Ziffern unterscheiden sich', start_mismatch: 'Wortanfang unterscheidet sich, Schreibweise zählt nicht' } as Record<string, string>)[veto] ?? veto
export const unavailableTextLabel =(reason: string | null) => reason === 'missing_text' ? 'Beschriftung fehlt' : reason === 'unsupported_text' ? 'Beschriftungsformat nicht unterstützt' : 'Kein Wert berechnet'

/** Candidate matrix plus the thresholds the matcher actually used; only returned when both artifacts are bound to each other. */
export function candidateEvidence(detail: EvaluationDetail, referenceKey: string): CandidateEvidence | null {
  const candidates = detail.steps.find(step => step.id === `match_synonyms_${referenceKey}`)?.result
  const comparison = detail.steps.find(step => step.id === `match_graph_${referenceKey}`)?.result
  if (candidates?.schema !== 'semantic-candidates/v1' || candidates.evaluationId !== detail.id || !object(candidates.pair) || candidates.pair.referenceKey !== referenceKey ||
      !object(comparison) || !hash(candidates.candidateHash) || comparison.candidateHash !== candidates.candidateHash ||
      !Array.isArray(candidates.methods) || !Array.isArray(candidates.synonymMatrix)) return null
  const configuration = object(comparison.semanticConfiguration) ? comparison.semanticConfiguration : {}
  const thresholds: Record<string, unknown> = object(configuration.minimumSimilarity) ? { ...configuration.minimumSimilarity } : {}
  // Tiers: a pair is supported when any tier method reaches its threshold, so the lowest threshold per method decides.
  const tiers = object(configuration.textEvidence) && Array.isArray(configuration.textEvidence.tiers) ? configuration.textEvidence.tiers : []
  const stages: Record<string, string[]> = {}
  const floors: Record<string, number> = {}
  const format = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  for (const tier of tiers as unknown[]) {
    const minimum = object(tier) && object(tier.minimumSimilarity) ? tier.minimumSimilarity : {}
    const name = object(tier) ? tierLabel(String(tier.name ?? '')) : ''
    for (const [method, value] of Object.entries(minimum)) {
      if (typeof value !== 'number') continue
      const current = thresholds[method]
      if (typeof current !== 'number' || value < current) thresholds[method] = value
      ;(stages[method] ??= []).push(`${name} ${value >= 1 ? '=' : '≥'} ${format.format(value)}`)
    }
    for (const [method, value] of Object.entries(object(tier) && object(tier.confirmationFloor) ? tier.confirmationFloor : {})) {
      if (typeof value === 'number') floors[method] = value
    }
  }
  const methods: SimilarityMethod[] = []
  for (const method of candidates.methods as unknown[]) {
    if (!object(method) || !id(method.name) || !Array.isArray(method.scoreRange) || method.scoreRange.length !== 2 || !method.scoreRange.every(Number.isFinite)) return null
    const threshold = thresholds[method.name]
    methods.push({ name: method.name, range: method.scoreRange as [number, number], threshold: typeof threshold === 'number' && Number.isFinite(threshold) ? threshold : null,
      stages: stages[method.name] ?? [], floor: floors[method.name] ?? null })
  }
  const pairs: CandidatePair[] = []
  for (const row of candidates.synonymMatrix as unknown[]) {
    if (!object(row) || !id(row.referenceElementId) || !Array.isArray(row.matches)) return null
    for (const match of row.matches as unknown[]) {
      if (!object(match) || !id(match.submissionElementId)) return null
      const scores = match.scoreStatus === 'scored' && object(match.scores)
        ? Object.fromEntries(Object.entries(match.scores).filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1])))
        : null
      pairs.push({ referenceId: row.referenceElementId, submissionId: match.submissionElementId, referenceLabel: String(row.referenceLabel ?? ''),
        submissionLabel: String(match.submissionLabel ?? ''), scores, unavailableReason: typeof match.unavailableReason === 'string' ? match.unavailableReason : null })
    }
  }
  const decisions = (Array.isArray(comparison.pairDecisions) ? comparison.pairDecisions as unknown[] : []).filter((row): row is PairDecision =>
    object(row) && id(row.referenceId) && id(row.studentId) && ['identified', 'partial', 'open'].includes(String(row.decision)) && id(row.reason))
  return { configured: methods.some(method => method.threshold !== null), methods, pairs, decisions }
}
/** GM-15: a pair is supported when any configured method reaches its own threshold; methods are never combined. */
export const aboveThreshold = (pair: CandidatePair, methods: SimilarityMethod[]) =>
  methods.some(method => method.threshold !== null && pair.scores?.[method.name] !== undefined && pair.scores[method.name] >= method.threshold)
/** Same normalization as the matcher's exact text anchor (GM-04): NFC and collapsed whitespace, case preserved. */
export const exactText = (pair: CandidatePair) => {
  const normalize = (value: string) => value.normalize('NFC').split(/\s+/).filter(Boolean).join(' ')
  return normalize(pair.referenceLabel) !== '' && normalize(pair.referenceLabel) === normalize(pair.submissionLabel)
}

const methodList = (criteria: IdentityCriterion[]) => criteria.map(criterion => analysisIdentityMethodLabel(criterion.method)).join(', ')
/** Spells out the matcher's identity rule (GM-26 and the competitor downgrade at the end of evaluate_identity). */
export function identityExplanation(item: { identity?: AnalysisIdentity; referenceId?: string; mappingReason?: string }) {
  const identity = item.identity
  if (!identity) return null
  const anchors = identity.criteria.filter(criterion => criterion.role === 'identity_anchor' && criterion.result === 'satisfied')
  const support = identity.criteria.filter(criterion => criterion.role === 'support' && criterion.result === 'satisfied')
  if (identity.status === 'uniquely_supported') return `${methodList(anchors) || 'Ein Identitätsanker'} lässt unter allen zulässigen Kandidaten nur dieses Gegenstück zu.`
  if (identity.status === 'supported') return `${methodList(support)} spricht für dieses Gegenstück, schließt konkurrierende Kandidaten aber nicht eindeutig aus. Zählt daher nicht als erkannt.`
  if (support.length) return `Mehrdeutig: ${methodList(support)} spricht zwar dafür, aber mindestens ein konkurrierendes Paar mit demselben Referenz- oder Abgabeobjekt hat ebenfalls positive Evidenz.`
  if (item.referenceId) return `Nur vorläufig zugeordnet${item.mappingReason ? ` (${analysisReasonLabel(item.mappingReason)})` : ''}. Keine Evidenz belegt dieses Gegenstück; Prüfungen gelten nur unter dieser Annahme.`
  return 'Kein Gegenstück: Für dieses Objekt liegt keine tragfähige Identitätsevidenz vor.'
}
export function identityCriterionNote(criterion: IdentityCriterion, describe: (dependency: { referenceId: string; studentId: string }) => string) {
  const counts = (typeof criterion.expected === 'number' ? ` · ${criterion.matched ?? 0} / ${criterion.expected}` : '') +
    (criterion.tier ? ` · Stufe ${tierLabel(criterion.tier)}` : '') + (criterion.veto ? ` · verworfen: ${textVetoLabel(criterion.veto)}` : '')
  if (criterion.role === 'compatibility') return (criterion.result === 'satisfied' ? 'Vergleich zulässig, kein Identitätsbeleg' : 'Typen nicht vergleichbar') + counts
  if (criterion.role === 'identity_anchor') return 'Entscheidend: schließt alle Konkurrenten aus' + counts
  if (criterion.result === 'satisfied') return 'Spricht dafür, allein nicht eindeutig' + counts
  if (criterion.result === 'unresolved' && criterion.dependsOn?.length) return `Offen: stützt sich auf ${criterion.dependsOn.map(describe).join(', ')}, selbst nicht eindeutig erkannt` + counts
  if (criterion.result === 'unresolved') return 'Offen: Datenlage reicht nicht aus' + counts
  if (criterion.method === 'label_structure') return 'Gleiche Beschriftung, aber Kinder und Nachbarn passen zu einem anderen Gegenstück; zur Prüfung offen gelassen'
  return (criterion.result === 'violated' ? 'Nicht erfüllt' : analysisValueLabel(criterion.result)) + counts
}

/** Why a check stays open, derived from its own evidence and the parser's completeness flag. */
export function factOpenReason(fact: AnalysisFact, graphsComplete: boolean | null) {
  if (fact.status !== 'unresolved') return null
  const evidence = fact.evidence
  if (evidence.reason === 'identity_unresolved') return 'Gegenstück nicht eindeutig identifiziert.'
  if (evidence.pathsUnambiguous === false) return 'Containerpfade sind nicht eindeutig bestimmbar.'
  const listed = (key: string) => Array.isArray(evidence[key]) ? (evidence[key] as unknown[]).length : 0
  const open = listed('unmatchedReferenceIds') + listed('unmatchedSubmissionIds') + listed('unresolvedReferenceIds')
  if (open) return `${open} beteiligte Objekte sind nicht eindeutig zugeordnet.`
  if (graphsComplete === false) return typeof evidence.expected === 'number' && evidence.expected === evidence.observed
    ? `Anzahl stimmt überein (${evidence.observed} / ${evidence.expected}), Vollständigkeit ist aber nicht bestätigt, weil mindestens ein Graph nur teilweise interpretierbar ist (Überblick › Datenqualität).`
    : 'Mindestens ein Graph ist nur teilweise interpretierbar; die Prüfung kann nicht abgeschlossen werden (Überblick › Datenqualität).'
  return null
}
