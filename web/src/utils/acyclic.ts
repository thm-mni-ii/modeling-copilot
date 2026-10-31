import type { Cell } from '@maxgraph/core'
import type { DiagramSyntax } from '@/model/Syntax'

export const DEFAULT_ACYCLIC_MESSAGE_TEMPLATE = 'The connection {source} -> {target} would close a cycle.'

/** Meldungstext der Acyclic-Regel; null = Zyklen erlaubt. */
export const buildAcyclicFromSyntax = (rules: DiagramSyntax[] | null | undefined): string | null => {
  const rule = rules?.find((entry) => entry.ruleType === 'acyclic')
  if (rule?.ruleType !== 'acyclic') return null
  return rule.config.messageTemplate.trim() || DEFAULT_ACYCLIC_MESSAGE_TEMPLATE
}

/** Füllt {source}/{target} mit den Elementtypen; der Zeilenumbruch trennt Meldungen wie bei den Multiplicities. */
export const renderAcyclicMessage = (template: string, source: Cell, target: Cell): string => {
  const typeOf = (cell: Cell): string => (cell as any).diagramElementType ?? '-'
  return `${template.split('{source}').join(typeOf(source)).split('{target}').join(typeOf(target))}\n`
}

/** Prüft, ob das Ziel über ausgehende Kanten zur Quelle zurückführt; die geprüfte Kante selbst zählt nicht mit. */
export const closesCycle = (edge: Cell | null, source: Cell, target: Cell): boolean => {
  const visited = new Set<Cell>()
  const stack = [target]

  while (stack.length > 0) {
    const cell = stack.pop()!
    if (cell === source) return true
    if (visited.has(cell)) continue
    visited.add(cell)

    for (let index = 0; index < cell.getEdgeCount(); index += 1) {
      const outgoing = cell.getEdgeAt(index)
      if (!outgoing || outgoing === edge || outgoing.getTerminal(true) !== cell) continue
      const next = outgoing.getTerminal(false)
      if (next && !next.isEdge()) stack.push(next)
    }
  }

  return false
}
