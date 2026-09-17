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
      <TaskColorPicker title="Text color Edit" icon="mdi-format-color-text" :colors="TASK_TEXT_COLORS" size="x-small" :disabled="!hasSelection" :active="isFormatActive('taskEditTextColor')" @select="applyFormat('taskEditTextColor', 'textColor', $event)" />
      <TaskColorPicker title="Highlight Edit" icon="mdi-marker" :colors="TASK_HIGHLIGHT_COLORS" size="x-small" :disabled="!hasSelection" :active="isFormatActive('taskEditHighlight')" @select="applyFormat('taskEditHighlight', 'highlight', $event)" />
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
import { Editor as CoreEditor, Extension } from '@tiptap/core'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import { Plugin } from '@tiptap/pm/state'
import type { JsonObject } from '@/services/api/types/common'
import { cloneTaskDocument, taskDocumentsEqual } from '@/utils/taskEdits'
import TaskColorPicker from './TaskColorPicker.vue'
import { createTaskEditorExtensions, readTaskConnectionReference, TASK_HIGHLIGHT_COLORS, TASK_TEXT_COLORS, writeTaskElementDragData, type TaskConnectionOption, type TaskElementOption } from './taskEditorExtensions'
import { createTaskEditMark, toggleTaskEditMark, type TaskEditMarkName } from './taskEditMarks'

type EditType = 'highlight' | 'bold' | 'italic' | 'underline' | 'strike' | 'textColor' | 'inlineCode'

const props = withDefaults(
  defineProps<{
    baseHtml: string
    modelValue: JsonObject | null
    mode?: 'read' | 'edit'
    elementOptions?: TaskElementOption[]
    connectionOptions?: TaskConnectionOption[]
  }>(),
  { mode: 'read', elementOptions: () => [], connectionOptions: () => [] }
)

const emit = defineEmits<{
  'update:modelValue': [document: JsonObject]
  'select-connection': [reference: { languageId: string; connectionType: string }]
}>()

const baseExtensions = [
  ...createTaskEditorExtensions(),
  createTaskEditMark('taskEditHighlight', 'highlight'),
  createTaskEditMark('taskEditBold', 'bold'),
  createTaskEditMark('taskEditItalic', 'italic'),
  createTaskEditMark('taskEditUnderline', 'underline'),
  createTaskEditMark('taskEditStrike', 'strike'),
  createTaskEditMark('taskEditTextColor', 'textColor'),
  createTaskEditMark('taskEditInlineCode', 'inlineCode'),
  createTaskEditMark('taskEditInsertion', 'insertion')
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
  onSelectionUpdate: () => {
    selectionTick.value += 1
  }
})

const hasSelection = computed(() => {
  selectionTick.value
  return Boolean(editor.value && editor.value.state.selection.from !== editor.value.state.selection.to)
})

const newId = () =>
  globalThis.crypto?.randomUUID?.() ??
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (token) => {
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
  editor.value
    .chain()
    .focus()
    .insertContent({ type: 'text', text: insertionText.value, marks: [{ type: 'taskEditInsertion', attrs: attributes('insertion') }] })
    .run()
  insertionText.value = ''
  insertionDialog.value = false
}

watch(
  () => props.mode,
  (mode) => editor.value?.setEditable(mode === 'edit')
)
watch(
  () => props.baseHtml,
  (html) => {
    const parser = new CoreEditor({ content: html, editable: false, extensions: baseExtensions })
    baseDocument = cloneTaskDocument(parser.getJSON() as JsonObject)
    parser.destroy()
    if (props.modelValue === null && editor.value) {
      lastDocument = JSON.stringify(baseDocument)
      if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.commands.setContent(baseDocument, false)
    }
  }
)
watch(
  () => props.modelValue,
  (document) => {
    if (!editor.value) return
    const next = document ?? baseDocument
    lastDocument = JSON.stringify(next)
    if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.commands.setContent(next, false)
  },
  { deep: true }
)

const onTaskReferenceClick = (event: MouseEvent) => {
  if (props.mode === 'edit') return
  const reference = readTaskConnectionReference(event.target)
  if (reference) emit('select-connection', reference)
}

const onDragStart = (event: DragEvent) => {
  if (props.mode === 'edit') return event.preventDefault()
  writeTaskElementDragData(event)
}

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.task-edit-editor {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: #fff;
}
.task-edit-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
  background: #f5f5f5;
}
.task-edit-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.task-edit-body :deep(.ProseMirror) {
  min-height: 120px;
  height: 100%;
  padding: 12px 16px;
  outline: none;
  font-size: 14px;
  line-height: 1.6;
  color: #212121;
}
.task-edit-body :deep(.task-element-mark) {
  border-bottom: 2px solid rgb(var(--v-theme-primary));
  cursor: grab;
}
.task-edit-body :deep(.task-connection-mark) {
  border-bottom: 2px dashed rgb(var(--v-theme-secondary));
  cursor: pointer;
}
</style>
