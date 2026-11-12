import type { ChildElement, DiagramElement } from '@/model/Element'

export const evaluationElementTypes = (elements: (DiagramElement | ChildElement)[]): string[] =>
  [...new Set(elements.flatMap((element): string[] => [element.type, ...evaluationElementTypes(element.children ?? [])]))]

const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const isName = (value: unknown): value is string => typeof value === 'string' && !!value.trim() && value.length <= 256

/** Validate at save/import boundaries without changing immutable definitions. */
export const evaluationConfigErrors = (value: unknown, elementTypes: string[], connectionTypes: string[] = []): string[] => {
  if (value === undefined) return []
  if (!isObject(value) || !Array.isArray(value.comparisonGroups)) return ['Evaluation must contain a list of comparison groups.']
  const errors: string[] = []
  const ids = new Set<string>()
  for (const [index, group] of value.comparisonGroups.entries()) {
    const label = isObject(group) && isName(group.name) ? group.name : `Group ${index + 1}`
    if (!isObject(group)) {
      errors.push(`${label}: Invalid comparison group.`)
      continue
    }
    if (!isName(group.id) || ids.has(group.id)) errors.push(`${label}: Group identifiers must be valid and unique.`)
    else ids.add(group.id)
    if (!isName(group.name)) errors.push(`${label}: Enter a name with at most 256 characters.`)
    const categories = [
      { field: 'elementTypes', label: 'element', knownTypes: new Set(elementTypes) },
      { field: 'connectionTypes', label: 'connection', knownTypes: new Set(connectionTypes) }
    ]
    if (!categories.some(({ field }) => {
      const members = group[field]
      return Array.isArray(members) && members.length > 0
    })) errors.push(`${label}: Select at least two element or connection types.`)
    for (const category of categories) {
      const members = group[category.field]
      if (members === undefined) continue
      if (!Array.isArray(members)) {
        errors.push(`${label}: ${category.field} must be a list.`)
        continue
      }
      if (members.length > 0 && members.length < 2) errors.push(`${label}: Select at least two distinct ${category.label} types.`)
      if (new Set(members).size !== members.length) errors.push(`${label}: Each ${category.label} type may occur only once per group.`)
      if (members.some((type) => typeof type !== 'string' || !category.knownTypes.has(type))) errors.push(`${label}: Remove or replace unknown ${category.label} types.`)
    }
  }
  return errors
}
