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

export interface TaskEditListEntry {
  id: string
  type: TaskEditType
  createdAt: string
  updatedAt: string | null
  color: string | null
  fragments: string[]
}

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

const normalizeNode = (node: JsonNode | null): JsonNode | null => {
  if (!node) return null
  const result = { ...node }
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
  return result
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
  const visit = (node: JsonNode) => {
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
      if (text) current.fragments.push(text)
      entries.set(id, current)
    }
    node.content?.forEach(visit)
  }
  visit(document as JsonNode)
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
