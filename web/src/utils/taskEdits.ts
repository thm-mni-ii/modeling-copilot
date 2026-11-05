import type { JsonObject } from '@/services/api/types/common'

export const TASK_EDIT_MARKS = {
  taskEditHighlight: 'highlight',
  taskEditBold: 'bold',
  taskEditItalic: 'italic',
  taskEditUnderline: 'underline',
  taskEditStrike: 'strike',
  taskEditTextColor: 'textColor',
  taskEditInlineCode: 'inlineCode',
  taskEditInsertion: 'insertion'
} as const

export type TaskEditType = (typeof TASK_EDIT_MARKS)[keyof typeof TASK_EDIT_MARKS]
export type TaskEditSyncState = 'synced' | 'dirty' | 'saving' | 'offline' | 'conflict'

export interface TaskEditListEntry {
  id: string
  type: TaskEditType
  createdAt: string
  updatedAt: string | null
  color: string | null
  fragments: TaskEditFragment[]
}

export interface TaskEditFragment { text: string; from: number; to: number }
export interface TaskEditFocus { id: string; from?: number; to?: number }

interface JsonNode extends JsonObject {
  type?: string
  text?: string
  marks?: JsonMark[]
  content?: JsonNode[]
}

interface JsonMark extends JsonObject {
  type?: string
  attrs?: Record<string, unknown>
}

export const cloneTaskDocument = (document: JsonObject): JsonObject => JSON.parse(JSON.stringify(document)) as JsonObject

export const flashTaskEdits = (host: HTMLElement, ids: readonly string[]) => {
  for (const id of new Set(ids)) {
    host.querySelectorAll<HTMLElement>(`[data-task-edit-id="${CSS.escape(id)}"]`).forEach((element) => element.animate([
      { outline: '2px solid rgb(25, 118, 210)' },
      { outline: '2px solid transparent' }
    ], { duration: 1400 }))
  }
}

const normalizeNode = (node: JsonNode | null): JsonNode | null => {
  if (!node) return null
  const result = { ...node }
  if (node.attrs) {
    const attrs = Object.fromEntries(Object.entries(node.attrs).filter(([, value]) => value !== null).sort(([a], [b]) => a.localeCompare(b)))
    if (Object.keys(attrs).length) result.attrs = attrs
    else delete result.attrs
  }
  if (node.marks?.length) result.marks = node.marks.map((mark) => normalizeNode(mark as JsonNode) as JsonMark).sort((a, b) => (a.type ?? '').localeCompare(b.type ?? ''))
  if (Array.isArray(node.content)) {
    const content: JsonNode[] = []
    for (const child of node.content) {
      const normalized = normalizeNode(child)
      if (!normalized) continue
      const previous = content.length ? content[content.length - 1] : undefined
      if (previous?.type === 'text' && normalized.type === 'text' && JSON.stringify(previous.marks ?? []) === JSON.stringify(normalized.marks ?? [])) previous.text = `${previous.text ?? ''}${normalized.text ?? ''}`
      else content.push(normalized)
    }
    if (content.length) result.content = content
    else delete result.content
  }
  if (result.type === 'text' && !result.text) return null
  return Object.fromEntries(Object.entries(result).sort(([a], [b]) => a.localeCompare(b))) as JsonNode
}

export const stripTaskEdits = (document: JsonObject): JsonObject => {
  const visit = (node: JsonNode): JsonNode | null => {
    const marks = Array.isArray(node.marks) ? node.marks : []
    if (marks.some((mark) => mark.type === 'taskEditInsertion')) return null
    const result: JsonNode = { ...node }
    const originalMarks = marks.filter((mark) => !(mark.type && mark.type in TASK_EDIT_MARKS))
    if (originalMarks.length) result.marks = originalMarks
    else delete result.marks
    if (Array.isArray(node.content)) result.content = node.content.map(visit).filter((child): child is JsonNode => Boolean(child))
    return result
  }
  return normalizeNode(visit(document as JsonNode)) ?? { type: 'doc' }
}

export const taskDocumentsEqual = (left: JsonObject, right: JsonObject) => JSON.stringify(stripTaskEdits(left)) === JSON.stringify(stripTaskEdits(right))

export const collectTaskEdits = (document: JsonObject | null | undefined): TaskEditListEntry[] => {
  if (!document) return []
  const entries = new Map<string, TaskEditListEntry>()
  const visit = (node: JsonNode, position: number): number => {
    const text = typeof node.text === 'string' ? node.text : ''
    for (const mark of Array.isArray(node.marks) ? node.marks : []) {
      if (!mark.type || !(mark.type in TASK_EDIT_MARKS)) continue
      const attrs = mark.attrs ?? {}
      const id = typeof attrs.editId === 'string' ? attrs.editId : ''
      if (!id) continue
      const current = entries.get(id) ?? {
        id,
        type: TASK_EDIT_MARKS[mark.type as keyof typeof TASK_EDIT_MARKS],
        createdAt: typeof attrs.createdAt === 'string' ? attrs.createdAt : '',
        updatedAt: typeof attrs.updatedAt === 'string' ? attrs.updatedAt : null,
        color: typeof attrs.color === 'string' ? attrs.color : null,
        fragments: []
      }
      if (text) {
        const previous = current.fragments[current.fragments.length - 1]
        if (previous?.to === position) { previous.text += text; previous.to += text.length }
        else current.fragments.push({ text, from: position, to: position + text.length })
      }
      entries.set(id, current)
    }
    if (node.type === 'text') return position + text.length
    if (!node.content) return position + (node.type === 'doc' ? 0 : node.type === 'hardBreak' || node.type === 'horizontalRule' ? 1 : 2)
    let next = position + (node.type === 'doc' ? 0 : 1)
    for (const child of node.content) next = visit(child, next)
    return next + (node.type === 'doc' ? 0 : 1)
  }
  visit(document as JsonNode, 0)
  return [...entries.values()].sort((left, right) => right.createdAt.localeCompare(left.createdAt) || left.id.localeCompare(right.id))
}

export const removeTaskEdit = (document: JsonObject, editId: string): JsonObject => {
  const visit = (node: JsonNode): JsonNode | null => {
    const marks = Array.isArray(node.marks) ? node.marks : []
    if (marks.some((mark) => mark.type === 'taskEditInsertion' && mark.attrs?.editId === editId)) return null
    const result: JsonNode = { ...node }
    const remaining = marks.filter((mark) => mark.attrs?.editId !== editId)
    if (remaining.length) result.marks = remaining
    else delete result.marks
    if (Array.isArray(node.content)) result.content = node.content.map(visit).filter((child): child is JsonNode => Boolean(child))
    return result
  }
  return normalizeNode(visit(cloneTaskDocument(document) as JsonNode)) ?? { type: 'doc' }
}
