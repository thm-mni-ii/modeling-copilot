import { InternalEvent, styleUtils, type Graph } from '@maxgraph/core'
import type { CollabSession } from './collabSession'

/** A pointer in model coordinates, so it points at the same element whatever the zoom. */
type Cursor = { x: number; y: number } | null

interface CursorState {
  user?: { id: string; name: string }
  cursor?: Cursor
}

/** At most this often a moving pointer goes out; the last position always follows. */
const SEND_EVERY_MS = 50

const ARROW = '<svg width="14" height="18" viewBox="0 0 14 18" style="display:block"><path d="M1 1 L1 15 L5 11.5 L8 17 L10.5 16 L7.5 10.5 L13 10.5 Z" stroke="#fff" stroke-width="1" /></svg>'

/** Sends where the pointer is on the canvas and shows the pointers of the others above it. */
export const startCursors = (graph: Graph, awareness: CollabSession['awareness'], colorOf: (id: string) => string) => {
  const { container, view } = graph
  const pointers = new Map<number, HTMLElement>()
  let latest: Cursor = null
  let sent: Cursor = null
  let timer: ReturnType<typeof setTimeout> | undefined

  // Its own layer, above the graph and out of the way of the mouse; nothing of it is in the model.
  const layer = document.createElement('div')
  layer.style.cssText = 'position:absolute;inset:0;overflow:hidden;pointer-events:none'
  container.appendChild(layer)

  const flush = () => {
    timer = undefined
    if (latest?.x === sent?.x && latest?.y === sent?.y) return
    sent = latest
    awareness.setLocalStateField('cursor', latest)
  }
  const send = (cursor: Cursor) => {
    latest = cursor
    timer ??= setTimeout(flush, SEND_EVERY_MS)
  }

  const onMove = (event: PointerEvent) => {
    const point = styleUtils.convertPoint(container, event.clientX, event.clientY)
    send({ x: Math.round(point.x / view.scale - view.translate.x), y: Math.round(point.y / view.scale - view.translate.y) })
  }
  const onLeave = () => send(null)

  // The name comes from another client, so it is only ever set as text.
  const pointerFor = (clientId: number, user: { id: string; name: string }) => {
    let pointer = pointers.get(clientId)
    if (!pointer) {
      const color = colorOf(user.id)
      pointer = document.createElement('div')
      pointer.style.cssText = 'position:absolute;left:0;top:0;will-change:transform'
      pointer.innerHTML = ARROW
      pointer.querySelector('path')?.setAttribute('fill', color)
      const label = document.createElement('span')
      label.style.cssText = `position:absolute;left:12px;top:14px;padding:1px 6px;border-radius:4px;background:${color};color:#fff;font-size:11px;white-space:nowrap`
      pointer.appendChild(label)
      layer.appendChild(pointer)
      pointers.set(clientId, pointer)
    }
    const label = pointer.querySelector('span')
    if (label && label.textContent !== user.name) label.textContent = user.name
    return pointer
  }

  const draw = () => {
    const shown = new Set<number>()
    for (const [clientId, { user, cursor }] of awareness.getStates() as Map<number, CursorState>) {
      if (clientId === awareness.clientID || !user || !cursor) continue
      const pointer = pointerFor(clientId, user)
      pointer.style.transform = `translate(${(cursor.x + view.translate.x) * view.scale}px, ${(cursor.y + view.translate.y) * view.scale}px)`
      shown.add(clientId)
    }
    for (const [clientId, pointer] of pointers) {
      if (shown.has(clientId)) continue
      pointer.remove()
      pointers.delete(clientId)
    }
  }

  container.addEventListener('pointermove', onMove)
  container.addEventListener('pointerleave', onLeave)
  awareness.on('change', draw)
  // Zooming or panning here moves every pointer, as they stay at their place in the model.
  view.addListener(InternalEvent.SCALE, draw)
  view.addListener(InternalEvent.TRANSLATE, draw)
  view.addListener(InternalEvent.SCALE_AND_TRANSLATE, draw)

  return () => {
    if (timer) clearTimeout(timer)
    container.removeEventListener('pointermove', onMove)
    container.removeEventListener('pointerleave', onLeave)
    awareness.off('change', draw)
    view.removeListener(draw)
    layer.remove()
  }
}
