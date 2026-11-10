import type { Cell } from '@maxgraph/core'
import type { DiagramConnection } from '@/model/Connection'
import type { DiagramElement } from '@/model/Element'
import type { EdgeCardinality, MultiplicityCardinality, MultiplicityConfig, MultiplicityRelation } from '@/model/Syntax'
import { DEFAULT_CONNECTION_MESSAGE_TEMPLATES, renderEndpointMessage, renderValidationIssue, resolveQuantityMessage, type ValidationIssue } from './syntaxMessages'
import { elementTypeOf, endpointId, matchesEndpoint, pointId, pointLabel, pointsOf } from './connectionPoints'

export interface ConnectionEndpointContext {
  elements: DiagramElement[]
  connections: DiagramConnection[]
  endpointConfigs?: Map<string, MultiplicityConfig>
}

export interface ConnectionRuleContext extends ConnectionEndpointContext {
  config: MultiplicityConfig
  scopeElementTypes?: string[]
}

export const connectionTypeOf = (edge: Cell): string => (edge as any).connectionId ?? ''
const connectionOf = (context: ConnectionEndpointContext, edge: Cell) => context.connections.find((c) => c.type === (edge as any).connectionId)
const isUndirected = (context: ConnectionEndpointContext, edge: Cell) => {
  const definition = connectionOf(context, edge)
  return definition ? definition.undirected === true : (edge as any).connectionUndirected === true
}
const pointsFor = (context: ConnectionEndpointContext, cell: Cell) => context.elements.find((e) => e.type === elementTypeOf(cell))?.anchorPoints ?? pointsOf(cell)
const selectedType = (types: string[] | undefined, edge: Cell) => !types?.length || types.includes(connectionTypeOf(edge))
const outside = (count: number, bounds: MultiplicityCardinality, minimum: boolean) => (minimum && count < bounds.min) || (bounds.max !== null && count > bounds.max)

const incidentEdges = (cell: Cell): Cell[] => [...new Set(cell.getEdges().filter((e) => e.isEdge()))]
const ends = (edge: Cell): [Cell | null, Cell | null] => [edge.getTerminal(true), edge.getTerminal(false)]
const orientations = (context: ConnectionRuleContext, edge: Cell, source: Cell, target: Cell) => isUndirected(context, edge) && source !== target ? [[source, target, true], [target, source, false]] as const : [[source, target, true]] as const

/** A route of the individual mode behaves like a relation of its own, bound to its connection points. */
type EffectiveRelation = MultiplicityRelation & { routed?: boolean; label: string; routeName?: string }

export const effectiveRelations = (config: MultiplicityConfig): EffectiveRelation[] =>
  config.relations.flatMap((relation): EffectiveRelation[] => {
    const label = `${relation.sourceType} → ${relation.targetType}`
    const routes = relation.state === 'allowed' ? relation.refinement.routes : undefined
    if (!routes?.length) return [{ ...relation, label }]
    return routes.map((route, index) => ({
      ...relation,
      routed: true,
      routeName: route.name?.trim() || `route ${index + 1}`,
      label: `${label} (${route.name?.trim() || `route ${index + 1}`})`,
      refinement: { connectionTypes: route.connectionTypes, cardinality: route.cardinality, targetCardinality: route.targetCardinality, pairCardinality: route.pairCardinality, endpoints: [{ source: route.source, target: route.target }] }
    }))
  })

const endpointMatch = (context: ConnectionRuleContext, relation: MultiplicityRelation, edge: Cell, from: Cell, to: Cell, forward: boolean): boolean =>
  !relation.refinement.endpoints?.length || relation.refinement.endpoints.some((pair) => matchesEndpoint(pair.source, endpointId(edge, forward, from, pointsFor(context, from)), pointsFor(context, from)) && matchesEndpoint(pair.target, endpointId(edge, !forward, to, pointsFor(context, to)), pointsFor(context, to)))

const orientationMatches = (context: ConnectionRuleContext, relation: EffectiveRelation, edge: Cell, from: Cell, to: Cell, forward: boolean): boolean =>
  elementTypeOf(from) === relation.sourceType && elementTypeOf(to) === relation.targetType && endpointMatch(context, relation, edge, from, to, forward)

const matchesRelation = (context: ConnectionRuleContext, relation: EffectiveRelation, edge: Cell, source: Cell, target: Cell): boolean => {
  return selectedType(relation.refinement.connectionTypes, edge) && orientations(context, edge, source, target).some(([from, to, forward]) => orientationMatches(context, relation, edge, from, to, forward))
}

