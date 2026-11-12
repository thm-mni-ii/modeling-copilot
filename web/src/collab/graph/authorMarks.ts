import { CellOverlay, ImageBox, InternalEvent, Point, type Cell, type EventObject, type Graph } from '@maxgraph/core'
import type { Session } from '@/collab/kit/collabKitV1'
import { colorOf, nameOf } from '@/collab/presence/presence'
import { cellAuthors } from '@/collab/storage/workpieceVersions'

/** Größe des Punkts in px; maxGraph skaliert ihn mit dem Zoom. */
const SIZE = 14
/** So lange nach einer Änderung wird gewartet, damit collab-kit sie gespeichert hat und mehrere zusammen gelesen werden. */
const WAIT_MS = 1500

/** Der Punkt an einer Zelle; eine eigene Klasse, damit nur diese Overlays entfernt werden, nicht die Warnungen. */
class AuthorOverlay extends CellOverlay {
  /** Kein Hover-Tooltip, die Namen zeigt ein Klick (useCanvasOverlays, OverlayAwareTooltipHandler in DrawingCanvas). */
  readonly hoverTooltip = false
}

/** Füllung in der Farbe des Erstellers, Rand in der des letzten Bearbeiters, auf weißem Grund für jeden Hintergrund. */
const imageOf = (fill: string, ring: string) => new ImageBox(`data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}"><circle cx="7" cy="7" r="7" fill="#fff"/><circle cx="7" cy="7" r="4.75" fill="${fill}" stroke="${ring}" stroke-width="2.5"/></svg>`)}`, SIZE, SIZE)

/**
 * Ob die Zelle ein Teil ihres Elements ist, etwa die Attributliste unter einem E-Typ: maxGraph legt solche Zellen
 * mit relativer Geometrie zum Parent an (Geometry.relative), sie existieren nicht ohne ihr Element.
 */
const isPart = (cell: Cell | null) => Boolean(cell?.isVertex() && cell.getGeometry()?.relative)

/**
 * Wo der Punkt sitzt (CellOverlay.getBounds): bei Kanten in der Mitte, in einem Teil-Container wie der Attributliste
 * links neben dem Element, damit er keinen Text verdeckt, sonst links unten ins Element gerückt.
 */
const placeOf = (cell: Cell) => {
  if (cell.isEdge()) return { vertical: 'bottom' as const, offset: new Point() }
  if (isPart(cell.getParent())) return { vertical: 'middle' as const, offset: new Point(-(SIZE / 2 + 3), 0) }
  return { vertical: 'bottom' as const, offset: new Point(SIZE / 2 + 3, -(SIZE / 2 + 3)) }
}

/** Eine Zeile des Fensters: Beschriftung, darunter Farbpunkt und Name. */
const rowOf = (label: string, name: string, color: string) => {
  const row = document.createElement('div')
  row.style.cssText = 'margin-top: 2px'
  const caption = document.createElement('div')
  caption.style.cssText = 'font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.6)'
  caption.textContent = label
  const person = document.createElement('div')
  person.style.cssText = 'display: flex; align-items: center; gap: 6px'
  const dot = document.createElement('span')
  dot.style.cssText = `width: 10px; height: 10px; border-radius: 50%; flex: none; background: ${color}`
  person.append(dot, name)
  row.append(caption, person)
  return row
}

/**
 * Zeigt an jeder Zelle, wer sie angelegt und wer sie zuletzt bearbeitet hat; ein Klick auf den Punkt öffnet ein
 * kleines Fenster mit beiden Namen. Teil-Container bekommen keinen Punkt, sie gehören zu ihrem Element. Liest nach
 * jeder Änderung die neuen Updates von collab-kit nach. Gibt zurück, wie die Punkte wieder verschwinden.
 */
export const showAuthors = (graph: Graph, session: Session) => {
  const drawn = new Map<Cell, AuthorOverlay>()
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined

  // Neben dem Container des Canvas, nicht darin: beim Verschieben der Ansicht bewegt maxGraph alle Kinder des Containers mit.
  const popup = document.createElement('div')
  popup.style.cssText = 'position: absolute; z-index: 6; display: none; min-width: 150px; padding: 6px 10px; font-size: 12px; line-height: 1.6; border-radius: 6px; background: rgb(var(--v-theme-surface)); color: rgb(var(--v-theme-on-surface)); border: 1px solid rgba(var(--v-theme-on-surface), 0.15); box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15)'
  const host = graph.container.parentElement
  host?.append(popup)
  const close = () => (popup.style.display = 'none')

  /** Ohne Änderung durch jemand anderen nur der Ersteller. */
  const open = (event: MouseEvent, created: [string, string], changed: [string, string] | null) => {
    if (!host) return
    popup.replaceChildren(rowOf('Created by', ...created), ...(changed ? [rowOf('Last changed by', ...changed)] : []))
    const bounds = host.getBoundingClientRect()
    popup.style.left = `${event.clientX - bounds.left + 10}px`
    popup.style.top = `${event.clientY - bounds.top + 10}px`
    popup.style.display = 'block'
  }

  // Schließt bei einem Klick daneben, mit Esc und sobald sich die Ansicht verschiebt oder zoomt.
  const onPointer = (event: PointerEvent) => !popup.contains(event.target as Node) && close()
  const onKey = (event: KeyboardEvent) => event.key === 'Escape' && close()
  document.addEventListener('pointerdown', onPointer, true)
  document.addEventListener('keydown', onKey)
  graph.view.addListener(InternalEvent.SCALE, close)
  graph.view.addListener(InternalEvent.TRANSLATE, close)
  graph.view.addListener(InternalEvent.SCALE_AND_TRANSLATE, close)

  // removeCellOverlays (OverlaysMixin.js:55) leert die ganze Liste einer Zelle, so auch die Syntaxprüfung über
  // setCellWarning(cell, null) bei jeder Änderung. Solange die Punkte an sind, setzt diese Hülle den eigenen gleich
  // wieder ein; alles andere entfernt sie wie bisher.
  const removeAll = graph.removeCellOverlays
  graph.removeCellOverlays = (cell: Cell) => {
    const removed = removeAll.call(graph, cell)
    const own = drawn.get(cell)
    if (!own) return removed
    graph.addCellOverlay(cell, own)
    return removed.filter((overlay) => overlay !== own)
  }

  const clear = () => {
    close()
    drawn.forEach((overlay, cell) => graph.removeCellOverlay(cell, overlay))
    drawn.clear()
  }

  const draw = async () => {
    const { authors, names } = await cellAuthors(session.workpieceId)
    if (stopped) return
    const person = (id: string): [string, string] => [nameOf({ id, name: names[id] }), colorOf(id)]
    clear()
    for (const [id, { createdBy, changedBy }] of authors) {
      const cell = graph.getDataModel().getCell(id)
      if (!cell || !(cell.isVertex() || cell.isEdge()) || isPart(cell)) continue
      const { vertical, offset } = placeOf(cell)
      const overlay = new AuthorOverlay(imageOf(colorOf(createdBy), colorOf(changedBy)), null, 'left', vertical, offset, 'pointer')
      overlay.addListener(InternalEvent.CLICK, (_: unknown, event: EventObject) => open(event.getProperty('event') as MouseEvent, person(createdBy), changedBy === createdBy ? null : person(changedBy)))
      graph.addCellOverlay(cell, overlay)
      drawn.set(cell, overlay)
    }
  }

  const redraw = () => void draw().catch((error) => console.warn('Could not read who changed the cells.', error))
  const stopChanges = session.units.onChange(() => {
    clearTimeout(timer)
    timer = setTimeout(redraw, WAIT_MS)
  })
  redraw()

  return () => {
    stopped = true
    clearTimeout(timer)
    stopChanges()
    clear()
    graph.removeCellOverlays = removeAll
    document.removeEventListener('pointerdown', onPointer, true)
    document.removeEventListener('keydown', onKey)
    graph.view.removeListener(close)
    popup.remove()
  }
}
