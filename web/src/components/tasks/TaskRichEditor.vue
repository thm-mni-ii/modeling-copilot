<template>
  <div class="task-rich-editor">
    <!-- Toolbar -->
    <div v-if="editor && !props.readonly" class="editor-toolbar">
      <!-- Undo / Redo -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :disabled="!editor.can().undo()" title="Undo" @click="editor.chain().focus().undo().run()">
          <v-icon>mdi-undo</v-icon>
        </v-btn>
        <v-btn :disabled="!editor.can().redo()" title="Redo" @click="editor.chain().focus().redo().run()">
          <v-icon>mdi-redo</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Schriftart / Überschriften -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :color="editor.isActive('heading', { level: 1 }) ? 'primary' : undefined" title="Heading 1" @click="editor.chain().focus().toggleHeading({ level: 1 }).run()">
          <v-icon>mdi-format-header-1</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('heading', { level: 2 }) ? 'primary' : undefined" title="Heading 2" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()">
          <v-icon>mdi-format-header-2</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('heading', { level: 3 }) ? 'primary' : undefined" title="Heading 3" @click="editor.chain().focus().toggleHeading({ level: 3 }).run()">
          <v-icon>mdi-format-header-3</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('paragraph') ? 'primary' : undefined" title="Paragraph" @click="editor.chain().focus().setParagraph().run()">
          <v-icon>mdi-format-paragraph</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Fettschrift, kursiv, unterstrichen, durchgestrichen -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :color="editor.isActive('bold') ? 'primary' : undefined" title="Bold (Ctrl+B)" @click="editor.chain().focus().toggleBold().run()">
          <v-icon>mdi-format-bold</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('italic') ? 'primary' : undefined" title="Italic (Ctrl+I)" @click="editor.chain().focus().toggleItalic().run()">
          <v-icon>mdi-format-italic</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('underline') ? 'primary' : undefined" title="Underline (Ctrl+U)" @click="editor.chain().focus().toggleUnderline().run()">
          <v-icon>mdi-format-underline</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('strike') ? 'primary' : undefined" title="Strikethrough" @click="editor.chain().focus().toggleStrike().run()">
          <v-icon>mdi-format-strikethrough</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Textfarbe -->
      <v-menu :close-on-content-click="false" location="bottom">
        <template #activator="{ props: menuProps }">
          <v-btn size="small" variant="outlined" title="Text color" class="mr-1" v-bind="menuProps">
            <span class="toolbar-color-indicator">
              A
              <span class="toolbar-color-dot" :style="{ backgroundColor: activeColor ?? '#616161' }"></span>
            </span>
          </v-btn>
        </template>
        <v-card class="pa-2 color-picker-card">
          <div class="color-swatches">
            <button v-for="color in textColors" :key="color.value" class="color-swatch" :style="{ background: color.value }" :title="color.label" @click="applyTextColor(color.value)" />
            <button class="color-swatch color-swatch--reset" title="Reset color" @click="editor.chain().focus().unsetColor().run()">
              <v-icon size="14">mdi-close</v-icon>
            </button>
          </div>
        </v-card>
      </v-menu>

      <!-- Hervorhebung -->
      <v-menu :close-on-content-click="false" location="bottom">
        <template #activator="{ props: menuProps }">
          <v-btn size="small" variant="outlined" title="Highlight color" class="mr-1" v-bind="menuProps">
            <span class="toolbar-highlight-indicator">
              <v-icon size="14">mdi-marker</v-icon>
              <span class="toolbar-highlight-dot" :style="{ backgroundColor: activeHighlightColor ?? '#e0e0e0' }"></span>
            </span>
          </v-btn>
        </template>
        <v-card class="pa-2 color-picker-card">
          <div class="color-swatches">
            <button v-for="color in highlightColors" :key="color.value" class="color-swatch" :style="{ background: color.value }" :title="color.label" @click="applyHighlight(color.value)" />
            <button class="color-swatch color-swatch--reset" title="Remove highlight" @click="editor.chain().focus().unsetHighlight().run()">
              <v-icon size="14">mdi-close</v-icon>
            </button>
          </div>
        </v-card>
      </v-menu>

      <v-divider vertical class="mx-1" />

      <!-- Ausrichtung -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :color="editor.isActive({ textAlign: 'left' }) ? 'primary' : undefined" title="Align left" @click="editor.chain().focus().setTextAlign('left').run()">
          <v-icon>mdi-format-align-left</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive({ textAlign: 'center' }) ? 'primary' : undefined" title="Center" @click="editor.chain().focus().setTextAlign('center').run()">
          <v-icon>mdi-format-align-center</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive({ textAlign: 'right' }) ? 'primary' : undefined" title="Align right" @click="editor.chain().focus().setTextAlign('right').run()">
          <v-icon>mdi-format-align-right</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive({ textAlign: 'justify' }) ? 'primary' : undefined" title="Justify" @click="editor.chain().focus().setTextAlign('justify').run()">
          <v-icon>mdi-format-align-justify</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Listen -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :color="editor.isActive('bulletList') ? 'primary' : undefined" title="Bulleted list" @click="editor.chain().focus().toggleBulletList().run()">
          <v-icon>mdi-format-list-bulleted</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('orderedList') ? 'primary' : undefined" title="Numbered list" @click="editor.chain().focus().toggleOrderedList().run()">
          <v-icon>mdi-format-list-numbered</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Code / Blockquote / Trennlinie -->
      <v-btn-group size="x-small" density="compact" variant="outlined">
        <v-btn :color="editor.isActive('code') ? 'primary' : undefined" title="Code (Inline)" @click="editor.chain().focus().toggleCode().run()">
          <v-icon>mdi-code-tags</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('blockquote') ? 'primary' : undefined" title="Quote" @click="editor.chain().focus().toggleBlockquote().run()">
          <v-icon>mdi-format-quote-open</v-icon>
        </v-btn>
        <v-btn title="Horizontal line" @click="editor.chain().focus().setHorizontalRule().run()">
          <v-icon>mdi-minus</v-icon>
        </v-btn>
      </v-btn-group>

      <template v-if="props.elementOptions.length > 0 || props.connectionOptions.length > 0">
        <v-divider vertical class="mx-1" />
        <template v-if="props.elementOptions.length > 0">
          <v-select v-model="selectedElementKey" :items="elementSelectItems" label="Link model element" density="compact" variant="outlined" hide-details class="element-link-select" />
          <v-btn size="small" variant="outlined" :disabled="!selectedElement" title="Link selected text to model element" @click="applyElementLink">
            <v-icon>mdi-link-variant</v-icon>
          </v-btn>
          <v-btn size="small" variant="outlined" title="Remove element link" @click="removeElementLink">
            <v-icon>mdi-link-variant-off</v-icon>
          </v-btn>
        </template>
        <template v-if="props.connectionOptions.length > 0">
          <v-select v-model="selectedConnectionKey" :items="connectionSelectItems" label="Link connection" density="compact" variant="outlined" hide-details class="element-link-select" />
          <v-btn size="small" variant="outlined" :disabled="!selectedConnection" title="Link selected text to connection" @click="applyConnectionLink">
            <v-icon>mdi-connection</v-icon>
          </v-btn>
          <v-btn size="small" variant="outlined" title="Remove connection link" @click="removeConnectionLink">
            <v-icon>mdi-link-variant-off</v-icon>
          </v-btn>
        </template>
        <v-chip v-if="activeReferenceLabel" size="small" color="primary" variant="tonal" class="active-reference-chip" prepend-icon="mdi-link-variant">
          Selected: {{ activeReferenceLabel }}
        </v-chip>
      </template>
    </div>

    <!-- Editierbarer Bereich -->
    <editor-content :editor="editor" class="editor-body" @click="onTaskReferenceClick" @dragstart="onDragStart" @mouseleave="hideReferencePreview" @mouseover="onTaskReferenceMouseOver" />
    <div v-if="referencePreview" class="task-reference-preview" :style="{ left: `${referencePreview.x}px`, top: `${referencePreview.y}px` }">
      <div class="task-reference-preview__kind">{{ referencePreview.kind === 'element' ? 'Model element' : 'Connection' }}</div>
      <div class="task-reference-preview__title">{{ referencePreview.option.label }}</div>
      <DiagramPreviewItem v-if="referencePreview.kind === 'element' && referencePreview.option.element" :element="referencePreview.option.element" :width="180" :height="92" class="task-reference-preview__diagram" />
      <ConnectionPreviewItem v-else-if="referencePreview.kind === 'connection' && referencePreview.option.connection" :connection="referencePreview.option.connection" :width="180" :height="56" class="task-reference-preview__diagram" />
      <div class="task-reference-preview__hint">{{ referencePreview.kind === 'element' ? 'Drag into the canvas to create this element.' : 'Click to select this connection in the canvas.' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Mark, mergeAttributes, type Editor } from '@tiptap/core'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import { TextStyle } from '@tiptap/extension-text-style'
import { Color } from '@tiptap/extension-color'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'
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

const TaskElementMark = Mark.create({
  name: 'taskElement',
  addAttributes() {
    return {
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
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-task-element-language-id][data-task-element-type]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes, { class: 'task-element-mark', draggable: 'true' }), 0]
  }
})

