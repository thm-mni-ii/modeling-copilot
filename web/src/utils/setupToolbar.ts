import type { Ref } from 'vue'
import type { Graph, Cell } from '@maxgraph/core'
import { MaxToolbar, Geometry, cellArrayUtils, CellHighlight, Point, styleUtils, constants } from '@maxgraph/core'
import { Cell as MaxGraphCell } from '@maxgraph/core'
import { addCellsToContainer, isContainerSectionTarget } from './setupSwimlaneSupport'
import type { DiagramElement } from '@/model/Element'
import { createCellFromElement, addCellToGraph } from './elementFactory'

/**
 * Shape-Konfiguration für die Toolbar
 */
export interface ShapeConfig {
  name: string
  languageId?: string
  width: number
  height: number
  style: Record<string, any>
  tooltip: string
  image: string
  label?: string
  dropOnDefaultParent?: boolean
  dropHandler?: (graph: Graph, parent: Cell | undefined, position: { x?: number; y?: number }, taskLabel?: string) => void
}

type ToolbarDropContext = {
  cleanup: () => void
}

const resolveContainerSectionTarget = (cell: Cell | null, graph: Graph, droppedCell: Cell): Cell | null => {
  let current = cell

  while (current) {
    if ((graph.isSwimlane(current) || isContainerSectionTarget(current)) && graph.isValidDropTarget(current, [droppedCell])) {
      return current
    }

    // Composite elements such as SERM types expose a dedicated child container.
    // Only resolve an unambiguous section; never guess between multiple sections.
    if (current.isVertex() && !graph.isSwimlane(current)) {
      const sections = current.getChildren().filter((child) =>
        child.isVisible() && !child.isCollapsed() &&
        (graph.isSwimlane(child) || isContainerSectionTarget(child)) &&
        graph.isValidDropTarget(child, [droppedCell])
      )
      if (!current.isCollapsed() && sections.length === 1) return sections[0]
    }

    const nextParent = (current as any).getParent?.() ?? null
    current = nextParent
  }

  return null
}

const resolveEffectiveParent = (graph: Graph, defaultParent: Cell, dropTarget: Cell | null, shape: ShapeConfig, droppedCell: Cell): Cell => {
  if (shape.dropOnDefaultParent || graph.isSwimlane(droppedCell)) {
    return defaultParent
  }

  return resolveContainerSectionTarget(dropTarget, graph, droppedCell) ?? defaultParent
}

const getTargetForEvent = (graph: Graph, evt: MouseEvent): Cell | null => {
  const point = styleUtils.convertPoint(graph.container, evt.clientX, evt.clientY)
  return graph.getCellAt(point.x - graph.panDx, point.y - graph.panDy, null, true, false)
}

const getLocalPosition = (graph: Graph, target: Cell, point: Point): Point => {
  const origin = graph.view.getState(target)?.origin
  return new Point(point.x - (origin?.x ?? 0), point.y - (origin?.y ?? 0))
}

