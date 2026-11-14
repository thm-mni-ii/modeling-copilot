import { InternalEvent, type Cell, type CellOverlay, type Graph } from '@maxgraph/core'
import { createOverlayFromConfig } from './feedbackOverlays'
import { analysisDisplay, analysisHintText, analysisStatus, type AdaptedAnalysis, type AnalysisTarget, type ReferenceHint } from './analysisFeedback'

/** Reference hints on invisible structural containers move to the nearest rendered parent. */
export function analysisTargetCell(graph: Graph, target: AnalysisTarget): Cell | null {
  if (target.kind === 'model' || target.kind === null) return null
  let cell = graph.getDataModel().getCell(target.id)
  const seen = new Set<Cell>()
  while (cell && !seen.has(cell)) {
    seen.add(cell)
    const state = graph.view.getState(cell)
    if (state && (cell.isEdge() || cell.isVertex() && state.width !== 0 && state.height !== 0)) return cell
    cell = cell.getParent()
  }
  return null
}

export const referenceHintTarget = (graph: Graph, hint: ReferenceHint) => analysisTargetCell(graph, hint.target)

/** Runtime overlays only: no style/XML mutation and no removal of other feedback overlays. */
export function installAnalysisOverlays(graph: Graph, analysis: AdaptedAnalysis, select: (id: string) => void) {
  const installed: { cell: Cell; overlay: CellOverlay }[] = []
  const add = (cell: Cell, status: keyof typeof analysisDisplay, tooltip: string, bottom = false, selectedId = cell.getId()!) => {
    const display = analysisDisplay[status]
    const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: display.icon, color: display.color,
      tooltip, align: 'right', verticalAlign: bottom ? 'bottom' : 'top', cursor: 'pointer', offset: { x: 8, y: bottom ? 8 : -8 } })
    overlay.addListener(InternalEvent.CLICK, () => { graph.setSelectionCell(cell); select(selectedId) })
    graph.addCellOverlay(cell, overlay)
    installed.push({ cell, overlay })
  }
  const undisplayedAnnotations = analysis.report.annotations.filter(item => {
    const cell = analysisTargetCell(graph, item.target)
    if (!cell) return true
    const status = analysisStatus(item)
    // Selection keeps the original annotated object even when an invisible container uses its parent.
    add(cell, status, `${analysisDisplay[status].label} (${item.target.id})`, false, item.target.id)
    return false
  })
  const hintsByCell = new Map<Cell, ReferenceHint[]>()
  const placementsByCell = new Map<Cell, Map<string, { text: string; subjectId: string }>>()
  for (const item of analysis.report.annotations) {
    for (const hint of item.hints) {
      if (typeof hint.findingId !== 'string') continue
      for (const target of hint.targets ?? []) {
        if (target.side !== 'submission' || target.id === item.target.id) continue
        const cell = analysisTargetCell(graph, { ...target, side: 'submission' })
        if (!cell) continue
        if (!placementsByCell.has(cell)) placementsByCell.set(cell, new Map())
        placementsByCell.get(cell)!.set(hint.findingId, { text: `${analysisHintText(hint)} (${item.target.id})`, subjectId: item.target.id })
      }
    }
  }
  for (const [cell, findings] of placementsByCell) add(cell, 'warning', [...findings.values()].map(item => item.text).join('\n'), true, findings.values().next().value!.subjectId)
  const modelHints: ReferenceHint[] = []
  for (const hint of analysis.report.referenceHints) {
    const cell = referenceHintTarget(graph, hint)
    if (!cell) modelHints.push(hint)
    else hintsByCell.set(cell, [...(hintsByCell.get(cell) ?? []), hint])
  }
  for (const [cell, hints] of hintsByCell) add(cell, hints.some(hint => hint.status !== 'not_evaluated') ? 'unresolved' : 'not_evaluated', hints.map(hint => `${analysisHintText(hint)} (${hint.label ?? hint.referenceId})`).join('\n'), true)
  for (const group of analysis.report.connectionGroups ?? []) {
    if (!group.hints.length) continue
    for (const id of group.submissionEndpointIds) {
      const item = analysis.report.annotations.find(item => item.target.id === id)
      const cell = item && analysisTargetCell(graph, item.target)
      if (cell) add(cell, group.status === 'different' ? 'warning' : 'unresolved', `Verbindungsgruppe: ${group.hints.map(analysisHintText).join('\n')}`, true, id)
    }
  }
  return { modelHints, undisplayedAnnotations, remove: () => installed.forEach(({ cell, overlay }) => graph.removeCellOverlay(cell, overlay)) }
}
