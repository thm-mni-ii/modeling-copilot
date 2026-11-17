import { ref } from 'vue'
import type { RemoteEdit } from '@/collab/graph/graphBinding'
import type { Person } from '@/collab/presence/presence'

/** The kind of an entry in the log. */
export type LogKind = 'failed' | 'joined' | 'left' | RemoteEdit['kind'] | 'saved' | 'release' | 'conflict' | 'connected' | 'offline' | 'closed' | 'rights' | 'undo'
export interface LogEntry {
  kind: LogKind
  /** For entries of a person only what they did; their name stands above their block in the log. */
  text: string
  at: number
  /** Who it was, if known, with the color the person wears in the model. */
  by?: string
  color?: string
  /** For changes: everything merged into it. */
  edits?: RemoteEdit[]
}
/** Without a kind it is technical: it goes to the console only, students do not need it. */
export type Log = (text: string, kind?: LogKind) => void

/** The entries of the event log, the newest on top; the connection keeps one log per workpiece. */
export const logEntries = ref<LogEntry[]>([])

/** Puts an entry in place by its time, the newest on top; mostly it is the newest itself. */
const addEntry = (entry: LogEntry) => {
  const index = logEntries.value.findIndex(({ at }) => at <= entry.at)
  logEntries.value.splice(index < 0 ? logEntries.value.length : index, 0, entry)
}

export const log: Log = (text, kind) => {
  if (kind) addEntry({ kind, text, at: Date.now() })
  else console.debug(`[collab] ${text}`)
}

/** An entry of a person, in the color they wear in the model. */
export const logBy = (kind: LogKind, by: string, text: string, at: number, color: string | undefined) => addEntry({ kind, text, at, by, color })

/** The color for changes that belong to no known person. */
export const SOMEONE_COLOR = '#757575'

/** How long changes of the same person merge into one entry. */
const MERGE_MS = 2 * 60_000

/** An element by its name, without one in general terms. */
export const elementName = ({ name, edge }: { name?: string; edge: boolean }) => name || (edge ? 'a connection' : 'an element')

/** Names one element, counts several; a rename shows the first and the last name. */
const editText = (kind: RemoteEdit['kind'], edits: RemoteEdit[]) => {
  const elements = new Set(edits.map(({ id }) => id)).size
  if (elements > 1) return `${kind} ${elements} elements`
  const last = edits[edits.length - 1]
  return kind === 'renamed' ? `renamed ${elementName({ ...last, name: edits[0].from })} to ${elementName(last)}` : `${kind} ${elementName(last)}`
}

/** A change by someone else, one entry per kind; the same kind by the same person shortly before goes on there. */
export const logChange = (author: Pick<Person, 'name' | 'color'> | undefined, edits: RemoteEdit[]) => {
  const now = Date.now()
  for (const kind of new Set(edits.map((edit) => edit.kind))) {
    const index = logEntries.value.findIndex((entry) => entry.kind === kind && entry.by === author?.name && now - entry.at < MERGE_MS)
    const merged = [...(logEntries.value[index]?.edits ?? []), ...edits.filter((edit) => edit.kind === kind)]
    if (index >= 0) logEntries.value.splice(index, 1)
    logEntries.value.unshift({ kind, text: editText(kind, merged), at: now, by: author?.name, color: author?.color, edits: merged })
  }
}

/** How long after the sync the presence of the others still arrives and counts as the state on connecting. */
const SETTLE_MS = 3000
/** How long a person must be away to count as gone; background tabs are throttled and report only about once a minute. */
const LEAVE_MS = 90_000

/**
 * Logs who joins and leaves a session, except oneself. Until shortly after `settle`, called once the session
 * is in sync, a new list is only the state on connecting. `stop` drops the left entries not yet due.
 */
export const trackPeople = () => {
  // The people as the presence last named them; null until the first list.
  let last: Map<string, Person> | null = null
  let settledAt = Infinity
  // Who has gone, until their left is due; a person back before that was never gone.
  const leaving = new Map<string, ReturnType<typeof setTimeout>>()
  const update = (list: Person[]) => {
    const now = new Map(list.flatMap((person) => (person.self ? [] : [[person.id, person] as const])))
    if (last && Date.now() > settledAt) {
      for (const [id, person] of now) {
        if (last.has(id)) continue
        if (!leaving.has(id)) logBy('joined', person.name, 'joined', Date.now(), person.color)
        clearTimeout(leaving.get(id))
        leaving.delete(id)
      }
      for (const [id, person] of last) {
        if (now.has(id)) continue
        const at = Date.now()
        leaving.set(
          id,
          setTimeout(() => {
            leaving.delete(id)
            logBy('left', person.name, 'left', at, person.color)
          }, LEAVE_MS)
        )
      }
    }
    last = now
  }
  const stop = () => {
    for (const timer of leaving.values()) clearTimeout(timer)
    leaving.clear()
  }
  return { settle: () => (settledAt = Date.now() + SETTLE_MS), update, stop }
}
