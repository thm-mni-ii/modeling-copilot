import { InternalEvent, type Cell, type CellOverlay, type Graph } from '@maxgraph/core'
import { createOverlayFromConfig } from './feedbackOverlays'
import { analysisDisplay, analysisHintText, analysisStatus, type AdaptedAnalysis, type ReferenceHint } from './analysisFeedback'

/** Reference hints on invisible structural containers move to the nearest rendered parent. */
export function referenceHintTarget(graph: Graph, hint: ReferenceHint): Cell | null {
  if (hint.target.kind === 'model') return null
  let cell = graph.getDataModel().getCell(hint.target.id)
  const seen = new Set<Cell>()
  while (cell && !seen.has(cell)) {
    seen.add(cell)
    const state = graph.view.getState(cell)
    if (state && (cell.isEdge() || cell.isVertex() && state.width !== 0 && state.height !== 0)) return cell
    cell = cell.getParent()
  }
  return null
}

/** Runtime overlays only: no style/XML mutation and no removal of other feedback overlays. */
export function installAnalysisOverlays(graph: Graph, analysis: AdaptedAnalysis, select: (id: string) => void) {
  const installed: { cell: Cell; overlay: CellOverlay }[] = []
  const add = (cell: Cell, status: keyof typeof analysisDisplay, tooltip: string, bottom = false) => {
    const display = analysisDisplay[status]
    const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: display.icon, color: display.color,
      tooltip, align: 'right', verticalAlign: bottom ? 'bottom' : 'top', cursor: 'pointer', offset: { x: 8, y: bottom ? 8 : -8 } })
    overlay.addListener(InternalEvent.CLICK, () => { graph.setSelectionCell(cell); select(cell.getId()!) })
    graph.addCellOverlay(cell, overlay)
    installed.push({ cell, overlay })
  }
  for (const item of analysis.report.annotations) {
    const cell = graph.getDataModel().getCell(item.target.id)
    if (cell && graph.view.getState(cell)) add(cell, analysisStatus(item), analysisDisplay[analysisStatus(item)].label)
  }
  const hintsByCell = new Map<Cell, ReferenceHint[]>()
  const modelHints: ReferenceHint[] = []
  for (const hint of analysis.report.referenceHints) {
    const cell = referenceHintTarget(graph, hint)
    if (!cell) modelHints.push(hint)
    else hintsByCell.set(cell, [...(hintsByCell.get(cell) ?? []), hint])
  }
  for (const [cell, hints] of hintsByCell) add(cell, 'unresolved', hints.map(hint => `${analysisHintText(hint)} (${hint.label ?? hint.referenceId})`).join('\n'), true)
  return { modelHints, remove: () => installed.forEach(({ cell, overlay }) => graph.removeCellOverlay(cell, overlay)) }
}
