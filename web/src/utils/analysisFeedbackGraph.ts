import { CellHighlight, InternalEvent, Rectangle, RectangleShape, type Cell, type CellOverlay, type Graph } from '@maxgraph/core'
import { createOverlayFromConfig } from './feedbackOverlays'
import type { HelpFeedbackNote } from '@/services/api/types/evaluation'
import { analysisDisplay, analysisHintText, analysisStudentQuestions, analysisOverviewAppearance, analysisOverviewStatus, analysisStatus, displayStatusOrder, type AdaptedAnalysis, type AnalysisTarget, type DisplayStatus, type ReferenceHint } from './analysisFeedback'

/** A runtime frame without custom element fills, selection handles or model changes. */
export function createCellOutline(graph: Graph, cell: Cell) {
  const highlight = new CellHighlight(graph, '#64b5f6', 2)
  highlight.spacing = 4
  const createShape = highlight.createShape.bind(highlight)
  highlight.createShape = () => {
    const shape = cell.isEdge() ? createShape() : new RectangleShape(new Rectangle(), 'none', '#64b5f6', 2)
    if (!shape) return null
    // Set before the first redraw: SVG children can override pointer-events on their group.
    shape.pointerEvents = false
    shape.svgPointerEvents = 'none'
    shape.shapePointerEvents = false
    shape.stencilPointerEvents = false
    if (!cell.isEdge()) {
      shape.dialect = 'svg'
      shape.init(graph.view.getOverlayPane())
    }
    return shape
  }
  highlight.highlight(graph.view.getState(cell))
  if (highlight.shape?.node) highlight.shape.node.style.pointerEvents = 'none'
  return highlight
}

/** Mark only the requested visible domain object, never a structural container or ancestor. */
export function analysisTargetCell(graph: Graph, target: AnalysisTarget): Cell | null {
  if (target.kind === 'model' || target.kind === 'structuralElement' || target.kind === null) return null
  const cell = graph.getDataModel().getCell(target.id)
  const state = cell && graph.view.getState(cell)
  return cell && state && (cell.isEdge() || cell.isVertex() && state.width !== 0 && state.height !== 0) ? cell : null
}

export const referenceHintTarget = (graph: Graph, hint: ReferenceHint) => analysisTargetCell(graph, hint.target)

/** Runtime overlays only: no style/XML mutation and no removal of other feedback overlays.
 * All findings of one cell merge into a single marker (most severe status, every finding in the tooltip),
 * so markers never stack on top of each other. */
