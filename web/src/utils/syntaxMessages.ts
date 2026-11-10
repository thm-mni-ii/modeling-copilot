import type { Cell } from '@maxgraph/core'
import type { CycleMode, EndpointMessageKey, MultiplicityCardinality } from '@/model/Syntax'
import { elementTypeOf } from './connectionPoints'

export const DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE = '{quantityContext}: {quantityResult}.'

export const DEFAULT_CONNECTION_MESSAGE_TEMPLATES = {
  forbiddenMessageTemplate: 'A connection between {sourceLabel} and {targetLabel} is not allowed.',
  connectionTypeMessageTemplate: 'The connection type {connection} is not allowed between {sourceLabel} and {targetLabel}.',
  endpointMessageTemplate: 'The connection points {sourcePoint} on {sourceLabel} and {targetPoint} on {targetLabel} cannot be used together.'
}

export const resolveQuantityMessage = (template?: string): string => template?.trim() ? template : DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE

export const DEFAULT_CONTAINMENT_MESSAGE = '{element} is not allowed inside {container}.'

export const DEFAULT_CYCLE_MESSAGE_TEMPLATES: Record<CycleMode, string> = {
  forbid: 'A cycle involving the connection between {sourceLabel} and {targetLabel} is not allowed.',
  every: '{elementLabel} must be part of a cycle.',
  any: 'The diagram must contain at least one cycle.'
}

export const DEFAULT_ENDPOINT_MESSAGES: Record<EndpointMessageKey, string> = {
  loop: '{connection} cannot connect {element} to itself.',
  looseEnd: '{connection} has an unconnected end.',
  missingPoint: 'A connection point on {element} no longer exists.',
  notConnectable: '{element} does not accept connections.',
  pointRequired: 'A connection to {element} requires a connection point.',
  pointDirection: 'The connection point {point} on {element} does not allow {direction} connections.'
}

export const renderEndpointMessage = (key: EndpointMessageKey, templates: Partial<Record<EndpointMessageKey, string>> | undefined, cell: Cell | null, values: Record<string, string> = {}): string =>
  renderValidationIssue({ kind: 'endpoint', code: `endpoint.${key}`, cell: cell ?? undefined, template: templates?.[key]?.trim() || DEFAULT_ENDPOINT_MESSAGES[key], values })

export interface ValidationIssue {
  kind: 'quantity' | 'connection' | 'containment' | 'cycle' | 'endpoint'
  code: 'quantity.minimum' | 'quantity.maximum' | 'connection.forbidden' | 'connection.type' | 'connection.endpoint' | 'containment' | 'cycle.forbid' | 'cycle.every' | 'cycle.any' | `endpoint.${EndpointMessageKey}`
  cell?: Cell
  source?: Cell
  target?: Cell
  other?: Cell
  template?: string
  values: Record<string, string | number>
  quantity?: {
    count: number
    bounds: MultiplicityCardinality
    scope: 'source' | 'target' | 'pair' | 'element' | 'point' | 'group'
    direction: 'incoming' | 'outgoing' | 'both' | 'undirected' | 'incoming or undirected' | 'outgoing or undirected'
    connections: string[]
    neighbors: string[]
    point?: string
    details?: string
    proposed?: boolean
  }
}

export const cellLabel = (cell?: Cell | null): string => {
  if (!cell) return 'element'
  const value = cell.getValue()
  const label = typeof value === 'string' ? value.replace(/<\/?(?:b|strong|i|em|u|div|br)\s*\/?>/gi, ' ').replace(/\s+/g, ' ').trim() : ''
  return label || elementTypeOf(cell) || 'unnamed element'
}

export const renderTemplate = (template: string, values: Record<string, string | number>): string =>
  template.replace(/\{([^{}]+)\}/g, (match, key: string) => key in values ? String(values[key]) : match)

export const renderValidationIssue = (issue: ValidationIssue): string => {
  const values: Record<string, string | number> = {
    ...issue.values,
    element: issue.kind === 'cycle' ? issue.values.element ?? '-' : cellLabel(issue.cell),
    elementLabel: cellLabel(issue.cell),
    sourceLabel: cellLabel(issue.source),
    targetLabel: cellLabel(issue.target),
    other: issue.kind === 'quantity' && !issue.other ? '-' : cellLabel(issue.other)
  }
  if (issue.kind === 'quantity' && issue.quantity) {
    const { count, bounds, scope, direction, connections, neighbors, point, details, proposed } = issue.quantity
    const directed = direction === 'both' ? '' : `${direction} `
    const kind = connections.length ? `${connections.join(', ')} connections` : 'connections'
    const location = scope === 'pair' ? `between ${cellLabel(issue.cell)} and ${cellLabel(issue.other)}`
      : scope === 'point' ? `at point ${point} on ${cellLabel(issue.cell)}`
        : scope === 'group' ? `at point group ${point} on ${cellLabel(issue.cell)}`
          : direction === 'incoming' ? `to ${cellLabel(issue.cell)}`
            : direction === 'outgoing' ? `from ${cellLabel(issue.cell)}` : `on ${cellLabel(issue.cell)}`
    const neighbor = neighbors.length ? ` with ${neighbors.join(', ')}` : ''
    const route = issue.values.route && issue.values.route !== '-' ? ` (${issue.values.route})` : ''
    const context = `${directed}${kind} ${location}${neighbor}${details ? ` ${details}` : ''}${route}`
    values.quantityContext = context.charAt(0).toUpperCase() + context.slice(1)
    if (issue.code === 'quantity.maximum' && bounds.max === null) throw new Error('A maximum quantity violation requires a maximum bound.')
    const bound = issue.code === 'quantity.minimum' ? `at least ${bounds.min} required` : `at most ${bounds.max} allowed`
    values.quantityResult = `${count} ${proposed ? 'would result' : 'present'}; ${bound}`
  }
  return renderTemplate(issue.template ?? '', values)
}
