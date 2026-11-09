<template>
  <div class="task-edit-editor">
    <div v-if="editor && mode === 'help'" class="task-edit-toolbar help-text-toolbar">
      <span class="text-caption">Wähle die Textstelle aus, die dir Schwierigkeiten bereitet.</span>
      <v-btn size="small" color="warning" variant="tonal" prepend-icon="mdi-marker" :disabled="!hasSelection" @mousedown.prevent @click="markHelpText">Textstelle markieren</v-btn>
    </div>
    <div v-if="editor && mode === 'edit'" class="task-edit-toolbar">
      <template v-if="!shared || history">
        <v-btn-group size="x-small" density="compact" variant="outlined">
          <v-btn :disabled="activeHistory ? !activeHistory.canUndo : !editor.can().undo()" title="Undo Edit" @mousedown.prevent @click="activeHistory ? activeHistory.undo() : editor.chain().focus().undo().run()"><v-icon>mdi-undo</v-icon></v-btn>
          <v-btn :disabled="activeHistory ? !activeHistory.canRedo : !editor.can().redo()" title="Redo Edit" @mousedown.prevent @click="activeHistory ? activeHistory.redo() : editor.chain().focus().redo().run()"><v-icon>mdi-redo</v-icon></v-btn>
        </v-btn-group>
        <v-divider vertical class="mx-1" />
      </template>
      <v-btn-group size="x-small" density="compact" variant="outlined">
        <v-btn :color="isFormatActive('taskEditBold') ? 'primary' : undefined" :disabled="!canFormat" title="Bold Edit" @mousedown.prevent @click="applyFormat('taskEditBold', 'bold')"><v-icon>mdi-format-bold</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditItalic') ? 'primary' : undefined" :disabled="!canFormat" title="Italic Edit" @mousedown.prevent @click="applyFormat('taskEditItalic', 'italic')"><v-icon>mdi-format-italic</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditUnderline') ? 'primary' : undefined" :disabled="!canFormat" title="Underline Edit" @mousedown.prevent @click="applyFormat('taskEditUnderline', 'underline')"><v-icon>mdi-format-underline</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditStrike') ? 'primary' : undefined" :disabled="!canFormat" title="Strikethrough Edit" @mousedown.prevent @click="applyFormat('taskEditStrike', 'strike')"><v-icon>mdi-format-strikethrough</v-icon></v-btn>
        <v-btn :color="isFormatActive('taskEditInlineCode') ? 'primary' : undefined" :disabled="!canFormat" title="Inline code Edit" @mousedown.prevent @click="applyFormat('taskEditInlineCode', 'inlineCode')"><v-icon>mdi-code-tags</v-icon></v-btn>
      </v-btn-group>
      <TaskColorPicker title="Text color Edit" icon="mdi-format-color-text" :colors="TASK_TEXT_COLORS" size="x-small" :disabled="!canFormat" :active="isFormatActive('taskEditTextColor')" @select="applyFormat('taskEditTextColor', 'textColor', $event)" />
      <TaskColorPicker title="Highlight Edit" icon="mdi-marker" :colors="TASK_HIGHLIGHT_COLORS" size="x-small" :disabled="!canFormat" :active="isFormatActive('taskEditHighlight')" @select="applyFormat('taskEditHighlight', 'highlight', $event)" />
      <v-divider vertical class="mx-1" />
      <v-tooltip :text="commentHint" location="bottom">
        <template #activator="{ props: tooltipProps }">
          <span v-bind="tooltipProps" class="task-comment-action" :tabindex="canAddComment ? undefined : 0">
            <v-btn size="x-small" variant="tonal" color="primary" prepend-icon="mdi-comment-plus-outline" :disabled="!canAddComment" @mousedown.prevent @click="openInsertion">Add Comment</v-btn>
          </span>
        </template>
      </v-tooltip>
    </div>

    <editor-content :editor="editor" class="task-edit-body" @click="onTaskReferenceClick" @dragstart="onDragStart" @mouseleave="hideReferencePreview" @mouseover="onTaskReferenceMouseOver" />

    <Teleport to="body">
      <div v-if="referencePreview" class="task-reference-preview" :style="{ left: `${referencePreview.x}px`, top: `${referencePreview.y}px` }">
        <div class="task-reference-preview__kind">{{ referencePreview.kind === 'element' ? 'Model element' : 'Connection' }}</div>
        <div class="task-reference-preview__title">{{ referencePreview.option.label }}</div>
        <DiagramPreviewItem v-if="referencePreview.kind === 'element' && referencePreview.option.element" :element="referencePreview.option.element" :width="180" :height="92" class="task-reference-preview__diagram" />
        <ConnectionPreviewItem v-else-if="referencePreview.kind === 'connection' && referencePreview.option.connection" :connection="referencePreview.option.connection" :width="180" :height="56" class="task-reference-preview__diagram" />
        <div class="task-reference-preview__hint">{{ referencePreview.kind === 'element' ? 'Drag into the canvas to create this element.' : 'Click to select this connection in the canvas.' }}</div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, ref, watch } from 'vue'
