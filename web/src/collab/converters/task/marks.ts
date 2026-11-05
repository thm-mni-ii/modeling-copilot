import type { JsonObject } from '@/services/api/types/common'
import { TASK_EDIT_MARKS } from '@/utils/taskEdits'

type NodeMark = { type?: string; attrs?: Record<string, unknown> }

/** Text added to the fixed text of the task, as the editor holds it, marks included. `lead` tells it belongs to the start of the block at `at`, not to the end of the text before. */
export interface SharedInsert {
  at: number
  lead: boolean
  text: string
  marks: NodeMark[]
}

/** One mark on the fixed task text, or an insertion into it; offsets count the characters of the fixed text only, which never change. */
export interface SharedMark {
  mark: string
  color: string | null
  createdAt: string
  ranges: { from: number; to: number }[]
  inserts?: SharedInsert[]
}

export type SharedMarks = Record<string, SharedMark>

interface TaskNode extends JsonObject {
  text?: string
  marks?: NodeMark[]
  content?: TaskNode[]
}

const isSharedMark = (type: string | undefined): type is keyof typeof TASK_EDIT_MARKS => Boolean(type && type in TASK_EDIT_MARKS && type !== 'taskEditInsertion')

/** The marks of an editor document by edit ID, each with the passages it covers; insertions come with the place they stand at. */
export const marksOf = (document: JsonObject): SharedMarks => {
  const marks: SharedMarks = {}
  let offset = 0
  let lastParent: TaskNode | undefined
  const visit = (node: TaskNode, parent?: TaskNode) => {
    if (typeof node.text === 'string') {
      const insertion = node.marks?.find((mark) => mark.type === 'taskEditInsertion' && typeof mark.attrs?.editId === 'string')
      if (insertion) {
        const entry = (marks[insertion.attrs?.editId as string] ??= {
          mark: 'insertion',
          color: typeof insertion.attrs?.color === 'string' ? insertion.attrs.color : null,
          createdAt: typeof insertion.attrs?.createdAt === 'string' ? insertion.attrs.createdAt : '',
          ranges: [],
          inserts: []
        })
        entry.inserts?.push({ at: offset, lead: parent !== lastParent, text: node.text, marks: node.marks ?? [] })
        return
      }
      lastParent = parent
      const from = offset
      offset += node.text.length
      for (const mark of node.marks ?? []) {
        const id = mark.attrs?.editId
        if (!isSharedMark(mark.type) || typeof id !== 'string') continue
        const entry = (marks[id] ??= {
          mark: mark.type,
          color: typeof mark.attrs?.color === 'string' ? mark.attrs.color : null,
          createdAt: typeof mark.attrs?.createdAt === 'string' ? mark.attrs.createdAt : '',
          ranges: []
        })
        // Text nodes next to each other with the same mark make one passage.
        const last = entry.ranges[entry.ranges.length - 1]
        if (last?.to === from) last.to = offset
        else entry.ranges.push({ from, to: offset })
      }
    }
    node.content?.forEach((child) => visit(child, node))
  }
  visit(document as TaskNode)
  return marks
}

const textLength = (node: TaskNode): number => (typeof node.text === 'string' ? node.text.length : (node.content ?? []).reduce((sum, child) => sum + textLength(child), 0))

/** The task document with the marks laid over it; text nodes are cut where a passage starts or ends. */
export const withMarks = (base: JsonObject, marks: SharedMarks): JsonObject => {
  const entries = Object.entries(marks)
  const inserts = entries.flatMap(([, entry]) => entry.inserts ?? [])
  const total = textLength(base as TaskNode)
  const insertedAt = (at: number, lead: boolean): TaskNode[] => inserts.filter((insert) => insert.at === at && (insert.lead === lead || (lead === false && at === total))).map((insert) => ({ type: 'text', text: insert.text, marks: insert.marks }))
  let offset = 0
  const visit = (node: TaskNode): TaskNode[] => {
    const text = node.text
    if (typeof text !== 'string') return [node.content ? { ...node, content: node.content.flatMap(visit) } : node]
    const start = offset
    offset += text.length
    const cuts = new Set([start, offset])
    for (const [, entry] of entries) for (const range of entry.ranges) for (const at of [range.from, range.to]) if (at > start && at < offset) cuts.add(at)
    for (const insert of inserts) if (insert.at > start && insert.at < offset) cuts.add(insert.at)
    const points = [...cuts].sort((left, right) => left - right)
    const own = (node.marks ?? []).filter((mark) => !(mark.type && mark.type in TASK_EDIT_MARKS))
    const pieces = points.slice(1).map((to, index) => {
      const from = points[index]
      const added = entries.filter(([, entry]) => entry.ranges.some((range) => range.from <= from && range.to >= to)).map(([id, entry]) => ({ type: entry.mark, attrs: { editId: id, editType: TASK_EDIT_MARKS[entry.mark as keyof typeof TASK_EDIT_MARKS], createdAt: entry.createdAt, updatedAt: null, color: entry.color } }))
      const piece: TaskNode = { ...node, text: text.slice(from - start, to - start) }
      if (own.length || added.length) piece.marks = [...own, ...added]
      else delete piece.marks
      return { piece, to }
    })
    return [...insertedAt(start, true), ...pieces.flatMap(({ piece, to }) => [piece, ...insertedAt(to, false)])]
  }
  return visit(base as TaskNode)[0]
}
