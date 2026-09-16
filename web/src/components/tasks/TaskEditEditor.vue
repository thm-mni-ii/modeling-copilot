<template>
  <div class="task-edit-editor">
    <div v-if="editor && mode === 'edit'" class="task-edit-toolbar">
      <v-btn-group size="x-small" density="compact" variant="outlined">
        <v-btn :disabled="!editor.can().undo()" title="Undo Edit" @click="editor.chain().focus().undo().run()"><v-icon>mdi-undo</v-icon></v-btn>
        <v-btn :disabled="!editor.can().redo()" title="Redo Edit" @click="editor.chain().focus().redo().run()"><v-icon>mdi-redo</v-icon></v-btn>
      </v-btn-group>
      <v-divider vertical class="mx-1" />
      <v-btn-group size="x-small" density="compact" variant="outlined">
        <v-btn :color="isFormatActive('taskEditBold') ? 'primary' : undefined" :disabled="!hasSelection" title="Bold Edit" @mousedown.prevent @click="applyFormat('taskEditBold', 'bold')"><v-icon>mdi-format-bold</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditItalic') ? 'primary' : undefined" :disabled="!hasSelection" title="Italic Edit" @mousedown.prevent @click="applyFormat('taskEditItalic', 'italic')"><v-icon>mdi-format-italic</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditUnderline') ? 'primary' : undefined" :disabled="!hasSelection" title="Underline Edit" @mousedown.prevent @click="applyFormat('taskEditUnderline', 'underline')"><v-icon>mdi-format-underline</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditStrike') ? 'primary' : undefined" :disabled="!hasSelection" title="Strikethrough Edit" @mousedown.prevent @click="applyFormat('taskEditStrike', 'strike')"><v-icon>mdi-format-strikethrough</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditInlineCode') ? 'primary' : undefined" :disabled="!hasSelection" title="Inline code Edit" @mousedown.prevent @click="applyFormat('taskEditInlineCode', 'inlineCode')"><v-icon>mdi-code-tags</v-icon></v-btn>
      </v-btn-group>
      <v-menu location="bottom">
        <template #activator="{ props: menuProps }"><v-btn v-bind="menuProps" size="x-small" variant="outlined" :color="isFormatActive('taskEditTextColor') ? 'primary' : undefined" :disabled="!hasSelection" title="Text color Edit" @mousedown.prevent><v-icon>mdi-format-color-text</v-icon></v-btn></template>
        <v-card class="pa-2"><div class="color-swatches"><button v-for="color in textColors" :key="color" type="button" class="color-swatch" :style="{ background: color }" :title="color" @mousedown.prevent @click="applyFormat('taskEditTextColor', 'textColor', color)" /></div></v-card>
      </v-menu>
      <v-menu location="bottom">
        <template #activator="{ props: menuProps }"><v-btn v-bind="menuProps" size="x-small" variant="outlined" :color="isFormatActive('taskEditHighlight') ? 'primary' : undefined" :disabled="!hasSelection" title="Highlight Edit" @mousedown.prevent><v-icon>mdi-marker</v-icon></v-btn></template>
        <v-card class="pa-2"><div class="color-swatches"><button v-for="color in highlightColors" :key="color" type="button" class="color-swatch" :style="{ background: color }" :title="color" @mousedown.prevent @click="applyFormat('taskEditHighlight', 'highlight', color)" /></div></v-card>
      </v-menu>
      <v-divider vertical class="mx-1" />
      <v-btn size="x-small" variant="tonal" color="primary" prepend-icon="mdi-text-box-plus-outline" title="Insert text Edit" @click="insertionDialog = true">Add text</v-btn>
    </div>

    <editor-content :editor="editor" class="task-edit-body" @click="onTaskReferenceClick" @dragstart="onDragStart" />

    <v-dialog v-model="insertionDialog" max-width="520">
      <v-card>
        <v-card-title>Add text Edit</v-card-title>
        <v-card-text><v-text-field v-model="insertionText" label="Text" maxlength="4000" counter autofocus @keyup.enter="insertText" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="insertionDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!insertionText" @click="insertText">Insert</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Editor as CoreEditor, Extension, Mark, mergeAttributes } from '@tiptap/core'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import { Plugin } from '@tiptap/pm/state'
import StarterKit from '@tiptap/starter-kit'
import { TextStyle } from '@tiptap/extension-text-style'
import { Color } from '@tiptap/extension-color'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import type { JsonObject } from '@/services/api/types/common'
import { cloneTaskDocument, taskDocumentsEqual } from '@/utils/taskEdits'
import type { TaskConnectionOption, TaskElementOption } from './TaskRichEditor.vue'
import { createTaskEditMark, toggleTaskEditMark, type TaskEditMarkName } from './taskEditMarks'

