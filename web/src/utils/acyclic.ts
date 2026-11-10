import type { Cell } from '@maxgraph/core'
import type { CycleMode, DiagramSyntax } from '@/model/Syntax'
import { getConnectionType } from '@/utils/multiplicity'
import { DEFAULT_CYCLE_MESSAGE_TEMPLATES, renderValidationIssue } from '@/utils/syntaxMessages'

export { DEFAULT_CYCLE_MESSAGE_TEMPLATES } from '@/utils/syntaxMessages'
export const DEFAULT_ACYCLIC_MESSAGE_TEMPLATE = DEFAULT_CYCLE_MESSAGE_TEMPLATES.forbid

export interface AcyclicSettings {
  mode: CycleMode
  message: string
  /** Empty = all connection types count for the cycle */
  connectionTypes: string[]
  /** Empty = every element must lie on a cycle for every */
  elementTypes: string[]
  ignoreDirection: boolean
  scopeConnectionTypes?: string[]
  scopeElementTypes?: string[]
}

/** All cycle rules, optionally restricted to their language's default types. */
export const buildAcyclicFromSyntax = (rules: DiagramSyntax[] | null | undefined, scope?: { elementTypes: string[]; connectionTypes: string[] }): AcyclicSettings[] =>
  (rules ?? []).flatMap((rule) => {
    if (rule.ruleType !== 'acyclic') return []
    const mode = rule.config.mode ?? 'forbid'
    return [{ mode, message: rule.config.messageTemplate.trim() || DEFAULT_CYCLE_MESSAGE_TEMPLATES[mode], connectionTypes: rule.config.connectionTypes ?? [], elementTypes: rule.config.elementTypes ?? [], ignoreDirection: rule.config.ignoreDirection ?? false, scopeConnectionTypes: rule.config.connectionTypes?.length ? undefined : scope?.connectionTypes, scopeElementTypes: scope?.elementTypes }]
  })

/** Fills {source}/{target} with the element types; the line break separates messages as with the multiplicities. */
export const renderAcyclicMessage = (template: string, source: Cell, target: Cell): string => {
  const typeOf = (cell: Cell): string => (cell as any).diagramElementType ?? '-'
  return `${renderValidationIssue({ kind: 'cycle', code: 'cycle.forbid', source, target, template, values: { source: typeOf(source), target: typeOf(target) } })}\n`
}

/** Fills {element} with the element type, for every and any. */
export const renderCycleRequiredMessage = (template: string, element?: Cell): string => {
  return `${renderValidationIssue({ kind: 'cycle', code: element ? 'cycle.every' : 'cycle.any', cell: element, template, values: { element: (element as any)?.diagramElementType ?? '-' } })}\n`
}

/**
 * Checks whether the target leads back to the source; the edge being checked does not count.
 * Directed via outgoing edges, with ignoreDirection via all edges.
 * Only edges of the chosen connection types count. "Allow Loops" of the connection decides loops on the same element.
 */
export const closesCycle = (edge: Cell | null, source: Cell, target: Cell, connectionTypes: string[] = [], ignoreDirection = false, scopeConnectionTypes?: string[]): boolean => {
  const counts = (candidate: Cell | null) => (!connectionTypes.length || connectionTypes.includes(getConnectionType(candidate) ?? '')) && (!scopeConnectionTypes || scopeConnectionTypes.includes(getConnectionType(candidate) ?? ''))
  if (source === target || !counts(edge)) return false

  const visited = new Set<Cell>()
  const stack = [target]

  while (stack.length > 0) {
    const cell = stack.pop()!
    if (cell === source) return true
    if (visited.has(cell)) continue
    visited.add(cell)

    for (let index = 0; index < cell.getEdgeCount(); index += 1) {
      const next = cell.getEdgeAt(index)
      if (!next || next === edge || next === (edge as any)?.replacesEdge || !counts(next)) continue
      const from = next.getTerminal(true)
      const to = next.getTerminal(false)
      const neighbor = from === cell ? to : ignoreDirection && to === cell ? from : null
      if (neighbor && neighbor !== cell && !neighbor.isEdge()) stack.push(neighbor)
    }
  }

  return false
}

/** Does the element lie on a cycle? One of its edges must lead back to it by another path. */
export const isOnCycle = (cell: Cell, settings: AcyclicSettings): boolean => {
  for (let index = 0; index < cell.getEdgeCount(); index += 1) {
    const edge = cell.getEdgeAt(index)
    const from = edge?.getTerminal(true)
    const to = edge?.getTerminal(false)
    const neighbor = from === cell ? to : settings.ignoreDirection && to === cell ? from : null
    if (edge && neighbor && !neighbor.isEdge() && closesCycle(edge, cell, neighbor, settings.connectionTypes, settings.ignoreDirection, settings.scopeConnectionTypes)) return true
  }
  return false
}
