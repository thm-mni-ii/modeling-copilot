import { Cell, ConnectionConstraint, ConnectionHandler, ConstraintHandler, CellState, InternalMouseEvent, mathUtils, Point, type Graph, type ImageShape, type Rectangle } from '@maxgraph/core'
import type { CellStyle } from '@maxgraph/core'
import type { DiagramConnection } from '@/model/Connection'
import type { FeedbackCanvasRulesConfig } from '@/model/Feedback'
import { applyConnectionAdditionalLabels, applyConnectionLabelOffset } from '@/utils/connectionLabelHelpers'
import { createConnectionStyle } from '@/utils/elementFactory'
import { getGraphValidationMode, setValidationPassActive, shouldBlockInteractiveValidation } from '@/utils/graphValidationRuntime'
import { isTruthyFlag } from '@/utils/flagUtils'
import { constraintStyle } from '@/utils/connectionPoints'

/** Distance in pixels within which an edge end is held on the outline with "Free on Outline". */
const OUTLINE_SNAP_DISTANCE = 10

/** Elements with "Free on Outline" (docking = 'outline'); otherwise edges snap to the nearest anchor point. */
export const isOutlineDocking = (cell: Cell | null | undefined): boolean => (cell as any)?.docking === 'outline'

/** Docking points for new edges (ConnectionHandler) and for reconnecting edge ends (EdgeHandler). */
export class AnchorConstraintHandler extends ConstraintHandler {
  // Target and reconnecting snap to the nearest anchor; with free docking only to directly hit ones
  override intersects(icon: ImageShape, rectangle: Rectangle, source: boolean, existingEdge: boolean): boolean {
    const hit = mathUtils.intersects(icon.bounds!, rectangle)
    return isOutlineDocking(this.currentFocus?.cell) ? hit : !source || existingEdge || hit
  }

  override update(me: InternalMouseEvent, source: boolean, existingEdge: boolean, point: Point | null): void {
    super.update(me, source, existingEdge, point)
    const focus = this.currentFocus
    if (this.currentConstraint || !focus || !isOutlineDocking(focus.cell) || (source && !existingEdge)) return
    // Free docking: near the outline the end stays fixed there, further inside it docks freely on the facing side
    const mouse = new Point(me.getGraphX(), me.getGraphY())
    const outlinePoint = this.graph.view.getPerimeterPoint(focus, mouse, false)
    if (!outlinePoint || Math.hypot(outlinePoint.x - mouse.x, outlinePoint.y - mouse.y) > OUTLINE_SNAP_DISTANCE) return
    this.currentConstraint = this.graph.getOutlineConstraint(outlinePoint, focus, me)
    this.currentPoint = outlinePoint
  }

  // No anchor points on edges that must not be docked onto
  override isStateIgnored(state: CellState): boolean {
    return !this.graph.isValidSource(state.cell)
  }
}

export class CustomConnectionHandler extends ConnectionHandler {
  private sourcePointChosen = false
  private selectedConnection: DiagramConnection | null = null
  private feedbackConnection: DiagramConnection | null = null
  private feedbackConnectionByElementId = new Map<string, DiagramConnection>()
  private feedbackConnectionByType = new Map<string, DiagramConnection>()
  private feedbackRules: FeedbackCanvasRulesConfig = {
    onlyFeedbackAsSource: true,
    allowTargetElements: true,
    allowTargetConnections: true,
    forbidFeedbackAsTarget: true,
    enforceDedicatedConnection: true,
    preventContainerDrop: true
  }

  private reportValidatingFeedback(edge: Cell, source: Cell | null, target: Cell | null): void {
    if (getGraphValidationMode(this.graph) !== 'validating') return

    window.setTimeout(() => {
      setValidationPassActive(this.graph, true)
      try {
        const validationError = this.graph.getEdgeValidationError(edge, source, target)
        if (validationError) {
          this.graph.validationAlert(validationError)
        }
      } finally {
        setValidationPassActive(this.graph, false)
      }
    }, 0)
  }

