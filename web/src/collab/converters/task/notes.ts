import type { JSONContent } from '@tiptap/core'
import type { Node as ProseMirrorNode } from '@tiptap/pm/model'
import { TextSelection } from '@tiptap/pm/state'
import type { TextDelta } from '@/collab/kit/collabKitV1'

type Attributes = Record<string, unknown>
type Op = { insert: string; attributes?: Attributes } | { retain: number; attributes?: Attributes } | { delete: number }

/** One UTF-16 unit of the text with its attributes, as Yjs and ProseMirror both count. */
export interface Char {
  char: string
  attributes: Attributes
  key: string
}

const keyOf = (attributes: Attributes) =>
  JSON.stringify(
    Object.entries(attributes)
      .filter(([, value]) => value !== null && value !== undefined)
      .sort(([left], [right]) => left.localeCompare(right))
  )

const charsOfText = (text: string, attributes: Attributes): Char[] => {
  const key = keyOf(attributes)
  return text.split('').map((char) => ({ char, attributes, key }))
}

/** The shared text as characters; a line ends with a newline, which carries whether it is a bullet. */
export const charsOfDelta = (delta: TextDelta): Char[] => delta.flatMap((op) => ('insert' in op && typeof op.insert === 'string' ? charsOfText(op.insert, { ...op.attributes }) : []))

const attributesOfMarks = (marks: JSONContent['marks']): Attributes => {
  const attributes: Attributes = {}
  for (const mark of marks ?? []) {
    if (mark.type === 'bold' || mark.type === 'underline') attributes[mark.type] = true
    if (mark.type === 'highlight') attributes.highlight = mark.attrs?.color ?? true
  }
  return attributes
}

const marksOfAttributes = (attributes: Attributes): JSONContent['marks'] => [...(attributes.bold ? [{ type: 'bold' }] : []), ...(attributes.underline ? [{ type: 'underline' }] : []), ...(attributes.highlight ? [{ type: 'highlight', attrs: typeof attributes.highlight === 'string' ? { color: attributes.highlight } : {} }] : [])]

/** The editor document as characters; a nested bullet counts as a bullet like any other. */
export const charsOfDoc = (document: JSONContent): Char[] => {
  const chars: Char[] = []
  const walk = (node: JSONContent, bullet: boolean) => {
    if (node.type === 'paragraph') {
      for (const child of node.content ?? []) if (typeof child.text === 'string') chars.push(...charsOfText(child.text, attributesOfMarks(child.marks)))
      chars.push(...charsOfText('\n', bullet ? { list: 'bullet' } : {}))
      return
    }
    for (const child of node.content ?? []) walk(child, bullet || node.type === 'bulletList')
  }
  walk(document, false)
  return chars
}

/** The editor document of the characters; bullets in a row form one list. */
export const docOfChars = (chars: Char[]): JSONContent => {
  const blocks: JSONContent[] = []
  let inline: JSONContent[] = []
  let inlineKey = ''
  const endLine = (bullet: boolean) => {
    const paragraph: JSONContent = inline.length ? { type: 'paragraph', content: inline } : { type: 'paragraph' }
    const last = blocks[blocks.length - 1]
    if (!bullet) blocks.push(paragraph)
    else if (last?.type === 'bulletList') last.content?.push({ type: 'listItem', content: [paragraph] })
    else blocks.push({ type: 'bulletList', content: [{ type: 'listItem', content: [paragraph] }] })
    inline = []
  }
  for (const char of chars) {
    if (char.char === '\n') {
      endLine(char.attributes.list === 'bullet')
      continue
    }
    const last = inline[inline.length - 1]
    if (last && inlineKey === char.key) last.text += char.char
    else {
      const marks = marksOfAttributes(char.attributes)
      inline.push(marks?.length ? { type: 'text', text: char.char, marks } : { type: 'text', text: char.char })
      inlineKey = char.key
    }
  }
  // A last line without newline, or the empty text, still needs a paragraph.
  if (inline.length || !blocks.length) endLine(false)
  return { type: 'doc', content: blocks }
}

const same = (left: Char, right: Char) => left.char === right.char && left.key === right.key

/** Attributes that differ, with null for those taken away, as the text expects them. */
const formatChange = (before: Attributes, after: Attributes): Attributes => {
  const change: Attributes = {}
  for (const key of new Set([...Object.keys(before), ...Object.keys(after)])) if (before[key] !== after[key]) change[key] = after[key] ?? null
  return change
}

/** The change from one state to the next: what stays the same at both ends is kept. */
export const changeOf = (before: Char[], after: Char[]): Op[] => {
  let start = 0
  while (start < before.length && start < after.length && same(before[start], after[start])) start++
  let end = 0
  while (end < before.length - start && end < after.length - start && same(before[before.length - 1 - end], after[after.length - 1 - end])) end++
  const removed = before.slice(start, before.length - end)
  const added = after.slice(start, after.length - end)
  if (!removed.length && !added.length) return []

  const ops: Op[] = start ? [{ retain: start }] : []
  const append = (op: Op) => {
    const last = ops[ops.length - 1]
    // Steps of the same kind and the same attributes become one.
    if (last && 'retain' in last && 'retain' in op && keyOf(last.attributes ?? {}) === keyOf(op.attributes ?? {})) last.retain += op.retain
    else if (last && 'insert' in last && 'insert' in op && keyOf(last.attributes ?? {}) === keyOf(op.attributes ?? {})) last.insert += op.insert
    else ops.push(op)
  }
  if (removed.length === added.length && removed.every((char, index) => char.char === added[index].char)) {
    // Only the formatting changed: the text stays, so what others type inside it stays as well.
    removed.forEach((char, index) => {
      const change = formatChange(char.attributes, added[index].attributes)
      append(Object.keys(change).length ? { retain: 1, attributes: change } : { retain: 1 })
    })
  } else {
    if (removed.length) ops.push({ delete: removed.length })
    for (const char of added) append(Object.keys(char.attributes).length ? { insert: char.char, attributes: char.attributes } : { insert: char.char })
  }
  return ops
}

/** Where a position of the editor lies in the text: each line counts its characters and its newline. */
export const indexAt = (doc: ProseMirrorNode, pos: number) => {
  let index = 0
  let found: number | null = null
  doc.descendants((node, start) => {
    if (found !== null) return false
    if (!node.isTextblock) return true
    const from = start + 1
    if (pos <= from + node.content.size) found = index + Math.max(0, pos - from)
    else index += node.content.size + 1
    return false
  })
  return found ?? index
}

/** The editor position of a place in the text, at the end if the text is shorter. */
export const posAt = (doc: ProseMirrorNode, index: number) => {
  let rest = index
  let found: number | null = null
  doc.descendants((node, start) => {
    if (found !== null) return false
    if (!node.isTextblock) return true
    if (rest <= node.content.size) found = start + 1 + rest
    else rest -= node.content.size + 1
    return false
  })
  return found ?? TextSelection.atEnd(doc).from
}