const countRelation = (context: ConnectionRuleContext, relation: EffectiveRelation, cell: Cell, scope: 'source' | 'target' | 'pair', ignored: Cell, other?: Cell): number => {
  return incidentEdges(cell).filter((edge) => {
    if (edge === ignored || edge === (ignored as any).replacesEdge) return false
    const [source, target] = ends(edge)
    if (!source || !target || !matchesRelation(context, relation, edge, source, target)) return false
    return orientations(context, edge, source, target).some(([from, to, forward]) => orientationMatches(context, relation, edge, from, to, forward) && (scope === 'target' ? to === cell : from === cell) && (scope !== 'pair' || to === other))
  }).length
}

const matchingEndIds = (context: ConnectionRuleContext, rule: EdgeCardinality, edge: Cell, source: Cell, target: Cell, cell: Cell): (string | null)[] => {
  if (!selectedType(rule.connectionTypes, edge)) return []
  const direction = rule.direction ?? 'incoming'
  const result: (string | null)[] = []
  for (const sourceEnd of [true, false]) {
    const terminal = sourceEnd ? source : target
    const neighbor = sourceEnd ? target : source
    if (terminal !== cell) continue
    if (!isUndirected(context, edge) && direction !== 'both' && (direction === 'outgoing') !== sourceEnd) continue
    if (rule.neighborTypes?.length && !rule.neighborTypes.includes(elementTypeOf(neighbor) ?? '')) continue
    const id = endpointId(edge, sourceEnd, cell, pointsFor(context, cell))
    if (matchesEndpoint(rule.endpoints, id, pointsFor(context, cell))) result.push(id)
  }
  return result
}

const buckets = (context: ConnectionRuleContext, rule: EdgeCardinality, cell: Cell): { label: string; matches: (id: string | null) => boolean }[] => {
  const points = pointsFor(context, cell)
  if (rule.countScope === 'point') return points.filter((p) => matchesEndpoint(rule.endpoints, pointId(p), points)).map((p) => ({ label: pointLabel(p), matches: (id) => id === pointId(p) }))
  if (rule.countScope === 'group') return (rule.endpoints?.groups ?? []).map((group) => ({ label: group, matches: (id) => points.some((p) => pointId(p) === id && p.groups?.includes(group)) }))
  return [{ label: 'all selected connections', matches: () => true }]
}

const connectionNames = (context: ConnectionEndpointContext, types: string[]): string[] =>
  types.map((type) => context.connections.find((connection) => connection.type === type)?.label || type)

const displayDirection = (context: ConnectionEndpointContext, direction: 'incoming' | 'outgoing' | 'both', types: string[]): NonNullable<ValidationIssue['quantity']>['direction'] => {
  if (direction === 'both') return direction
  const connections = context.connections.filter((connection) => !types.length || types.includes(connection.type))
  if (connections.length && connections.every((connection) => connection.undirected)) return 'undirected'
  return connections.some((connection) => connection.undirected) ? `${direction} or undirected` : direction
}

const elementNames = (context: ConnectionEndpointContext, types: string[]): string[] =>
  types.map((type) => context.elements.find((element) => element.type === type)?.defaultLabel?.trim() || type)

const selectorDescription = (context: ConnectionEndpointContext, type: string, selector?: import('@/model/Syntax').EndpointSelector): string => {
  const points = context.elements.find((element) => element.type === type)?.anchorPoints ?? []
  const names = (selector?.pointIds ?? []).map((id) => {
    const point = points.find((candidate) => pointId(candidate) === id)
    return point ? pointLabel(point) : id
  })
  return [...names, ...(selector?.groups ?? []).map((group) => `group ${group}`)].join(' or ')
}

const endpointDescription = (context: ConnectionEndpointContext, relation: EffectiveRelation): string => {
  const alternatives = (relation.refinement.endpoints ?? []).map((pair) => {
    const source = selectorDescription(context, relation.sourceType, pair.source)
    const target = selectorDescription(context, relation.targetType, pair.target)
    return [source && `source point ${source}`, target && `target point ${target}`].filter(Boolean).join(' and ')
  }).filter(Boolean)
  return alternatives.length ? `using ${alternatives.join(' or ')}` : ''
}

