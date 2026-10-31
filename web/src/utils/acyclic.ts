import type { Cell } from '@maxgraph/core'
import type { CycleMode, DiagramSyntax } from '@/model/Syntax'
import { getConnectionType } from '@/utils/multiplicity'

export const DEFAULT_ACYCLIC_MESSAGE_TEMPLATE = 'The connection {source} -> {target} would close a cycle.'

/** Standardmeldung je Modus; {element} = Elementtyp bei every */
export const DEFAULT_CYCLE_MESSAGE_TEMPLATES: Record<CycleMode, string> = {
  forbid: DEFAULT_ACYCLIC_MESSAGE_TEMPLATE,
  every: '{element} must be part of a cycle.',
  any: 'The diagram must contain at least one cycle.'
}

export interface AcyclicSettings {
  mode: CycleMode
  message: string
  /** Leer = alle Verbindungstypen zählen für den Zyklus */
  connectionTypes: string[]
  /** Leer = jedes Element muss bei every auf einem Zyklus liegen */
  elementTypes: string[]
  ignoreDirection: boolean
}

/** Einstellungen der Zyklus-Regel; null = Zyklen erlaubt. */
export const buildAcyclicFromSyntax = (rules: DiagramSyntax[] | null | undefined): AcyclicSettings | null => {
  const rule = rules?.find((entry) => entry.ruleType === 'acyclic')
  if (rule?.ruleType !== 'acyclic') return null
  const mode = rule.config.mode ?? 'forbid'
  return { mode, message: rule.config.messageTemplate.trim() || DEFAULT_CYCLE_MESSAGE_TEMPLATES[mode], connectionTypes: rule.config.connectionTypes ?? [], elementTypes: rule.config.elementTypes ?? [], ignoreDirection: rule.config.ignoreDirection ?? false }
}

/** Füllt {source}/{target} mit den Elementtypen; der Zeilenumbruch trennt Meldungen wie bei den Multiplicities. */
export const renderAcyclicMessage = (template: string, source: Cell, target: Cell): string => {
  const typeOf = (cell: Cell): string => (cell as any).diagramElementType ?? '-'
  return `${template.split('{source}').join(typeOf(source)).split('{target}').join(typeOf(target))}\n`
}

/** Füllt {element} mit dem Elementtyp, für every und any. */
export const renderCycleRequiredMessage = (template: string, element?: Cell): string => `${template.split('{element}').join((element as any)?.diagramElementType ?? '-')}\n`

/**
 * Prüft, ob das Ziel zur Quelle zurückführt; die geprüfte Kante selbst zählt nicht mit.
 * Gerichtet über ausgehende Kanten, mit ignoreDirection über alle Kanten.
 * Es zählen nur Kanten der gewählten Verbindungstypen. Schleifen am selben Element entscheidet "Allow Loops" der Verbindung.
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
      if (!next || next === edge || !counts(next)) continue
      const from = next.getTerminal(true)
      const to = next.getTerminal(false)
      const neighbor = from === cell ? to : ignoreDirection && to === cell ? from : null
      if (neighbor && neighbor !== cell && !neighbor.isEdge()) stack.push(neighbor)
    }
  }

  return false
}

/** Liegt das Element auf einem Zyklus? Eine seiner Kanten muss über einen anderen Weg zu ihm zurückführen. */
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