export function ensureGraphDropHandlers(graph: Graph, parent: Ref<Cell | undefined>, shapes: ShapeConfig[], onRejectedContainer?: (container: Cell, cell: Cell, label: string) => void) {
  const graphContainer = graph.container as HTMLElement & {
    __mxToolbarDropContext?: ToolbarDropContext
  }

  graphContainer.__mxToolbarDropContext?.cleanup()

  let draggedShape: ShapeConfig | undefined
  let highlight: CellHighlight | undefined
  const clearHighlight = () => {
    highlight?.destroy()
    highlight = undefined
  }
  const resetDrag = () => {
    draggedShape = undefined
    clearHighlight()
  }
  const readShape = (evt: DragEvent) => {
    const shapeName = evt.dataTransfer?.getData('text/plain')
    let languageId: string | undefined
    let label: string | undefined
    const taskReference = evt.dataTransfer?.getData('application/x-modeling-task-element')
    if (taskReference) {
      try {
        const reference = JSON.parse(taskReference) as { languageId?: string; label?: string }
        languageId = reference.languageId
        label = reference.label?.trim() || undefined
      } catch { /* Ignore malformed optional task metadata. */ }
    }
    return { shape: shapes.find((shape) => shape.name === shapeName && (!languageId || shape.languageId === languageId)), label }
  }
  const createTemplate = (shape: ShapeConfig) => {
    const cell = new MaxGraphCell(null, new Geometry(0, 0, shape.width, shape.height), shape.style)
    cell.setVertex(true)
    ;(cell as any).diagramElementType = shape.name
    return cell
  }
  const resolveTarget = (shape: ShapeConfig, evt: DragEvent, template: Cell) =>
    resolveEffectiveParent(graph, parent.value ?? graph.getDefaultParent(), getTargetForEvent(graph, evt), shape, template)

  // Read the payload while dragstart is writable. Browsers protect it during dragover.
  const dragStartHandler = (evt: DragEvent) => {
    resetDrag()
    draggedShape = readShape(evt).shape
  }
  const dragOverHandler = (evt: DragEvent) => {
    if (!draggedShape || !graph.isEnabled()) return
    evt.preventDefault()
    if (evt.dataTransfer) evt.dataTransfer.dropEffect = 'copy'
    graphContainer.focus({ preventScroll: true })
    const target = resolveTarget(draggedShape, evt, createTemplate(draggedShape))
    const state = target !== (parent.value ?? graph.getDefaultParent()) ? graph.view.getState(target) : null
    if (!state) {
      clearHighlight()
      return
    }
    highlight ??= new CellHighlight(graph, constants.DROP_TARGET_COLOR, 3)
    highlight.highlight(state)
    if (highlight.shape?.node) highlight.shape.node.style.pointerEvents = 'none'
  }
  const dragLeaveHandler = (evt: DragEvent) => {
    if (!(evt.relatedTarget instanceof Node) || !graphContainer.contains(evt.relatedTarget)) clearHighlight()
  }
  const dropHandler = (evt: DragEvent) => {
    clearHighlight()
    if (!graph.isEnabled()) {
      resetDrag()
      return
    }
    const { shape, label } = readShape(evt)
    resetDrag()
    if (!shape) return
    evt.preventDefault()
    graphContainer.focus({ preventScroll: true })
    const template = createTemplate(shape)
    const target = resolveTarget(shape, evt, template)
    if (onRejectedContainer && !shape.dropOnDefaultParent && !graph.isSwimlane(template) && target === (parent.value ?? graph.getDefaultParent())) {
      let candidate = getTargetForEvent(graph, evt)
      while (candidate) {
        if (graph.isSwimlane(candidate) || isContainerSectionTarget(candidate)) {
          if (!graph.isValidDropTarget(candidate, [template])) onRejectedContainer(candidate, template, label || shape.label || shape.name)
          break
        }
        const sections = candidate.getChildren().filter((child) => child.isVisible() && !child.isCollapsed() && (graph.isSwimlane(child) || isContainerSectionTarget(child)))
        if (sections.length === 1 && !candidate.isCollapsed()) {
          if (!graph.isValidDropTarget(sections[0], [template])) onRejectedContainer(sections[0], template, label || shape.label || shape.name)
          break
        }
        candidate = candidate.getParent()
      }
    }
    const point = getLocalPosition(graph, target, graph.getPointForEvent(evt))
    if (shape.dropHandler) {
      shape.dropHandler(graph, target, point, label)
      return
    }
    const cloned = cellArrayUtils.cloneCell(template)!
    ;(cloned as any).diagramElementType = shape.name
    if (cloned.geometry) {
      cloned.geometry.x = point.x
      cloned.geometry.y = point.y
    }
    addCellsToContainer(graph, [cloned], target)
  }
  const cleanup = () => {
    resetDrag()
    document.removeEventListener('dragstart', dragStartHandler)
    document.removeEventListener('dragend', resetDrag)
    document.removeEventListener('drop', resetDrag)
    graphContainer.removeEventListener('dragover', dragOverHandler)
    graphContainer.removeEventListener('dragleave', dragLeaveHandler)
    graphContainer.removeEventListener('drop', dropHandler)
    delete graphContainer.__mxToolbarDropContext
  }
  document.addEventListener('dragstart', dragStartHandler)
  document.addEventListener('dragend', resetDrag)
  document.addEventListener('drop', resetDrag)
  graphContainer.addEventListener('dragover', dragOverHandler)
  graphContainer.addEventListener('dragleave', dragLeaveHandler)
  graphContainer.addEventListener('drop', dropHandler)
  graphContainer.__mxToolbarDropContext = { cleanup }
  return cleanup
}

/**
 * Setup-Funktion für die MaxGraph Toolbar
 *
 * Erstellt eine Toolbar mit Drag & Drop Shapes:
 * - Rechteck, Ellipse, Raute, Dreieck, Wolke
 * - Click-to-add Funktionalität
 * - Drag & Drop zum Graph
 *
 * @param graph - Ref auf die Graph-Instanz
 * @param toolbarContainer - Ref auf den Toolbar-Container
 * @param parent - Ref auf die Parent-Zelle
 * @param showToolbar - Ob die Toolbar angezeigt werden soll
 * @param shapes - Array von Shape-Konfigurationen
 */