const chosenPoint = (context: ConnectionEndpointContext, edge: Cell, cell: Cell, source: boolean): string => {
  const points = pointsFor(context, cell)
  const id = endpointId(edge, source, cell, points)
  if (!id) return 'outline'
  const point = points.find((candidate) => pointId(candidate) === id)
  return point ? pointLabel(point) : 'missing point'
}

const limitIssues = (context: ConnectionRuleContext, cell: Cell, candidate?: { edge: Cell; source: Cell; target: Cell }, minimum = false): ValidationIssue[] => {
  const errors: ValidationIssue[] = []
  for (const rule of context.config.incoming ?? []) {
    if (!rule.elementType && context.scopeElementTypes && !context.scopeElementTypes.includes(elementTypeOf(cell) ?? '')) continue
    if (rule.elementType && rule.elementType !== elementTypeOf(cell)) continue
    for (const bucket of buckets(context, rule, cell)) {
      const count = incidentEdges(cell).filter((edge) => {
        if (edge === candidate?.edge || edge === (candidate?.edge as any)?.replacesEdge) return false
        const [source, target] = ends(edge)
        return source && target && matchingEndIds(context, rule, edge, source, target, cell).some(bucket.matches)
      }).length
      const addition = candidate && matchingEndIds(context, rule, candidate.edge, candidate.source, candidate.target, cell).some(bucket.matches) ? 1 : 0
      if ((!candidate || addition) && outside(count + addition, rule.cardinality, minimum)) {
        const template = resolveQuantityMessage(context.config.messageTemplate)
        const type = elementTypeOf(cell) ?? '*'
        const neighbors = rule.neighborTypes?.length ? rule.neighborTypes.join(', ') : '*'
        const direction = rule.direction ?? 'incoming'
        const displayedDirection = displayDirection(context, direction, rule.connectionTypes ?? [])
        const eitherEnd = neighbors === '*' ? '*' : [...new Set([type, ...rule.neighborTypes ?? []])].join(', ')
        const eitherDirection = direction === 'both' || displayedDirection !== direction
        const values: Record<string, string | number> = { source: eitherDirection ? eitherEnd : direction === 'incoming' ? neighbors : type, target: eitherDirection ? eitherEnd : direction === 'incoming' ? type : neighbors, connection: rule.connectionTypes?.length ? rule.connectionTypes.join(', ') : '*', min: rule.cardinality.min, max: rule.cardinality.max ?? '*' }
        const selectedPoints = selectorDescription(context, type, rule.endpoints)
        errors.push({
          kind: 'quantity', code: count + addition < rule.cardinality.min ? 'quantity.minimum' : 'quantity.maximum', cell, template,
          values: { ...values, count: count + addition, direction: displayedDirection, point: rule.countScope === 'point' || rule.countScope === 'group' ? bucket.label : selectedPoints || '*', scope: rule.countScope ?? 'element', route: '-' },
          quantity: { count: count + addition, bounds: rule.cardinality, scope: rule.countScope ?? 'element', direction: displayedDirection, connections: connectionNames(context, rule.connectionTypes ?? []), neighbors: elementNames(context, rule.neighborTypes ?? []), point: bucket.label, details: rule.countScope === 'element' || !rule.countScope ? selectedPoints && `at selected points or groups: ${selectedPoints}` : '', proposed: Boolean(candidate && !candidate.edge.getParent()) }
        })
      }
    }
  }
  return errors
}

const relationIssue = (context: ConnectionRuleContext, relation: EffectiveRelation, cell: Cell, scope: 'source' | 'target' | 'pair', bounds: MultiplicityCardinality, count: number, other?: Cell, proposed = false): ValidationIssue => ({
  kind: 'quantity', code: count < bounds.min ? 'quantity.minimum' : 'quantity.maximum', cell, other,
  template: resolveQuantityMessage(context.config.messageTemplate),
  values: { source: relation.sourceType, target: relation.targetType, connection: relation.refinement.connectionTypes.join(', ') || '*', min: bounds.min, max: bounds.max ?? '*', count, direction: displayDirection(context, scope === 'target' ? 'incoming' : 'outgoing', relation.refinement.connectionTypes), point: endpointDescription(context, relation).replace(/^using /, '') || '*', scope, route: relation.routeName ?? '-' },
  quantity: { count, bounds, scope, direction: displayDirection(context, scope === 'target' ? 'incoming' : 'outgoing', relation.refinement.connectionTypes), connections: connectionNames(context, relation.refinement.connectionTypes), neighbors: scope === 'pair' ? [] : elementNames(context, [scope === 'target' ? relation.sourceType : relation.targetType]), details: endpointDescription(context, relation), proposed }
})

