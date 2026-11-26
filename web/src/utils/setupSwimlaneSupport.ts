import { Cell, EventObject, Graph, InternalEvent, styleUtils, type SelectionHandler } from '@maxgraph/core'
import { isTruthyFlag } from '@/utils/flagUtils'

/**
 * Swimlane Support für MaxGraph
 *
 * Zentrale Verwaltung aller Swimlane-Funktionalität:
 * - Auto-Stack Layout für Container-Children ('list' Layout)
 * - Auto-Resize basierend auf Inhalt ('list' und 'free' Layout)
 * - Drop-Handling und Event-Listener
 * - Pool-Erkennung
 */

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Erweiterter Graph-Typ mit Swimlane-Support
 */
export interface GraphWithSwimlaneSupport extends Graph {
  isPool(cell: Cell | null): boolean
  autoStackChildren(container: Cell): void
  autoResizeSwimlane(swimlane: Cell): void
}

interface ListLayoutConfig {
  direction: 'vertical' | 'horizontal'
  itemSpacing: number
  crossPadding: number
  stretchCrossAxis: boolean
  resizeMainAxis: boolean
  resizeCrossAxis: boolean
  minWidth: number
  minHeight: number
  startOffset: number
}

interface FreeLayoutConfig {
  resizeToContent: 'none' | 'grow'
  contentPadding: number
}

export const isContainerSectionTarget = (cell: Cell | null): boolean => {
  if (!cell) return false
  const attrValue = (cell as any).getAttribute?.('containerSection', null)
  return isTruthyFlag(attrValue)
}

const isLayerLockedCell = (graph: Graph, cell: Cell): boolean => {
  const style = graph.getCurrentCellStyle(cell) as Record<string, any> | null
  const lockFlag = style?.lockToLayer ?? (cell as any).lockToLayer
  return isTruthyFlag(lockFlag)
}

function getContainerLayout(style: Record<string, any>): 'free' | 'list' {
  return style?.containerLayout === 'free' ? 'free' : 'list'
}

// Wie isTruthyFlag, aber mit explizitem Default-Wert für undefined/null (z.B. Migration alter Daten)
function flagOrDefault(value: unknown, defaultValue: boolean): boolean {
  if (value === null || value === undefined) return defaultValue
  return isTruthyFlag(value)
}

function readListLayoutConfig(style: Record<string, any>): ListLayoutConfig {
  return {
    direction: style?.listDirection === 'horizontal' ? 'horizontal' : 'vertical',
    itemSpacing: Number(style?.listItemSpacing ?? 10),
    crossPadding: Number(style?.listCrossPadding ?? 10),
    stretchCrossAxis: flagOrDefault(style?.listStretchCrossAxis, true),
    resizeMainAxis: flagOrDefault(style?.resizeMainAxis, true),
    resizeCrossAxis: flagOrDefault(style?.resizeCrossAxis, false),
    minWidth: Number(style?.minWidth ?? 40),
    minHeight: Number(style?.minHeight ?? 40),
    startOffset: Number(style?.startSize ?? 0)
  }
}

function readFreeLayoutConfig(style: Record<string, any>): FreeLayoutConfig {
  return {
    resizeToContent: style?.resizeToContent === 'none' ? 'none' : 'grow',
    contentPadding: Number(style?.contentPadding ?? 20)
  }
}

