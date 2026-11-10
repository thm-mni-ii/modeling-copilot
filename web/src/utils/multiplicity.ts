import { InternalEvent, Multiplicity, type Cell, type Graph } from '@maxgraph/core'
import type { DiagramSyntax } from '@/model/Syntax'
import type { DiagramElement } from '@/model/Element'
import type { DiagramConnection } from '@/model/Connection'
import { connectionErrors, connectionEndpointErrors, elementConnectionErrors, type ConnectionRuleContext } from './connectionRules'
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

export interface DiagramWarning {
  cell: Cell | null
  message: string
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
  constructor(private readonly context: ConnectionRuleContext, private readonly endpointsOnly = false) {
    super(true, '*', null, null, 0, Number.MAX_VALUE, [], '', '', true)
  }

  override check(_graph: Graph, edge: Cell, source: Cell, target: Cell): string | null {
    const errors = this.endpointsOnly ? connectionEndpointErrors(this.context, edge, source, target) : connectionErrors(this.context, edge, source, target)
    return errors.length ? errors.join('\n') + '\n' : null
  }

  checkTerminalCardinality(cell: Cell): string | null {
    if (this.endpointsOnly) return null
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

  private runValidationPass(graph: PatchedGraph, warnings?: DiagramWarning[]): string | null {
    const setCellWarning = graph.setCellWarning
    graph.setCellWarning = (cell, warning, ...args) => {
      if (warning && warnings) {
        warnings.push(...normalizeMessages(warning.replace(/<br\s*\/?>/gi, '\n')).map((message) => ({ cell, message })))
      }
      const safeWarning = warning?.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/&lt;br\s*\/?&gt;/gi, '<br>')
      return setCellWarning.call(graph, cell, safeWarning ?? null, ...args)
    }
    setValidationPassActive(graph, true)
    try {
      // Native setCellWarning (OverlaysMixin.js:80) attaches another overlay per run; remove old warnings first
      clearValidationWarningOverlays(graph)
      return graph.validateGraph()
    } finally {
      graph.setCellWarning = setCellWarning
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

  validateGraph(graph: Graph): DiagramWarning[] {
    const results: DiagramWarning[] = []
    const warning = this.runValidationPass(graph as PatchedGraph, results)
    results.push(...normalizeMessages(warning).map((message) => ({ cell: null, message })))
    return results
  }
}

export interface ValidationLanguage {
  syntax: DiagramSyntax[]
  elements: DiagramElement[]
  connections: DiagramConnection[]
}

export const buildValidationRulesForLanguages = (languages: ValidationLanguage[]): DiagramValidationRule[] => {
  const elements = languages.flatMap((language) => language.elements)
  const connections = languages.flatMap((language) => language.connections)
  const endpointConfigs = new Map<string, import('@/model/Syntax').MultiplicityConfig>()
  for (const language of languages) {
    const rule = language.syntax.find((entry) => entry.ruleType === 'multiplicity')
    if (rule?.ruleType !== 'multiplicity') continue
    for (const element of language.elements) if (!endpointConfigs.has(element.type)) endpointConfigs.set(element.type, rule.config)
  }
  const multiplicities = [new ConnectionMultiplicity({ config: { relations: [], messageTemplate: '' }, elements, connections, endpointConfigs }, true)]
  for (const language of languages) {
    for (const rule of language.syntax) {
      if (rule.ruleType === 'multiplicity') multiplicities.push(new ConnectionMultiplicity({ config: rule.config, elements, connections, scopeElementTypes: language.elements.map((element) => element.type) }))
    }
  }
  return [new MultiplicityValidationRule(multiplicities)]
}

export const buildValidationRulesFromSyntax = (rules: DiagramSyntax[] | null | undefined, elements: DiagramElement[] = [], connections: DiagramConnection[] = []): DiagramValidationRule[] =>
  buildValidationRulesForLanguages([{ syntax: rules ?? [], elements, connections }])