type EditType = 'highlight' | 'bold' | 'italic' | 'underline' | 'strike' | 'textColor' | 'inlineCode'

const props = withDefaults(defineProps<{
  baseHtml: string
  modelValue: JsonObject | null
  mode?: 'read' | 'edit'
  elementOptions?: TaskElementOption[]
  connectionOptions?: TaskConnectionOption[]
}>(), { mode: 'read', elementOptions: () => [], connectionOptions: () => [] })

const emit = defineEmits<{
  'update:modelValue': [document: JsonObject]
  'select-connection': [reference: { languageId: string; connectionType: string }]
}>()

const TaskElementMark = Mark.create({
  name: 'taskElement',
  addAttributes: () => ({
    languageId: { default: null, parseHTML: (element) => element.getAttribute('data-task-element-language-id'), renderHTML: (attrs) => ({ 'data-task-element-language-id': attrs.languageId }) },
    elementType: { default: null, parseHTML: (element) => element.getAttribute('data-task-element-type'), renderHTML: (attrs) => ({ 'data-task-element-type': attrs.elementType }) }
  }),
  parseHTML: () => [{ tag: 'span[data-task-element-language-id][data-task-element-type]' }],
  renderHTML: ({ HTMLAttributes }) => ['span', mergeAttributes(HTMLAttributes, { class: 'task-element-mark', draggable: 'true' }), 0]
})

const TaskConnectionMark = Mark.create({
  name: 'taskConnection',
  addAttributes: () => ({
    languageId: { default: null, parseHTML: (element) => element.getAttribute('data-task-connection-language-id'), renderHTML: (attrs) => ({ 'data-task-connection-language-id': attrs.languageId }) },
    connectionType: { default: null, parseHTML: (element) => element.getAttribute('data-task-connection-type'), renderHTML: (attrs) => ({ 'data-task-connection-type': attrs.connectionType }) }
  }),
  parseHTML: () => [{ tag: 'span[data-task-connection-language-id][data-task-connection-type]' }],
  renderHTML: ({ HTMLAttributes }) => ['span', mergeAttributes(HTMLAttributes, { class: 'task-connection-mark' }), 0]
})

const baseExtensions = [
  StarterKit.configure({ underline: false }), TextStyle, Color, Underline,
  TextAlign.configure({ types: ['heading', 'paragraph'] }), Highlight.configure({ multicolor: true }),
  TaskElementMark, TaskConnectionMark,
  createTaskEditMark('taskEditHighlight', 'highlight'), createTaskEditMark('taskEditBold', 'bold'),
  createTaskEditMark('taskEditItalic', 'italic'), createTaskEditMark('taskEditUnderline', 'underline'),
  createTaskEditMark('taskEditStrike', 'strike'), createTaskEditMark('taskEditTextColor', 'textColor'),
  createTaskEditMark('taskEditInlineCode', 'inlineCode'), createTaskEditMark('taskEditInsertion', 'insertion')
]

const baseParser = new CoreEditor({ content: props.baseHtml, editable: false, extensions: baseExtensions })
let baseDocument = cloneTaskDocument(baseParser.getJSON() as JsonObject)
baseParser.destroy()

const OriginalGuard = Extension.create({
  name: 'taskEditOriginalGuard',
  addProseMirrorPlugins: () => [new Plugin({ filterTransaction: (transaction) => !transaction.docChanged || taskDocumentsEqual(transaction.doc.toJSON() as JsonObject, baseDocument) })]
})

const EditShortcutGuard = Extension.create({
  name: 'taskEditShortcutGuard',
  priority: 1000,
  addKeyboardShortcuts: () => ({
    'Mod-b': () => true,
    'Mod-i': () => true,
    'Mod-u': () => true,
    'Mod-Shift-s': () => true,
    'Mod-e': () => true
  })
})

let lastDocument = JSON.stringify(props.modelValue ?? baseDocument)
const insertionDialog = ref(false)
const insertionText = ref('')
const selectionTick = ref(0)

const editor = useEditor({
  content: props.modelValue ?? props.baseHtml,
  editable: props.mode === 'edit',
  extensions: [...baseExtensions, OriginalGuard, EditShortcutGuard],
  onUpdate: ({ editor: current }) => {
    const document = current.getJSON() as JsonObject
    const serialized = JSON.stringify(document)
    if (serialized === lastDocument) return
    lastDocument = serialized
    selectionTick.value += 1
    emit('update:modelValue', document)
  },
  onSelectionUpdate: () => { selectionTick.value += 1 }
})