/** Resolve the insertion slot before maxGraph constrains moved children to their parent. */
function listReorderAt(graph: Graph, cells: Cell[], evt: MouseEvent, target: Cell | null) {
  const parent = cells[0]?.getParent()
  if (!parent || cells.some(cell => cell.isEdge() || cell.getParent() !== parent) ||
    (target && target !== parent) || !graph.isSwimlane(parent)) return null
  const style = graph.getCellStyle(parent) as Record<string, any>
  if (getContainerLayout(style) !== 'list') return null
  const state = graph.view.getState(parent)
  if (!state) return null
  const point = styleUtils.convertPoint(graph.container, evt.clientX, evt.clientY)
  point.x -= graph.panDx
  point.y -= graph.panDy
  if (point.x < state.x || point.x > state.x + state.width || point.y < state.y || point.y > state.y + state.height) return null

  const config = readListLayoutConfig(style)
  const vertical = config.direction === 'vertical'
  const start = (cell: Cell) => (vertical ? cell.getGeometry()?.y : cell.getGeometry()?.x) ?? 0
  const size = (cell: Cell) => (vertical ? cell.getGeometry()?.height : cell.getGeometry()?.width) ?? 0
  const children = parent.getChildren().filter(cell => !cell.isEdge()).sort((a, b) => start(a) - start(b))
  const moving = children.filter(cell => cells.includes(cell))
  const remaining = children.filter(cell => !cells.includes(cell))
  const position = (vertical ? point.y - state.y : point.x - state.x) / graph.view.scale
  const next = remaining.findIndex(cell => position < start(cell) + size(cell) / 2)
  const index = next < 0 ? remaining.length : next
  const order = [...remaining.slice(0, index), ...moving, ...remaining.slice(index)]
  const last = remaining[remaining.length - 1]
  const offset = index < remaining.length ? start(remaining[index]) : last ? start(last) + size(last) : config.startOffset + config.itemSpacing
  return { parent, order, changed: order.some((cell, i) => cell !== children[i]), vertical, state, offset }
}

// ============================================================================
// Main Setup Function
// ============================================================================

/**
 * Konfiguriert Swimlane-Support für einen MaxGraph
 *
 * @param graph - Die Graph-Instanz
 */