export function setupToolbar(graph: Ref<Graph | undefined>, toolbarContainer: Ref<HTMLElement | undefined>, parent: Ref<Cell | undefined>, showToolbar: boolean, shapes: ShapeConfig[]) {
  // Prüfe ob Toolbar überhaupt angezeigt werden soll
  if (!showToolbar) {
    return
  }

  // Prüfe ob der Toolbar-Container verfügbar ist
  if (!toolbarContainer.value) {
    console.warn('Toolbar container not available yet')
    return
  }

  if (!graph.value) {
    console.warn('Graph not available yet')
    return
  }

  try {
    const toolbar = new MaxToolbar(toolbarContainer.value)
    toolbar.enabled = true

    // Erstelle MaxGraph Toolbar Items
    for (const shape of shapes) {
      const cell = new MaxGraphCell(shape.label ?? shape.name, new Geometry(0, 0, shape.width, shape.height), shape.style)
      cell.setVertex(true)
      ;(cell as any).diagramElementType = shape.name

      // Erstelle einen Drop-Handler für Drag & Drop
      const dropHandler = (graph: Graph, evt: MouseEvent, target: Cell | null, x?: number, y?: number) => {
        const defaultParent = parent.value ?? graph.getDefaultParent()
        const point = graph.getPointForEvent(evt)
        const resolvedX = x ?? point.x
        const resolvedY = y ?? point.y

        const dropTarget = target ?? getTargetForEvent(graph, evt)
        const effectiveParent = resolveEffectiveParent(graph, defaultParent, dropTarget, shape, cell)
        const localPoint = getLocalPosition(graph, effectiveParent, new Point(resolvedX, resolvedY))
        graph.container.focus({ preventScroll: true })

        if (shape.dropHandler) {
          shape.dropHandler(graph, effectiveParent, { x: localPoint.x, y: localPoint.y })
          return
        }

        const cloned = cellArrayUtils.cloneCell(cell)!
        ;(cloned as any).diagramElementType = (cell as any).diagramElementType ?? shape.name
        if (cloned.geometry) {
          cloned.geometry.x = localPoint.x
          cloned.geometry.y = localPoint.y
        }

        // Nutze zentrale Funktion für Container-Drops
        addCellsToContainer(graph, [cloned], effectiveParent)
      }

      // Füge das Tool zur Toolbar hinzu
      const img = toolbar.addMode(
        shape.name,
        shape.image,
        (evt: MouseEvent, cell: Cell) => {
          const pt = graph.value!.getPointForEvent(evt)
          dropHandler(graph.value!, evt, cell, pt.x, pt.y)
        },
        shape.tooltip
      )

      // Konfiguriere Drag & Drop für das Image
      if (img) {
        img.style.cursor = 'move'

        // Erstelle einen Drag-Handler
        const dragHandler = (evt: DragEvent) => {
          if (evt.dataTransfer) {
            evt.dataTransfer.setData('text/plain', shape.name)
            evt.dataTransfer.effectAllowed = 'copy'
          }
        }

        // Mache das Image draggable
        img.setAttribute('draggable', 'true')
        img.addEventListener('dragstart', dragHandler)
      }
    }

    ensureGraphDropHandlers(graph.value, parent, shapes)
  } catch (error) {
    console.error('Error initializing toolbar:', error)
  }
}

/**
 * Erstellt Shape-Konfigurationen aus DiagramElement-Definitionen
 *
 * Wandelt DiagramElement-Definitionen in das Format um,
 * das von der MaxGraph Toolbar erwartet wird.
 *
 * @param elements - Array von DiagramElement-Definitionen
 * @param placeholderImage - Platzhalter-Bild für Shapes
 * @returns Array von ShapeConfig-Definitionen
 */
