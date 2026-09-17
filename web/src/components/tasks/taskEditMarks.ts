import { Mark, mergeAttributes, type Editor } from '@tiptap/core'

export type TaskEditMarkName = 'taskEditHighlight' | 'taskEditBold' | 'taskEditItalic' | 'taskEditUnderline' | 'taskEditStrike' | 'taskEditTextColor' | 'taskEditInlineCode'

export const commonTaskEditAttributes = () => ({
  editId: { default: null, parseHTML: (element: HTMLElement) => element.getAttribute('data-task-edit-id'), renderHTML: (attrs: Record<string, unknown>) => ({ 'data-task-edit-id': attrs.editId }) },
  editType: { default: null, parseHTML: (element: HTMLElement) => element.getAttribute('data-task-edit-type'), renderHTML: (attrs: Record<string, unknown>) => ({ 'data-task-edit-type': attrs.editType }) },
  createdAt: { default: null, parseHTML: (element: HTMLElement) => element.getAttribute('data-task-edit-created-at'), renderHTML: (attrs: Record<string, unknown>) => ({ 'data-task-edit-created-at': attrs.createdAt }) },
  updatedAt: { default: null, parseHTML: (element: HTMLElement) => element.getAttribute('data-task-edit-updated-at'), renderHTML: (attrs: Record<string, unknown>) => (attrs.updatedAt ? { 'data-task-edit-updated-at': attrs.updatedAt } : {}) },
  color: { default: null, parseHTML: (element: HTMLElement) => element.getAttribute('data-task-edit-color'), renderHTML: (attrs: Record<string, unknown>) => (attrs.color ? { 'data-task-edit-color': attrs.color } : {}) }
})

const editStyle = (type: string, color: unknown) => {
  if (type === 'highlight') return `background-color: ${String(color)}`
  if (type === 'textColor') return `color: ${String(color)}`
  if (type === 'bold') return 'font-weight: 700'
  if (type === 'italic') return 'font-style: italic'
  if (type === 'underline') return 'text-decoration: underline'
  if (type === 'strike') return 'text-decoration: line-through'
  if (type === 'inlineCode') return 'font-family: monospace; background: #f0f0f0; padding: 1px 3px; border-radius: 3px'
  if (type === 'insertion') return 'background: rgba(25, 118, 210, 0.08); border-bottom: 1px dashed #1976d2'
  return ''
}

export const createTaskEditMark = (name: string, type: string) =>
  Mark.create({
    name,
    inclusive: type === 'insertion',
    addAttributes: commonTaskEditAttributes,
    parseHTML: () => [{ tag: `span[data-task-edit-mark="${name}"]` }],
    renderHTML: ({ HTMLAttributes }) => [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-task-edit-mark': name,
        style: editStyle(type, HTMLAttributes['data-task-edit-color'])
      }),
      0
    ]
  })

export const toggleTaskEditMark = (editor: Editor, mark: TaskEditMarkName, attributes: Record<string, unknown>) => {
  const color = typeof attributes.color === 'string' ? attributes.color : undefined
  const active = color ? editor.isActive(mark, { color }) : editor.isActive(mark)
  const chain = editor.chain().focus()
  if (active) return chain.unsetMark(mark).run()

  // A selection may overlap fragments carrying older edit IDs. Clear that
  // mark type before applying the new edit so marks never stack invisibly.
  return chain.unsetMark(mark).setMark(mark, attributes).run()
}
