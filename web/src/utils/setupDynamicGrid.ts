import { watch, type Ref } from 'vue'
import { InternalEvent, type Graph, type PanningHandler } from '@maxgraph/core'

type GridGraph = Graph & { repaintGrid?: () => void }

/** Paint a viewport-sized grid independently of maxGraph's moving DOM preview. */
export function setupDynamicGrid(graph: Ref<Graph | undefined>, canvasGrid: Ref<HTMLCanvasElement | undefined>, graphContainer: Ref<HTMLElement | undefined>, gridSize: Ref<number>, snapToGrid: Ref<boolean>): () => void {
  const currentGraph = graph.value as GridGraph | undefined
  const canvas = canvasGrid.value
  const container = graphContainer.value
  const ctx = canvas?.getContext('2d')
  if (!currentGraph || !canvas || !container || !ctx) return () => {}

  const view = currentGraph.getView()
  const panningHandler = currentGraph.getPlugin<PanningHandler>('PanningHandler')
  let frame: number | null = null
  let disposed = false

  const repaintGrid = () => {
    if (disposed) return
    const width = container.clientWidth
    const height = container.clientHeight
    const ratio = window.devicePixelRatio || 1
    const pixelWidth = Math.round(width * ratio)
    const pixelHeight = Math.round(height * ratio)
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth
      canvas.height = pixelHeight
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.clearRect(0, 0, width, height)
    if (!snapToGrid.value || width === 0 || height === 0) return

    // panDx/panDy belong to Graph, not GraphView or the PAN event. Never
    // accumulate them or translate the canvas bitmap and expose blank edges.
    const tx = view.translate.x * view.scale + currentGraph.panDx - container.scrollLeft
    const ty = view.translate.y * view.scale + currentGraph.panDy - container.scrollTop
    const rawStep = (currentGraph.gridSize || gridSize.value) * view.scale
    if (!Number.isFinite(rawStep) || rawStep <= 0) return
    const step = rawStep < 5 ? rawStep * Math.ceil(5 / rawStep) : rawStep
    const startX = ((tx % step) + step) % step
    const startY = ((ty % step) + step) % step

    ctx.strokeStyle = `rgba(120, 120, 120, ${Math.min(0.8, Math.max(0.4, step / 30))})`
    ctx.lineWidth = step > 10 ? 1 : 0.5
    ctx.beginPath()
    for (let x = startX; x <= width; x += step) {
      ctx.moveTo(x + 0.5, 0)
      ctx.lineTo(x + 0.5, height)
    }
    for (let y = startY; y <= height; y += step) {
      ctx.moveTo(0, y + 0.5)
      ctx.lineTo(width, y + 0.5)
    }
    ctx.stroke()

    ctx.strokeStyle = 'rgba(170, 100, 100, 0.7)'
    ctx.lineWidth = 2
    ctx.beginPath()
    if (tx >= 0 && tx <= width) {
      ctx.moveTo(tx + 0.5, 0)
      ctx.lineTo(tx + 0.5, height)
    }
    if (ty >= 0 && ty <= height) {
      ctx.moveTo(0, ty + 0.5)
      ctx.lineTo(width, ty + 0.5)
    }
    ctx.stroke()
  }

  const scheduleRepaint = () => {
    if (!disposed && frame === null) {
      frame = requestAnimationFrame(() => {
        frame = null
        repaintGrid()
      })
    }
  }
  const flushRepaint = () => {
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    repaintGrid()
  }

  currentGraph.addListener(InternalEvent.PAN, scheduleRepaint)
  view.addListener(InternalEvent.SCALE, scheduleRepaint)
  view.addListener(InternalEvent.TRANSLATE, scheduleRepaint)
  view.addListener(InternalEvent.SCALE_AND_TRANSLATE, scheduleRepaint)
  panningHandler?.addListener(InternalEvent.PAN_END, flushRepaint)
  container.addEventListener('scroll', scheduleRepaint)
  const resizeObserver = new ResizeObserver(scheduleRepaint)
  resizeObserver.observe(container)
  const stopWatch = watch([gridSize, snapToGrid], scheduleRepaint)
  const previousRepaint = currentGraph.repaintGrid
  currentGraph.repaintGrid = flushRepaint
  repaintGrid()

  return () => {
    disposed = true
    if (frame !== null) cancelAnimationFrame(frame)
    frame = null
    currentGraph.removeListener(scheduleRepaint)
    view.removeListener(scheduleRepaint)
    panningHandler?.removeListener(flushRepaint)
    container.removeEventListener('scroll', scheduleRepaint)
    resizeObserver.disconnect()
    stopWatch()
    if (currentGraph.repaintGrid === flushRepaint) {
      if (previousRepaint) currentGraph.repaintGrid = previousRepaint
      else delete currentGraph.repaintGrid
    }
  }
}
