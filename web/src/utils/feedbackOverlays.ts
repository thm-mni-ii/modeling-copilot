import { CellOverlay, CellRenderer, Geometry, ImageBox, Point, Rectangle, Shape } from '@maxgraph/core'
import type { AbstractCanvas2D, CellState, Graph } from '@maxgraph/core'
import type { FeedbackOverlayConfig } from '@/model/Feedback'

const glyphs = new Map<string, string>()

export const getMdiGlyph = (icon: string): string => {
  if (!/^mdi-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(icon)) return ''
  const cached = glyphs.get(icon)
  if (cached) return cached
  const probe = document.createElement('i')
  probe.className = `mdi ${icon}`
  probe.style.display = 'none'
  document.body.appendChild(probe)
  const content = getComputedStyle(probe, '::before').content
  probe.remove()
  const glyph = /^(["']).*\1$/.test(content) ? content.slice(1, -1) : ''
  if (glyph) glyphs.set(icon, glyph)
  return glyph
}

class FeedbackOverlay extends CellOverlay {
  override getBounds(state: CellState): Rectangle {
    const bounds = super.getBounds(state)
    if (state.cell.isEdge() && state.length > 0 && state.segments?.length) {
      const overlays = (state.view.graph.getCellOverlays(state.cell) ?? []).filter((overlay) => overlay instanceof FeedbackOverlay)
      const hints = overlays.filter((overlay) => overlay.verticalAlign === 'bottom')
      const verdicts = overlays.filter((overlay) => overlay.verticalAlign !== 'bottom')
      const geometry = new Geometry()
      geometry.relative = true
      if (hints.length && verdicts.length) {
        const diameter = (overlay: CellOverlay) => (overlay instanceof MdiOverlay ? Math.min(overlay.image.width, overlay.image.height) : Math.hypot(overlay.image.width, overlay.image.height))
        const spacing = ((Math.max(...hints.map(diameter)) + Math.max(...verdicts.map(diameter))) / 2 + 4) * state.view.scale
        let distance = Math.min(spacing / 2, state.length / 2)
        // At bends, arc distance alone can still leave the two icons overlapping.
        for (let attempt = 0; attempt < 8; attempt++) {
          geometry.x = (-2 * distance) / state.length
          const before = state.view.getPoint(state, geometry)
          geometry.x *= -1
          const after = state.view.getPoint(state, geometry)
          const separation = Math.hypot(after.x - before.x, after.y - before.y)
          if (separation >= spacing || distance >= state.length / 2) break
          distance = Math.min(distance + Math.max((spacing - separation) / 2, state.view.scale), state.length / 2)
        }
        geometry.x = ((this.verticalAlign === 'bottom' ? 2 : -2) * distance) / state.length
      }
      geometry.offset = this.offset
      const point = state.view.getPoint(state, geometry)
      bounds.x = point.x - bounds.width * this.defaultOverlap
      bounds.y = point.y - bounds.height * this.defaultOverlap
    }
    return bounds
  }
}

class MdiOverlay extends FeedbackOverlay {
  icon = ''
  color = '#000000'
}

class MdiOverlayShape extends Shape {
  constructor(private readonly mdiOverlay: MdiOverlay) {
    super()
    this.bounds = new Rectangle()
  }

  override paintBackground(canvas: AbstractCanvas2D, x: number, y: number, width: number, height: number) {
    const diameter = Math.min(width, height)
    canvas.setFillColor('#FFFFFF')
    canvas.setStrokeColor(null)
    canvas.ellipse(x + (width - diameter) / 2, y + (height - diameter) / 2, diameter, diameter)
    canvas.fill()
    canvas.setFontFamily('Material Design Icons')
    canvas.setFontSize(diameter)
    canvas.setFontColor(this.mdiOverlay.color)
    canvas.text(x + width / 2, y + height / 2, 0, 0, getMdiGlyph(this.mdiOverlay.icon), 'center', 'middle', false, '', 'visible', false, 0, 'ltr')
  }
}

class FeedbackCellRenderer extends CellRenderer {
  protected override createOverlayShape(state: CellState, overlay: CellOverlay): Shape {
    return overlay instanceof MdiOverlay ? new MdiOverlayShape(overlay) : super.createOverlayShape(state, overlay)
  }
}

export const installFeedbackOverlayRenderer = (graph: Graph) => {
  if (!(graph.cellRenderer instanceof FeedbackCellRenderer)) {
    graph.cellRenderer = Object.assign(new FeedbackCellRenderer(), graph.cellRenderer)
  }
}

export const createOverlayFromConfig = (config: FeedbackOverlayConfig): CellOverlay => {
  const image = new ImageBox(config.image.src, config.image.width, config.image.height)
  const offsetPoint = config.offset ? new Point(config.offset.x, config.offset.y) : undefined

  const Overlay = config.icon ? MdiOverlay : FeedbackOverlay
  const overlay = new Overlay(image, config.tooltip ?? null, config.align, config.verticalAlign, offsetPoint, config.cursor)
  if (overlay instanceof MdiOverlay) {
    overlay.icon = config.icon!
    overlay.color = config.color ?? '#000000'
  }
  return overlay
}
