import { Cell, EventObject, Graph, InternalEvent } from '@maxgraph/core'
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

const isContainerSectionTarget = (cell: Cell | null): boolean => {
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

// ============================================================================
// Main Setup Function
// ============================================================================

/**
 * Konfiguriert Swimlane-Support für einen MaxGraph
 *
 * @param graph - Die Graph-Instanz
 */
export function setupSwimlaneSupport(graph: Graph): void {
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

  // Override moveCells um Auto-Stack bei Verschiebungen zu triggern
  const originalMoveCells = g.moveCells.bind(g)
  g.moveCells = function (cells, dx, dy, clone, target, evt) {
    // Layer-gebundene Elemente (z.B. Feedback-Labels) dürfen nicht in Container reparented werden.
    if (target && cells && cells.length > 0) {
      const hasLayerLockedCell = cells.some((cell) => isLayerLockedCell(this, cell))
      const targetIsContainer = this.isSwimlane(target) || isContainerSectionTarget(target)
      if (hasLayerLockedCell && targetIsContainer) {
        target = null
      }
    }

    // Verhindere zirkuläre Referenzen: Prüfe ob eine Cell in sich selbst verschoben wird
    if (target && cells && cells.length > 0) {
      for (const cell of cells) {
        // Einfache ID-Prüfung: Verhindere wenn target-ID === cell-ID
        if (target.getId() === cell.getId()) {
          console.warn('[moveCells] Prevented: Cannot move cell into itself (ID match)', {
            cellId: cell.getId(),
            cellLabel: cell.getValue()
          })
          return cells // Verhindere die Bewegung, gib original cells zurück
        }

        // Prüfe auch ob target ein Nachfahre (descendant) der zu bewegenden Cell ist
        let currentParent: Cell | null = target
        while (currentParent) {
          if (currentParent.getId() === cell.getId()) {
            console.warn('[moveCells] Prevented: Cannot move cell into its own descendant', {
              cellId: cell.getId(),
              targetId: target.getId()
            })
            return cells // Verhindere die Bewegung
          }
          currentParent = currentParent.getParent?.() ?? null
        }
      }
    }

    const result = originalMoveCells(cells, dx, dy, clone, target, evt)

    // Layout wenn Ziel-Parent eine Swimlane ist
    if (result && result.length > 0) {
      const movedCell = result[0]
      const parentCell = movedCell?.getParent?.() ?? null
      if (parentCell && this.isSwimlane(parentCell)) {
        relayout(parentCell)
      }
    }

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

  // Auto-Layout bei CELLS_REMOVED (Element entfernt -> Swimlane anpassen)
  g.addListener(InternalEvent.CELLS_REMOVED, function (_sender: any, evt: EventObject) {
    const removedCells = (evt.getProperty('cells') as Cell[] | undefined) ?? []
    if (!removedCells.length) return

    const affectedSwimlanes = new Set<Cell>()
    for (const cell of removedCells) {
      if (cell.isEdge()) continue
      const parent = cell.getParent?.() ?? null
      if (parent && g.isSwimlane(parent)) {
        affectedSwimlanes.add(parent)
      }
    }

    affectedSwimlanes.forEach((swimlane) => relayout(swimlane))
  })

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
 */
export function stackContainerChildren(graph: Graph, container: Cell): void {
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

  const orderedChildren = [...children].sort((a, b) => {
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

      const childGeo = child.getGeometry()
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
      graph.getDataModel().setGeometry(child, childGeo)
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
  const geometry = swimlane.getGeometry()
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
      graph.getDataModel().setGeometry(swimlane, geometry)
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

    graph.getDataModel().setGeometry(swimlane, geometry)
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
