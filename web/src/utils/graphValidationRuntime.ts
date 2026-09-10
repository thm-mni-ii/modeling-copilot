import type { Cell, CellOverlay, Graph } from '@maxgraph/core'
import type { AutonomyMode } from '@/model/Autonomy'

const VALIDATION_MODE_KEY = Symbol('validationMode')
const VALIDATION_PASS_KEY = Symbol('validationPass')

type ValidationRuntimeCarrier = {
  [VALIDATION_MODE_KEY]?: AutonomyMode
  [VALIDATION_PASS_KEY]?: boolean
}

type WarningImageProvider = {
  getWarningImage(): { src: string; width: number; height: number }
}

export const setGraphValidationMode = (graph: object, mode: AutonomyMode): void => {
  ;(graph as ValidationRuntimeCarrier)[VALIDATION_MODE_KEY] = mode
}

export const getGraphValidationMode = (graph: object): AutonomyMode => {
  return (graph as ValidationRuntimeCarrier)[VALIDATION_MODE_KEY] ?? 'free'
}

export const setValidationPassActive = (graph: object, active: boolean): void => {
  ;(graph as ValidationRuntimeCarrier)[VALIDATION_PASS_KEY] = active
}

export const isValidationPassActive = (graph: object): boolean => {
  return Boolean((graph as ValidationRuntimeCarrier)[VALIDATION_PASS_KEY])
}

export const shouldBlockInteractiveValidation = (graph: object): boolean => {
  return getGraphValidationMode(graph) === 'preventive'
}

export const isValidationWarningOverlay = (graph: WarningImageProvider, overlay: CellOverlay): boolean => {
  const warningImage = graph.getWarningImage()
  const overlayImage = overlay.image

  return overlayImage?.src === warningImage.src && overlayImage?.width === warningImage.width && overlayImage?.height === warningImage.height
}

export const clearValidationWarningOverlays = (graph: Graph): void => {
  const root = graph.getDataModel().getRoot()
  if (!root) return

  const clearOnCell = (cell: Cell) => {
    const overlays = graph.getCellOverlays(cell) ?? []
    overlays.forEach((overlay) => {
      if (isValidationWarningOverlay(graph, overlay)) {
        graph.removeCellOverlay(cell, overlay)
      }
    })

    const childCount = cell.getChildCount()
    for (let index = 0; index < childCount; index += 1) {
      clearOnCell(cell.getChildAt(index))
    }
  }

  clearOnCell(root)
}
