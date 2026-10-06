import { WebsocketProvider } from 'y-websocket'
import * as Y from 'yjs'
import { useBearerToken } from '@/composables/useBearerToken'
import { collabUrl } from './collabApi'

export interface CollabSession {
  doc: Y.Doc
  /** Who is at the workpiece and what they point at; collab-kit passes it on but never stores it. */
  awareness: WebsocketProvider['awareness']
  /** Fulfilled once the document holds what collab-kit has. */
  synced: Promise<void>
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

  // collab-kit checks the token only at the handshake, so every reconnect takes the current one.
  provider.on('connection-close', () => {
    provider.protocols = ['bearer', bearerToken.value]
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
  provider.on('closed', ({ code, reason }) => onStatus(`closed ${code} ${reason}`))

  return {
    doc,
    awareness: provider.awareness,
    synced,
    close: () => {
      provider.destroy()
      doc.destroy()
    }
  }
}