export function buildShapesFromElements(elements: DiagramElement[], placeholderImage: string, languageId?: string): ShapeConfig[] {
  return elements.map((element) => {
    const width = element.width ?? 120
    const height = element.height ?? 80
    const style = element.style ?? {}

    // Basis-Style: Übernehme ALLE Style-Eigenschaften aus der Element-Definition
    const baseStyle: Record<string, any> = {
      shape: element.renderMode === 'swimlane' ? 'swimlane' : element.predefinedShape ?? 'rectangle',
      ...style, // Alle Style-Eigenschaften aus Definition übernehmen
      // Nur Defaults für fehlende Werte (identisch zu elementFactory.ts)
      strokeColor: style.strokeColor ?? 'black',
      fillColor: style.fillColor ?? '#f5f5f5',
      strokeWidth: style.strokeWidth ?? 1,
      fontSize: style.fontSize ?? 11,
      fontColor: style.fontColor ?? 'black',
      fontFamily: style.fontFamily ?? 'Arial',
      align: style.align ?? 'center',
      verticalAlign: style.verticalAlign ?? 'middle'
    }

    // Swimlane-spezifische Eigenschaften (nur Defaults, wenn nicht gesetzt)
    if (element.renderMode === 'swimlane') {
      if (baseStyle.startSize === undefined) baseStyle.startSize = 22
      if (baseStyle.horizontal === undefined) baseStyle.horizontal = false
      if (baseStyle.swimlaneLine === undefined) baseStyle.swimlaneLine = true
      if (baseStyle.layoutPreset === undefined) baseStyle.layoutPreset = 'list'
      if (baseStyle.labelBackgroundColor === undefined) baseStyle.labelBackgroundColor = 'transparent'
      if (baseStyle.containerLayout === undefined) baseStyle.containerLayout = 'list'
      if (baseStyle.listDirection === undefined) baseStyle.listDirection = 'vertical'
      if (baseStyle.listItemSpacing === undefined) baseStyle.listItemSpacing = 10
      if (baseStyle.listCrossPadding === undefined) baseStyle.listCrossPadding = 10
      if (baseStyle.listStretchCrossAxis === undefined) baseStyle.listStretchCrossAxis = true
      if (baseStyle.resizeMainAxis === undefined) baseStyle.resizeMainAxis = true
      if (baseStyle.resizeCrossAxis === undefined) baseStyle.resizeCrossAxis = false
    }

    return {
      name: element.type,
      languageId,
      label: element.defaultLabel ?? element.type,
      width,
      height,
      style: baseStyle,
      tooltip: element.type,
      image: placeholderImage,
      dropHandler: (graphInstance: Graph, parentCell: Cell | undefined, position: { x?: number; y?: number }, taskLabel?: string) => {
        const parentTarget = parentCell ?? graphInstance.getDefaultParent()
        const x = (position.x ?? 0) - width / 2
        const y = (position.y ?? 0) - height / 2

        // Nutze die zentrale Element-Erstellungsmethode
        const cellToInsert = createCellFromElement(element, x, y)
        if (taskLabel && element.allowLabelEdit !== false) {
          cellToInsert.setValue(taskLabel)
          ;(cellToInsert as any).diagramAttributes = {
            ...(cellToInsert as any).diagramAttributes,
            label: taskLabel
          }
        }

        // Füge zum Graph hinzu mit Child-Elementen
        addCellToGraph(graphInstance, cellToInsert, element, parentTarget)

        graphInstance.setSelectionCell(cellToInsert)
      }
    }
  })
}

/**
 * Erstellt die Standard-Shape-Konfigurationen
 *
 * @param images - Objekt mit den Image-Pfaden
 */
export function createDefaultShapes(images: { rectangle: string; ellipse: string; rhombus: string; triangle: string; cloud: string }): ShapeConfig[] {
  return [
    {
      name: 'rectangle',
      width: 80,
      height: 60,
      style: { shape: 'rectangle', perimeter: 'rectanglePerimeter', fillColor: '#f0f0f0' },
      tooltip: 'Rectangle (Drag & Drop)',
      image: images.rectangle
    },
    {
      name: 'ellipse',
      width: 60,
      height: 60,
      style: { shape: 'ellipse', perimeter: 'ellipsePerimeter', fillColor: '#e3f2fd' },
      tooltip: 'Ellipse (Drag & Drop)',
      image: images.ellipse
    },
    {
      name: 'diamond',
      width: 70,
      height: 70,
      style: { shape: 'rhombus', perimeter: 'rhombusPerimeter', fillColor: '#fff3e0' },
      tooltip: 'Diamond (Drag & Drop)',
      image: images.rhombus
    },
    {
      name: 'triangle',
      width: 60,
      height: 60,
      style: { shape: 'triangle', perimeter: 'trianglePerimeter', fillColor: '#f3e5f5' },
      tooltip: 'Triangle (Drag & Drop)',
      image: images.triangle
    },
    {
      name: 'cloud',
      width: 100,
      height: 60,
      style: { shape: 'cloud', perimeter: 'rectanglePerimeter', fillColor: '#fce4ec' },
      tooltip: 'Cloud (Drag & Drop)',
      image: images.cloud
    }
  ]
}
