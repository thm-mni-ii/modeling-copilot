import type { Cell } from '@maxgraph/core'
import type { DiagramSyntax } from '@/model/Syntax'
import { getConnectionType } from '@/utils/multiplicity'

export const DEFAULT_ACYCLIC_MESSAGE_TEMPLATE = 'The connection {source} -> {target} would close a cycle.'

export interface AcyclicSettings {
  message: string
  /** Leer = alle Verbindungstypen zählen für den Zyklus */
  connectionTypes: string[]
}

/** Einstellungen der Acyclic-Regel; null = Zyklen erlaubt. */
export const buildAcyclicFromSyntax = (rules: DiagramSyntax[] | null | undefined): AcyclicSettings | null => {
  const rule = rules?.find((entry) => entry.ruleType === 'acyclic')
  if (rule?.ruleType !== 'acyclic') return null
  return { message: rule.config.messageTemplate.trim() || DEFAULT_ACYCLIC_MESSAGE_TEMPLATE, connectionTypes: rule.config.connectionTypes ?? [] }
}

/** Füllt {source}/{target} mit den Elementtypen; der Zeilenumbruch trennt Meldungen wie bei den Multiplicities. */
export const renderAcyclicMessage = (template: string, source: Cell, target: Cell): string => {
  const typeOf = (cell: Cell): string => (cell as any).diagramElementType ?? '-'
  return `${template.split('{source}').join(typeOf(source)).split('{target}').join(typeOf(target))}\n`
}

/**
 * Prüft, ob das Ziel über ausgehende Kanten zur Quelle zurückführt; die geprüfte Kante selbst zählt nicht mit.
 * Es zählen nur Kanten der gewählten Verbindungstypen. Schleifen am selben Element entscheidet "Allow Loops" der Verbindung.
 */
export const closesCycle = (edge: Cell | null, source: Cell, target: Cell, connectionTypes: string[] = []): boolean => {
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
      const outgoing = cell.getEdgeAt(index)
      if (!outgoing || outgoing === edge || outgoing.getTerminal(true) !== cell || !counts(outgoing)) continue
      const next = outgoing.getTerminal(false)
      if (next && !next.isEdge()) stack.push(next)
    }
  }

  return false
}