import { Editor as CoreEditor, Extension } from '@tiptap/core'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import type { Mark as ProseMirrorMark } from '@tiptap/pm/model'
import { Decoration, DecorationSet } from '@tiptap/pm/view'
import type { HelpTextRange } from '@/services/learningPaths'
import type { JsonObject } from '@/services/api/types/common'
import { cloneTaskDocument, flashTaskEdits, taskDocumentsEqual, TASK_EDIT_MARKS } from '@/utils/taskEdits'
import TaskColorPicker from './TaskColorPicker.vue'
import { readTaskConnectionReference, TASK_HIGHLIGHT_COLORS, TASK_TEXT_COLORS, writeTaskElementDragData, type TaskConnectionOption, type TaskElementOption } from './taskEditorExtensions'
import { createTaskEditExtensions, toggleTaskEditMark, type TaskEditMarkName } from './taskEditMarks'

type EditType = 'highlight' | 'bold' | 'italic' | 'underline' | 'strike' | 'textColor' | 'inlineCode'

const DiagramPreviewItem = defineAsyncComponent(() => import('@/components/modeling/canvas/DiagramPreviewItem.vue'))
const ConnectionPreviewItem = defineAsyncComponent(() => import('@/components/modeling/canvas/ConnectionPreviewItem.vue'))

const props = withDefaults(
  defineProps<{
    baseHtml: string
    baseDocument?: JsonObject | null
    modelValue: JsonObject | null
    mode?: 'read' | 'edit' | 'help'
    /** Im Raum: kein eigener Verlauf, weil er fremde Änderungen zurücknehmen würde; `history` nimmt nur die eigenen Schritte. */
    shared?: boolean
    history?: { canUndo: boolean; canRedo: boolean; undo: () => void; redo: () => void; notes?: { canUndo: boolean; canRedo: boolean; undo: () => void; redo: () => void } }
    helpTextRanges?: HelpTextRange[]
    elementOptions?: TaskElementOption[]
    connectionOptions?: TaskConnectionOption[]
    /** Im Raum: der Editor der Notizen; hat er zuletzt den Fokus, formatiert die Leiste ihn statt der Task. */
    notes?: CoreEditor | null
  }>(),
  { mode: 'read', shared: false, elementOptions: () => [], connectionOptions: () => [], helpTextRanges: () => [] }
)

const emit = defineEmits<{
  'update:modelValue': [document: JsonObject]
  'select-connection': [reference: { languageId: string; connectionType: string }]
  'mark-help-text': [range: HelpTextRange]
  'select-edits': [ids: string[]]
}>()

const baseExtensions = createTaskEditExtensions()

const baseParser = new CoreEditor({ content: props.baseDocument ?? props.baseHtml, editable: false, extensions: baseExtensions })
let originalDocument = cloneTaskDocument(baseParser.getJSON() as JsonObject)
baseParser.destroy()

const OriginalGuard = Extension.create({
  name: 'taskEditOriginalGuard',
  addProseMirrorPlugins: () => [new Plugin({ filterTransaction: (transaction) => !transaction.docChanged || taskDocumentsEqual(transaction.doc.toJSON() as JsonObject, originalDocument) })]
})