const connectionIssue = (context: ConnectionEndpointContext, code: 'connection.forbidden' | 'connection.type' | 'connection.endpoint', template: string, source: Cell, target: Cell, edge: Cell, extra: Record<string, string> = {}): ValidationIssue => ({
  kind: 'connection', code, source, target, template,
  values: { source: elementTypeOf(source) ?? '-', target: elementTypeOf(target) ?? '-', connection: connectionOf(context, edge)?.label || connectionTypeOf(edge) || 'connection', ...extra }
})

/** One decision path for dragging, reconnecting, graph validation and suggestions. Minima are checked separately. */
export const connectionEndpointErrors = (context: ConnectionEndpointContext, edge: Cell, source: Cell, target: Cell): string[] => {
  if (!elementTypeOf(source) || !elementTypeOf(target) || (source as any).cellRole === 'feedback' || (target as any).cellRole === 'feedback') return []
  const errors: string[] = []
  if (source === target && !connectionOf(context, edge)?.allowLoops) errors.push(renderEndpointMessage('loop', context.endpointConfigs?.get(elementTypeOf(source) ?? '')?.endpointMessages, source, { connection: connectionOf(context, edge)?.label || connectionTypeOf(edge) || 'this connection' }))
  for (const [cell, sourceEnd] of [[source, true], [target, false]] as const) {
    const points = pointsFor(context, cell)
    const templates = context.endpointConfigs?.get(elementTypeOf(cell) ?? '')?.endpointMessages
    const id = endpointId(edge, sourceEnd, cell, points)
    const point = points.find((p) => pointId(p) === id)
    if (id && !point) errors.push(renderEndpointMessage('missingPoint', templates, cell))
    const element = context.elements.find((e) => e.type === elementTypeOf(cell))
    if (element?.connectable === false) errors.push(renderEndpointMessage('notConnectable', templates, cell))
    // Older language versions allowed outline connections without an explicit docking mode.
    if (element?.docking === 'anchors' && points.length && !id) errors.push(renderEndpointMessage('pointRequired', templates, cell))
    if (!isUndirected(context, edge) && point?.role && point.role !== 'bidirectional' && (point.role === 'output') !== sourceEnd) errors.push(renderEndpointMessage('pointDirection', templates, cell, { point: pointLabel(point), direction: sourceEnd ? 'outgoing' : 'incoming' }))
  }

  return [...new Set(errors)]
}

export const connectionErrors = (context: ConnectionRuleContext, edge: Cell, source: Cell, target: Cell): string[] => {
  return [...new Set(connectionIssues(context, edge, source, target).map(renderValidationIssue))]
}

export const connectionIssues = (context: ConnectionRuleContext, edge: Cell, source: Cell, target: Cell): ValidationIssue[] => {
  if (!elementTypeOf(source) || !elementTypeOf(target) || (source as any).cellRole === 'feedback' || (target as any).cellRole === 'feedback') return []
  const errors: ValidationIssue[] = []
  const applicable = orientations(context, edge, source, target).flatMap(([from, to, forward]) => effectiveRelations(context.config).filter((r) => r.sourceType === elementTypeOf(from) && r.targetType === elementTypeOf(to)).map((relation) => ({ relation, from, to, forward })))
  const inScope = !context.scopeElementTypes || [source, target].every((cell) => context.scopeElementTypes!.includes(elementTypeOf(cell) ?? ''))
  if (applicable.some(({ relation }) => relation.state === 'forbidden') || (!applicable.length && inScope && context.config.defaultState === 'forbidden')) return [connectionIssue(context, 'connection.forbidden', context.config.forbiddenMessageTemplate?.trim() || DEFAULT_CONNECTION_MESSAGE_TEMPLATES.forbiddenMessageTemplate, source, target, edge)]
  const allowed = applicable.filter(({ relation }) => relation.state === 'allowed' && selectedType(relation.refinement.connectionTypes, edge))
  if (applicable.length && !allowed.length) {
    const types = [...new Set(applicable.filter(({ relation }) => relation.state === 'allowed').flatMap(({ relation }) => relation.refinement.connectionTypes))]
    return [connectionIssue(context, 'connection.type', context.config.connectionTypeMessageTemplate?.trim() || DEFAULT_CONNECTION_MESSAGE_TEMPLATES.connectionTypeMessageTemplate, source, target, edge, { allowedConnections: connectionNames(context, types).join(', ') })]
  }

  const endpointAllowed = !allowed.length || allowed.some(({ relation, from, to, forward }) => endpointMatch(context, relation, edge, from, to, forward))
  if (!endpointAllowed) errors.push(connectionIssue(context, 'connection.endpoint', context.config.endpointMessageTemplate?.trim() || DEFAULT_CONNECTION_MESSAGE_TEMPLATES.endpointMessageTemplate, source, target, edge, { sourcePoint: chosenPoint(context, edge, source, true), targetPoint: chosenPoint(context, edge, target, false), allowedPoints: [...new Set(allowed.map(({ relation }) => endpointDescription(context, relation)).filter(Boolean))].join(' or ') }))

  for (const { relation, from, to, forward } of allowed) {
    if (relation.routed && !endpointMatch(context, relation, edge, from, to, forward)) continue
    const r = relation.refinement
    for (const [scope, cell, bounds] of [['source', from, r.cardinality], ['target', to, r.targetCardinality], ['pair', from, r.pairCardinality]] as const) {
      if (!bounds) continue
      const count = countRelation(context, relation, cell, scope, edge, to) + 1
      if (outside(count, bounds, false)) errors.push(relationIssue(context, relation, cell, scope, bounds, count, scope === 'pair' ? to : undefined, !edge.getParent()))
    }
  }
  for (const cell of new Set([source, target])) errors.push(...limitIssues(context, cell, { edge, source, target }))
  return errors
}

