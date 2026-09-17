import type { Ref } from 'vue'
import type { Graph, Cell } from '@maxgraph/core'
import { MaxToolbar, Geometry, cellArrayUtils } from '@maxgraph/core'
import { Cell as MaxGraphCell } from '@maxgraph/core'
import { addCellsToContainer } from './setupSwimlaneSupport'
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
  dropHandler?: (graph: Graph, parent: Cell | undefined, position: { x?: number; y?: number }, taskLabel?: string) => void
}

type ToolbarDropContext = {
  getShapes: () => ShapeConfig[]
  dragOverHandler?: (event: DragEvent) => void
  dropHandler?: (event: DragEvent) => void
}

const isTruthyAttribute = (value: string | null | undefined) => {
  if (value === null || value === undefined) {
    return false
  }

  const normalized = value.toString().trim().toLowerCase()
  return normalized !== '' && normalized !== '0' && normalized !== 'false'
}

const resolveContainerSectionTarget = (cell: Cell | null, graph?: Graph): Cell | null => {
  let current = cell

  while (current) {
    if (graph?.isSwimlane(current)) {
      return current
    }

    const attribute = (current as any).getAttribute?.('containerSection', null)
    if (isTruthyAttribute(attribute)) {
      return current
    }

    const nextParent = (current as any).getParent?.() ?? null
    current = nextParent
  }

  return null
}

const resolveEffectiveParent = (graph: Graph, defaultParent: Cell, dropTarget: Cell | null, isSwimlaneDrop: boolean): Cell => {
  if (isSwimlaneDrop) {
    return defaultParent
  }

  const containerSection = resolveContainerSectionTarget(dropTarget, graph)
  if (containerSection) {
    return containerSection
  }

  if (dropTarget && graph.isSwimlane(dropTarget)) {
    return dropTarget
  }

  return defaultParent
}

export function ensureGraphDropHandlers(graph: Graph, parent: Ref<Cell | undefined>, shapes: ShapeConfig[]) {
  const graphContainer = graph.container as HTMLElement & {
    __mxToolbarDropContext?: ToolbarDropContext
  }

  let context = graphContainer.__mxToolbarDropContext
  if (!context) {
    context = {
      getShapes: () => shapes
    }
    graphContainer.__mxToolbarDropContext = context
  }

  context.getShapes = () => shapes

  if (!context.dragOverHandler) {
    context.dragOverHandler = (evt: DragEvent) => {
      evt.preventDefault()
      if (evt.dataTransfer) {
        evt.dataTransfer.dropEffect = 'copy'
      }
    }

    graphContainer.addEventListener('dragover', context.dragOverHandler)
  }

  if (!context.dropHandler) {
    context.dropHandler = (evt: DragEvent) => {
      evt.preventDefault()

      const shapesList = context?.getShapes?.() ?? []
      if (!shapesList.length) {
        return
      }

      const { dataTransfer } = evt
      if (!dataTransfer) {
        return
      }

      const shapeName = dataTransfer.getData('text/plain')
      const taskReference = dataTransfer.getData('application/x-modeling-task-element')
      let taskLanguageId: string | undefined
      let taskLabel: string | undefined
      if (taskReference) {
        try {
          const reference = JSON.parse(taskReference) as { languageId?: string; label?: string }
          taskLanguageId = reference.languageId
          taskLabel = reference.label?.trim() || undefined
        } catch {
          taskLanguageId = undefined
        }
      }
      const shape = shapesList.find((s) => s.name === shapeName && (!taskLanguageId || s.languageId === taskLanguageId))

      if (!shape) {
        return
      }

      const graphInstance = graph
      const defaultParent = parent.value ?? graphInstance.getDefaultParent()
      const point = graphInstance.getPointForEvent(evt as any)

      const templateCell = new MaxGraphCell(null, new Geometry(0, 0, shape.width, shape.height), shape.style)
      templateCell.setVertex(true)
      ;(templateCell as any).diagramElementType = shape.name

      const isDroppingSwimlane = shape.style?.shape === 'swimlane' || graphInstance.isSwimlane(templateCell as unknown as Cell)
      const dropTarget = graphInstance.getCellAt(point.x, point.y)
      const effectiveParent = resolveEffectiveParent(graphInstance, defaultParent, dropTarget, isDroppingSwimlane)

      if (shape.dropHandler) {
        shape.dropHandler(graphInstance, effectiveParent, { x: point.x, y: point.y }, taskLabel)
        return
      }

      const cloned = cellArrayUtils.cloneCell(templateCell)!
      ;(cloned as any).diagramElementType = (templateCell as any).diagramElementType ?? shape.name
      if (cloned.geometry) {
        const newGeometry = new Geometry(point.x, point.y, cloned.geometry.width, cloned.geometry.height)
        if (cloned.geometry.alternateBounds) {
          newGeometry.alternateBounds = new Geometry(cloned.geometry.alternateBounds.x, cloned.geometry.alternateBounds.y, cloned.geometry.alternateBounds.width, cloned.geometry.alternateBounds.height) as any
        }
        cloned.geometry = newGeometry
      }

      // Nutze zentrale Funktion für Container-Drops
      addCellsToContainer(graphInstance, [cloned], effectiveParent)
    }

    graphContainer.addEventListener('drop', context.dropHandler)
  }
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

        const dropTarget = target ?? graph.getCellAt(resolvedX, resolvedY)
        const isDroppingSwimlane = shape.style?.shape === 'swimlane' || graph.isSwimlane(cell as unknown as Cell)
        const effectiveParent = resolveEffectiveParent(graph, defaultParent, dropTarget, isDroppingSwimlane)

        if (shape.dropHandler) {
          shape.dropHandler(graph, effectiveParent, { x: resolvedX, y: resolvedY })
          return
        }

        const cloned = cellArrayUtils.cloneCell(cell)!
        ;(cloned as any).diagramElementType = (cell as any).diagramElementType ?? shape.name
        if (cloned.geometry) {
          cloned.geometry.x = resolvedX
          cloned.geometry.y = resolvedY
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
      if (baseStyle.labelBackgroundColor === undefined) baseStyle.labelBackgroundColor = 'transparent'
      if (baseStyle.childSpacing === undefined) baseStyle.childSpacing = 10
      if (baseStyle.childSpacingX === undefined) baseStyle.childSpacingX = 10
      if (baseStyle.autoFitWidth === undefined) baseStyle.autoFitWidth = true
      if (baseStyle.autoStackY === undefined) baseStyle.autoStackY = true
      if (baseStyle.autoResize === undefined) baseStyle.autoResize = true
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