const EditShortcutGuard = Extension.create({
  name: 'taskEditShortcutGuard',
  priority: 1000,
  addKeyboardShortcuts: () => ({
    'Mod-b': () => true,
    'Mod-i': () => true,
    'Mod-u': () => true,
    'Mod-Shift-s': () => true,
    'Mod-e': () => true,
    // Im Raum gibt es keinen eigenen Verlauf, siehe `shared`.
    'Mod-z': () => (props.history ? (props.history.undo(), true) : props.shared),
    'Mod-Shift-z': () => (props.history ? (props.history.redo(), true) : props.shared),
    'Mod-y': () => (props.history ? (props.history.redo(), true) : props.shared)
  })
})

const HelpSelection = Extension.create({
  name: 'helpTextSelection',
  addProseMirrorPlugins: () => [new Plugin({
    props: {
      decorations: (state) => props.mode === 'help' ? DecorationSet.create(state.doc,
        props.helpTextRanges.filter((range) => range.start >= 0 && range.end <= state.doc.content.size)
          .map((range) => Decoration.inline(range.start, range.end, { class: 'help-text-mark' }))) : null
    }
  })]
})

const commentComposerKey = new PluginKey<number | null>('taskCommentComposer')
const CommentComposer = Extension.create({
  name: 'taskCommentComposer',
  addProseMirrorPlugins: () => [new Plugin<number | null>({
    key: commentComposerKey,
    state: {
      init: () => null,
      apply: (transaction, position) => {
        const next = transaction.getMeta(commentComposerKey)
        if (next !== undefined) return next
        if (position === null) return null
        const mapped = transaction.mapping.mapResult(position, -1)
        return mapped.deleted ? null : mapped.pos
      }
    },
    props: {
      decorations: (state) => {
        const position = commentComposerKey.getState(state)
        return position == null ? null : DecorationSet.create(state.doc, [Decoration.widget(position, createCommentComposer, {
          key: 'task-comment-composer', side: -1, stopEvent: () => true, ignoreSelection: true
        })])
      }
    }
  })]
})

let lastDocument = JSON.stringify(props.modelValue ?? originalDocument)
const insertionOpen = ref(false)
const insertionText = ref('')
const selectionTick = ref(0)
const cursorActive = ref(false)
// Ob die Leiste gerade die Notizen formatiert: ab dem Fokus in den Notizen bis zum Fokus in der Task.
const notesActive = ref(false)
watch(
  () => props.notes,
  (notes, _, onCleanup) => {
    if (!notes) return
    const onFocus = () => {
      notesActive.value = true
      selectionTick.value += 1
    }
    const onChange = () => {
      selectionTick.value += 1
    }
    notes.on('focus', onFocus)
    notes.on('transaction', onChange)
    onCleanup(() => {
      notes.off('focus', onFocus)
      notes.off('transaction', onChange)
    })
  },
  { immediate: true }
)
// Die Marks der Task als Marks der Notizen; ein Kommentar hat dort kein Gegenstück.
const NOTES_MARKS: Partial<Record<TaskEditMarkName, string>> = { taskEditBold: 'bold', taskEditItalic: 'italic', taskEditUnderline: 'underline', taskEditStrike: 'strike', taskEditInlineCode: 'code', taskEditTextColor: 'textStyle', taskEditHighlight: 'highlight' }

const emitSelectedEdits = (current: CoreEditor, range: { from: number; to: number } = current.state.selection) => {
  if (props.mode === 'help') return []
  const ids = new Set<string>()
  const collect = (marks: readonly ProseMirrorMark[]) => {
    for (const mark of marks) {
      if (mark.type.name in TASK_EDIT_MARKS && typeof mark.attrs.editId === 'string') ids.add(mark.attrs.editId)
    }
  }
  const { from, to } = range
  if (from === to) collect(current.state.doc.resolve(from).marks())
  else current.state.doc.nodesBetween(from, to, (node) => collect(node.marks))
  const selected = [...ids]
  emit('select-edits', selected)
  return selected
}

