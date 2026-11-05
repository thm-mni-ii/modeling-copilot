import { Cell, Codec, type Graph, type UndoableEdit } from '@maxgraph/core'
import { createModelSerializer } from '@/utils/modelPersistence'
import { cellElement, siblingOrder, type SharedCell } from '@/collab/storage/modelCells'

/** What maxGraph keeps on every cell; anything else is the Copilot's own, such as diagramElementType. */
const CELL_FIELDS = new Set([...Object.keys(new Cell()), 'mxObjectId'])

type Fields = Record<string, unknown>

/** The edits made here; the Copilot's own undo keeps them in its history like any other. */
const applied = new WeakSet<UndoableEdit>()

/** The cells an edit made here touched, if an undo or redo of the Copilot just took it back or did it again; else null. */
export const cellsOfUndoneEdit = (edit: UndoableEdit | undefined) => {
  if (!edit || !applied.has(edit) || !(edit.undone || edit.redone)) return null
  return edit.changes.flatMap((change) => {
    const { cell, child } = change as { cell?: Cell; child?: Cell }
    return [cell?.getId(), child?.getId()].filter((id): id is string => Boolean(id))
  })
}

// XML knows no booleans: the codec reads true as 1 and "12" as 12, so values are compared as XML holds them.
const asInXml = (_key: string, value: unknown) => (typeof value === 'boolean' ? Number(value) : typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value)) ? Number(value) : value)
const same = (a: unknown, b: unknown) => a === b || JSON.stringify(a ?? null, asInXml) === JSON.stringify(b ?? null, asInXml)

/** The Copilot's own fields of a cell that hold data. */
const ownFields = (cell: Cell) => Object.keys(cell).filter((key) => !CELL_FIELDS.has(key) && typeof (cell as unknown as Fields)[key] !== 'function')

/** A text of another that waits until the own edit of the cell ends; before tells whether it was taken over unchanged. */
export interface HeldText {
  cell: Cell
  before: unknown
}

/**
 * Takes the shared state of these keys into the graph, each cell in place, so the selection and an
 * edit in progress stay. Builds as joinModel does: parents before children, siblings by index, and
 * what concurrent deletes strand stays out. Holds back the text of the cell being edited, so the
 * own text wins. Throws on what it cannot read; then the whole model is to be loaded.
 */
