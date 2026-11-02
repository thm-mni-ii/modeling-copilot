import { InternalEvent, Multiplicity, type Cell, type Graph } from '@maxgraph/core'
import type { DiagramSyntax } from '@/model/Syntax'
import type { DiagramElement } from '@/model/Element'
import type { DiagramConnection } from '@/model/Connection'
import { connectionErrors, elementConnectionErrors, type ConnectionRuleContext } from './connectionRules'
import { clearValidationWarningOverlays, setValidationPassActive } from '@/utils/graphValidationRuntime'

export type ValidationCheckType = 'ElementCheck' | 'ConnectionCheck' | 'MultiplicityCheck'

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

export const getConnectionType = (edge: Cell | null): string | null => {
  if (!edge) return null

  const connectionId = (edge as any).connectionId
  if (typeof connectionId === 'string' && connectionId.length > 0) {
    return connectionId
  }

  return null
}

export class DiagramValidationRule {
  readonly checkType: ValidationCheckType

  constructor(checkType: ValidationCheckType) {
    this.checkType = checkType
  }
}

class ConnectionMultiplicity extends Multiplicity {
  constructor(private readonly context: ConnectionRuleContext) {
    super(true, '*', null, null, 0, Number.MAX_VALUE, [], '', '', true)
  }

  override check(_graph: Graph, edge: Cell, source: Cell, target: Cell): string | null {
    const errors = connectionErrors(this.context, edge, source, target)
    return errors.length ? errors.join('\n') + '\n' : null
  }

  checkTerminalCardinality(cell: Cell): string | null {
    const errors = elementConnectionErrors(this.context, cell)
    return errors.length ? errors.join('\n') + '\n' : null
  }
}

class MultiplicityValidationRule extends DiagramValidationRule {
  readonly multiplicities: ConnectionMultiplicity[]

  constructor(multiplicities: ConnectionMultiplicity[]) {
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
      // Native setCellWarning (OverlaysMixin.js:80) attaches another overlay per run; remove old warnings first
      clearValidationWarningOverlays(graph)
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

    if (this.rules.length === 0) {
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

export const buildValidationRulesFromSyntax = (rules: DiagramSyntax[] | null | undefined, elements: DiagramElement[] = [], connections: DiagramConnection[] = []): DiagramValidationRule[] => {
  if (!rules || rules.length === 0) {
    return []
  }

  const multiplicities: ConnectionMultiplicity[] = []

  for (const rule of rules) {
    if (rule.ruleType !== 'multiplicity') continue

    multiplicities.push(new ConnectionMultiplicity({ config: rule.config, elements, connections }))
  }

  const validationRules: DiagramValidationRule[] = multiplicities.length > 0 ? [new MultiplicityValidationRule(multiplicities)] : []
  // The cycle check itself runs in MyCustomGraph.validateEdge; the entry only keeps live validation on
  if (rules.some((rule) => rule.ruleType === 'acyclic')) validationRules.push(new DiagramValidationRule('ConnectionCheck'))
  return validationRules
}