const editor = useEditor({
  content: props.modelValue ?? originalDocument,
  editable: props.mode === 'edit',
  extensions: [...baseExtensions, OriginalGuard, EditShortcutGuard, HelpSelection, CommentComposer],
  onFocus: () => {
    cursorActive.value = true
    notesActive.value = false
  },
  onBlur: ({ editor: current, event }) => {
    const host = current.view.dom.closest('.task-edit-editor')
    cursorActive.value = event.relatedTarget instanceof Node && Boolean(host?.contains(event.relatedTarget))
  },
  onTransaction: ({ editor: current }) => {
    insertionOpen.value = commentComposerKey.getState(current.state) != null
  },
  onUpdate: ({ editor: current }) => {
    const document = current.getJSON() as JsonObject
    const serialized = JSON.stringify(document)
    if (serialized === lastDocument) return
    lastDocument = serialized
    selectionTick.value += 1
    emit('update:modelValue', document)
    emitSelectedEdits(current)
  },
  onSelectionUpdate: ({ editor: current }) => {
    selectionTick.value += 1
    emitSelectedEdits(current)
  }
})

const hasSelection = computed(() => {
  selectionTick.value
  return Boolean(editor.value && editor.value.state.selection.from !== editor.value.state.selection.to)
})
// Undo und Redo der Leiste gehören zu dem Editor, der zuletzt den Fokus hatte.
const activeHistory = computed(() => (notesActive.value && props.history?.notes ? props.history.notes : props.history))
const canFormat = computed(() => (notesActive.value ? Boolean(props.notes?.isEditable) : hasSelection.value))
const canAddComment = computed(() => {
  selectionTick.value
  return props.mode === 'edit' && !notesActive.value && cursorActive.value && !hasSelection.value && !insertionOpen.value && Boolean(editor.value?.state.selection.$from.parent.inlineContent)
})
const commentHint = computed(() => {
  if (insertionOpen.value) return 'Add or cancel your current comment first.'
  if (hasSelection.value) return 'Clear the selection and place the cursor where the comment should go.'
  if (!canAddComment.value) return 'Place the cursor in the task text to add a comment.'
  return 'Add a comment at the cursor.'
})
const markHelpText = () => {
  const current = editor.value
  if (!current || props.mode !== 'help' || !hasSelection.value) return
  const { from, to } = current.state.selection
  const text = current.state.doc.textBetween(from, to, '\n')
  if (text.trim()) emit('mark-help-text', { start: from, end: to, text })
}
watch(() => props.helpTextRanges, () => {
  editor.value?.view.dispatch(editor.value.state.tr.setMeta('helpSelection', true))
}, { deep: true })

const newId = () =>
  globalThis.crypto?.randomUUID?.() ??
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (token) => {
    const random = Math.floor(Math.random() * 16)
    return (token === 'x' ? random : (random & 0x3) | 0x8).toString(16)
  })
const attributes = (type: EditType | 'insertion', color?: string) => ({ editId: newId(), editType: type, createdAt: new Date().toISOString(), updatedAt: null, color: color ?? null })

const applyFormat = (mark: TaskEditMarkName, type: EditType, color?: string) => {
  const notes = notesActive.value ? props.notes : null
  const name = NOTES_MARKS[mark]
  if (notes && name) {
    const chain = notes.chain().focus()
    if (name === 'textStyle') chain.setColor(color ?? '').run()
    else chain.toggleMark(name, name === 'highlight' ? { color } : undefined).run()
    return
  }
  if (!editor.value || !hasSelection.value) return
  toggleTaskEditMark(editor.value, mark, attributes(type, color))
}

const isFormatActive = (mark: TaskEditMarkName) => {
  selectionTick.value
  const name = NOTES_MARKS[mark]
  if (notesActive.value && props.notes && name) return props.notes.isActive(name)
  return Boolean(editor.value?.isActive(mark))
}

const openInsertion = () => {
  if (!editor.value || !canAddComment.value) return
  insertionText.value = ''
  const { state, view } = editor.value
  view.dispatch(state.tr.setMeta(commentComposerKey, state.selection.from))
  view.dom.querySelector<HTMLInputElement>('[data-task-comment-input]')?.focus()
}
const closeInsertion = (restoreFocus = true) => {
  if (!editor.value) return
  const position = commentComposerKey.getState(editor.value.state)
  if (position == null) return
  editor.value.view.dispatch(editor.value.state.tr.setMeta(commentComposerKey, null))
  insertionText.value = ''
  if (restoreFocus) editor.value.chain().setTextSelection(position).focus().run()
}