export function setupSwimlaneSupport(graph: Graph, onRejectedContainer?: (container: Cell, cells: Cell[]) => void): void {
  const g = graph as GraphWithSwimlaneSupport

  // Pool-Erkennung (nur für Top-Level Swimlanes)
  g.isPool = function (cell: Cell | null) {
    const parent = cell?.getParent()
    return parent?.getParent() == g.getDataModel().getRoot()
  }

  // Registriere Auto-Stack global
  g.autoStackChildren = (container: Cell) => stackContainerChildren(g, container)

  // Registriere Auto-Resize global
  g.autoResizeSwimlane = (swimlane: Cell) => autoResizeSwimlane(g, swimlane)

  // Drop aktivieren
  g.setDropEnabled(true)
  g.setSplitEnabled(false)

  // MaxGraph's eingebautes "Parent wächst automatisch mit Kind mit" deaktivieren:
  // Es wirkt nur auf den direkten Parent (nicht rekursiv) und würde unsere eigene,
  // modusabhängige Layout-/Resize-Logik umgehen (z.B. bei "list"+stretchCrossAxis).
  g.setExtendParents(false)
  g.setExtendParentsOnAdd(false)
  g.setExtendParentsOnMove(false)

  // Führt Auto-Stack + Auto-Resize für eine Swimlane und alle Vorfahren-Swimlanes aus,
  // solange sich deren Größe dadurch tatsächlich ändert (Layout-Modus wird intern geprüft).
  const relayout = (cell: Cell) => relayoutSwimlaneChain(g, cell)

  // Preview only: do not generate model, undo or collaboration changes during dragging.
  const selection = g.getPlugin<SelectionHandler>('SelectionHandler')
  if (selection) {
    let insertionLine: HTMLDivElement | null = null
    const updateHint = selection.updateHint.bind(selection)
    const removeHint = selection.removeHint.bind(selection)
    selection.removeHint = () => {
      insertionLine?.remove()
      insertionLine = null
      removeHint()
    }
    selection.updateHint = (me) => {
      updateHint(me)
      const slot = me && selection.cells && !selection.cloning && (selection.shape || selection.livePreviewActive)
        ? listReorderAt(g, selection.cells, me.getEvent(), selection.target) : null
      if (!slot?.changed) {
        insertionLine?.remove()
        insertionLine = null
        return
      }
      if (!insertionLine) {
        insertionLine = document.createElement('div')
        insertionLine.setAttribute('aria-hidden', 'true')
        Object.assign(insertionLine.style, { position: 'absolute', pointerEvents: 'none', zIndex: '10',
          background: 'rgb(var(--v-theme-primary))', boxShadow: '0 0 0 1px white', borderRadius: '2px' })
        g.container.appendChild(insertionLine)
      }
      const { state, vertical, offset } = slot
      const position = offset * g.view.scale
      Object.assign(insertionLine.style, {
        left: `${state.x + g.panDx + (vertical ? 0 : position - 1)}px`,
        top: `${state.y + g.panDy + (vertical ? position - 1 : 0)}px`,
        width: `${vertical ? state.width : 3}px`, height: `${vertical ? 3 : state.height}px`
      })
    }
  }

  // Override moveCells um Auto-Stack bei Verschiebungen zu triggern
  const originalMoveCells = g.moveCells.bind(g)
  g.moveCells = function (cells, dx, dy, clone, target, evt) {
    // A drop onto oneself or one's descendants only moves the selection.
    // Keep the existing parents and skip containment validation for this gesture.
    const selfDrop = !!target && !!cells?.some((cell) => cell.isAncestor(target ?? null))
    if (selfDrop) target = null

    if (!selfDrop && onRejectedContainer && evt && cells?.length && (!target || target === this.getDefaultParent())) {
      const point = styleUtils.convertPoint(this.container, evt.clientX, evt.clientY)
      let candidate = this.getCellAt(point.x - this.panDx, point.y - this.panDy)
      while (candidate && !cells.includes(candidate)) {
        if (this.isSwimlane(candidate) || isContainerSectionTarget(candidate)) {
          if (cells.some((cell) => cell.isAncestor(candidate))) {
            target = null
            break
          }
          if (!this.isValidDropTarget(candidate, cells)) {
            onRejectedContainer(candidate, cells.filter((cell) => cell.getParent() !== candidate))
            break
          }
        }
        candidate = candidate.getParent()
      }
    }
    // Layer-gebundene Elemente (z.B. Feedback-Labels) dürfen nicht in Container reparented werden.
    if (target && cells && cells.length > 0) {
      const hasLayerLockedCell = cells.some((cell) => isLayerLockedCell(this, cell))
      const targetIsContainer = this.isSwimlane(target) || isContainerSectionTarget(target)
      if (hasLayerLockedCell && targetIsContainer) {
        target = null
      }
    }

    // Remember source containers before reparenting; a multi-selection can leave
    // several containers. Cloning leaves the originals in place.
    const affectedSwimlanes = new Set<Cell>()
    if (!clone) {
      for (const cell of cells ?? []) {
        const parent = cell.getParent()
        if (!cell.isEdge() && parent && this.isSwimlane(parent)) affectedSwimlanes.add(parent)
      }
    }

    const reorder = !clone && evt ? listReorderAt(this, cells, evt, target ?? null) : null
    let result: Cell[] = []
    this.batchUpdate(() => {
      result = originalMoveCells(cells, dx, dy, clone, target, evt)

      if (reorder) stackContainerChildren(this, reorder.parent, reorder.order)

      for (const cell of result) {
        const parent = cell.getParent()
        if (!cell.isEdge() && parent && this.isSwimlane(parent)) affectedSwimlanes.add(parent)
      }

      // Resize and restack sources and destinations in the same undo operation.
      affectedSwimlanes.forEach((parent) => {
        if (parent.getParent()) relayout(parent)
      })
    })

    return result
  }

  // Auto-Layout bei ADD_CELLS (für neue Cells aus Toolbar)
  g.addListener(InternalEvent.ADD_CELLS, function (_sender: any, evt: EventObject) {
    const addedCells = (evt.getProperty('cells') as Cell[] | undefined) ?? []
    if (!addedCells.length) return

    const parentCell = (evt.getProperty('parent') as Cell | null) ?? addedCells[0].getParent?.() ?? null
    if (parentCell && g.isSwimlane(parentCell)) {
      relayout(parentCell)
    }
  })

  // Auto-Layout bei CELLS_ADDED (zusätzlicher Fallback)
  g.addListener(InternalEvent.CELLS_ADDED, function (_sender: any, evt: EventObject) {
    const addedCells = (evt.getProperty('cells') as Cell[] | undefined) ?? []
    if (!addedCells.length) return

    const parentCell = (evt.getProperty('parent') as Cell | null) ?? addedCells[0].getParent?.() ?? null
    if (parentCell && g.isSwimlane(parentCell)) {
      relayout(parentCell)
    }
  })

  // Auto-Layout beim Entfernen (Element entfernt -> Swimlane anpassen)
  // Der Parent wird vorher gemerkt: Nach dem Entfernen ist er null (cellsRemoved in CellsMixin.js),
  // deshalb fand der frühere CELLS_REMOVED-Listener ihn nie.
  const originalRemoveCells = g.removeCells.bind(g)
  g.removeCells = function (cells, includeEdges) {
    const parents = new Set<Cell>()
    for (const cell of cells ?? []) {
      const parent = cell.getParent?.() ?? null
      if (!cell.isEdge() && parent && this.isSwimlane(parent)) parents.add(parent)
    }

    const result = originalRemoveCells(cells, includeEdges)

    // Ein mitentfernter Parent hat selbst keinen Parent mehr und wird übersprungen
    parents.forEach((parent) => {
      if (parent.getParent()) relayout(parent)
    })
    return result
  }

  // Auto-Layout bei CELLS_RESIZED (Swimlane selbst oder ein Child wurde resized)
  g.addListener(InternalEvent.CELLS_RESIZED, function (_sender: any, evt: EventObject) {
    const resizedCells = (evt.getProperty('cells') as Cell[] | undefined) ?? []
    if (!resizedCells.length) return

    const affectedSwimlanes = new Set<Cell>()
    for (const cell of resizedCells) {
      if (cell.isEdge()) continue

      // Die Swimlane wurde selbst resized -> ihre eigenen Children neu anordnen/strecken
      if (g.isSwimlane(cell)) {
        affectedSwimlanes.add(cell)
      }

      // Ein Child wurde resized -> den Container neu anordnen/anpassen
      const parent = cell.getParent?.() ?? null
      if (parent && g.isSwimlane(parent)) {
        affectedSwimlanes.add(parent)
      }
    }

    affectedSwimlanes.forEach((swimlane) => relayout(swimlane))
  })
}

