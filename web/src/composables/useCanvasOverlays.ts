import { computed, reactive, ref, watch, type Ref } from 'vue'
import type { Cell, CellOverlay } from '@maxgraph/core'
import type { FeedbackCanvasOverlayEntry, FeedbackOverlayConfig, FeedbackOverlayOffset } from '@/model/Feedback'
import { createOverlayFromConfig } from '@/utils/feedbackOverlays'
import { isValidationWarningOverlay } from '@/utils/graphValidationRuntime'

export interface OverlayAwareGraph {
  setOverlayCallbacks(onAdd?: (cell: Cell, overlay: CellOverlay) => void, onRemove?: (cell: Cell, overlay: CellOverlay) => void): void
  addCellOverlay(cell: Cell, overlay: CellOverlay): CellOverlay
  removeCellOverlay(cell: Cell, overlay: CellOverlay | null): CellOverlay | null
  removeCellOverlays(cell: Cell): CellOverlay[]
  getWarningImage(): { src: string; width: number; height: number }
  getDataModel(): { getCell(id: string): Cell | null }
  view: { getState(cell: Cell): any }
}

type OverlayAnchor = {
  left: number
  top: number
  width: number
  height: number
}

interface OverlayInstance {
  cellId: string
  overlay: CellOverlay
  config: FeedbackOverlayConfig
}

type OverlayEntryWithKey = FeedbackCanvasOverlayEntry & { key: string }