const TaskConnectionMark = Mark.create({
  name: 'taskConnection',
  addAttributes() {
    return {
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
    }
  },
  parseHTML() {
    return [{ tag: 'span[data-task-connection-language-id][data-task-connection-type]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes, { class: 'task-connection-mark' }), 0]
  }
})

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    readonly?: boolean
    elementOptions?: TaskElementOption[]
    connectionOptions?: TaskConnectionOption[]
  }>(),
  {
    placeholder: 'Enter task text here…',
    readonly: false,
    elementOptions: () => [],
    connectionOptions: () => []
  }
)

const emit = defineEmits<{
  'update:modelValue': [string]
  'select-connection': [reference: { languageId: string; connectionType: string }]
}>()

const editor = useEditor({
  content: props.modelValue,
  editable: !props.readonly,
  extensions: [StarterKit.configure({ underline: false }), TextStyle, Color, Underline, TextAlign.configure({ types: ['heading', 'paragraph'] }), Highlight.configure({ multicolor: true }), Placeholder.configure({ placeholder: props.placeholder }), TaskElementMark, TaskConnectionMark],
  onUpdate: ({ editor: e }) => {
    emit('update:modelValue', e.getHTML())
  },
  onSelectionUpdate: ({ editor: e }) => {
    syncLinkControls(e)
  }
})

