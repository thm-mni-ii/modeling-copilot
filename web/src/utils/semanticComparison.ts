import type { JsonObject } from '@/services/api/types/common'

export interface ComparisonMethod {
  name: string
  label: string
  scoreRange?: [number, number]
  missingMetadata?: boolean
}

export interface SemanticCandidate {
  id: string
  label: string
  scores: JsonObject
  comparisonBasis: string
  scoreStatus: string
  unavailableReason: string
  referenceOwnerId: string
  submissionOwnerId: string
  kind: string
  connectionLabelId: string
}

export interface SemanticReference {
  id: string
  label: string
  candidates: SemanticCandidate[]
}

const object = (value: unknown): JsonObject => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonObject : {}
const list = (value: unknown): JsonObject[] => Array.isArray(value) ? value.map(object) : []
const text = (value: unknown): string => typeof value === 'string' ? value : ''
export const semanticScore = (candidate: SemanticCandidate, method: string): number | undefined => {
  const value = candidate.scores[method]
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export const semanticComparisonResult = (value: unknown): JsonObject | undefined => {
  const data = object(value)
  if (data.schema === 'semantic-candidates/v1') return data
  const result = object(data.result)
  return result.schema === 'semantic-candidates/v1' ? result : undefined
}

/** Adapt both matrices to the same view model without changing the evidence. */
export const prepareSemanticComparison = (result: JsonObject) => {
  const processed = object(result.processedTexts)
  const labels = (side: string) => new Map(list(processed[side]).map((entry) => [text(entry.id), text(entry.text)]))
  const referenceLabels = labels('reference')
  const submissionLabels = labels('student')
  const label = (value: unknown, id: string, fallback: Map<string, string>) => typeof value === 'string' ? value : fallback.get(id) ?? ''
  const candidate = (entry: JsonObject, id: string): SemanticCandidate => ({
    id,
    label: label(entry.submissionLabel, id, submissionLabels),
    scores: object(entry.scores),
    comparisonBasis: text(entry.comparisonBasis),
    scoreStatus: text(entry.scoreStatus),
    unavailableReason: text(entry.unavailableReason),
    referenceOwnerId: text(entry.referenceOwnerConnectionId),
    submissionOwnerId: text(entry.submissionOwnerConnectionId),
    kind: text(entry.kind),
    connectionLabelId: text(entry.connectionLabelId)
  })
  const elements: SemanticReference[] = list(result.synonymMatrix).map((row) => {
    const id = text(row.referenceElementId)
    return { id, label: label(row.referenceLabel, id, referenceLabels), candidates: list(row.matches).map((entry) => candidate(entry, text(entry.submissionElementId))) }
  })
  const connections = new Map<string, SemanticReference>()
  for (const entry of list(result.connectionTextMatrix)) {
    const id = text(entry.referenceConnectionTextId)
    let reference = connections.get(id)
    if (!reference) {
      reference = { id, label: label(entry.referenceLabel, id, referenceLabels), candidates: [] }
      connections.set(id, reference)
    }
    reference.candidates.push(candidate(entry, text(entry.submissionConnectionTextId)))
  }
  const methods: ComparisonMethod[] = []
  const names = new Set<string>()
  for (const entry of list(result.methods)) {
    const name = text(entry.name)
    if (!name || names.has(name)) continue
    names.add(name)
    const range = entry.scoreRange
    methods.push({ name, label: text(entry.displayName) || text(entry.label) || name,
      scoreRange: Array.isArray(range) && range.length === 2 && range.every((value) => typeof value === 'number' && Number.isFinite(value)) ? range as [number, number] : undefined })
  }
  // Preserve scores even when an older result omitted their method metadata.
  for (const reference of [...elements, ...connections.values()]) {
    for (const entry of reference.candidates) {
      for (const name of Object.keys(entry.scores)) {
        if (names.has(name)) continue
        names.add(name)
        methods.push({ name, label: name, missingMetadata: true })
      }
    }
  }
  return { methods, elements, connections: [...connections.values()] }
}
