import { InternalEvent, Multiplicity, type Cell, type Graph } from '@maxgraph/core'
import type { DiagramSyntax, MultiplicityRelation } from '@/model/Syntax'
import { setValidationPassActive } from '@/utils/graphValidationRuntime'

export type ValidationCheckType = 'ElementCheck' | 'ConnectionCheck' | 'MultiplicityCheck'

const DEFAULT_MESSAGE_TEMPLATE = 'The Connection {source} -> {target} with Connection type {connection} violates the cardinality ({min}..{max}).'
const FORBIDDEN_CONNECTION_MESSAGE_TEMPLATE = 'The Connection {source} -> {target} with Connection type {connection} is forbidden.'
const UNSUPPORTED_CONNECTION_TYPE_MESSAGE_TEMPLATE = 'The Connection {source} -> {target} does not allow Connection type {connection}.'
const ORIGINAL_CELL_VALIDATION_KEY = Symbol('originalCellValidation')
const LIVE_VALIDATION_LISTENER_KEY = Symbol('liveValidationListener')

type PatchedGraph = Graph & {
  [ORIGINAL_CELL_VALIDATION_KEY]?: (cell: Cell) => string | null
  [LIVE_VALIDATION_LISTENER_KEY]?: () => void
}

export interface ValidatorApplyOptions {
  liveValidation?: boolean
}

