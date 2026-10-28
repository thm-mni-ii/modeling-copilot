import { ConnectorShape, Point, Shape, ShapeRegistry, type AbstractCanvas2D } from '@maxgraph/core'
import type { ChildElement, DiagramElement } from '@/model/Element'

/** Abstand zwischen den beiden Linien in Pixeln (bei Zoom 1). */
const DOUBLE_LINE_SPACING = 4

/**
 * Kante aus zwei parallelen Linien (z.B. SERM-Kanten mit min = 1).
 * Pfeilspitzen kommen wie bei jeder Kante über startArrow/endArrow.
 * Die Punkte sind bereits unskaliert, der Zoom wirkt über den Canvas.
 */
class DoubleLineShape extends ConnectorShape {
  override paintLine(c: AbstractCanvas2D, pts: Point[], rounded?: boolean): void {
    const offset = DOUBLE_LINE_SPACING / 2
    super.paintLine(c, offsetPolyline(pts, offset), rounded)
    super.paintLine(c, offsetPolyline(pts, -offset), rounded)
  }
}

const unitNormal = (from: Point, to: Point): Point => {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy) || 1
  return new Point(-dy / length, dx / length)
}

/** Verschiebt einen Linienzug seitlich, an Knicken mit Gehrung (gleicher Abstand auf beiden Segmenten). */
const offsetPolyline = (pts: Point[], offset: number): Point[] => {
  return pts.map((pt, i) => {
    const before = i > 0 ? unitNormal(pts[i - 1], pt) : null
    const after = i < pts.length - 1 ? unitNormal(pt, pts[i + 1]) : null
    const a = before ?? after!
    const b = after ?? before!
    const mx = a.x + b.x
    const my = a.y + b.y
    const dot = mx * a.x + my * a.y || 1
    return new Point(pt.x + (mx / dot) * offset, pt.y + (my / dot) * offset)
  })
}

/** Registriert die eigenen Formen; danach als `shape` im Style nutzbar. */
export function registerCustomShapes(): void {
  ShapeRegistry.add('doubleLine', DoubleLineShape)
}

/** Registriert eine Canvas2D-Form unter ihrem Typ (Befehle: MOVE, LINE, RECT, ELLIPSE, relativ 0-1). */
const registerCanvasShape = (shapeId: string, canvasCommands: string) => {
  class DynamicCustomShape extends Shape {
    override paintBackground(c: AbstractCanvas2D, x: number, y: number, w: number, h: number) {
      c.translate(x, y)

      const lines = canvasCommands.trim().split('\n')
      // Start und letzter Punkt des offenen Pfads; endet er am Start, wird die Fläche gefüllt
      let pathStart: [number, number] | null = null
      let pathEnd: [number, number] | null = null

      const finishPath = () => {
        if (!pathStart) return
        if (pathEnd && Math.abs(pathStart[0] - pathEnd[0]) < 1e-6 && Math.abs(pathStart[1] - pathEnd[1]) < 1e-6) {
          c.close()
          c.fillAndStroke()
        } else {
          c.stroke()
        }
        c.end()
        pathStart = null
        pathEnd = null
      }

      for (const line of lines) {
        const [cmd, ...args] = line.trim().split(/\s+/)
        const nums = args.map(Number)

        if (nums.some((n) => isNaN(n))) {
          console.warn(`Invalid numbers in: ${line}`)
          continue
        }

        switch (cmd.toUpperCase()) {
          case 'MOVE':
            finishPath()
            c.begin()
            c.moveTo(w * nums[0], h * nums[1])
            pathStart = [nums[0], nums[1]]
            break

          case 'LINE':
            if (nums.length === 2) {
              c.lineTo(w * nums[0], h * nums[1])
              pathEnd = [nums[0], nums[1]]
            } else if (nums.length === 4) {
              finishPath()
              c.begin()
              c.moveTo(w * nums[0], h * nums[1])
              c.lineTo(w * nums[2], h * nums[3])
              c.stroke()
              c.end()
            }
            break

          case 'RECT':
            if (nums.length === 4) {
              finishPath()
              c.begin()
              c.rect(w * nums[0], h * nums[1], w * nums[2], h * nums[3])
              c.fillAndStroke()
              c.end()
            }
            break

          case 'ELLIPSE':
            if (nums.length === 4) {
              finishPath()
              c.begin()
              c.ellipse(w * nums[0], h * nums[1], w * nums[2], h * nums[3])
              c.fillAndStroke()
              c.end()
            }
            break
        }
      }

      finishPath()
    }
  }

  ShapeRegistry.add(shapeId, DynamicCustomShape)
}

/**
 * Registriert die Canvas2D-Formen eines Elements samt Children.
 * Muss vor dem Zeichnen laufen, sonst fällt maxGraph auf ein Rechteck zurück.
 */
export function registerElementShapes(definition: DiagramElement | ChildElement | null | undefined): void {
  if (!definition) return

  if (definition.renderMode === 'canvas2d' && definition.canvas) {
    registerCanvasShape(definition.type, definition.canvas)
  }

  definition.children?.forEach((child) => registerElementShapes(child))
}
