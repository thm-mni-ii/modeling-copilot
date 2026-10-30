import type { Cell } from '@maxgraph/core'
import type { DiagramSyntax } from '@/model/Syntax'

/** Erlaubte Elementtypen je Container-Typ aus allen Containment-Regeln. */
export type ContainmentMap = Map<string, Set<string>>

export const buildContainmentFromSyntax = (rules: DiagramSyntax[] | null | undefined): ContainmentMap => {
  const containment: ContainmentMap = new Map()

  for (const rule of rules ?? []) {
    if (rule.ruleType !== 'containment') continue

    for (const relation of rule.config.relations) {
      const allowed = containment.get(relation.containerType) ?? new Set<string>()
      relation.childTypes.forEach((type) => allowed.add(type))
      containment.set(relation.containerType, allowed)
    }
  }

  return containment
}

/** Prüft, ob alle Zellen in den Container dürfen; ungeregelte Container nehmen alles auf. */
export const canContain = (containment: ContainmentMap, container: Cell, cells: Cell[]): boolean => {
  const allowed = containment.get((container as any).diagramElementType)
  if (!allowed) return true

  return cells.every((cell) => allowed.has((cell as any).diagramElementType))
}
