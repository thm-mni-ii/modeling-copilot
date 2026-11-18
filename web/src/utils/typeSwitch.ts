import { Cell, CellState, Geometry, Point, type Graph } from '@maxgraph/core'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { ChildElement, DiagramElement } from '@/model/Element'
import type { DiagramConnection } from '@/model/Connection'
import { createCellFromElement, createConnectionStyle } from './elementFactory'
import { applyConnectionLabelOffset } from './connectionLabelHelpers'
import { elementTypeOf, endpointId, endpointStyle, pointId } from './connectionPoints'
import { buildContainmentFromSyntax, canContain } from './containment'
import { getGraphValidationMode, isValidationPassActive, setValidationPassActive } from './graphValidationRuntime'
import { cellLabel } from './syntaxMessages'

export type SwitchLanguage = Pick<DiagramLanguage, 'elements' | 'connections' | 'syntax' | 'evaluation'>
export interface TypeSwitchOption {
  type: string
  element?: DiagramElement
  connection?: DiagramConnection
  reasons: string[]
  losses: string[]
}
interface Update { cell: Cell; template: Cell }
interface Plan { updates: Update[]; additions: { parent: Cell; cell: Cell }[]; removals: Cell[]; losses: string[]; reasons: string[] }

class TypeSwitchBlocked extends Error {
  constructor(readonly reasons: string[]) {
    super(reasons.join(' '))
  }
}

const namedCell = (cell: Cell | null): string | undefined =>
  cell && typeof cell.value === 'string' && cell.value.trim() ? cellLabel(cell) : undefined

const connectionSubject = (edge: Cell, at?: Cell): string => {
  const label = namedCell(edge)
  if (label) return `The connection “${label}”`
  const neighbor = at ? namedCell(edge.source === at ? edge.target : edge.source) : undefined
  return neighbor ? `The connection to “${neighbor}”` : 'An existing connection'
}

// These fields are part of a type definition and must travel with its undoable edit.
const typeFields = ['diagramElementType', 'diagramAttributes', 'connectionPointsJson', 'docking', 'allowLabelEdit', 'collapsedConfig', 'getStyle', 'connectable', 'connectionId', 'connectionUndirected', 'connectionStyle', 'connectionLabelOffset', 'connectionLabelId']
const fieldsOf = (cell: Cell) => cell as unknown as Record<string, unknown>
class TypeFieldsChange {
  private values: Record<string, unknown>
  constructor(readonly cell: Cell, template: Cell) {
    this.values = Object.fromEntries(typeFields.map((key) => [key, Object.prototype.hasOwnProperty.call(template, key) ? fieldsOf(template)[key] : undefined]))
  }
  execute() {
    const fields = fieldsOf(this.cell)
    for (const key of typeFields) {
      const previous = Object.prototype.hasOwnProperty.call(this.cell, key) ? fields[key] : undefined
      if (this.values[key] === undefined) delete fields[key]
      else fields[key] = this.values[key]
      this.values[key] = previous
    }
  }
}

const previewElement = (definition: DiagramElement | ChildElement): DiagramElement => 'position' in definition
  ? { ...definition, ...definition.position, anchorPoints: [], movable: true, resizable: true, connectable: definition.connectable ?? false }
  : definition

const elementTemplate = (definition: DiagramElement | ChildElement): Cell => {
  const cell = createCellFromElement(previewElement(definition), 0, 0)
  // Let the graph read the new style directly, including after undo or remote updates.
  if (Object.prototype.hasOwnProperty.call(cell, 'getStyle')) delete (cell as Partial<Pick<Cell, 'getStyle'>>).getStyle
  if ('position' in definition) {
    const { x, y, width, height, relative } = definition.position
    cell.geometry = new Geometry(x, y, width, height)
    cell.geometry.relative = relative
  }
  return cell
}

const keepText = (cell: Cell, template: Cell, editable: boolean, losses: string[]) => {
  if (editable) template.value = cell.value
  else if (String(cell.value ?? '').trim() && cell.value !== template.value) losses.push(String(cell.value))
}

