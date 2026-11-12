import { GraphDataModel, type Cell, type Graph } from '@maxgraph/core'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { ChildElement, DiagramElement } from '@/model/Element'
import type { LanguageVersionReference } from '@/services/api/types/common'
import { languageReferenceKey } from '@/services/model/workspaceLanguageResolver'
import { createModelSerializer, exportModelAsXml } from './modelPersistence'
import { validateModelCellIds } from './modelPatches'
import { evaluationConfigErrors, evaluationElementTypes } from './languageEvaluation'

export interface PackagedLanguage extends LanguageVersionReference {
  name: string
  data: DiagramLanguage
  includedLanguageVersions: LanguageVersionReference[]
}

export interface ModelPackage {
  format: 'modeling-copilot-model'
  version: 1
  model: { xml: string }
  workspaceLanguages: LanguageVersionReference[]
  languages: PackagedLanguage[]
}

export const MAX_PACKAGE_BYTES = 20 * 1024 * 1024
const isObject = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const isReference = (value: unknown): value is LanguageVersionReference => isObject(value) && typeof value.languageId === 'string' && !!value.languageId && typeof value.versionId === 'string' && !!value.versionId
const elementTypesOf = (element: DiagramElement | ChildElement): string[] => [element.type, ...(element.children ?? []).flatMap(elementTypesOf)]
const checkDefinition = (definition: unknown): void => {
  if (!isObject(definition) || typeof definition.type !== 'string' || !definition.type || !isObject(definition.style)) throw new Error('Invalid language element or connection definition.')
  if (definition.children !== undefined) {
    if (!Array.isArray(definition.children)) throw new Error('Invalid child element definitions.')
    definition.children.forEach(checkDefinition)
  }
  if (definition.anchorPoints !== undefined && (!Array.isArray(definition.anchorPoints) || !definition.anchorPoints.every((point) => isObject(point) && Number.isFinite(point.x) && Number.isFinite(point.y)))) throw new Error('Invalid language connection points.')
}

/** Stable comparison also works when JSON object keys were reordered in transit. */
export const canonicalJson = (value: unknown): string => JSON.stringify(value, (_key, item) =>
  isObject(item) ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]])) : item)

export const decodePackageModel = (xml: string): GraphDataModel => {
  validateModelCellIds(xml)
  const document = new DOMParser().parseFromString(xml, 'application/xml')
  if (document.doctype || document.documentElement.tagName !== 'GraphDataModel') throw new Error('Invalid model document.')
  const cells = [...document.querySelectorAll('GraphDataModel > root > Cell')]
  const byId = new Map(cells.map((cell) => [cell.getAttribute('id')!, cell]))
  const roots = cells.filter((cell) => !cell.hasAttribute('parent'))
  if (roots.length !== 1) throw new Error('The model must have exactly one root.')
  for (const cell of cells) {
    for (const attribute of ['parent', 'source', 'target']) {
      const id = cell.getAttribute(attribute)
      if (id && !byId.has(id)) throw new Error(`Unknown model ${attribute}: ${id}`)
    }
    const visited = new Set<Element>()
    let parent: Element | undefined = cell
    while (parent) {
      if (visited.has(parent)) throw new Error('The model contains a parent cycle.')
      visited.add(parent)
      parent = byId.get(parent.getAttribute('parent') ?? '')
    }
  }
  const model = new GraphDataModel()
  // Decode away from the live canvas; malformed imports never clear the open model.
  createModelSerializer({ getDataModel: () => model } as Graph).import(xml)
  if (!model.getRoot()?.getChildCount()) throw new Error('The model has no model layer.')
  return model
}

export const parseModelPackage = (text: string): ModelPackage => {
  if (new Blob([text]).size > MAX_PACKAGE_BYTES) throw new Error('The model package exceeds 20 MB.')
  let value: unknown
  try { value = JSON.parse(text) } catch { throw new Error('Select a Modeling Copilot model package (.mcmodel). XML and images cannot be imported.') }
  if (!isObject(value) || value.format !== 'modeling-copilot-model' || value.version !== 1 || !isObject(value.model) || typeof value.model.xml !== 'string' || !Array.isArray(value.workspaceLanguages) || !value.workspaceLanguages.every(isReference) || !Array.isArray(value.languages)) {
    throw new Error('Unsupported or invalid Modeling Copilot model package (version 1 required).')
  }
  for (const language of value.languages) {
    if (!isReference(language) || !isObject(language) || typeof language.name !== 'string' || !language.name.trim() || !isObject(language.data) || !Array.isArray(language.data.elements) || !Array.isArray(language.data.connections) || !Array.isArray(language.data.syntax) || !isObject(language.data.feedback) || !Array.isArray(language.includedLanguageVersions) || !language.includedLanguageVersions.every(isReference)) {
      throw new Error('The package contains an invalid modeling language.')
    }
    ;[...language.data.elements, ...language.data.connections].forEach(checkDefinition)
    const errors = evaluationConfigErrors(language.data.evaluation, evaluationElementTypes(language.data.elements as DiagramElement[]), (language.data.connections as { type: string }[]).map((connection) => connection.type))
    if (errors.length) throw new Error(errors.join('\n'))
  }
  const result = value as unknown as ModelPackage
  const definitions = new Map(result.languages.map((language) => [languageReferenceKey(language), language]))
  if (definitions.size !== result.languages.length) throw new Error('Duplicate language versions in the package.')
  if (new Set(result.workspaceLanguages.map((reference) => reference.languageId)).size !== result.workspaceLanguages.length) throw new Error('Duplicate workspace languages in the package.')
  const visited = new Set<string>()
  const active = new Set<string>()
  const visit = (reference: LanguageVersionReference) => {
    const key = languageReferenceKey(reference)
    if (active.has(key)) throw new Error('Cyclic language dependencies in the package.')
    if (visited.has(key)) return
    const language = definitions.get(key)
    if (!language) throw new Error('A required language definition is missing from the package.')
    active.add(key)
    language.includedLanguageVersions.forEach(visit)
    active.delete(key)
    visited.add(key)
  }
  result.workspaceLanguages.forEach(visit)
  if (visited.size !== definitions.size) throw new Error('The package contains unrelated language definitions.')
  const model = decodePackageModel(result.model.xml)
  const elementTypes = new Set(result.languages.flatMap((language) => language.data.elements.flatMap(elementTypesOf)))
  const connectionTypes = new Set(result.languages.flatMap((language) => language.data.connections.map((connection) => connection.type)))
  const checkCell = (cell: Cell, feedback = false) => {
    const metadata = cell as Cell & { diagramElementType?: string; connectionId?: string; cellRole?: string }
    feedback ||= metadata.cellRole === 'feedback'
    if (!feedback && metadata.diagramElementType && !elementTypes.has(metadata.diagramElementType)) throw new Error(`The package has no language for element ${metadata.diagramElementType}.`)
    if (!feedback && metadata.connectionId && !connectionTypes.has(metadata.connectionId)) throw new Error(`The package has no language for connection ${metadata.connectionId}.`)
    cell.getChildren().forEach((child) => checkCell(child, feedback))
  }
  model.getRoot()!.getChildren().forEach((layer, index) => checkCell(layer, index === 1))
  return result
}

export const packageModelXml = (graph: Graph, includeFeedback: boolean): string => {
  const model = decodePackageModel(exportModelAsXml(graph, false))
  if (!includeFeedback) {
    const feedback = model.getRoot()!.getChildAt(1)
    if (feedback) for (const child of [...feedback.getChildren()]) model.remove(child)
  }
  return createModelSerializer({ getDataModel: () => model } as Graph).export({ pretty: false })
}