  constructor(graph: Graph) {
    super(graph)
  }

  private isFeedbackCell(cell: Cell | null): boolean {
    if (!cell || cell.isEdge()) {
      return false
    }

    const style = this.graph.getCurrentCellStyle(cell) as Record<string, any> | null
    const roleFromStyle = style?.cellRole
    const roleFromCell = (cell as any).cellRole ?? (cell as any).canvasRole
    const lockFlag = style?.lockToLayer ?? (cell as any).lockToLayer

    return roleFromStyle === 'feedback' || roleFromCell === 'feedback' || isTruthyFlag(lockFlag)
  }

  private isFeedbackEdge(cell: Cell | null): boolean {
    if (!cell || !cell.isEdge()) {
      return false
    }

    const style = this.graph.getCurrentCellStyle(cell) as Record<string, any> | null
    const roleFromStyle = style?.cellRole
    const roleFromCell = (cell as any).cellRole ?? (cell as any).canvasRole
    const connectionId = (cell as any).connectionId
    const configuredFeedbackConnectionId = this.feedbackConnection?.type
    const isConfiguredType = connectionId && this.feedbackConnectionByType.has(connectionId)

    return roleFromStyle === 'feedback' || roleFromCell === 'feedback' || (configuredFeedbackConnectionId ? connectionId === configuredFeedbackConnectionId : false) || Boolean(isConfiguredType) || connectionId === '__feedback_note_link__'
  }

  private isFeedbackEntity(cell: Cell | null): boolean {
    return this.isFeedbackCell(cell) || this.isFeedbackEdge(cell)
  }

  private isModelTarget(cell: Cell | null): boolean {
    if (!cell) {
      return false
    }

    if (cell.isEdge()) {
      return !this.isFeedbackEdge(cell)
    }

    return !this.isFeedbackCell(cell)
  }

  private getConnectionForSource(source: Cell | null): DiagramConnection | null {
    if (source && this.isFeedbackCell(source)) {
      const feedbackElementId = (source as any).feedbackElementId
      const feedbackConnectionType = (source as any).feedbackConnectionType ?? (source as any).feedbackConnectionId
      if (typeof feedbackElementId === 'string' && this.feedbackConnectionByElementId.has(feedbackElementId)) {
        return this.feedbackConnectionByElementId.get(feedbackElementId) ?? null
      }
      if (typeof feedbackConnectionType === 'string' && this.feedbackConnectionByType.has(feedbackConnectionType)) {
        return this.feedbackConnectionByType.get(feedbackConnectionType) ?? null
      }
      return this.feedbackConnection ?? this.selectedConnection
    }
    return this.selectedConnection
  }

  protected override createConstraintHandler(): ConstraintHandler {
    return new AnchorConstraintHandler(this.graph)
  }

  // Via the graph check, so edges that must not be docked onto are blocked in free mode too
  override isConnectableCell(cell: Cell): boolean {
    return this.graph.isValidSource(cell)
  }

  override updateEdgeState(pt: Point, constraint: ConnectionConstraint | null): void {
    // Over the start element itself the start anchor stays, otherwise it falls back to the target anchor
    // and maxGraph discards the loop (checkConstraints in ConnectionHandler.mouseUp)
    const overSource = this.constraintHandler.currentFocus?.cell === this.previous?.cell
    if (pt != null && this.previous != null && !overSource && !this.sourcePointChosen && !isOutlineDocking(this.previous.cell)) {
      const constraints = this.graph.getAllConnectionConstraints(this.previous, true)
      let nearestConstraint: ConnectionConstraint | null = null
      let bestDist: number | null = null

      for (const ref of constraints ?? []) {
        const cp = this.graph.getConnectionPoint(this.previous, ref)
        if (cp != null) {
          const dx = cp.x - pt.x
          const dy = cp.y - pt.y
          const dist = dx * dx + dy * dy
          if (bestDist === null || dist < bestDist) {
            nearestConstraint = ref
            bestDist = dist
          }
        }
      }

      if (nearestConstraint != null) {
        this.sourceConstraint = nearestConstraint
      }
    }

    super.updateEdgeState(pt, constraint)
    if (this.previous?.cell && this.constraintHandler.currentFocus?.cell) this.error = this.validateConnection(this.previous.cell, this.constraintHandler.currentFocus.cell)
  }