export const elementConnectionErrors = (context: ConnectionRuleContext, cell: Cell): string[] => {
  return elementConnectionIssues(context, cell).map(renderValidationIssue)
}

export const elementConnectionIssues = (context: ConnectionRuleContext, cell: Cell): ValidationIssue[] => {
  if (!elementTypeOf(cell) || !cell.isVertex() || !cell.isConnectable() || (cell as any).cellRole === 'feedback') return []
  const errors = limitIssues(context, cell, undefined, true)
  for (const relation of effectiveRelations(context.config).filter((r) => r.state === 'allowed')) {
    for (const [scope, type, bounds] of [['source', relation.sourceType, relation.refinement.cardinality], ['target', relation.targetType, relation.refinement.targetCardinality]] as const) {
      if (!bounds || type !== elementTypeOf(cell)) continue
      // The ignored edge is detached; it cannot remove a real connection from the count.
      const count = countRelation(context, relation, cell, scope, {} as Cell)
      if (outside(count, bounds, true)) errors.push(relationIssue(context, relation, cell, scope, bounds, count))
    }
    // Pair minima apply to existing pairs, not to every possible pair of instances.
    if (relation.refinement.pairCardinality && elementTypeOf(cell) === relation.sourceType) {
      const neighbors = new Set(incidentEdges(cell).flatMap((edge) => {
        const [source, target] = ends(edge)
        return source && target && matchesRelation(context, relation, edge, source, target) ? orientations(context, edge, source, target).filter(([from, to, forward]) => from === cell && orientationMatches(context, relation, edge, from, to, forward)).map(([, to]) => to) : []
      }))
      for (const neighbor of neighbors) {
        const count = countRelation(context, relation, cell, 'pair', {} as Cell, neighbor)
        if (outside(count, relation.refinement.pairCardinality, true)) errors.push(relationIssue(context, relation, cell, 'pair', relation.refinement.pairCardinality, count, neighbor))
      }
    }
  }
  return errors
}