// ============================================================================
// Core Functions
// ============================================================================

/**
 * Ordnet die Children eines Containers an, sofern `containerLayout: 'list'` aktiv ist.
 *
 * Reihenfolge: Die Kinder werden zunächst nach ihrer aktuellen visuellen Position entlang
 * der Stapelrichtung sortiert (statt nach starrer Modell-/Einfüge-Reihenfolge). Das
 * ermöglicht es, die Reihenfolge einfach per Drag & Drop zu verändern - die neue Position
 * wird anschließend in den Model-Child-Index zurückgeschrieben, damit sie erhalten bleibt.
 *
 * Bei `containerLayout: 'free'` (z.B. Aktivitätsdiagramm-Pool/Lane) wird nichts verändert.
 *
 * @param graph - Die Graph-Instanz
 * @param container - Der Container, dessen Children angeordnet werden sollen
 * @param order - Explicit insertion order resolved from the pointer before moving.
 */
export function stackContainerChildren(graph: Graph, container: Cell, order?: Cell[]): void {
  const style = graph.getCellStyle(container) as Record<string, any>
  if (getContainerLayout(style) !== 'list') return

  const config = readListLayoutConfig(style)
  const geometry = container.getGeometry()
  if (!geometry) return

  const isVertical = config.direction === 'vertical'
  const containerMainCross = isVertical ? geometry.width : geometry.height

  const children: Cell[] = []
  const childCount = container.getChildCount()
  for (let i = 0; i < childCount; i++) {
    const child = container.getChildAt(i)
    if (child && !child.isEdge()) children.push(child)
  }

  const orderedChildren = order ?? [...children].sort((a, b) => {
    const aGeo = a.getGeometry()
    const bGeo = b.getGeometry()
    const aPos = isVertical ? aGeo?.y ?? 0 : aGeo?.x ?? 0
    const bPos = isVertical ? bGeo?.y ?? 0 : bGeo?.x ?? 0
    return aPos - bPos
  })

  let nextMain = config.startOffset + config.itemSpacing

  graph.batchUpdate(() => {
    orderedChildren.forEach((child, index) => {
      // Model-Reihenfolge an die visuelle Reihenfolge angleichen, damit Drag-Reorder erhalten bleibt
      if (container.getIndex(child) !== index) {
        graph.getDataModel().add(container, child, index)
      }

      const childGeo = child.getGeometry()?.clone()
      if (!childGeo) return

      // Kreuz-Achse: Kinder auf volle Containerbreite/-höhe strecken oder nur vom Rand abrücken
      if (config.stretchCrossAxis) {
        if (isVertical) {
          childGeo.x = config.crossPadding
          childGeo.width = containerMainCross - 2 * config.crossPadding
        } else {
          childGeo.y = config.crossPadding
          childGeo.height = containerMainCross - 2 * config.crossPadding
        }
      } else if (config.crossPadding > 0) {
        if (isVertical) childGeo.x = Math.max(config.crossPadding, childGeo.x)
        else childGeo.y = Math.max(config.crossPadding, childGeo.y)
      }

      // Hauptachse: entlang der Stapelrichtung aneinanderreihen
      if (isVertical) {
        childGeo.y = nextMain
        nextMain += childGeo.height + config.itemSpacing
      } else {
        childGeo.x = nextMain
        nextMain += childGeo.width + config.itemSpacing
      }

      childGeo.relative = false
      if (!childGeo.equals(child.getGeometry())) graph.getDataModel().setGeometry(child, childGeo)
    })
  })
}

