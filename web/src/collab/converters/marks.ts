import type { JsonObject } from '@/services/api/types/common'
import { TASK_EDIT_MARKS } from '@/utils/taskEdits'

/** One mark on the fixed task text; offsets count the characters of its text nodes, which never change. */
export interface SharedMark {
  mark: string
  color: string | null
  createdAt: string
  ranges: { from: number; to: number }[]
}

export type SharedMarks = Record<string, SharedMark>

interface TaskNode extends JsonObject {
  text?: string
  marks?: { type?: string; attrs?: Record<string, unknown> }[]
  content?: TaskNode[]
}

/** In the room the text is only marked, never added to, so insertions are no shared mark. */
const isSharedMark = (type: string | undefined): type is keyof typeof TASK_EDIT_MARKS => Boolean(type && type in TASK_EDIT_MARKS && type !== 'taskEditInsertion')

/** The marks of an editor document by edit ID, each with the passages it covers. */
export const marksOf = (document: JsonObject): SharedMarks => {
  const marks: SharedMarks = {}
  let offset = 0
  const visit = (node: TaskNode) => {
    if (typeof node.text === 'string') {
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
    node.content?.forEach(visit)
  }
  visit(document as TaskNode)
  return marks
}

/** The task document with the marks laid over it; text nodes are cut where a passage starts or ends. */
export const withMarks = (base: JsonObject, marks: SharedMarks): JsonObject => {
  const entries = Object.entries(marks)
  let offset = 0
  const visit = (node: TaskNode): TaskNode[] => {
    const text = node.text
    if (typeof text !== 'string') return [node.content ? { ...node, content: node.content.flatMap(visit) } : node]
    const start = offset
    offset += text.length
    const cuts = new Set([start, offset])
    for (const [, entry] of entries) for (const range of entry.ranges) for (const at of [range.from, range.to]) if (at > start && at < offset) cuts.add(at)
    const points = [...cuts].sort((left, right) => left - right)
    const own = (node.marks ?? []).filter((mark) => !(mark.type && mark.type in TASK_EDIT_MARKS))
    return points.slice(1).map((to, index) => {
      const from = points[index]
      const added = entries.filter(([, entry]) => entry.ranges.some((range) => range.from <= from && range.to >= to)).map(([id, entry]) => ({ type: entry.mark, attrs: { editId: id, editType: TASK_EDIT_MARKS[entry.mark as keyof typeof TASK_EDIT_MARKS], createdAt: entry.createdAt, updatedAt: null, color: entry.color } }))
      const piece: TaskNode = { ...node, text: text.slice(from - start, to - start) }
      if (own.length || added.length) piece.marks = [...own, ...added]
      else delete piece.marks
      return piece
    })
  }
  return visit(base as TaskNode)[0]
}