const planElement = (cell: Cell, source: DiagramElement | ChildElement, target: DiagramElement | ChildElement, plan: Plan): void => {
  const template = elementTemplate(target)
  template.collapsed = 'collapsible' in target && !!target.collapsible && cell.collapsed
  keepText(cell, template, target.allowLabelEdit !== false, plan.losses)
  const geometry = cell.geometry?.clone() ?? template.geometry!
  if (cell.collapsed && !template.collapsed && geometry.alternateBounds) {
    geometry.width = geometry.alternateBounds.width
    geometry.height = geometry.alternateBounds.height
  }
  if ('position' in target) {
    geometry.x = target.position.x
    geometry.y = target.position.y
    geometry.relative = target.position.relative
  } else if (!target.resizable) {
    geometry.width = target.width
    geometry.height = target.height
  }
  // Preserve the user's size; replace type-specific constraints and folding bounds.
  ;(geometry as any).constraints = (template.geometry as any)?.constraints
  geometry.alternateBounds = template.collapsed ? cell.geometry?.alternateBounds?.clone() ?? null : template.geometry?.alternateBounds ?? null
  template.geometry = geometry
  plan.updates.push({ cell, template })

  for (const child of cell.children.filter((part) => part.isVertex())) {
    const type = elementTypeOf(child)
    const declared = source.children.filter((part) => part.type === type)
    if (!declared.length) continue // User-inserted content stays inside its container.
    const matches = target.children.filter((part) => part.type === type)
    if (declared.length !== 1 || matches.length !== 1 || cell.children.filter((part) => elementTypeOf(part) === type).length !== 1) {
      const label = namedCell(child)
      plan.reasons.push(`${label ? `The contained element “${label}”` : 'A contained element'} has no unique counterpart in the destination type.`)
      continue
    }
    planElement(child, declared[0], matches[0], plan)
  }
  for (const child of target.children) {
    if (target.children.filter((part) => part.type === child.type).length !== 1) {
      plan.reasons.push('The destination type defines several matching child elements, so the contents cannot be assigned uniquely.')
      continue
    }
    if (cell.children.some((part) => elementTypeOf(part) === child.type)) continue
    const add = (parent: Cell, definition: ChildElement) => {
      const added = elementTemplate(definition)
      plan.additions.push({ parent, cell: added })
      definition.children.forEach((nested) => add(added, nested))
    }
    add(cell, child)
  }
  if ('anchorPoints' in target) {
    for (const edge of cell.edges) {
      for (const isSource of [true, false]) {
        if (edge.getTerminal(isSource) !== cell) continue
        const id = endpointId(edge, isSource, cell)
        if (!id) continue
        const point = target.anchorPoints.find((candidate) => pointId(candidate) === id)
        const previous = 'anchorPoints' in source ? source.anchorPoints.find((candidate) => pointId(candidate) === id) : undefined
        if (!point || (previous?.role && point.role && previous.role !== point.role && point.role !== 'bidirectional')) {
          plan.reasons.push(`${connectionSubject(edge, cell)} has no compatible attachment point in the destination type.`)
          continue
        }
        let update = plan.updates.find((entry) => entry.cell === edge)
        if (!update) {
          update = { cell: edge, template: edge.clone() }
          plan.updates.push(update)
        }
        update.template.style = { ...update.template.style, ...endpointStyle(point, isSource) }
      }
    }
  }
}