const hasSelection = computed(() => {
  selectionTick.value
  return Boolean(editor.value && editor.value.state.selection.from !== editor.value.state.selection.to)
})

const newId = () => globalThis.crypto?.randomUUID?.() ?? 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (token) => {
  const random = Math.floor(Math.random() * 16)
  return (token === 'x' ? random : (random & 0x3) | 0x8).toString(16)
})
const attributes = (type: EditType | 'insertion', color?: string) => ({ editId: newId(), editType: type, createdAt: new Date().toISOString(), updatedAt: null, color: color ?? null })

const applyFormat = (mark: TaskEditMarkName, type: EditType, color?: string) => {
  if (!editor.value || !hasSelection.value) return
  toggleTaskEditMark(editor.value, mark, attributes(type, color))
}

const isFormatActive = (mark: TaskEditMarkName) => {
  selectionTick.value
  return Boolean(editor.value?.isActive(mark))
}

const insertText = () => {
  if (!editor.value || !insertionText.value) return
  editor.value.chain().focus().insertContent({ type: 'text', text: insertionText.value, marks: [{ type: 'taskEditInsertion', attrs: attributes('insertion') }] }).run()
  insertionText.value = ''
  insertionDialog.value = false
}

watch(() => props.mode, (mode) => editor.value?.setEditable(mode === 'edit'))
watch(() => props.baseHtml, (html) => {
  const parser = new CoreEditor({ content: html, editable: false, extensions: baseExtensions })
  baseDocument = cloneTaskDocument(parser.getJSON() as JsonObject)
  parser.destroy()
  if (props.modelValue === null && editor.value) {
    lastDocument = JSON.stringify(baseDocument)
    if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.commands.setContent(baseDocument, false)
  }
})
watch(() => props.modelValue, (document) => {
  if (!editor.value) return
  const next = document ?? baseDocument
  lastDocument = JSON.stringify(next)
  if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.commands.setContent(next, false)
}, { deep: true })

const onTaskReferenceClick = (event: MouseEvent) => {
  if (props.mode === 'edit') return
  const mark = (event.target as Element | null)?.closest('[data-task-connection-language-id][data-task-connection-type]')
  const languageId = mark?.getAttribute('data-task-connection-language-id')
  const connectionType = mark?.getAttribute('data-task-connection-type')
  if (languageId && connectionType) emit('select-connection', { languageId, connectionType })
}

const onDragStart = (event: DragEvent) => {
  if (props.mode === 'edit') return event.preventDefault()
  const mark = (event.target as Element | null)?.closest('[data-task-element-language-id][data-task-element-type]')
  const elementType = mark?.getAttribute('data-task-element-type')
  if (!elementType || !event.dataTransfer) return
  event.dataTransfer.setData('text/plain', elementType)
  event.dataTransfer.setData('application/x-modeling-task-element', JSON.stringify({ languageId: mark?.getAttribute('data-task-element-language-id'), elementType, label: mark?.textContent?.trim() || undefined }))
  event.dataTransfer.effectAllowed = 'copy'
}

const textColors = ['#000000', '#424242', '#E53935', '#D81B60', '#8E24AA', '#1E88E5', '#00ACC1', '#43A047', '#FB8C00', '#FDD835']
const highlightColors = ['#FFF176', '#C8E6C9', '#BBDEFB', '#F8BBD0', '#FFE0B2', '#E1BEE7']

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.task-edit-editor { display: flex; flex-direction: column; min-height: 0; height: 100%; background: #fff; }
.task-edit-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; padding: 6px 8px; border-bottom: 1px solid rgba(0, 0, 0, 0.12); background: #f5f5f5; }
.task-edit-body { flex: 1; min-height: 0; overflow-y: auto; }
.task-edit-body :deep(.ProseMirror) { min-height: 120px; height: 100%; padding: 12px 16px; outline: none; font-size: 14px; line-height: 1.6; color: #212121; }
.task-edit-body :deep(.task-element-mark) { border-bottom: 2px solid rgb(var(--v-theme-primary)); cursor: grab; }
.task-edit-body :deep(.task-connection-mark) { border-bottom: 2px dashed rgb(var(--v-theme-secondary)); cursor: pointer; }
.color-swatches { display: grid; grid-template-columns: repeat(5, 26px); gap: 6px; }
.color-swatch { width: 26px; height: 26px; border: 1px solid rgba(0, 0, 0, 0.25); border-radius: 4px; cursor: pointer; }
</style>
