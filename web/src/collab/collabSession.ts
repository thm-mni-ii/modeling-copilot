import { WebsocketProvider } from 'y-websocket'
import * as Y from 'yjs'
import { useBearerToken } from '@/composables/useBearerToken'
import { collabUrl } from './collabApi'

export interface CollabSession {
  workpieceId: string
  doc: Y.Doc
  /** Who is at the workpiece and what they point at; collab-kit passes it on but never stores it. */
  awareness: WebsocketProvider['awareness']
  /** Fulfilled once the document holds what collab-kit has. */
  synced: Promise<void>
  /** Calls back whenever collab-kit reconnects this session because the rights at the workpiece changed. */
  onRightsChanged: (listener: () => void) => () => void
  /** Calls back when collab-kit ends the session for good, as when access is withdrawn (4403). */
  onClosed: (listener: (reason: string) => void) => () => void
  close: () => void
}

/** Opens the live connection to one workpiece; the token goes along as a WebSocket subprotocol. */
export const openCollabSession = (workpieceId: string, onStatus: (status: string) => void): CollabSession => {
  if (!collabUrl) throw new Error('VITE_COLLAB_URL is not set.')
  const { bearerToken } = useBearerToken()
  const doc = new Y.Doc()
  const provider = new WebsocketProvider(`${collabUrl.replace(/^http/, 'ws')}/ws`, workpieceId, doc, {
    protocols: ['bearer', bearerToken.value],
    // Two tabs of one browser must meet at collab-kit, not on a channel of their own.
    disableBc: true,
    // 4400-4499 are final, except 4409: the rights changed and a new connection gets the new ones.
    shouldReconnect: (event) => event.code === 4409 || event.code < 4400 || event.code >= 4500
  })

  const rightsListeners = new Set<() => void>()
  const closedListeners = new Set<(reason: string) => void>()

  // collab-kit checks the token only at the handshake, so every reconnect takes the current one.
  provider.on('connection-close', (event) => {
    provider.protocols = ['bearer', bearerToken.value]
    if (event?.code === 4409) rightsListeners.forEach((listener) => listener())
  })
  let markSynced!: () => void
  const synced = new Promise<void>((resolve) => {
    markSynced = resolve
  })

  provider.on('status', ({ status }) => onStatus(status))
  provider.on('sync', (isSynced) => {
    if (!isSynced) return
    markSynced()
    onStatus('synced')
  })
  // Only for codes after which y-websocket does not reconnect; it would otherwise look connected forever.
  provider.on('closed', ({ code, reason }) => {
    onStatus(`closed ${code} ${reason}`)
    closedListeners.forEach((listener) => listener(`${code} ${reason}`))
  })

  return {
    workpieceId,
    doc,
    awareness: provider.awareness,
    synced,
    onRightsChanged: (listener) => {
      rightsListeners.add(listener)
      return () => rightsListeners.delete(listener)
    },
    onClosed: (listener) => {
      closedListeners.add(listener)
      return () => closedListeners.delete(listener)
    },
    close: () => {
      provider.destroy()
      doc.destroy()
    }
  }
}