const planConnection = (edge: Cell, target: DiagramConnection, plan: Plan): void => {
  if (target.connectable === false && edge.edges.length) plan.reasons.push('Other connections are attached to this connection. The destination type cannot accept them.')
  const template = edge.clone()
  template.style = createConnectionStyle(target)
  // Keep endpoint attachments, independent of the connection's visual style.
  for (const key of ['exitPointId', 'exitX', 'exitY', 'exitPerimeter', 'entryPointId', 'entryX', 'entryY', 'entryPerimeter']) {
    if (key in edge.style) (template.style as Record<string, unknown>)[key] = (edge.style as Record<string, unknown>)[key]
  }
  Object.assign(template, { connectionId: target.type, connectionUndirected: target.undirected === true, connectionStyle: template.style, connectionLabelOffset: target.labelOffset, allowLabelEdit: target.allowLabelEdit !== false })
  template.value = target.defaultLabel ?? ''
  keepText(edge, template, target.allowLabelEdit !== false, plan.losses)
  applyConnectionLabelOffset(template, target.labelOffset)
  plan.updates.push({ cell: edge, template })
  const definitions = target.additionalLabels ?? []
  for (const child of edge.children) {
    const id = fieldsOf(child).connectionLabelId
    if (!id) continue
    const matches = definitions.filter((label) => label.type === id)
    if (matches.length > 1) {
      plan.reasons.push('A connection label has several possible counterparts in the destination type.')
      continue
    }
    if (!matches.length) {
      if (child.edges.length || child.children.length) {
        plan.reasons.push('A connection label contains elements or attached connections that the destination type cannot retain.')
        continue
      }
      if (String(child.value ?? '').trim()) plan.losses.push(String(child.value))
      plan.removals.push(child)
    }
  }
  for (const definition of definitions) {
    const existing = edge.children.filter((child) => fieldsOf(child).connectionLabelId === definition.type)
    if (existing.length > 1) {
      plan.reasons.push('Several existing connection labels match the same destination label. They cannot be assigned uniquely.')
      continue
    }
    const label = new Cell(definition.text, new Geometry(definition.geometry?.x ?? 0, definition.geometry?.y ?? 0, definition.geometry?.width ?? 0, definition.geometry?.height ?? 0), {
      shape: 'label', strokeColor: 'transparent', fillColor: 'transparent', align: 'center', verticalAlign: 'middle', fontColor: target.style.fontColor ?? '#000000', fontSize: target.style.fontSize ?? 12, ...definition.style, editable: definition.allowLabelEdit !== false
    })
    label.setVertex(true)
    label.setConnectable(definition.connectable ?? false)
    Object.assign(label, { connectionLabelId: definition.type, allowLabelEdit: definition.allowLabelEdit !== false })
    label.geometry!.relative = definition.geometry?.relative ?? true
    label.geometry!.offset = new Point(definition.geometry?.offsetX ?? 0, definition.geometry?.offsetY ?? 0)
    if (existing[0]) {
      keepText(existing[0], label, definition.allowLabelEdit !== false, plan.losses)
      plan.updates.push({ cell: existing[0], template: label })
    } else plan.additions.push({ parent: edge, cell: label })
  }
}

const prepare = (graph: Graph, cell: Cell, option: TypeSwitchOption, language: SwitchLanguage, languages: SwitchLanguage[]): Plan => {
  const plan: Plan = { updates: [], additions: [], removals: [], losses: [], reasons: [] }
  if (option.element) {
    const collect = (elements: (DiagramElement | ChildElement)[]): (DiagramElement | ChildElement)[] => elements.flatMap((element) => [element, ...collect(element.children)])
    const sources = collect(language.elements).filter((element) => element.type === elementTypeOf(cell))
    if (sources.length !== 1) throw new TypeSwitchBlocked(['The selected element matches several definitions in this modeling language. Its contents cannot be assigned uniquely.'])
    planElement(cell, sources[0], option.element, plan)
  } else if (option.connection) planConnection(cell, option.connection, plan)

  // Inspect the prospective state synchronously, without model events or history entries.
  const restore: (() => void)[] = []
  const previousPass = isValidationPassActive(graph)
  try {
    for (const update of plan.updates) {
      const change = new TypeFieldsChange(update.cell, update.template)
      const { style, value, geometry, collapsed } = update.cell
      restore.push(() => { change.execute(); Object.assign(update.cell, { style, value, geometry, collapsed }) })
      change.execute()
      Object.assign(update.cell, { style: update.template.style, value: update.template.value, geometry: update.template.geometry, collapsed: update.template.collapsed })
    }
    const containment = buildContainmentFromSyntax(languages.flatMap((entry) => entry.syntax))
    for (const addition of plan.additions) {
      if (!canContain(containment, addition.parent, [addition.cell])) plan.reasons.push('A child element required by the destination type is not allowed in its container.')
    }
    for (const { cell: changed } of plan.updates) {
      if (changed.isVertex() && changed.parent && !canContain(containment, changed.parent, [changed])) {
        const container = namedCell(changed.parent)
        plan.reasons.push(`The destination type is not allowed inside ${container ? `“${container}”` : 'the current container'}.`)
      }
      if (!changed.isConnectable() && changed.edges.length) plan.reasons.push('Existing connections are attached to an element that cannot accept connections in the destination type.')
    }
    if (getGraphValidationMode(graph) === 'preventive') {
      setValidationPassActive(graph, true)
      const affected = new Set(plan.updates.flatMap(({ cell: changed }) => [changed, ...changed.edges, ...changed.edges.flatMap((edge) => [edge.source, edge.target].filter((end): end is Cell => !!end))]))
      if (cell.isEdge()) { if (cell.source) affected.add(cell.source); if (cell.target) affected.add(cell.target) }
      for (const changed of affected) {
        const error = changed.isEdge() ? graph.getEdgeValidationError(changed, changed.source, changed.target) : graph.getCellValidationError(changed)
        if (error !== null && error !== undefined) {
          plan.reasons.push(changed.isEdge()
            ? `${connectionSubject(changed, cell)} would violate a connection rule of this modeling language after the change.`
            : `${namedCell(changed) ? `The element “${namedCell(changed)}”` : 'An affected element'} would no longer meet the connection limits of this modeling language.`)
        }
        const customError = graph.validateCell(changed, new CellState(graph.view, changed, changed.style))
        if (customError) plan.reasons.push('The change would violate a containment or cycle rule of this modeling language.')
      }
    }
  } finally {
    restore.reverse().forEach((undo) => undo())
    setValidationPassActive(graph, previousPass)
  }
  if (plan.reasons.length) throw new TypeSwitchBlocked([...new Set(plan.reasons)])
  return plan
}