export const applyCells = (graph: Graph, keys: readonly string[], shared: ReadonlyMap<string, SharedCell>): HeldText | null => {
  const model = graph.getDataModel()
  // Registers the codecs the Copilot adds to those of maxGraph.
  createModelSerializer(graph)
  // Without a lookup the codec resolves no references; parent and ends come from the attributes.
  const codec = new Codec()
  const order = siblingOrder(shared)
  const elements = new Map<string, Element | null>()
  const stranded = new Set<Cell>()
  const touched = new Set<Cell>()
  let held: HeldText | null = null

  const elementOf = (id: string) => {
    if (!elements.has(id)) {
      const cell = shared.get(id)
      elements.set(id, cell ? cellElement(cell) : null)
    }
    return elements.get(id) ?? null
  }
  const attributeOf = (id: string, name: string) => elementOf(id)?.getAttribute(name) || null

  const depthOf = (id: string, seen = new Set<string>()): number => {
    const parent = attributeOf(id, 'parent')
    return parent && shared.has(parent) && !seen.has(parent) ? 1 + depthOf(parent, seen.add(id)) : 0
  }

  // Its place among the other children of parent, by the order of the shared cells.
  const positionIn = (parent: Cell, cell: Cell) => parent.children.filter((sibling) => sibling !== cell && order(sibling.getId() ?? '', cell.getId() ?? '') < 0).length

  // The edges at what goes are checked at the end, as their ends may be gone.
  const remove = (cell: Cell) => {
    for (const part of cell.filterDescendants(() => true)) for (const edge of part.edges) stranded.add(edge)
    model.remove(cell)
  }

  const update = (cell: Cell, decoded: Cell) => {
    if (!same(cell.value, decoded.value)) {
      if (graph.isEditing(cell)) held = { cell, before: cell.value }
      else model.setValue(cell, decoded.value)
    }
    if (!same(cell.style, decoded.style)) {
      // A style function of the Copilot would hide the shared style; without it the cell is as after a full import.
      if (Object.prototype.hasOwnProperty.call(cell, 'getStyle')) delete (cell as Partial<Pick<Cell, 'getStyle'>>).getStyle
      model.setStyle(cell, decoded.style)
    }
    if (decoded.geometry && !same(cell.geometry, decoded.geometry)) model.setGeometry(cell, decoded.geometry)
    if (cell.visible !== decoded.visible) model.setVisible(cell, decoded.visible)
    if (cell.collapsed !== decoded.collapsed) model.setCollapsed(cell, decoded.collapsed)
    const fields = cell as unknown as Fields
    const next = decoded as unknown as Fields
    for (const key of new Set([...ownFields(cell), ...ownFields(decoded)])) {
      if (same(fields[key], next[key])) continue
      if (key in next) fields[key] = next[key]
      else delete fields[key]
      touched.add(cell)
    }
  }

  const maintainEdgeParent = model.maintainEdgeParent
  // Edges keep the parent the shared state gives them, as after a full import.
  model.maintainEdgeParent = false
  model.beginUpdate()
  applied.add(model.currentEdit)
  try {
    for (const id of keys) {
      const cell = model.getCell(id)
      if (cell && !shared.has(id)) remove(cell)
    }

    const present = keys.filter((id) => shared.has(id)).sort((a, b) => depthOf(a) - depthOf(b) || order(a, b))
    for (const id of present) {
      const element = elementOf(id)
      const decoded = element && codec.decodeCell(element, false)
      if (!element || !decoded) throw new Error(`Cell ${id} could not be read.`)
      const cell = model.getCell(id)
      const parentId = element.getAttribute('parent')
      if (!parentId) {
        // The root: it is replaced only by loading the whole model.
        if (!cell) throw new Error('The root cell is missing.')
        update(cell, decoded)
        continue
      }
      const parent = model.getCell(parentId)
      if (!parent) {
        if (cell) remove(cell)
        continue
      }
      if (!cell) {
        model.add(parent, decoded, positionIn(parent, decoded))
        continue
      }
      update(cell, decoded)
      if (cell.parent !== parent || parent.getIndex(cell) !== positionIn(parent, cell)) model.add(parent, cell, positionIn(parent, cell))
    }

    for (const id of present) {
      const edge = model.getCell(id)
      if (!edge?.isEdge()) continue
      for (const isSource of [true, false]) {
        const end = attributeOf(id, isSource ? 'source' : 'target')
        const terminal = end ? model.getCell(end) : null
        if (end && !terminal) stranded.add(edge)
        else if (edge.getTerminal(isSource) !== terminal) model.setTerminal(edge, terminal, isSource)
      }
    }

    // As in joinModel, an edge whose end is gone stays out.
    const isLoose = (id: string) =>
      ['source', 'target'].some((end) => {
        const terminal = attributeOf(id, end)
        return terminal !== null && !model.getCell(terminal)
      })
    for (const edge of stranded) {
      const id = edge.getId()
      if (id && model.getCell(id) === edge && isLoose(id)) model.remove(edge)
    }
  } finally {
    model.endUpdate()
    model.maintainEdgeParent = maintainEdgeParent
  }

  // Fields of the Copilot alone change nothing maxGraph watches, so those cells are drawn anew;
  // not the one being edited, as drawing it anew shows its label again beneath the editor.
  for (const cell of touched) if (model.getCell(cell.getId() ?? '') === cell && !graph.isEditing(cell)) graph.refresh(cell)
  return held
}