function createCommentComposer() {
  const container = document.createElement('span')
  container.className = 'task-comment-composer'
  container.dataset.taskCommentComposer = ''
  container.contentEditable = 'false'
  container.setAttribute('role', 'group')
  container.setAttribute('aria-label', 'Add comment')
  const input = document.createElement('input')
  input.dataset.taskCommentInput = ''
  input.setAttribute('aria-label', 'Comment')
  input.placeholder = 'Comment here…'
  input.maxLength = 4000
  input.value = insertionText.value
  const add = document.createElement('button')
  add.type = 'button'
  add.textContent = 'Add'
  add.disabled = !input.value.trim()
  const cancel = document.createElement('button')
  cancel.type = 'button'
  cancel.textContent = '×'
  cancel.title = 'Cancel comment'
  cancel.setAttribute('aria-label', 'Cancel comment')
  input.addEventListener('input', () => {
    insertionText.value = input.value
    add.disabled = !input.value.trim()
  })
  input.addEventListener('keydown', (event) => {
    if (event.isComposing || !['Enter', 'Escape'].includes(event.key)) return
    event.preventDefault()
    event.stopPropagation()
    if (event.key === 'Escape') closeInsertion()
    else insertText()
  })
  add.addEventListener('click', () => insertText())
  cancel.addEventListener('click', () => closeInsertion())
  container.append(input, add, cancel)
  return container
}

const insertText = () => {
  if (!editor.value || props.mode !== 'edit' || !insertionText.value.trim()) return
  const position = commentComposerKey.getState(editor.value.state)
  if (position == null) return
  editor.value
    .chain()
    .setMeta(commentComposerKey, null)
    .setTextSelection(position)
    .insertContent({ type: 'text', text: insertionText.value, marks: [{ type: 'taskEditInsertion', attrs: attributes('insertion') }] })
    .focus()
    .run()
  insertionText.value = ''
}

watch(
  () => props.mode,
  (mode) => {
    closeInsertion(false)
    cursorActive.value = false
    editor.value?.setEditable(mode === 'edit')
  }
)
watch(
  () => [props.baseHtml, props.baseDocument] as const,
  ([html, document]) => {
    closeInsertion(false)
    const parser = new CoreEditor({ content: document ?? html, editable: false, extensions: baseExtensions })
    originalDocument = cloneTaskDocument(parser.getJSON() as JsonObject)
    parser.destroy()
    if (props.modelValue === null && editor.value) {
      lastDocument = JSON.stringify(originalDocument)
      if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.chain().setMeta('addToHistory', false).setContent(originalDocument, { emitUpdate: false }).run()
    }
  }
)
watch(
  () => props.modelValue,
  (document) => {
    if (!editor.value) return
    const next = document ?? originalDocument
    lastDocument = JSON.stringify(next)
    if (JSON.stringify(editor.value.getJSON()) !== lastDocument) editor.value.chain().setMeta('addToHistory', false).setContent(next, { emitUpdate: false }).run()
  },
  { deep: true }
)

const onTaskReferenceClick = (event: MouseEvent) => {
  if (event.target instanceof Element && event.target.closest('[data-task-comment-composer]')) return
  if (props.mode !== 'help' && editor.value) {
    const view = editor.value.view
    const selection = view.dom.ownerDocument.getSelection()
    let selected: string[]
    if (selection && !selection.isCollapsed && selection.anchorNode && selection.focusNode && view.dom.contains(selection.anchorNode) && view.dom.contains(selection.focusNode)) {
      const anchor = view.posAtDOM(selection.anchorNode, selection.anchorOffset)
      const focus = view.posAtDOM(selection.focusNode, selection.focusOffset)
      selected = emitSelectedEdits(editor.value, { from: Math.min(anchor, focus), to: Math.max(anchor, focus) })
    }
    else {
      const ids = new Set<string>()
      let target = event.target instanceof Element ? event.target : null
      while (target && editor.value.view.dom.contains(target)) {
        const id = target.getAttribute('data-task-edit-id')
        if (id) ids.add(id)
        target = target.parentElement
      }
      selected = [...ids]
      emit('select-edits', selected)
    }
    flashTaskEdits(view.dom, selected)
  }
  if (props.mode !== 'read') return
  const reference = readTaskConnectionReference(event.target)
  if (reference) emit('select-connection', reference)
}