export const typeSwitchOptions = (graph: Graph, cell: Cell, languages: SwitchLanguage[]): { language: SwitchLanguage; options: TypeSwitchOption[] } | undefined => {
  if (fieldsOf(cell).cellRole === 'feedback' || fieldsOf(cell).connectionLabelId) return
  const type = cell.isEdge() ? fieldsOf(cell).connectionId : elementTypeOf(cell)
  const owners = languages.filter((language) => cell.isEdge() ? language.connections.some((entry) => entry.type === type) : language.elements.some((entry) => entry.type === type))
  if (owners.length !== 1) return
  const language = owners[0]
  const groups = language.evaluation?.comparisonGroups ?? []
  const candidates = new Set(groups.filter((group) => group.elementTypes?.includes(String(type))).flatMap((group) => group.elementTypes ?? []))
  const relatedConnections = new Set(groups.filter((group) => group.connectionTypes?.includes(String(type))).flatMap((group) => group.connectionTypes ?? []))
  const options: TypeSwitchOption[] = cell.isEdge()
    ? language.connections.map((connection) => ({ type: connection.type, connection, losses: [], reasons: [] }))
    : language.elements.filter((element) => element.type === type || candidates.has(element.type)).map((element) => ({ type: element.type, element, losses: [], reasons: [] }))
  for (const option of options) {
    if (option.type === type) continue
    try { option.losses = prepare(graph, cell, option, language, languages).losses }
    catch (error) { option.reasons = error instanceof TypeSwitchBlocked ? error.reasons : ['The destination definition could not be matched to the selected object.'] }
  }
  options.sort((a, b) => Number(b.type === type) - Number(a.type === type) || Number(relatedConnections.has(b.type)) - Number(relatedConnections.has(a.type)))
  return { language, options }
}

export const applyTypeSwitch = (graph: Graph, cell: Cell, option: TypeSwitchOption, language: SwitchLanguage, languages: SwitchLanguage[], confirmLosses: boolean): string[] => {
  if (!graph.isEnabled() || graph.isCellsLocked()) throw new Error('This model is read-only.')
  if (!cell.getId() || graph.getDataModel().getCell(cell.getId()!) !== cell) throw new Error('The selected object is no longer available.')
  const plan = prepare(graph, cell, option, language, languages)
  if (plan.losses.length && !confirmLosses) return plan.losses
  const model = graph.getDataModel()
  model.batchUpdate(() => {
    for (const { cell: changed, template } of plan.updates) {
      model.execute(new TypeFieldsChange(changed, template))
      model.setStyle(changed, template.style)
      model.setValue(changed, template.value)
      if (template.geometry) model.setGeometry(changed, template.geometry)
      model.setCollapsed(changed, template.collapsed)
    }
    plan.removals.forEach((removed) => graph.removeCells([removed], false))
    plan.additions.forEach(({ parent, cell: added }) => graph.addCell(added, parent))
  })
  graph.setSelectionCell(cell)
  return []
}