// Sync externen Wert in Editor (z. B. bei Aufgabenwechsel)
watch(
  () => props.modelValue,
  (newValue) => {
    if (!editor.value) return
    const currentHtml = editor.value.getHTML()
    if (newValue !== currentHtml) {
      editor.value.commands.setContent(newValue, false)
    }
  }
)

watch(
  () => props.readonly,
  (value) => {
    editor.value?.setEditable(!value)
  }
)

onBeforeUnmount(() => {
  editor.value?.destroy()
})

const activeColor = computed(() => {
  const attrs = editor.value?.getAttributes('textStyle')
  return (attrs?.color as string | undefined) ?? undefined
})

const activeHighlightColor = computed(() => {
  const attrs = editor.value?.getAttributes('highlight')
  return (attrs?.color as string | undefined) ?? undefined
})

const selectedElementKey = ref('')
const elementSelectItems = computed(() => props.elementOptions.map((option) => ({ title: option.label, value: `${option.languageId}:${option.elementType}` })))
const selectedElement = computed(() => props.elementOptions.find((option) => `${option.languageId}:${option.elementType}` === selectedElementKey.value) ?? null)

const selectedConnectionKey = ref('')
const connectionSelectItems = computed(() => props.connectionOptions.map((option) => ({ title: option.label, value: `${option.languageId}:${option.connectionType}` })))
const selectedConnection = computed(() => props.connectionOptions.find((option) => `${option.languageId}:${option.connectionType}` === selectedConnectionKey.value) ?? null)
const activeReferenceKind = ref<'element' | 'connection' | null>(null)
const activeReferenceLabel = computed(() => {
  if (activeReferenceKind.value === 'element') return selectedElement.value?.label ?? 'Linked model element'
  if (activeReferenceKind.value === 'connection') return selectedConnection.value?.label ?? 'Linked connection'
  return null
})

