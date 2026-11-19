import { GraphDataModel, type Cell, type Graph } from '@maxgraph/core'
import { importModelFromXml } from './modelPersistence'
import type { AdaptedAnalysis, AnalysisAnnotation } from './analysisFeedback'

interface SemanticCell { own: string; parent: string | null; children: string[]; source: string | null; target: string | null; peerKey: string }
type SemanticModel = Map<string, SemanticCell>
export interface FeedbackValidity { changed: boolean; currentIds: Set<string> }

const canonical = (value: unknown): unknown => {
  if (value == null || typeof value !== 'object') return value
  if (value instanceof Node) return new XMLSerializer().serializeToString(value)
  if (Array.isArray(value)) return value.map(canonical)
  return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)]))
}
const encode = (value: unknown) => JSON.stringify(canonical(value))

/** Geometry, colours and view state do not change the facts of an evaluation. */
export const feedbackSemanticModel = (model: Pick<GraphDataModel, 'getRoot'>): SemanticModel => {
  const result: SemanticModel = new Map()
  const visit = (cell: Cell, feedback = false) => {
    const fields = cell as unknown as Record<string, unknown>
    feedback ||= fields.cellRole === 'feedback' || fields.canvasRole === 'feedback'
    const id = cell.getId()
    if (!feedback && id && (cell.isVertex() || cell.isEdge())) {
      const properties = Object.fromEntries(['diagramAttributes', 'diagramElementType', 'connectionId', 'connectionLabelId',
        'connectionUndirected', 'languageId', 'languageVersionId', 'comparisonRole', 'cellRole', 'canvasRole'].map(key => [key, fields[key]]))
      const parent = cell.getParent()?.getId() ?? null
      const source = cell.getTerminal(true)?.getId() ?? null, target = cell.getTerminal(false)?.getId() ?? null
      const value = cell.getValue()
      const attributes = properties.diagramAttributes as Record<string, unknown> | undefined
      result.set(id, { own: encode({ value, properties, vertex: cell.isVertex(), edge: cell.isEdge(), parent, source, target,
        fontStyle: Number(cell.getStyle()?.fontStyle ?? 0) }), parent, source, target,
        children: cell.getChildren().map(child => child.getId()).filter((id): id is string => !!id).sort(),
        peerKey: encode([properties.diagramElementType ?? attributes?.type, properties.connectionId,
          properties.languageId ?? attributes?.languageId, properties.languageVersionId ?? attributes?.languageVersionId,
          value ?? attributes?.label]) })
    }
    for (const child of cell.getChildren()) visit(child, feedback)
  }
  const root = model.getRoot()
  if (root) visit(root)
  for (const cell of result.values()) cell.children = cell.children.filter(id => result.has(id))
  return result
}

const scope = (model: SemanticModel, id: string) => {
  const cell = model.get(id)
  if (!cell) return null
  const descendants = new Set<string>(), ancestors = new Set<string>()
  const collect = (childId: string) => {
    if (descendants.has(childId)) return
    descendants.add(childId)
    for (const child of model.get(childId)?.children ?? []) collect(child)
  }
  for (const child of cell.children) collect(child)
  let parent = cell.parent
  while (parent && model.has(parent) && !ancestors.has(parent)) { ancestors.add(parent); parent = model.get(parent)!.parent }
  const related = [...model].filter(([, entry]) => entry.source === id || entry.target === id)
  const endpoints = [cell.source, cell.target, ...related.flatMap(([, edge]) => [edge.source, edge.target])].filter((id): id is string => !!id)
  const values = (ids: Iterable<string>) => [...ids].sort().map(key => [key, model.get(key)?.own ?? null])
  return encode({ own: cell.own, children: values(descendants), parents: values(ancestors),
    connections: related.map(([key]) => key).sort(), endpoints: values(endpoints),
    edgeValues: related.map(([key, edge]) => [key, edge.own]).sort(),
    peers: [...model].filter(([, entry]) => entry.peerKey === cell.peerKey).map(([key]) => key).sort() })
}

export const compareFeedbackModel = (baseline: SemanticModel | null, current: SemanticModel): FeedbackValidity => {
  if (!baseline) return { changed: true, currentIds: new Set() }
  const changed = baseline.size !== current.size || [...baseline].some(([id, cell]) => current.get(id)?.own !== cell.own)
  if (!changed) return { changed: false, currentIds: new Set(baseline.keys()) }
  return { changed, currentIds: new Set([...baseline.keys()].filter(id => current.has(id) && scope(baseline, id) === scope(current, id))) }
}

export const createFeedbackValidity = (xml: string | null | undefined) => {
  let baseline: SemanticModel | null = null
  if (xml) try {
    const model = new GraphDataModel()
    importModelFromXml({ getDataModel: () => model } as Graph, xml)
    baseline = feedbackSemanticModel(model)
  } catch { /* Unreadable snapshots cannot authorize markers on the edited graph. */ }
  return (graph: Graph): FeedbackValidity => {
    try { return compareFeedbackModel(baseline, feedbackSemanticModel(graph.getDataModel())) }
    catch { return { changed: true, currentIds: new Set() } }
  }
}

/** Published dependency IDs supplement the local structural neighbourhood. */
export const currentAnalysis = (analysis: AdaptedAnalysis, validity: FeedbackValidity): AdaptedAnalysis => {
  if (!validity.changed) return analysis
  const valid = (ids: string[]) => ids.every(id => validity.currentIds.has(id))
  const applies = (item: AnalysisAnnotation) => valid([item.target.id,
    ...(item.dependencies ?? []).map(dep => dep.studentId), ...(item.match?.dependsOn ?? []).map(dep => dep.submissionId),
    ...(item.identity?.criteria ?? []).flatMap(criterion => [...(criterion.submissionIds ?? []), ...(criterion.dependsOn ?? []).map(dep => dep.studentId)]),
    ...(item.facts ?? []).flatMap(fact => fact.submissionIds),
    ...item.hints.flatMap(hint => (hint.targets ?? []).filter(target => target.side === 'submission').map(target => target.id))])
  return { ...analysis, report: { ...analysis.report,
    annotations: analysis.report.annotations.filter(applies),
    // Absence/completeness claims may depend on model-wide matching.
    referenceHints: validity.changed ? [] : analysis.report.referenceHints,
    connectionGroups: analysis.report.connectionGroups?.filter(group => valid([...group.submissionIds, ...group.submissionEndpointIds])) } }
}