const normalizeMessages = (warning: string | null): string[] => {
  if (!warning) return []
  return warning
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

const combineErrors = (first: string | null, second: string | null): string | null => {
  if (first && second) return `${first}${second}`
  return first ?? second
}

const asMaxLabel = (value: number | null): string => (value === null ? '*' : String(value))

const findTypedCell = (cell: Cell | null): Cell | null => {
  let current: Cell | null = cell
  while (current) {
    const explicitType = (current as any).diagramElementType
    const attributesType = (current as any).diagramAttributes?.type
    const value = current.getValue()
    const valueType = value && typeof value === 'object' && 'type' in value ? (value as any).type : null

    if ((typeof explicitType === 'string' && explicitType.length > 0) || (typeof attributesType === 'string' && attributesType.length > 0) || (typeof valueType === 'string' && valueType.length > 0)) {
      return current
    }

    current = current.getParent()
  }

  return null
}

const getElementType = (cell: Cell | null): string | null => {
  const typedCell = findTypedCell(cell)
  if (!typedCell) return null

  const explicitType = (typedCell as any).diagramElementType
  if (typeof explicitType === 'string' && explicitType.length > 0) return explicitType

  const attributesType = (typedCell as any).diagramAttributes?.type
  if (typeof attributesType === 'string' && attributesType.length > 0) {
    return attributesType
  }

  const value = typedCell.getValue()
  if (value && typeof value === 'object' && 'type' in value && typeof (value as any).type === 'string') {
    return (value as any).type
  }

  return null
}

const getConnectionType = (edge: Cell | null): string | null => {
  if (!edge) return null

  const semanticType = (edge as any).connectionType
  if (typeof semanticType === 'string' && semanticType.length > 0) {
    return semanticType
  }

  const connectionId = (edge as any).connectionId
  if (typeof connectionId === 'string' && connectionId.length > 0) {
    return connectionId
  }

  return null
}

const fillTemplate = (template: string, payload: Record<string, string | number>): string => {
  let result = template
  for (const [key, value] of Object.entries(payload)) {
    result = result.split(`{${key}}`).join(String(value))
  }
  return result
}

export class DiagramValidationRule {
  readonly checkType: ValidationCheckType

  constructor(checkType: ValidationCheckType) {
    this.checkType = checkType
  }
}

class DiagramMultiplicity extends Multiplicity {
  readonly relation: MultiplicityRelation

  private readonly messageTemplate: string

  constructor(relation: MultiplicityRelation, messageTemplate: string) {
    super(true, relation.sourceType, null, null, relation.refinement.cardinality.min, relation.refinement.cardinality.max ?? Number.MAX_VALUE, [relation.targetType], '', '', true)
    this.relation = relation
    this.messageTemplate = messageTemplate.trim().length > 0 ? messageTemplate : DEFAULT_MESSAGE_TEMPLATE
  }

  private isConnectionTypeAllowed(edge: Cell | null): boolean {
    const selectedTypes = this.relation.refinement.connectionTypes
    if (selectedTypes.length === 0) return true
    const connectionType = getConnectionType(edge)
    if (!connectionType) return false
    return selectedTypes.includes(connectionType)
  }

  private countMatchingOutgoing(source: Cell, ignoredEdge?: Cell | null): number {
    const sourceForCount = source.getEdgeCount() > 0 ? source : findTypedCell(source) ?? source
    let count = 0
    const edgeCount = sourceForCount.getEdgeCount()

    for (let index = 0; index < edgeCount; index += 1) {
      const edge = sourceForCount.getEdgeAt(index)
      if (!edge || edge === ignoredEdge || !edge.isEdge()) continue

      const currentSource = edge.getTerminal(true)
      const currentTarget = edge.getTerminal(false)
      if (!currentSource || !currentTarget) continue
      if (getElementType(currentSource) !== this.relation.sourceType) continue

      const targetType = getElementType(currentTarget)
      if (targetType !== this.relation.targetType) continue
      if (!this.isConnectionTypeAllowed(edge)) continue

      count += 1
    }

    return count
  }

  private renderMessage(sourceType: string, targetType: string, connectionType: string, min: number, max: number | null): string {
    return fillTemplate(this.messageTemplate, {
      source: sourceType,
      target: targetType,
      connection: connectionType,
      min,
      max: asMaxLabel(max)
    })
  }

  private renderConnectionMessage(template: string, sourceType: string, targetType: string, connectionType: string): string {
    return fillTemplate(template, {
      source: sourceType,
      target: targetType,
      connection: connectionType
    })
  }

  override check(_graph: Graph, edge: Cell, source: Cell, target: Cell): string | null {
    const sourceType = getElementType(source)
    const targetType = getElementType(target)

    if (sourceType !== this.relation.sourceType || targetType !== this.relation.targetType) {
      return null
    }

    const connectionType = getConnectionType(edge) ?? '-'

    if (this.relation.state === 'forbidden') {
      return `${this.renderConnectionMessage(FORBIDDEN_CONNECTION_MESSAGE_TEMPLATE, sourceType, targetType, connectionType)}\n`
    }

    if (!this.isConnectionTypeAllowed(edge)) {
      return `${this.renderConnectionMessage(UNSUPPORTED_CONNECTION_TYPE_MESSAGE_TEMPLATE, sourceType, targetType, connectionType)}\n`
    }

    const max = this.relation.refinement.cardinality.max
    if (max === null) return null

    const currentCount = this.countMatchingOutgoing(source, edge)
    const nextCount = currentCount + 1

    if (nextCount > max) {
      return `${this.renderMessage(sourceType, targetType, connectionType, this.relation.refinement.cardinality.min, max)}\n`
    }

    return null
  }

  checkTerminalCardinality(cell: Cell): string | null {
    if (this.relation.state !== 'allowed') return null

    const sourceType = getElementType(cell)
    if (sourceType !== this.relation.sourceType) return null

    const count = this.countMatchingOutgoing(cell)
    const { min, max } = this.relation.refinement.cardinality

    if (count < min || (max !== null && count > max)) {
      return `${this.renderMessage(this.relation.sourceType, this.relation.targetType, '*', min, max)}\n`
    }

    return null
  }
}

class MultiplicityValidationRule extends DiagramValidationRule {
  readonly multiplicities: DiagramMultiplicity[]

  constructor(multiplicities: DiagramMultiplicity[]) {
    super('MultiplicityCheck')
    this.multiplicities = multiplicities
  }
}

export class DiagramValidator {
  private rules: DiagramValidationRule[] = []

  addRules(rules: DiagramValidationRule[]): void {
    this.rules = rules
  }

  private runValidationPass(graph: PatchedGraph): string | null {
    setValidationPassActive(graph, true)
    try {
      return graph.validateGraph()
    } finally {
      setValidationPassActive(graph, false)
    }
  }

  applyToGraph(graph: Graph, options?: ValidatorApplyOptions): void {
    const typedGraph = graph as PatchedGraph
    const liveValidation = options?.liveValidation ?? true
    const multiplicities = this.rules.filter((rule): rule is MultiplicityValidationRule => rule instanceof MultiplicityValidationRule).flatMap((rule) => rule.multiplicities)

    graph.multiplicities.length = 0
    graph.multiplicities.push(...multiplicities)

    if (typedGraph[ORIGINAL_CELL_VALIDATION_KEY] == null) {
      typedGraph[ORIGINAL_CELL_VALIDATION_KEY] = graph.getCellValidationError.bind(graph)
    }

    if (multiplicities.length === 0) {
      if (typedGraph[ORIGINAL_CELL_VALIDATION_KEY]) {
        graph.getCellValidationError = typedGraph[ORIGINAL_CELL_VALIDATION_KEY]
      }
      if (typedGraph[LIVE_VALIDATION_LISTENER_KEY]) {
        graph.getDataModel().removeListener(typedGraph[LIVE_VALIDATION_LISTENER_KEY])
        typedGraph[LIVE_VALIDATION_LISTENER_KEY] = undefined
      }
      return
    }

    graph.getCellValidationError = (cell: Cell) => {
      const baseError = typedGraph[ORIGINAL_CELL_VALIDATION_KEY]?.(cell) ?? null

      let multiplicityError: string | null = null
      for (const multiplicity of multiplicities) {
        multiplicityError = combineErrors(multiplicityError, multiplicity.checkTerminalCardinality(cell))
      }

      return combineErrors(baseError, multiplicityError)
    }

    if (typedGraph[LIVE_VALIDATION_LISTENER_KEY]) {
      graph.getDataModel().removeListener(typedGraph[LIVE_VALIDATION_LISTENER_KEY])
      typedGraph[LIVE_VALIDATION_LISTENER_KEY] = undefined
    }

    if (!liveValidation) {
      return
    }

    typedGraph[LIVE_VALIDATION_LISTENER_KEY] = () => {
      this.runValidationPass(typedGraph)
    }
    graph.getDataModel().addListener(InternalEvent.CHANGE, typedGraph[LIVE_VALIDATION_LISTENER_KEY])
    this.runValidationPass(typedGraph)
  }

  validateGraph(graph: Graph): string[] {
    const warning = this.runValidationPass(graph as PatchedGraph)
    return normalizeMessages(warning)
  }
}

export const buildValidationRulesFromSyntax = (rules: DiagramSyntax[] | null | undefined): DiagramValidationRule[] => {
  if (!rules || rules.length === 0) {
    return []
  }

  const multiplicities: DiagramMultiplicity[] = []

  for (const rule of rules) {
    if (rule.ruleType !== 'multiplicity') continue

    const template = rule.config.messageTemplate

    for (const relation of rule.config.relations) {
      multiplicities.push(new DiagramMultiplicity(relation, template))
    }
  }

  return multiplicities.length > 0 ? [new MultiplicityValidationRule(multiplicities)] : []
}
