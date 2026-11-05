import { type Ref } from 'vue'
import type { Graph, PanningHandler } from '@maxgraph/core'

/**
 * Composable für Grid- und Snap-Einstellungen
 *
 * Bietet Funktionen für:
 * - Grid-Größe aktualisieren
 * - Snap-to-Grid aktivieren/deaktivieren
 * - Maus-Toleranz einstellen
 * - Grid ein/ausschalten (Toggle)
 * - Grid neu zeichnen erzwingen
 * - UseGrid für Panning aktivieren/deaktivieren
 *
 * @param graph - Ref auf die Graph-Instanz
 * @param gridSize - Ref auf die Grid-Größe
 * @param snapToGrid - Ref auf den Snap-to-Grid Status
 * @param tolerance - Ref auf die Maus-Toleranz
 * @param useGridForPanning - Ref auf den UseGrid Status für Panning
 */
export function useGridSettings(graph: Ref<Graph | undefined>, gridSize: Ref<number>, snapToGrid: Ref<boolean>, tolerance: Ref<number>, useGridForPanning: Ref<boolean>) {
  const forceGridRepaint = () => (graph.value as (Graph & { repaintGrid?: () => void }) | undefined)?.repaintGrid?.()
  /**
   * Aktualisiert die Grid-Größe und zeichnet das Raster neu
   */
  const updateGridSize = (newSize?: number) => {
    if (newSize !== undefined) {
      gridSize.value = newSize
    }
    if (!graph.value) return

    graph.value.gridSize = gridSize.value
    graph.value.setGridSize(gridSize.value)
    graph.value.setGridEnabled(snapToGrid.value)
    forceGridRepaint()
  }

  /**
   * Aktiviert oder deaktiviert Snap-to-Grid
   * Aktualisiert das Grid entsprechend
   */
  const updateSnapToGrid = (newValue?: boolean) => {
    if (newValue !== undefined) {
      snapToGrid.value = newValue
    }

    if (!graph.value) return

    graph.value.setGridEnabled(snapToGrid.value)

    if (snapToGrid.value) {
      graph.value.gridSize = gridSize.value
      graph.value.setGridSize(gridSize.value)
    }

    forceGridRepaint()
  }

  /**
   * Aktualisiert die Maus-Toleranz für Event-Erkennung
   */
  const updateTolerance = (newValue?: number) => {
    if (newValue !== undefined) {
      tolerance.value = newValue
    }

    if (!graph.value) return

    // MaxGraph verwendet eventTolerance
    graph.value.setEventTolerance(tolerance.value)
  }

  /**
   * Aktiviert oder deaktiviert UseGrid für Panning
   * Aktualisiert den PanningHandler entsprechend
   */
  const updateUseGridForPanning = (newValue?: boolean) => {
    if (newValue !== undefined) {
      useGridForPanning.value = newValue
    }

    if (!graph.value) return

    // Aktualisiere PanningHandler
    const panningHandler = graph.value.getPlugin<PanningHandler>('PanningHandler')
    if (panningHandler) {
      panningHandler.useGrid = useGridForPanning.value
    }
  }

  /**
   * Schaltet das Grid ein oder aus (Toggle)
   * Invertiert den aktuellen snapToGrid-Wert
   */
  const toggleGrid = () => {
    snapToGrid.value = !snapToGrid.value
    updateSnapToGrid()

  }

  return {
    updateGridSize,
    updateSnapToGrid,
    updateTolerance,
    updateUseGridForPanning,
    toggleGrid,
    forceGridRepaint
  }
}