export const connectionConfigErrors = (context: ConnectionRuleContext): string[] => {
  const errors: string[] = []
  for (const element of context.elements) {
    const ids = element.anchorPoints.map(pointId)
    if (new Set(ids).size !== ids.length) errors.push(`${element.type}: connection point identities must be unique.`)
  }
  const checkBounds = (bounds: MultiplicityCardinality, label: string) => {
    if (!Number.isInteger(bounds.min) || bounds.min < 0 || (bounds.max !== null && (!Number.isInteger(bounds.max) || bounds.max < bounds.min))) errors.push(`${label}: use whole numbers with 0 ≤ minimum ≤ maximum.`)
  }
  const checkSelector = (selector: import('@/model/Syntax').EndpointSelector | undefined, type: string, label: string) => {
    const points = context.elements.filter((e) => !type || e.type === type).flatMap((e) => e.anchorPoints ?? [])
    for (const id of selector?.pointIds ?? []) if (!points.some((p) => pointId(p) === id)) errors.push(`${label}: connection point ${id} no longer exists.`)
    for (const group of selector?.groups ?? []) if (!points.some((p) => p.groups?.includes(group))) errors.push(`${label}: connection point group ${group} no longer exists.`)
  }
  const knownTypes = new Set(context.connections.map((c) => c.type))
  const checkTypes = (types: string[] | undefined, label: string) => { for (const type of types ?? []) if (!knownTypes.has(type)) errors.push(`${label}: connection type ${type} no longer exists.`) }
  for (const r of effectiveRelations(context.config)) {
    if (r.state !== 'allowed') continue
    const label = r.label
    if (![r.sourceType, r.targetType].every((type) => context.elements.some((e) => e.type === type))) errors.push(`${label}: element type no longer exists.`)
    for (const bounds of [r.refinement.cardinality, r.refinement.targetCardinality, r.refinement.pairCardinality]) if (bounds) checkBounds(bounds, label)
    checkTypes(r.refinement.connectionTypes, label)
    for (const pair of r.refinement.endpoints ?? []) { checkSelector(pair.source, r.sourceType, label); checkSelector(pair.target, r.targetType, label) }
    const opposite = context.config.relations.find((other) => other.sourceType === r.targetType && other.targetType === r.sourceType && other.state === 'forbidden')
    if (opposite && context.connections.some((c) => c.undirected && (!r.refinement.connectionTypes.length || r.refinement.connectionTypes.includes(c.type)))) errors.push(`${label}: an undirected connection conflicts with the forbidden reverse combination.`)
    for (const rule of context.config.incoming ?? []) {
      if (rule.countScope && rule.countScope !== 'element') continue
      if (rule.endpoints?.pointIds?.length || rule.endpoints?.groups?.length || rule.neighborTypes?.length) continue
      // A total across all connection types cannot be smaller than a required subset.
      if (rule.connectionTypes?.length) continue
      const direction = rule.direction ?? 'incoming'
      const sourceLimit = (!rule.elementType || rule.elementType === r.sourceType) && direction !== 'incoming'
      const targetLimit = (!rule.elementType || rule.elementType === r.targetType) && direction !== 'outgoing'
      if (rule.cardinality.max !== null && ((sourceLimit && r.refinement.cardinality.min > rule.cardinality.max) || (targetLimit && (r.refinement.targetCardinality?.min ?? 0) > rule.cardinality.max))) errors.push(`${label}: the required minimum exceeds a total connection limit.`)
    }
  }
  for (const rule of context.config.incoming ?? []) {
    checkBounds(rule.cardinality, rule.elementType || 'All elements')
    checkSelector(rule.endpoints, rule.elementType, 'Connection limit')
    checkTypes(rule.connectionTypes, 'Connection limit')
    if (rule.elementType && !context.elements.some((e) => e.type === rule.elementType)) errors.push(`Connection limit: element type ${rule.elementType} no longer exists.`)
    for (const type of rule.neighborTypes ?? []) if (!context.elements.some((e) => e.type === type)) errors.push(`Connection limit: neighbor type ${type} no longer exists.`)
    if (rule.countScope === 'point' && !context.elements.some((e) => (!rule.elementType || e.type === rule.elementType) && e.anchorPoints.some((p) => matchesEndpoint(rule.endpoints, pointId(p), e.anchorPoints)))) errors.push('A point limit needs at least one matching connection point.')
    if (rule.countScope === 'group' && !rule.endpoints?.groups?.length) errors.push('A group limit needs at least one connection point group.')
  }
  const limits = context.config.incoming ?? []
  const limitKey = (rule: EdgeCardinality) => JSON.stringify([rule.elementType, rule.direction ?? 'incoming', rule.countScope ?? 'element', [...rule.connectionTypes ?? []].sort(), [...rule.neighborTypes ?? []].sort(), [...rule.endpoints?.pointIds ?? []].sort(), [...rule.endpoints?.groups ?? []].sort()])
  for (let index = 0; index < limits.length; index++) {
    const matching = limits.filter((rule) => limitKey(rule) === limitKey(limits[index]))
    const min = Math.max(...matching.map((r) => r.cardinality.min))
    const max = Math.min(...matching.map((r) => r.cardinality.max ?? Infinity))
    if (min > max) errors.push(`${limits[index].elementType || 'All elements'}: overlapping connection limits contradict each other.`)
  }
  return [...new Set(errors)]
}
