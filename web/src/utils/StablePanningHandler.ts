import { EventObject, InternalEvent, PanningHandler, styleUtils, type AbstractGraph, type EventSource, type InternalMouseEvent } from '@maxgraph/core'

/** Fixes one-axis pan completion in maxGraph 0.24 without changing its preview. */
export class StablePanningHandler extends PanningHandler {
  private readonly finishOutside = () => this.finishPan()

  constructor(graph: AbstractGraph) {
    super(graph)
    // The default document listener only resets the handler, leaving the preview
    // behind when release happens outside the graph. Complete that pan as well.
    InternalEvent.removeListener(document, 'mouseup', this.mouseUpListener)
    this.mouseUpListener = this.finishOutside
    InternalEvent.addListener(document, 'mouseup', this.mouseUpListener)
    document.addEventListener('pointerup', this.finishOutside)
    document.addEventListener('pointercancel', this.finishOutside)
    window.addEventListener('blur', this.finishOutside)
  }

  override mouseUp(_sender: EventSource, me: InternalMouseEvent) {
    this.finishPan(me)
  }

  private finishPan(me?: InternalMouseEvent) {
    if (!this.active) {
      this.reset()
      return
    }
    const { dx, dy } = this
    try {
      if (!this.graph.isUseScrollbarsForPanning() || !styleUtils.hasScrollbars(this.graph.container)) {
        const { scale, translate } = this.graph.getView()
        const x = translate.x + dx / scale
        const y = translate.y + dy / scale
        // Always remove the temporary SVG/HTML preview, including a drag that
        // returns to its start. A change on either axis must be committed.
        this.graph.panGraph(0, 0)
        if (dx !== 0 || dy !== 0) this.panGraph(x, y)
      }
      me?.consume()
    } finally {
      this.reset()
      this.fireEvent(new EventObject(InternalEvent.PAN_END, { event: me }))
    }
  }

  override onDestroy() {
    document.removeEventListener('pointerup', this.finishOutside)
    document.removeEventListener('pointercancel', this.finishOutside)
    window.removeEventListener('blur', this.finishOutside)
    this.finishPan()
    super.onDestroy()
  }
}