type ReferencePreview = { kind: 'element'; option: TaskElementOption; x: number; y: number } | { kind: 'connection'; option: TaskConnectionOption; x: number; y: number }

const referencePreview = ref<ReferencePreview | null>(null)
const hideReferencePreview = () => {
  referencePreview.value = null
}
const onTaskReferenceMouseOver = (event: MouseEvent) => {
  if (props.mode === 'help') return
  const target = event.target as Element | null
  const elementMark = target?.closest('[data-task-element-language-id][data-task-element-type]')
  const connectionMark = target?.closest('[data-task-connection-language-id][data-task-connection-type]')

  if (elementMark) {
    const option = props.elementOptions.find((item) => item.languageId === elementMark.getAttribute('data-task-element-language-id') && item.elementType === elementMark.getAttribute('data-task-element-type'))
    referencePreview.value = option ? { kind: 'element', option, x: event.clientX + 14, y: event.clientY + 14 } : null
    return
  }

  if (connectionMark) {
    const option = props.connectionOptions.find((item) => item.languageId === connectionMark.getAttribute('data-task-connection-language-id') && item.connectionType === connectionMark.getAttribute('data-task-connection-type'))
    referencePreview.value = option ? { kind: 'connection', option, x: event.clientX + 14, y: event.clientY + 14 } : null
    return
  }

  hideReferencePreview()
}

const onDragStart = (event: DragEvent) => {
  if (props.mode !== 'read') return event.preventDefault()
  writeTaskElementDragData(event)
}

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.help-text-toolbar { background: #fff4d8; border-bottom: 1px solid #dbb970; }
:deep(.help-text-mark) { background: #ffe08a; box-shadow: 0 1px 0 #b68026; border-radius: 2px; }
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
.task-comment-action { display: inline-flex; }
.task-edit-body :deep(.task-comment-composer) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  margin: 2px 4px;
  padding: 4px;
  border: 2px solid rgb(var(--v-theme-primary));
  border-radius: 6px;
  background: rgb(var(--v-theme-surface));
  font: 400 13px/1.4 sans-serif;
  vertical-align: middle;
}
.task-edit-body :deep(.task-comment-composer input) {
  width: 160px;
  min-width: 0;
  padding: 4px;
  outline: none;
  color: rgb(var(--v-theme-on-surface));
}
.task-edit-body :deep(.task-comment-composer button) {
  padding: 3px 6px;
  border-radius: 4px;
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
  cursor: pointer;
}
.task-edit-body :deep(.task-comment-composer button:disabled) { opacity: 0.4; cursor: default; }
.task-edit-body :deep(.task-comment-composer button:focus-visible) { outline: 2px solid currentColor; }
.task-edit-body :deep(.ProseMirror) {
  min-height: 120px;
  height: 100%;
  padding: 12px 16px;
  outline: none;
  font-size: 14px;
  line-height: 1.6;
  color: #212121;
}
.task-edit-body :deep(.ProseMirror ul) {
  padding-left: 24px;
}
.task-edit-body :deep(.task-element-mark) {
  border-bottom: 2px solid rgb(var(--v-theme-primary));
  cursor: grab;
}
.task-edit-body :deep(.task-connection-mark) {
  border-bottom: 2px dashed rgb(var(--v-theme-secondary));
  cursor: pointer;
}
.task-reference-preview {
  position: fixed;
  z-index: 1000;
  width: 220px;
  padding: 10px;
  border: 1px solid rgba(var(--v-theme-primary), 0.3);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.2);
  pointer-events: none;
}
.task-reference-preview__kind {
  color: rgb(var(--v-theme-primary));
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}
.task-reference-preview__title {
  margin: 2px 0 6px;
  font-size: 13px;
  font-weight: 600;
}
.task-reference-preview__diagram {
  display: block;
  width: 100%;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 4px;
}
.task-reference-preview__hint {
  margin-top: 7px;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 11px;
  line-height: 1.35;
}
</style>