export function installAnalysisOverlays(graph: Graph, analysis: AdaptedAnalysis, select: (id: string, showQuestion?: boolean) => void, overview = false,
  notes: HelpFeedbackNote[] = []) {
  if (overview) return installOverviewOverlays(graph, analysis, select, notes)
  const markers = new Map<Cell, { status: DisplayStatus; lines: string[]; selectedId: string }>()
  // The first registration owns the click target; own annotations are registered first.
  const add = (cell: Cell, status: DisplayStatus, tooltip: string, selectedId = cell.getId()!) => {
    // The lab overview also marks unevaluated objects so missing coverage is visible.
    if (status === 'not_evaluated' && !overview) return
    const marker = markers.get(cell)
    if (!marker) return void markers.set(cell, { status, lines: [tooltip], selectedId })
    if (displayStatusOrder.indexOf(status) < displayStatusOrder.indexOf(marker.status)) marker.status = status
    marker.lines.push(tooltip)
  }
  const undisplayedAnnotations = analysis.report.annotations.filter(item => {
    const cell = analysisTargetCell(graph, item.target)
    if (!cell) return true
    const status = overview ? analysisOverviewStatus(item) : analysisStatus(item)
    // Selection keeps the original annotated object even when an invisible container uses its parent.
    const label = overview && item.consistency === 'partial' && status !== 'recognized' ? 'Teilweise konsistent; offene oder abweichende Prüfungen' : analysisDisplay[status].label
    add(cell, status, `${label} (${item.target.id})`, item.target.id)
    return false
  })
  const hintsByCell = new Map<Cell, ReferenceHint[]>()
  const placementsByCell = new Map<Cell, Map<string, { text: string; subjectId: string }>>()
  for (const item of analysis.report.annotations) {
    for (const hint of item.hints) {
      if (hint.code === 'label.different') continue
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
  for (const [cell, findings] of placementsByCell) add(cell, 'warning', [...findings.values()].map(item => item.text).join('\n'), findings.values().next().value!.subjectId)
  const modelHints: ReferenceHint[] = []
  for (const hint of analysis.report.referenceHints) {
    const cell = referenceHintTarget(graph, hint)
    if (!cell) modelHints.push(hint)
    else hintsByCell.set(cell, [...(hintsByCell.get(cell) ?? []), hint])
  }
  for (const [cell, hints] of hintsByCell) add(cell, hints.some(hint => hint.status !== 'not_evaluated') ? 'unresolved' : 'not_evaluated', hints.map(hint => `${analysisHintText(hint)} (${hint.label ?? hint.referenceId})`).join('\n'))
  for (const group of analysis.report.connectionGroups ?? []) {
    const hasIssue = group.facts?.some(fact => ['violated', 'unresolved'].includes(fact.status)) ?? !!group.hints?.length
    if (!hasIssue) continue
    for (const id of group.submissionEndpointIds) {
      const item = analysis.report.annotations.find(item => item.target.id === id)
      const cell = item && analysisTargetCell(graph, item.target)
      if (cell) add(cell, group.facts?.some(fact => fact.status === 'violated') || group.status === 'different' ? 'warning' : 'unresolved', `Verbindungsgruppe: ${group.hints?.map(analysisHintText).join('\n') || 'Abweichende oder offene Gruppenprüfungen; kein individueller Verbindungsfehler.'}`, id)
    }
  }
  // Observations from the learner feedback (e.g. same-named copies) join the tooltip; they never change the status.
  for (const note of notes) {
    const cell = graph.getDataModel().getCell(note.cellId)
    if (cell) markers.get(cell)?.lines.push(note.text)
  }
  const installed: { cell: Cell; overlay: CellOverlay }[] = []
  for (const [cell, marker] of markers) {
    const display = analysisDisplay[marker.status]
    const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: display.icon, color: display.color,
      tooltip: [...new Set(marker.lines)].join('\n'), align: 'right', verticalAlign: 'top', cursor: 'pointer', offset: { x: 8, y: -8 } })
    overlay.addListener(InternalEvent.CLICK, () => { graph.setSelectionCell(cell); select(marker.selectedId) })
    graph.addCellOverlay(cell, overlay)
    installed.push({ cell, overlay })
  }
  return { modelHints, undisplayedAnnotations, remove: () => installed.forEach(({ cell, overlay }) => graph.removeCellOverlay(cell, overlay)) }
}

/** One identity icon per domain object; property and group findings remain in the details. */
function installOverviewOverlays(graph: Graph, analysis: AdaptedAnalysis, select: (id: string, showQuestion?: boolean) => void, notes: HelpFeedbackNote[]) {
  const installed: { cell: Cell; overlay: CellOverlay }[] = []
  const marked = new Set<string>()
  const undisplayedAnnotations = analysis.report.annotations.filter(item => {
    if (item.target.kind === 'structuralElement') return false
    const cell = analysisTargetCell(graph, item.target)
    if (!cell || cell.getId() !== item.target.id) return true
    if (marked.has(item.target.id)) return false
    marked.add(item.target.id)
    const questions = analysisStudentQuestions(analysis.report, item.target.id)
    const display = analysisOverviewAppearance(item, questions.length > 0)
    const overlay = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: display.icon,
      color: display.color, tooltip: `${display.label}: ${item.target.id}`, align: 'right', verticalAlign: 'top', cursor: 'pointer' })
    overlay.addListener(InternalEvent.CLICK, () => { graph.setSelectionCell(cell); select(item.target.id) })
    graph.addCellOverlay(cell, overlay)
    installed.push({ cell, overlay })
    const information = [...questions.map(question => question.text), ...notes.filter(note => note.cellId === item.target.id).map(note => note.text)]
    if (information.length) {
      const info = createOverlayFromConfig({ image: { src: '', width: 16, height: 16 }, icon: 'mdi-information-outline',
        color: '#2196F3', tooltip: information.join('\n'), align: 'right', verticalAlign: 'top', offset: { x: 20, y: 0 }, cursor: 'pointer' })
      // Questions and observations are both learner hints, so the icon opens the hint list for either.
      info.addListener(InternalEvent.CLICK, () => select(item.target.id, true))
      graph.addCellOverlay(cell, info)
      installed.push({ cell, overlay: info })
    }

    return false
  })
  const modelHints = analysis.report.referenceHints.filter(hint => hint.kind !== 'structuralElement' && !referenceHintTarget(graph, hint))
  return { modelHints, undisplayedAnnotations, remove: () => installed.forEach(({ cell, overlay }) => graph.removeCellOverlay(cell, overlay)) }
}