  setSelectedConnection(connection: DiagramConnection | null) {
    this.selectedConnection = connection
  }

  setFeedbackConnection(connection: DiagramConnection | null) {
    this.feedbackConnection = connection
  }

  setFeedbackElementConnections(connectionsByElementId: Record<string, DiagramConnection> | null | undefined) {
    this.feedbackConnectionByElementId.clear()
    this.feedbackConnectionByType.clear()

    const entries = Object.entries(connectionsByElementId ?? {})
    for (const [elementId, connection] of entries) {
      if (!connection) continue
      this.feedbackConnectionByElementId.set(elementId, connection)

      if (connection.type) {
        this.feedbackConnectionByType.set(connection.type, connection)
      }
    }

    if (!this.feedbackConnection && entries.length > 0) {
      this.feedbackConnection = entries[0][1]
    }
  }

  setFeedbackRules(rules: FeedbackCanvasRulesConfig | null | undefined) {
    this.feedbackRules = {
      onlyFeedbackAsSource: true,
      allowTargetElements: true,
      allowTargetConnections: true,
      forbidFeedbackAsTarget: true,
      enforceDedicatedConnection: true,
      preventContainerDrop: true,
      ...(rules ?? {})
    }
  }

  override createEdgeState(_me: InternalMouseEvent): CellState | null {
    void _me

    const sourceCell = (this.previous?.cell as Cell | null) ?? null
    const effectiveConnection = this.getConnectionForSource(sourceCell)

    if (!effectiveConnection) {
      const edge = this.graph.createEdge(null, '', null, null, null)
      return new CellState(this.graph.view, edge, this.graph.getCellStyle(edge))
    }

    const style = createConnectionStyle(effectiveConnection)
    const edge = this.graph.createEdge(null, '', effectiveConnection.defaultLabel ?? '', null, null, style)
    ;(edge as any).connectionId = effectiveConnection.type
    ;(edge as any).connectionUndirected = effectiveConnection.undirected === true
    // ConnectionHandler.connect copies the geometry of this edge to the new one, hence the label offset here already
    applyConnectionLabelOffset(edge, effectiveConnection.labelOffset)

    return new CellState(this.graph.view, edge, this.graph.getCellStyle(edge))
  }

  override validateConnection(source: Cell, target: Cell): string | null {
    const sourceIsFeedbackLabel = this.isFeedbackCell(source)
    const sourceIsFeedbackEntity = this.isFeedbackEntity(source)
    const targetIsFeedbackEntity = this.isFeedbackEntity(target)
    const touchesFeedbackLayer = sourceIsFeedbackEntity || targetIsFeedbackEntity

    // Konfigurierbare Feedback-Regeln
    if (touchesFeedbackLayer) {
      if (this.feedbackRules.onlyFeedbackAsSource && !sourceIsFeedbackLabel) {
        return ''
      }
      if (this.feedbackRules.forbidFeedbackAsTarget && targetIsFeedbackEntity) {
        return ''
      }
      if (target.isEdge() && !this.feedbackRules.allowTargetConnections) {
        return ''
      }
      if (!target.isEdge() && !this.feedbackRules.allowTargetElements) {
        return ''
      }
      if (!this.isModelTarget(target)) {
        return ''
      }
      if (!this.getConnectionForSource(source)) {
        return ''
      }
    }

    if (!shouldBlockInteractiveValidation(this.graph)) {
      return null
    }

    const effectiveConnection = this.getConnectionForSource(source)
    if (!effectiveConnection) {
      return super.validateConnection(source, target)
    }

    const style = { ...createConnectionStyle(effectiveConnection), ...constraintStyle(this.sourceConstraint, true), ...constraintStyle(this.constraintHandler.currentConstraint, false) }
    const probeEdge = this.graph.createEdge(null, '', effectiveConnection.defaultLabel ?? '', source, target, style)
    probeEdge.setTerminal(source, true)
    probeEdge.setTerminal(target, false)
    ;(probeEdge as any).connectionId = effectiveConnection.type
    ;(probeEdge as any).connectionUndirected = effectiveConnection.undirected === true

    return this.graph.getEdgeValidationError(probeEdge, source, target)
  }