/**
 * Passt die Größe einer Swimlane automatisch an ihren Inhalt an.
 *
 * - `containerLayout: 'list'`: Die Hauptachse (Stapelrichtung) wird bei aktivem
 *   `resizeMainAxis` exakt auf den Inhalt geschrumpft/vergrößert. Die Kreuz-Achse wird nur
 *   bei aktivem `resizeCrossAxis` angepasst - ist `listStretchCrossAxis` aktiv, bleibt sie
 *   unangetastet, da sie bereits die Kinder vorgibt (verhindert zirkuläre Größenänderungen).
 * - `containerLayout: 'free'`: Bei `resizeToContent: 'grow'` wächst der Container bei Bedarf,
 *   schrumpft aber nie automatisch (z.B. Aktivitätsdiagramm-Pool/Lane). Bei `'none'` passiert nichts.
 *
 * @param graph - Die Graph-Instanz
 * @param swimlane - Die Swimlane, die angepasst werden soll
 */
export function autoResizeSwimlane(graph: Graph, swimlane: Cell): void {
  const geometry = swimlane.getGeometry()?.clone()
  if (!geometry) return

  const style = graph.getCellStyle(swimlane) as Record<string, any>
  const containerLayout = getContainerLayout(style)

  const childCount = swimlane.getChildCount()
  let maxX = 0
  let maxY = 0
  for (let i = 0; i < childCount; i++) {
    const child = swimlane.getChildAt(i)
    if (!child || child.isEdge()) continue
    const childGeo = child.getGeometry()
    if (!childGeo) continue
    maxX = Math.max(maxX, childGeo.x + childGeo.width)
    maxY = Math.max(maxY, childGeo.y + childGeo.height)
  }

  graph.batchUpdate(() => {
    if (containerLayout === 'free') {
      const config = readFreeLayoutConfig(style)
      if (config.resizeToContent !== 'grow') return

      const requiredWidth = maxX + config.contentPadding
      const requiredHeight = maxY + config.contentPadding
      // Nur vergrößern, nie automatisch schrumpfen - Modellierfläche bleibt stabil
      geometry.width = Math.max(geometry.width, requiredWidth)
      geometry.height = Math.max(geometry.height, requiredHeight)
      if (!geometry.equals(swimlane.getGeometry())) graph.getDataModel().setGeometry(swimlane, geometry)
      return
    }

    const config = readListLayoutConfig(style)
    const isVertical = config.direction === 'vertical'

    if (childCount === 0) {
      if (config.resizeMainAxis) {
        if (isVertical) geometry.height = Math.max(config.minHeight, config.startOffset + config.itemSpacing)
        else geometry.width = Math.max(config.minWidth, config.startOffset + config.itemSpacing)
      }
    } else {
      if (config.resizeMainAxis) {
        if (isVertical) geometry.height = Math.max(config.minHeight, maxY + config.itemSpacing)
        else geometry.width = Math.max(config.minWidth, maxX + config.itemSpacing)
      }

      // Kreuz-Achse nur zurückrechnen, wenn sie nicht bereits per stretchCrossAxis fixiert ist
      if (!config.stretchCrossAxis && config.resizeCrossAxis) {
        if (isVertical) geometry.width = Math.max(config.minWidth, maxX + config.crossPadding)
        else geometry.height = Math.max(config.minHeight, maxY + config.crossPadding)
      }
    }

    if (!geometry.equals(swimlane.getGeometry())) graph.getDataModel().setGeometry(swimlane, geometry)
  })
}