const syncLinkControls = (currentEditor: Editor) => {
  const elementAttributes = currentEditor.getAttributes('taskElement') as { languageId?: string; elementType?: string }
  if (elementAttributes.languageId && elementAttributes.elementType) {
    selectedElementKey.value = `${elementAttributes.languageId}:${elementAttributes.elementType}`
    activeReferenceKind.value = 'element'
    return
  }
  const connectionAttributes = currentEditor.getAttributes('taskConnection') as { languageId?: string; connectionType?: string }
  if (connectionAttributes.languageId && connectionAttributes.connectionType) {
    selectedConnectionKey.value = `${connectionAttributes.languageId}:${connectionAttributes.connectionType}`
    activeReferenceKind.value = 'connection'
    return
  }
  activeReferenceKind.value = null
}

const applyElementLink = () => {
  if (!selectedElement.value) return
  const chain = editor.value?.chain().focus()
  if (!chain) return
  if (editor.value?.isActive('taskElement')) chain.extendMarkRange('taskElement')
  chain.setMark('taskElement', { languageId: selectedElement.value.languageId, elementType: selectedElement.value.elementType }).run()
}

const removeElementLink = () => {
  const chain = editor.value?.chain().focus()
  if (!chain) return
  if (editor.value?.isActive('taskElement')) chain.extendMarkRange('taskElement')
  chain.unsetMark('taskElement').run()
}

const applyConnectionLink = () => {
  if (!selectedConnection.value) return
  const chain = editor.value?.chain().focus()
  if (!chain) return
  if (editor.value?.isActive('taskConnection')) chain.extendMarkRange('taskConnection')
  chain.setMark('taskConnection', { languageId: selectedConnection.value.languageId, connectionType: selectedConnection.value.connectionType }).run()
}
const removeConnectionLink = () => {
  const chain = editor.value?.chain().focus()
  if (!chain) return
  if (editor.value?.isActive('taskConnection')) chain.extendMarkRange('taskConnection')
  chain.unsetMark('taskConnection').run()
}

const onTaskReferenceClick = (event: MouseEvent) => {
  const target = event.target as Element | null
  if (!props.readonly) {
    if (editor.value) syncLinkControls(editor.value)
    return
  }
  const mark = target?.closest('[data-task-connection-language-id][data-task-connection-type]')
  const languageId = mark?.getAttribute('data-task-connection-language-id')
  const connectionType = mark?.getAttribute('data-task-connection-type')
  if (!languageId || !connectionType) return
  emit('select-connection', { languageId, connectionType })
}

type ReferencePreview =
  | { kind: 'element'; option: TaskElementOption; x: number; y: number }
  | { kind: 'connection'; option: TaskConnectionOption; x: number; y: number }

const referencePreview = ref<ReferencePreview | null>(null)
const hideReferencePreview = () => {
  referencePreview.value = null
}
const onTaskReferenceMouseOver = (event: MouseEvent) => {
  if (!props.readonly) return
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
  const target = event.target as Element | null
  const mark = target?.closest('[data-task-element-language-id][data-task-element-type]')
  const elementType = mark?.getAttribute('data-task-element-type')
  if (!elementType || !event.dataTransfer) return
  event.dataTransfer.setData('text/plain', elementType)
  event.dataTransfer.setData(
    'application/x-modeling-task-element',
    JSON.stringify({
      languageId: mark?.getAttribute('data-task-element-language-id'),
      elementType,
      label: mark?.textContent?.trim() || undefined
    })
  )
  event.dataTransfer.effectAllowed = 'copy'
}

const applyTextColor = (color: string) => {
  editor.value?.chain().focus().setColor(color).run()
}

const applyHighlight = (color: string) => {
  editor.value?.chain().focus().setHighlight({ color }).run()
}

