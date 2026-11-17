import { CellOverlay, ImageBox, InternalEvent, Point, type Cell, type EventObject, type Graph } from '@maxgraph/core'
import type { Session } from '@/collab/kit/collabKitV1'
import { colorOf, nameOf } from '@/collab/presence/presence'
import { cellAuthors } from '@/collab/storage/workpieceVersions'

/** Size of the dot in px; maxGraph scales it with the zoom. */
const SIZE = 14
/** How long to wait after a change, so collab-kit has stored it and several are read together. */
const WAIT_MS = 1500

/** The dot at a cell; a class of its own, so only these overlays are removed, not the warnings. */
class AuthorOverlay extends CellOverlay {
  /** No hover tooltip, a click shows the names (useCanvasOverlays, OverlayAwareTooltipHandler in DrawingCanvas). */
  readonly hoverTooltip = false
}

/** Fill in the color of the creator, ring in that of the last editor, on white for any background. */
const imageOf = (fill: string, ring: string) => new ImageBox(`data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}"><circle cx="7" cy="7" r="7" fill="#fff"/><circle cx="7" cy="7" r="4.75" fill="${fill}" stroke="${ring}" stroke-width="2.5"/></svg>`)}`, SIZE, SIZE)

/**
 * Whether the cell is a part of its element, such as the attribute list below an entity type: maxGraph creates such
 * cells with a geometry relative to the parent (Geometry.relative), they do not exist without their element.
 */
const isPart = (cell: Cell | null) => Boolean(cell?.isVertex() && cell.getGeometry()?.relative)

/**
 * Where the dot sits (CellOverlay.getBounds): on edges in the middle, in a part container such as the attribute list
 * left of the element, so it covers no text, otherwise moved into the element at the bottom left.
 */
const placeOf = (cell: Cell) => {
  if (cell.isEdge()) return { vertical: 'bottom' as const, offset: new Point() }
  if (isPart(cell.getParent())) return { vertical: 'middle' as const, offset: new Point(-(SIZE / 2 + 3), 0) }
  return { vertical: 'bottom' as const, offset: new Point(SIZE / 2 + 3, -(SIZE / 2 + 3)) }
}

/** A row of the popup: caption, below it color dot and name. */
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
 * Shows at every cell who created it and who last edited it; a click on the dot opens a small popup with both
 * names. Part containers get no dot, they belong to their element. Reads the new updates of collab-kit after
 * every change. Gives back how the dots go again.
 */
export const showAuthors = (graph: Graph, session: Session) => {
  const drawn = new Map<Cell, AuthorOverlay>()
  let stopped = false
  let timer: ReturnType<typeof setTimeout> | undefined

  // Next to the container of the canvas, not in it: while panning, maxGraph moves every child of the container along.
  const popup = document.createElement('div')
  popup.style.cssText = 'position: absolute; z-index: 6; display: none; min-width: 150px; padding: 6px 10px; font-size: 12px; line-height: 1.6; border-radius: 6px; background: rgb(var(--v-theme-surface)); color: rgb(var(--v-theme-on-surface)); border: 1px solid rgba(var(--v-theme-on-surface), 0.15); box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15)'
  const host = graph.container.parentElement
  host?.append(popup)
  const close = () => (popup.style.display = 'none')

  /** Without a change by someone else, the creator only. */
  const open = (event: MouseEvent, created: [string, string], changed: [string, string] | null) => {
    if (!host) return
    popup.replaceChildren(rowOf('Created by', ...created), ...(changed ? [rowOf('Last changed by', ...changed)] : []))
    const bounds = host.getBoundingClientRect()
    popup.style.left = `${event.clientX - bounds.left + 10}px`
    popup.style.top = `${event.clientY - bounds.top + 10}px`
    popup.style.display = 'block'
  }

  // Closes on a click outside, on Esc and as soon as the view pans or zooms.
  const onPointer = (event: PointerEvent) => !popup.contains(event.target as Node) && close()
  const onKey = (event: KeyboardEvent) => event.key === 'Escape' && close()
  document.addEventListener('pointerdown', onPointer, true)
  document.addEventListener('keydown', onKey)
  graph.view.addListener(InternalEvent.SCALE, close)
  graph.view.addListener(InternalEvent.TRANSLATE, close)
  graph.view.addListener(InternalEvent.SCALE_AND_TRANSLATE, close)

  // removeCellOverlays (OverlaysMixin.js:55) empties the whole list of a cell, as the syntax check does through
  // setCellWarning(cell, null) on every change. While the dots are on, this wrapper puts the own one back at once;
  // it removes everything else as before.
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