/**
 * Führt Auto-Stack + Auto-Resize für eine Swimlane aus und propagiert die Größenänderung
 * die Elternkette hoch (Vorfahren-Swimlanes werden ebenfalls neu layoutet), solange sich
 * die Größe dadurch tatsächlich ändert. Bricht ab, sobald eine Ebene sich nicht mehr ändert
 * oder kein weiterer Vorfahre eine Swimlane ist.
 *
 * @param graph - Die Graph-Instanz
 * @param cell - Die Cell, ab der (inkl. deren Vorfahren) neu layoutet werden soll
 */
export function relayoutSwimlaneChain(graph: Graph, cell: Cell): void {
  let current: Cell | null = cell
  while (current && graph.isSwimlane(current)) {
    const before = current.getGeometry()
    const prevWidth = before?.width
    const prevHeight = before?.height

    stackContainerChildren(graph, current)
    autoResizeSwimlane(graph, current)

    const after = current.getGeometry()
    const sizeChanged = !before || !after || prevWidth !== after.width || prevHeight !== after.height
    if (!sizeChanged) break

    current = current.getParent()
  }
}

/**
 * Fügt Cells zu einem Container hinzu und triggert Auto-Layout
 *
 * Utility-Funktion für Toolbar-Drops und andere programmatische Cell-Additions.
 *
 * @param graph - Die Graph-Instanz
 * @param cells - Array von Cells, die hinzugefügt werden sollen
 * @param target - Das Ziel-Parent (Container, Swimlane, etc.)
 * @returns Die hinzugefügten Cells
 */
export function addCellsToContainer(graph: Graph, cells: Cell[], target: Cell): Cell[] {
  if (!cells || cells.length === 0) return []
  if (!target) return []

  // Verhindere zirkuläre Referenzen über ID-Vergleich
  for (const cell of cells) {
    // Einfache ID-Prüfung: Verhindere wenn target-ID === cell-ID
    if (target.getId() === cell.getId()) {
      console.warn('[addCellsToContainer] Prevented: Cannot add cell to itself (ID match)', {
        cellId: cell.getId(),
        cellLabel: cell.getValue()
      })
      return []
    }

    // Prüfe ob target ein Nachfahre (descendant) der hinzuzufügenden Cell ist
    let currentParent: Cell | null = target
    while (currentParent) {
      if (currentParent.getId() === cell.getId()) {
        console.warn('[addCellsToContainer] Prevented: Cannot add cell to its own descendant', {
          cellId: cell.getId(),
          targetId: target.getId()
        })
        return []
      }
      currentParent = currentParent.getParent?.() ?? null
    }
  }

  const processedCells: Cell[] = []

  graph.getDataModel().beginUpdate()
  try {
    for (const cell of cells) {
      try {
        graph.addCell(cell, target)
        processedCells.push(cell)
      } catch (error) {
        console.error('[setupSwimlaneSupport] Failed to add cell:', error)
      }
    }

    // Auto-Layout triggern, propagiert die Größenänderung auch zu Vorfahren-Swimlanes hoch
    if (graph.isSwimlane(target)) {
      relayoutSwimlaneChain(graph, target)
    }

    // Selektion auf letztes Element setzen
    if (processedCells.length > 0) {
      graph.setSelectionCell(processedCells[processedCells.length - 1])
    }
  } finally {
    graph.getDataModel().endUpdate()
  }

  return processedCells
}
