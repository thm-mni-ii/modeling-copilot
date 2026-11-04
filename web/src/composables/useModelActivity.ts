import { onScopeDispose, watch, type Ref } from 'vue'
import { useDocumentVisibility, useIdle, useIntervalFn, useWindowFocus } from '@vueuse/core'
import httpClient from '@/services/api/httpClient'
import type { ModelActivityInteraction, SaveModelActivitySession } from '@/services/api/types/modelActivity'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { serverNow } from '@/utils/serverTime'

interface PendingSession extends SaveModelActivitySession {
  modelId: string | null
  ownerId: string | null
  id: string
  dirty: boolean
  sending: boolean
}

const PREFIX = 'model-activity-session:'
const keyOf = (session: PendingSession) => `${PREFIX}${session.ownerId}:${session.modelId}:${session.id}`

/** One session per editor visit; only browser presence changes are recorded. */
export function useModelActivity(ready: Ref<boolean>) {
  const workspace = useModelWorkspaceStore()
  const visibility = useDocumentVisibility()
  const focused = useWindowFocus()
  const { idle } = useIdle(5 * 60_000, { listenForVisibilityChange: false })
  const pending = new Set<PendingSession>()
  let session: PendingSession | null = null
  let pageHidden = false
  let disposed = false

  const persist = (entry: PendingSession) => {
    if (!entry.modelId || !entry.ownerId) return
    try {
      if (entry.dirty || entry.interactions.length) {
        localStorage.setItem(keyOf(entry), JSON.stringify({ ...entry, sending: false }))
      } else localStorage.removeItem(keyOf(entry))
    } catch {
      // Editing remains available when local storage is restricted.
    }
  }

  const flush = async (entry: PendingSession, keepalive = false) => {
    if (!entry.modelId || (!entry.dirty && !entry.interactions.length) || (entry.sending && !keepalive)) return
    if (!keepalive) entry.sending = true
    try {
      do {
        const body: SaveModelActivitySession = {
          createdAt: entry.createdAt, endedAt: entry.endedAt,
          interactions: entry.interactions.slice(0, 100)
        }
        const url = `/v1/models/${entry.modelId}/activity/sessions/${entry.id}`
        if (keepalive) {
          const token = localStorage.getItem('token')
          if (!token) return
          const response = await fetch(`/api${url}`, {
            method: 'PUT', keepalive: true,
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(body)
          })
          if (!response.ok) return
        } else await httpClient.put(url, body, { timeout: 10_000 })
        const acknowledged = new Set(body.interactions.map((item) => item.id))
        entry.interactions = entry.interactions.filter((item) => !acknowledged.has(item.id))
        entry.dirty = entry.endedAt !== body.endedAt
        persist(entry)
        if (!entry.dirty && !entry.interactions.length && entry !== session) pending.delete(entry)
        if (keepalive) break
      } while (entry.dirty || entry.interactions.length)
    } catch {
      // Keep the pending session for a later retry with the same IDs.
    } finally {
      if (!keepalive) entry.sending = false
    }
  }

  const record = (type: ModelActivityInteraction['type']) => {
    if (!session) return
    session.interactions.push({ id: crypto.randomUUID(), createdAt: new Date(serverNow()).toISOString(), type })
    persist(session)
    if (session.interactions.length >= 50) void flush(session)
  }

  const recover = (entry: PendingSession) => {
    if (!entry.modelId || !entry.ownerId) return
    const prefix = `${PREFIX}${entry.ownerId}:${entry.modelId}:`
    try {
      for (const key of Object.keys(localStorage)) {
        if (!key.startsWith(prefix) || [...pending].some((item) => keyOf(item) === key)) continue
        const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as PendingSession | null
        if (!saved || saved.modelId !== entry.modelId || saved.ownerId !== entry.ownerId || !Array.isArray(saved.interactions)) continue
        saved.sending = false
        pending.add(saved)
        void flush(saved)
      }
    } catch {
      // An unavailable journal must not prevent opening another session.
    }
  }

  const end = () => {
    if (!session) return
    session.endedAt = new Date(serverNow()).toISOString()
    session.dirty = true
    persist(session)
    const closed = session
    session = null
    void flush(closed, true)
  }

  const begin = () => {
    if (session || !ready.value || pageHidden || disposed) return
    session = {
      id: crypto.randomUUID(), modelId: workspace.model?.id ?? null,
      ownerId: workspace.model?.ownerId ?? null, createdAt: new Date(serverNow()).toISOString(),
      endedAt: null, interactions: [], dirty: true, sending: false
    }
    pending.add(session)
    record(visibility.value === 'visible' ? 'tab_visible' : 'tab_hidden')
    record(focused.value ? 'focus_gained' : 'focus_lost')
    record(idle.value ? 'idle' : 'active')
    recover(session)
    void flush(session)
  }

  watch([ready, () => workspace.model?.id], ([enabled, modelId]) => {
    if (!enabled) return end()
    if (session?.modelId && session.modelId !== modelId) end()
    begin()
    // New models receive their server identity on the first save.
    if (session && !session.modelId && workspace.model) {
      session.modelId = workspace.model.id
      session.ownerId = workspace.model.ownerId
      persist(session)
      recover(session)
      void flush(session)
    }
  }, { immediate: true, flush: 'sync' })

  watch(visibility, (value) => {
    record(value === 'visible' ? 'tab_visible' : 'tab_hidden')
    if (session && value === 'hidden') void flush(session, true)
  }, { flush: 'sync' })
  watch(focused, (value) => record(value ? 'focus_gained' : 'focus_lost'), { flush: 'sync' })
  watch(idle, (value) => record(value ? 'idle' : 'active'), { flush: 'sync' })

  const retryPending = () => { for (const entry of pending) void flush(entry) }
  const pagehide = () => { pageHidden = true; end() }
  const pageshow = () => { pageHidden = false; begin() }
  window.addEventListener('pagehide', pagehide)
  window.addEventListener('pageshow', pageshow)
  window.addEventListener('online', retryPending)
  // Transport only: the timer never creates an interaction or changes session data.
  useIntervalFn(retryPending, 30_000)
  onScopeDispose(() => {
    disposed = true
    end()
    window.removeEventListener('pagehide', pagehide)
    window.removeEventListener('pageshow', pageshow)
    window.removeEventListener('online', retryPending)
  })
}
