import { Mark, mergeAttributes } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { Color } from '@tiptap/extension-color'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import { TextStyle } from '@tiptap/extension-text-style'
import Underline from '@tiptap/extension-underline'
import type { DiagramConnection } from '@/model/Connection'
import type { DiagramElement } from '@/model/Element'

export interface TaskElementOption {
  languageId: string
  elementType: string
  label: string
  element?: DiagramElement
}

export interface TaskConnectionOption {
  languageId: string
  connectionType: string
  label: string
  connection?: DiagramConnection
}

export interface TaskOptionLanguage {
  id: string
  name: string
  elements: DiagramElement[]
  connections: DiagramConnection[]
}

export const buildTaskElementOptions = (languages: readonly TaskOptionLanguage[]): TaskElementOption[] =>
  languages.flatMap((language) =>
    language.elements.map((element) => ({
      languageId: language.id,
      elementType: element.type,
      label: `${language.name}: ${element.defaultLabel || element.type}`,
      element
    }))
  )

export const buildTaskConnectionOptions = (languages: readonly TaskOptionLanguage[]): TaskConnectionOption[] =>
  languages.flatMap((language) =>
    language.connections.map((connection) => ({
      languageId: language.id,
      connectionType: connection.type,
      label: `${language.name}: ${connection.label || connection.type}`,
      connection
    }))
  )

export interface TaskEditorColor {
  label: string
  value: string
}

export const TASK_TEXT_COLORS: readonly TaskEditorColor[] = [
  { label: 'Black', value: '#000000' },
  { label: 'Dark gray', value: '#424242' },
  { label: 'Red', value: '#E53935' },
  { label: 'Pink', value: '#D81B60' },
  { label: 'Purple', value: '#8E24AA' },
  { label: 'Blue', value: '#1E88E5' },
  { label: 'Cyan', value: '#00ACC1' },
  { label: 'Green', value: '#43A047' },
  { label: 'Orange', value: '#FB8C00' },
  { label: 'Yellow', value: '#FDD835' }
]

export const TASK_HIGHLIGHT_COLORS: readonly TaskEditorColor[] = [
  { label: 'Yellow', value: '#FFF176' },
  { label: 'Green', value: '#C8E6C9' },
  { label: 'Blue', value: '#BBDEFB' },
  { label: 'Pink', value: '#F8BBD0' },
  { label: 'Orange', value: '#FFE0B2' },
  { label: 'Purple', value: '#E1BEE7' }
]

export const TaskElementMark = Mark.create({
  name: 'taskElement',
  addAttributes: () => ({
    languageId: {
      default: null,
      parseHTML: (element) => element.getAttribute('data-task-element-language-id'),
      renderHTML: (attributes) => ({ 'data-task-element-language-id': attributes.languageId })
    },
    elementType: {
      default: null,
      parseHTML: (element) => element.getAttribute('data-task-element-type'),
      renderHTML: (attributes) => ({ 'data-task-element-type': attributes.elementType })
    }
  }),
  parseHTML: () => [{ tag: 'span[data-task-element-language-id][data-task-element-type]' }],
  renderHTML: ({ HTMLAttributes }) => ['span', mergeAttributes(HTMLAttributes, { class: 'task-element-mark', draggable: 'true' }), 0]
})

export const TaskConnectionMark = Mark.create({
  name: 'taskConnection',
  addAttributes: () => ({
    languageId: {
      default: null,
      parseHTML: (element) => element.getAttribute('data-task-connection-language-id'),
      renderHTML: (attributes) => ({ 'data-task-connection-language-id': attributes.languageId })
    },
    connectionType: {
      default: null,
      parseHTML: (element) => element.getAttribute('data-task-connection-type'),
      renderHTML: (attributes) => ({ 'data-task-connection-type': attributes.connectionType })
    }
  }),
  parseHTML: () => [{ tag: 'span[data-task-connection-language-id][data-task-connection-type]' }],
  renderHTML: ({ HTMLAttributes }) => ['span', mergeAttributes(HTMLAttributes, { class: 'task-connection-mark' }), 0]
})

export const createTaskEditorExtensions = (placeholder?: string) => [StarterKit.configure({ heading: { levels: [1, 2, 3] }, link: false, underline: false }), TextStyle, Color, Underline, TextAlign.configure({ types: ['heading', 'paragraph'] }), Highlight.configure({ multicolor: true }), ...(placeholder ? [Placeholder.configure({ placeholder })] : []), TaskElementMark, TaskConnectionMark]

export const readTaskConnectionReference = (target: EventTarget | null) => {
  const mark = (target as Element | null)?.closest('[data-task-connection-language-id][data-task-connection-type]')
  const languageId = mark?.getAttribute('data-task-connection-language-id')
  const connectionType = mark?.getAttribute('data-task-connection-type')
  return languageId && connectionType ? { languageId, connectionType } : null
}

export const writeTaskElementDragData = (event: DragEvent): boolean => {
  const mark = (event.target as Element | null)?.closest('[data-task-element-language-id][data-task-element-type]')
  const elementType = mark?.getAttribute('data-task-element-type')
  if (!mark || !elementType || !event.dataTransfer) return false
  event.dataTransfer.setData('text/plain', elementType)
  event.dataTransfer.setData(
    'application/x-modeling-task-element',
    JSON.stringify({
      languageId: mark.getAttribute('data-task-element-language-id'),
      elementType,
      label: mark.textContent?.trim() || undefined
    })
  )
  event.dataTransfer.effectAllowed = 'copy'
  return true
}
