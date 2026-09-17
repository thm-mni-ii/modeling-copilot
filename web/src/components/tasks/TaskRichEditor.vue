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

      <!-- Text styles and headings -->
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

      <!-- Inline formatting -->
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

      <TaskColorPicker class="mr-1" title="Text color" icon="mdi-format-color-text" :colors="TASK_TEXT_COLORS" :indicator-color="activeColor ?? '#616161'" allow-reset @select="applyTextColor" @reset="editor.chain().focus().unsetColor().run()" />

      <TaskColorPicker class="mr-1" title="Highlight color" icon="mdi-marker" :colors="TASK_HIGHLIGHT_COLORS" :indicator-color="activeHighlightColor ?? '#e0e0e0'" allow-reset reset-title="Remove highlight" @select="applyHighlight" @reset="editor.chain().focus().unsetHighlight().run()" />

      <v-divider vertical class="mx-1" />

      <!-- Alignment -->
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

      <!-- Lists -->
      <v-btn-group size="x-small" density="compact" variant="outlined" class="mr-1">
        <v-btn :color="editor.isActive('bulletList') ? 'primary' : undefined" title="Bulleted list" @click="editor.chain().focus().toggleBulletList().run()">
          <v-icon>mdi-format-list-bulleted</v-icon>
        </v-btn>
        <v-btn :color="editor.isActive('orderedList') ? 'primary' : undefined" title="Numbered list" @click="editor.chain().focus().toggleOrderedList().run()">
          <v-icon>mdi-format-list-numbered</v-icon>
        </v-btn>
      </v-btn-group>

      <v-divider vertical class="mx-1" />

      <!-- Code, quote, and separator -->
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
        <v-menu location="bottom end" :close-on-content-click="false" max-width="360">
          <template #activator="{ props: menuProps }">
            <v-btn v-bind="menuProps" size="small" variant="outlined" title="Link selected task text">
              <v-icon>mdi-link-variant</v-icon>
            </v-btn>
          </template>
          <v-card class="task-link-menu pa-3">
            <div v-if="props.elementOptions.length > 0" class="task-link-menu__section">
              <div class="text-caption font-weight-medium mb-1">Model element</div>
              <div class="d-flex ga-1 align-center">
                <v-select v-model="selectedElementKey" :items="elementSelectItems" label="Element" density="compact" variant="outlined" hide-details />
                <v-btn size="small" variant="tonal" color="primary" :disabled="!selectedElement" title="Apply element link" @click="applyElementLink"><v-icon>mdi-link-plus</v-icon></v-btn>
                <v-btn size="small" variant="text" title="Remove current element link" @click="removeElementLink"><v-icon>mdi-link-variant-off</v-icon></v-btn>
              </div>
            </div>
            <div v-if="props.connectionOptions.length > 0" class="task-link-menu__section">
              <div class="text-caption font-weight-medium mb-1">Connection</div>
              <div class="d-flex ga-1 align-center">
                <v-select v-model="selectedConnectionKey" :items="connectionSelectItems" label="Connection" density="compact" variant="outlined" hide-details />
                <v-btn size="small" variant="tonal" color="primary" :disabled="!selectedConnection" title="Apply connection link" @click="applyConnectionLink"><v-icon>mdi-link-plus</v-icon></v-btn>
                <v-btn size="small" variant="text" title="Remove current connection link" @click="removeConnectionLink"><v-icon>mdi-link-variant-off</v-icon></v-btn>
              </div>
            </div>
          </v-card>
        </v-menu>
        <v-chip v-if="activeReferenceLabel" size="small" color="primary" variant="tonal" class="active-reference-chip" prepend-icon="mdi-link-variant"> Selected: {{ activeReferenceLabel }} </v-chip>
      </template>
    </div>

    <!-- Editable content -->
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
import type { Editor } from '@tiptap/core'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'
import TaskColorPicker from './TaskColorPicker.vue'
import { createTaskEditorExtensions, readTaskConnectionReference, TASK_HIGHLIGHT_COLORS, TASK_TEXT_COLORS, writeTaskElementDragData, type TaskConnectionOption, type TaskElementOption } from './taskEditorExtensions'

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
  extensions: createTaskEditorExtensions(props.placeholder),
  onUpdate: ({ editor: e }) => {
    emit('update:modelValue', e.getHTML())
  },
  onSelectionUpdate: ({ editor: e }) => {
    syncLinkControls(e)
  }
})

// Keep the editor in sync when the selected task changes.
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
  const reference = readTaskConnectionReference(target)
  if (reference) emit('select-connection', reference)
}

type ReferencePreview = { kind: 'element'; option: TaskElementOption; x: number; y: number } | { kind: 'connection'; option: TaskConnectionOption; x: number; y: number }

const referencePreview = ref<ReferencePreview | null>(null)
const hideReferencePreview = () => {
  referencePreview.value = null
}
const onTaskReferenceMouseOver = (event: MouseEvent) => {
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
  writeTaskElementDragData(event)
}

const applyTextColor = (color: string) => {
  editor.value?.chain().focus().setColor(color).run()
}

const applyHighlight = (color: string) => {
  editor.value?.chain().focus().setHighlight({ color }).run()
}
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

.task-link-menu {
  width: min(360px, calc(100vw - 32px));
}
.task-link-menu__section + .task-link-menu__section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.16);
}
.task-link-menu :deep(.v-select) {
  min-width: 0;
  flex: 1;
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
</style>
