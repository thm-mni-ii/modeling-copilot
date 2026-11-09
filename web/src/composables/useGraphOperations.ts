import { type Ref } from 'vue'
import type { Graph, Cell } from '@maxgraph/core'
import { cellArrayUtils, Point } from '@maxgraph/core'

/**
 * Composable für grundlegende Graph-Operationen
 *
 * Bietet Funktionen für:
 * - Löschen von ausgewählten Zellen
 * - Duplizieren von ausgewählten Zellen
 * - Alle Zellen auswählen
 * - Auswahl aufheben
 *
 * @param graph - Ref auf die Graph-Instanz
 * @param parent - Ref auf die Parent-Zelle (optional, für Duplicate-Operation)
 */
export function useGraphOperations(graph: Ref<Graph | undefined>, parent?: Ref<Cell | undefined>) {
  /**
   * Konvertiert absolute Bildschirmkoordinaten in Graph-Koordinaten
   */
  const toGraphCoordinates = (x: number, y: number): Point => {
    const scale = graph.value!.view.scale
    const translate = graph.value!.view.translate
    return new Point(x / scale - translate.x, y / scale - translate.y)
  }

  /**
   * Trennt eine Kante von einem Vertex und setzt einen absoluten Terminal-Punkt
   * damit die Kante auch ohne Verbindung sichtbar bleibt
   * Behält alle Waypoints und den Style der Kante bei
   */
  const disconnectEdgeFromVertex = (edge: Cell, vertex: Cell, model: any) => {
    const source = edge.getTerminal(true)
    const target = edge.getTerminal(false)
    const state = graph.value!.view.getState(edge)

    if (!state?.absolutePoints || state.absolutePoints.length === 0) return

    const geo = edge.geometry?.clone()
    if (!geo) return

    // Sammle alle Waypoints (ohne Source und Target Punkte)
    const waypoints: Point[] = []
    if (state.absolutePoints.length > 2) {
      for (let i = 1; i < state.absolutePoints.length - 1; i++) {
        const point = state.absolutePoints[i]
        if (point) {
          waypoints.push(toGraphCoordinates(point.x, point.y))
        }
      }
    }

    // Kopiere den aktuellen Style
    const currentStyle = edge.style ? { ...edge.style } : {}

    // Wenn die Source mit dem zu löschenden Vertex verbunden ist
    if (source === vertex) {
      const point = state.absolutePoints[0]
      if (point) {
        // Setze den Source-Punkt als absoluten Terminal-Punkt
        geo.setTerminalPoint(toGraphCoordinates(point.x, point.y), true)
        // Trenne die Verbindung
        model.setTerminal(edge, null, true)

        // Entferne Exit-Constraints aus dem Style
        delete currentStyle.exitX
        delete currentStyle.exitY
        delete currentStyle.exitPerimeter
      }
    }

    // Wenn das Target mit dem zu löschenden Vertex verbunden ist
    if (target === vertex) {
      const point = state.absolutePoints[state.absolutePoints.length - 1]
      if (point) {
        // Setze den Target-Punkt als absoluten Terminal-Punkt
        geo.setTerminalPoint(toGraphCoordinates(point.x, point.y), false)
        // Trenne die Verbindung
        model.setTerminal(edge, null, false)

        // Entferne Entry-Constraints aus dem Style
        delete currentStyle.entryX
        delete currentStyle.entryY
        delete currentStyle.entryPerimeter
      }
    }

    // Setze die Waypoints zurück (falls vorhanden)
    if (waypoints.length > 0) {
      geo.points = waypoints
    }

    // Aktualisiere Style und Geometrie
    edge.style = currentStyle
    model.setGeometry(edge, geo)
  }

  /**
   * Trennt alle Kanten von einem Vertex
   */
  const disconnectEdgesFromVertex = (vertex: Cell, edgesToDelete: Cell[], model: any) => {
    const edges = graph.value!.getEdges(vertex)

    edges.forEach((edge) => {
      // Nur trennen wenn die Kante nicht auch gelöscht wird
      if (!edgesToDelete.includes(edge)) {
        disconnectEdgeFromVertex(edge, vertex, model)
      }
    })
  }

  /**
   * Zerstört die SVG-Shapes von Zellen
   */
  const destroyShapes = (cells: Cell[]) => {
    cells.forEach((cell) => {
      const state = graph.value!.view.getState(cell)
      if (state?.shape) {
        state.shape.destroy()
      }
    })
  }

  /**
   * Löscht alle aktuell ausgewählten Zellen
   * Kanten werden von gelöschten Knoten getrennt, aber nicht gelöscht
   * Die getrennten Kanten bleiben sichtbar und können neu verbunden werden
   */
  const deleteSelected = () => {
    if (!graph.value) return

    // The native filter, so cells that are not deletable stay (isCellDeletable, CellsMixin.js)
    const cells = graph.value.getDeletableCells(graph.value.getSelectionCells())
    if (cells.length === 0) return

    const model = graph.value.getDataModel()
    const verticesToDelete = cells.filter((cell) => cell.isVertex())
    const edgesToDelete = cells.filter((cell) => cell.isEdge())

    model.beginUpdate()
    try {
      // Trenne alle Kanten von den zu löschenden Knoten
      verticesToDelete.forEach((vertex) => {
        disconnectEdgesFromVertex(vertex, edgesToDelete, model)
      })

      // Zerstöre die SVG-Shapes der zu löschenden Zellen
      destroyShapes(verticesToDelete)
      destroyShapes(edgesToDelete)

      // Entferne die Zellen aus dem Graph
      if (verticesToDelete.length > 0) {
        graph.value!.removeCells(verticesToDelete, false)
      }
      if (edgesToDelete.length > 0) {
        graph.value!.removeCells(edgesToDelete)
      }
    } finally {
      model.endUpdate()
    }

    // View aufräumen
    graph.value.view.validate()
    graph.value.refresh()
  }

  /**
   * Dupliziert alle aktuell ausgewählten Zellen
   * Verschiebt die Duplikate um 20px nach rechts und unten
   */
  const duplicateSelected = () => {
    if (!graph.value) return

    const cells = graph.value.getSelectionCells()
    if (cells.length === 0) return

    const cloned = cellArrayUtils.cloneCells(cells)

    // Verschiebe geklonte Zellen um 20px nach rechts und unten
    cloned.forEach((cell) => {
      if (cell.geometry) {
        cell.geometry.x += 20
        cell.geometry.y += 20
      }
    })

    // Füge jede Zelle einzeln hinzu
    cloned.forEach((cell) => {
      if (cell && parent?.value) {
        graph.value!.addCell(cell, parent.value)
      }
    })

    // Wähle die geklonten Zellen aus
    graph.value.setSelectionCells(cloned)
  }

  /**
   * Wählt alle Zellen im Graph aus
   */
  const selectAll = () => {
    if (!graph.value) return
    graph.value.selectAll()
  }

  /**
   * Hebt die Auswahl aller Zellen auf
   */
  const clearSelection = () => {
    if (!graph.value) return
    graph.value.clearSelection()
  }

  return {
    deleteSelected,
    duplicateSelected,
    selectAll,
    clearSelection
  }
}