const textColors = [
  { label: 'Black', value: '#000000' },
  { label: 'Dark Gray', value: '#424242' },
  { label: 'Red', value: '#E53935' },
  { label: 'Pink', value: '#D81B60' },
  { label: 'Purple', value: '#8E24AA' },
  { label: 'Blue', value: '#1E88E5' },
  { label: 'Cyan', value: '#00ACC1' },
  { label: 'Green', value: '#43A047' },
  { label: 'Orange', value: '#FB8C00' },
  { label: 'Yellow', value: '#FDD835' }
]

const highlightColors = [
  { label: 'Yellow', value: '#FFF176' },
  { label: 'Green', value: '#C8E6C9' },
  { label: 'Blue', value: '#BBDEFB' },
  { label: 'Pink', value: '#F8BBD0' },
  { label: 'Orange', value: '#FFE0B2' },
  { label: 'Purple', value: '#E1BEE7' }
]
</script>

<style scoped>
.task-rich-editor {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(0, 0, 0, 0.23);
  border-radius: 4px;
  overflow: hidden;
  background: #fff;
  flex: 1;
  min-height: 0;
}

.editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  background: #f5f5f5;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.editor-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
}

/* TipTap ProseMirror contenteditable area */
.editor-body :deep(.ProseMirror) {
  min-height: 200px;
  height: 100%;
  padding: 12px 16px;
  outline: none;
  font-size: 14px;
  line-height: 1.6;
  color: #212121;
}

.editor-body :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  color: #aaa;
  pointer-events: none;
  height: 0;
}

.editor-body :deep(.ProseMirror h1) {
  font-size: 1.6em;
  font-weight: 700;
  margin: 0.6em 0 0.3em;
}

.editor-body :deep(.ProseMirror h2) {
  font-size: 1.35em;
  font-weight: 600;
  margin: 0.6em 0 0.3em;
}

.editor-body :deep(.ProseMirror h3) {
  font-size: 1.15em;
  font-weight: 600;
  margin: 0.6em 0 0.3em;
}

.editor-body :deep(.ProseMirror blockquote) {
  border-left: 3px solid #1976d2;
  margin: 0;
  padding-left: 12px;
  color: #555;
}

.editor-body :deep(.ProseMirror code) {
  background: #f0f0f0;
  border-radius: 3px;
  padding: 1px 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.editor-body :deep(.ProseMirror ul),
.editor-body :deep(.ProseMirror ol) {
  padding-left: 1.5em;
}

.editor-body :deep(.ProseMirror hr) {
  border: none;
  border-top: 1px solid #ddd;
  margin: 12px 0;
}

.editor-body :deep(.ProseMirror mark) {
  border-radius: 2px;
  padding: 0 1px;
}

.element-link-select {
  width: 230px;
  min-width: 180px;
}

.editor-body :deep(.task-element-mark) {
  border-bottom: 2px solid rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.09);
  cursor: grab;
}

.editor-body :deep(.task-connection-mark) {
  border-bottom: 2px dashed rgb(var(--v-theme-secondary));
  background: rgba(var(--v-theme-secondary), 0.09);
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

.active-reference-chip {
  max-width: 280px;
}

.editor-body :deep(.task-element-mark:active) {
  cursor: grabbing;
}

.toolbar-color-indicator {
  display: inline-grid;
  align-items: center;
  justify-content: center;
  justify-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #212121;
  padding: 0;
  gap: 2px;
}

.toolbar-color-dot {
  width: 12px;
  height: 2px;
  border-radius: 999px;
}

.toolbar-highlight-indicator {
  display: inline-grid;
  align-items: center;
  justify-content: center;
  justify-items: center;
  gap: 2px;
}

.toolbar-highlight-dot {
  width: 12px;
  height: 2px;
  border-radius: 999px;
}

/* Farbpalette */
.color-picker-card {
  min-width: 160px;
}

.color-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.color-swatch {
  width: 22px;
  height: 22px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.2);
  cursor: pointer;
  transition: transform 0.1s;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.color-swatch:hover {
  transform: scale(1.2);
}

.color-swatch--reset {
  background: #fff;
  color: #333;
}
</style>
