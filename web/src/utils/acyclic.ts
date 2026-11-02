import type { Cell } from '@maxgraph/core'
import type { CycleMode, DiagramSyntax } from '@/model/Syntax'
import { getConnectionType } from '@/utils/multiplicity'

export const DEFAULT_ACYCLIC_MESSAGE_TEMPLATE = 'The connection {source} -> {target} would close a forbidden cycle.'

/** Default message per mode; {element} = element type for every */
export const DEFAULT_CYCLE_MESSAGE_TEMPLATES: Record<CycleMode, string> = {
  forbid: DEFAULT_ACYCLIC_MESSAGE_TEMPLATE,
  every: '{element} must be part of a cycle.',
  any: 'The diagram must contain at least one cycle.'
}

export interface AcyclicSettings {
  mode: CycleMode
  message: string
  /** Empty = all connection types count for the cycle */
  connectionTypes: string[]
  /** Empty = every element must lie on a cycle for every */
  elementTypes: string[]
  ignoreDirection: boolean
}

/** Settings of the cycle rule; null = cycles allowed. */
export const buildAcyclicFromSyntax = (rules: DiagramSyntax[] | null | undefined): AcyclicSettings | null => {
  const rule = rules?.find((entry) => entry.ruleType === 'acyclic')
  if (rule?.ruleType !== 'acyclic') return null
  const mode = rule.config.mode ?? 'forbid'
  return { mode, message: rule.config.messageTemplate.trim() || DEFAULT_CYCLE_MESSAGE_TEMPLATES[mode], connectionTypes: rule.config.connectionTypes ?? [], elementTypes: rule.config.elementTypes ?? [], ignoreDirection: rule.config.ignoreDirection ?? false }
}

/** Fills {source}/{target} with the element types; the line break separates messages as with the multiplicities. */
export const renderAcyclicMessage = (template: string, source: Cell, target: Cell): string => {
  const typeOf = (cell: Cell): string => (cell as any).diagramElementType ?? '-'
  return `${template.split('{source}').join(typeOf(source)).split('{target}').join(typeOf(target))}\n`
}

/** Fills {element} with the element type, for every and any. */
export const renderCycleRequiredMessage = (template: string, element?: Cell): string => `${template.split('{element}').join((element as any)?.diagramElementType ?? '-')}\n`

/**
 * Checks whether the target leads back to the source; the edge being checked does not count.
 * Directed via outgoing edges, with ignoreDirection via all edges.
 * Only edges of the chosen connection types count. "Allow Loops" of the connection decides loops on the same element.
 */
export const closesCycle = (edge: Cell | null, source: Cell, target: Cell, connectionTypes: string[] = [], ignoreDirection = false): boolean => {
  const counts = (candidate: Cell | null) => connectionTypes.length === 0 || connectionTypes.includes(getConnectionType(candidate) ?? '')
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
    if (edge && neighbor && !neighbor.isEdge() && closesCycle(edge, cell, neighbor, settings.connectionTypes, settings.ignoreDirection)) return true
  }
  return false
}