  override insertEdge(parent: Cell, id: string, value: any, source: Cell | null, target: Cell | null, style: CellStyle): Cell {
    const persistedId = id?.trim() || globalThis.crypto?.randomUUID?.() || `edge-${Date.now()}-${Math.random().toString(36).slice(2)}`
    const sourceCell = (source as Cell | null) ?? null
    const targetCell = (target as Cell | null) ?? null
    const sourceIsFeedbackLabel = this.isFeedbackCell(sourceCell)
    const sourceIsFeedbackEntity = this.isFeedbackEntity(sourceCell)
    const targetIsFeedbackEntity = this.isFeedbackEntity(targetCell)
    const effectiveConnection = this.getConnectionForSource(sourceCell)

    // Harte Durchsetzung der konfigurierten Feedback-Regeln.
    if (sourceIsFeedbackEntity || targetIsFeedbackEntity) {
      if (this.feedbackRules.onlyFeedbackAsSource && !sourceIsFeedbackLabel) {
        return null as unknown as Cell
      }
      if (this.feedbackRules.forbidFeedbackAsTarget && targetIsFeedbackEntity) {
        return null as unknown as Cell
      }
      if (targetCell?.isEdge() && !this.feedbackRules.allowTargetConnections) {
        return null as unknown as Cell
      }
      if (targetCell && !targetCell.isEdge() && !this.feedbackRules.allowTargetElements) {
        return null as unknown as Cell
      }
      if (!this.isModelTarget(targetCell)) {
        return null as unknown as Cell
      }
    }

    if (sourceIsFeedbackLabel && !effectiveConnection) {
      return null as unknown as Cell
    }

    // Without "Allow Loose Ends" no edge with an open end is created, in every mode
    if (effectiveConnection?.allowLooseEnds === false && (!sourceCell || !targetCell)) {
      return null as unknown as Cell
    }

    if (effectiveConnection) {
      const connectionId = effectiveConnection.type
      const edgeLabel = effectiveConnection.defaultLabel ?? ''
      const connectionStyle = createConnectionStyle(effectiveConnection)

      const edge = super.insertEdge(parent, persistedId, edgeLabel, source, target, connectionStyle)
      if (edge) {
        edge.setConnectable(true)
        ;(edge as any).connectionId = connectionId
        ;(edge as any).connectionUndirected = effectiveConnection.undirected === true
        ;(edge as any).connectionStyle = connectionStyle
        ;(edge as any).connectionLabelOffset = effectiveConnection.labelOffset

        applyConnectionLabelOffset(edge, effectiveConnection.labelOffset)
        applyConnectionAdditionalLabels(this.graph, edge, effectiveConnection)
        this.reportValidatingFeedback(edge, sourceCell, targetCell)
      }

      return edge
    }

    const edge = super.insertEdge(parent, persistedId, value, source, target, style)
    if (edge) {
      this.reportValidatingFeedback(edge, sourceCell, targetCell)
    }
    return edge
  }

  override mouseMove(sender: any, me: InternalMouseEvent): void {
    super.mouseMove(sender, me)
  }

  override mouseDown(sender: any, me: InternalMouseEvent): void {
    super.mouseDown(sender, me)
    if (this.first) this.sourcePointChosen = Boolean(this.sourceConstraint?.name)
  }

  override reset(): void {
    this.sourcePointChosen = false
    super.reset()
  }

  override mouseUp(sender: any, me: InternalMouseEvent): void {
    super.mouseUp(sender, me)
  }
}