export const useCanvasOverlays = (wrapperRef: Ref<HTMLElement | null>, entriesRef: Ref<FeedbackCanvasOverlayEntry[]>) => {
  const overlayTooltip = reactive<{
    text: string
    visible: boolean
    anchor: OverlayAnchor | null
  }>({
    text: '',
    visible: false,
    anchor: null
  })

  const overlayTooltipAnchorStyle = computed(() => {
    if (!overlayTooltip.anchor) return {}
    return {
      left: `${overlayTooltip.anchor.left}px`,
      top: `${overlayTooltip.anchor.top}px`,
      width: `${overlayTooltip.anchor.width || 24}px`,
      height: `${overlayTooltip.anchor.height || 24}px`
    }
  })

  const overlayEntriesWithKeys = computed<OverlayEntryWithKey[]>(() =>
    (entriesRef.value ?? []).map((entry, index) => ({
      ...entry,
      key: entry.id ?? `${entry.cellId}-${index}`
    }))
  )

  const graphRef = ref<OverlayAwareGraph | null>(null)
  const overlayCleanupMap = new WeakMap<CellOverlay, () => void>()
  const overlaySetupTimers = new WeakMap<CellOverlay, number>()
  const externalOverlayInstances = new Map<string, OverlayInstance>()
  const activeOverlay = ref<CellOverlay | null>(null)
  const activeOverlayNode = ref<HTMLElement | null>(null)
  let externalOverlayApplyTimeout: ReturnType<typeof setTimeout> | null = null
  let wrapperLeaveHandler: (() => void) | null = null
  let wrapperMoveHandler: ((event: MouseEvent) => void) | null = null
  let stopOverlayWatch: (() => void) | null = null
  let stopWrapperWatch: (() => void) | null = null

  const hideOverlayTooltip = (overlay?: CellOverlay) => {
    if (overlay && activeOverlay.value !== overlay) return
    overlayTooltip.visible = false
    overlayTooltip.anchor = null
    activeOverlay.value = null
    activeOverlayNode.value = null
  }

  const updateTooltipAnchor = (node: HTMLElement) => {
    if (!wrapperRef.value) return
    const wrapperRect = wrapperRef.value.getBoundingClientRect()
    const nodeRect = node.getBoundingClientRect()
    overlayTooltip.anchor = {
      left: nodeRect.left - wrapperRect.left,
      top: nodeRect.top - wrapperRect.top,
      width: nodeRect.width,
      height: nodeRect.height
    }
  }

  const showOverlayTooltip = (overlay: CellOverlay, node: HTMLElement) => {
    overlayTooltip.text = overlay.tooltip ?? ''
    updateTooltipAnchor(node)
    overlayTooltip.visible = true
    activeOverlay.value = overlay
    activeOverlayNode.value = node
  }

  const getOverlayNode = (cell: Cell, overlay: CellOverlay): HTMLElement | null => {
    const state = graphRef.value?.view.getState(cell)
    const overlayShape = state?.overlays?.get(overlay)
    return overlayShape?.node ?? null
  }

  const attachOverlayTooltipHandlers = (cell: Cell, overlay: CellOverlay, attempt = 0) => {
    // Ein Overlay mit hoverTooltip = false zeigt keinen Tooltip, etwa die Herkunftspunkte im Gruppenmodell.
    if ((overlay as { hoverTooltip?: boolean }).hoverTooltip === false || (graphRef.value && isValidationWarningOverlay(graphRef.value, overlay))) {
      return
    }

    const node = getOverlayNode(cell, overlay)
    if (!node) {
      if (attempt < 6) {
        const timer = window.setTimeout(() => attachOverlayTooltipHandlers(cell, overlay, attempt + 1), 80)
        overlaySetupTimers.set(overlay, timer)
      }
      return
    }

    node.style.pointerEvents = 'auto'

    const handleEnter = () => showOverlayTooltip(overlay, node)
    const handleMove = () => {
      if (activeOverlay.value === overlay) {
        updateTooltipAnchor(node)
      }
    }
    const handleLeave = () => hideOverlayTooltip(overlay)

    node.addEventListener('mouseenter', handleEnter)
    node.addEventListener('mousemove', handleMove)
    node.addEventListener('mouseleave', handleLeave)

    overlayCleanupMap.set(overlay, () => {
      node.removeEventListener('mouseenter', handleEnter)
      node.removeEventListener('mousemove', handleMove)
      node.removeEventListener('mouseleave', handleLeave)
      if (activeOverlay.value === overlay) {
        hideOverlayTooltip(overlay)
      }
    })
  }

  const handleOverlayAdded = (cell: Cell, overlay: CellOverlay) => {
    const timer = overlaySetupTimers.get(overlay)
    if (timer) {
      clearTimeout(timer)
      overlaySetupTimers.delete(overlay)
    }
    attachOverlayTooltipHandlers(cell, overlay)
  }

  const handleOverlayRemoved = (cell: Cell, overlay: CellOverlay) => {
    const timer = overlaySetupTimers.get(overlay)
    if (timer) {
      clearTimeout(timer)
      overlaySetupTimers.delete(overlay)
    }
    const cleanup = overlayCleanupMap.get(overlay)
    cleanup?.()
    overlayCleanupMap.delete(overlay)
    if (activeOverlay.value === overlay) {
      hideOverlayTooltip(overlay)
    }
    for (const [key, entry] of externalOverlayInstances.entries()) {
      if (entry.overlay === overlay && entry.cellId === cell.getId()) {
        externalOverlayInstances.delete(key)
        break
      }
    }
  }

  const areOverlayConfigsEqual = (a: FeedbackOverlayConfig, b: FeedbackOverlayConfig): boolean => {
    const offsetEquals = (aOffset?: FeedbackOverlayOffset, bOffset?: FeedbackOverlayOffset) => {
      return (aOffset?.x ?? 0) === (bOffset?.x ?? 0) && (aOffset?.y ?? 0) === (bOffset?.y ?? 0)
    }

    return (
      a.image.src === b.image.src &&
      a.icon === b.icon &&
      a.color === b.color &&
      a.image.width === b.image.width &&
      a.image.height === b.image.height &&
      (a.tooltip ?? '') === (b.tooltip ?? '') &&
      (a.align ?? '') === (b.align ?? '') &&
      (a.verticalAlign ?? '') === (b.verticalAlign ?? '') &&
      offsetEquals(a.offset, b.offset) &&
      (a.cursor ?? '') === (b.cursor ?? '')
    )
  }

  const scheduleApplyExternalOverlays = () => {
    if (externalOverlayApplyTimeout) {
      clearTimeout(externalOverlayApplyTimeout)
    }
    externalOverlayApplyTimeout = window.setTimeout(() => {
      externalOverlayApplyTimeout = null
      applyExternalOverlays()
    }, 80)
  }

  const applyExternalOverlays = () => {
    const graph = graphRef.value
    if (!graph) return
    const model = graph.getDataModel()
    const keysToKeep = new Set<string>()
    let requiresRetry = false

    overlayEntriesWithKeys.value.forEach((entry) => {
      const key = entry.key
      keysToKeep.add(key)
      const cell = model.getCell(entry.cellId)
      if (!cell) {
        requiresRetry = true
        return
      }

      const existing = externalOverlayInstances.get(key)
      if (existing) {
        if (existing.cellId === entry.cellId && areOverlayConfigsEqual(existing.config, entry.config)) {
          return
        }
        graph.removeCellOverlay(cell, existing.overlay)
        externalOverlayInstances.delete(key)
      }

      const overlay = createOverlayFromConfig(entry.config)
      graph.addCellOverlay(cell, overlay)
      externalOverlayInstances.set(key, {
        cellId: entry.cellId,
        overlay,
        config: entry.config
      })
    })

    for (const [key, record] of externalOverlayInstances.entries()) {
      if (!keysToKeep.has(key)) {
        const cell = model.getCell(record.cellId)
        if (cell) {
          graph.removeCellOverlay(cell, record.overlay)
        }
        externalOverlayInstances.delete(key)
      }
    }

    if (requiresRetry) {
      scheduleApplyExternalOverlays()
    }
  }

  const registerGraph = (graph: OverlayAwareGraph | null) => {
    if (graphRef.value === graph) return
    graphRef.value?.setOverlayCallbacks()
    graphRef.value = graph
    if (graph) {
      graph.setOverlayCallbacks(handleOverlayAdded, handleOverlayRemoved)
      scheduleApplyExternalOverlays()
    }
  }

  const cleanup = () => {
    stopOverlayWatch?.()
    stopWrapperWatch?.()
    const currentGraph = graphRef.value
    currentGraph?.setOverlayCallbacks()
    graphRef.value = null

    if (externalOverlayApplyTimeout) {
      clearTimeout(externalOverlayApplyTimeout)
      externalOverlayApplyTimeout = null
    }

    if (currentGraph) {
      externalOverlayInstances.forEach((record) => {
        const cell = currentGraph.getDataModel().getCell(record.cellId)
        if (cell) {
          currentGraph.removeCellOverlay(cell, record.overlay)
        }
      })
    }
    externalOverlayInstances.clear()
    overlayTooltip.visible = false
    overlayTooltip.anchor = null
    activeOverlay.value = null
    activeOverlayNode.value = null
    if (wrapperLeaveHandler && wrapperRef.value) {
      wrapperRef.value.removeEventListener('mouseleave', wrapperLeaveHandler)
    }
    if (wrapperMoveHandler && wrapperRef.value) {
      wrapperRef.value.removeEventListener('mousemove', wrapperMoveHandler as EventListener)
    }
    wrapperLeaveHandler = null
    wrapperMoveHandler = null
  }

  stopOverlayWatch = watch(
    [overlayEntriesWithKeys, graphRef],
    () => {
      if (graphRef.value) {
        scheduleApplyExternalOverlays()
      }
    },
    { deep: true, immediate: true }
  )

  const handleWrapperLeave = () => {
    hideOverlayTooltip()
  }

  const handleWrapperMove = (event: MouseEvent) => {
    if (!activeOverlayNode.value) return
    const target = event.target
    if (target instanceof Node && activeOverlayNode.value.contains(target)) {
      return
    }
    hideOverlayTooltip()
  }

  stopWrapperWatch = watch(
    wrapperRef,
    (wrapper, previous) => {
      previous?.removeEventListener('mouseleave', handleWrapperLeave)
      previous?.removeEventListener('mousemove', handleWrapperMove as EventListener)
      wrapper?.addEventListener('mouseleave', handleWrapperLeave)
      wrapper?.addEventListener('mousemove', handleWrapperMove as EventListener)
      wrapperLeaveHandler = wrapper ? handleWrapperLeave : null
      wrapperMoveHandler = wrapper ? handleWrapperMove : null
    },
    { immediate: true }
  )

  return {
    overlayTooltip,
    overlayTooltipAnchorStyle,
    registerGraph,
    cleanup
  }
}
