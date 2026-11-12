<template>
  <div v-if="content" class="shared-task-window">
    <TaskEditEditor :base-html="content.contentHtml" :model-value="sharedTaskEdit?.document ?? null" mode="edit" shared :history="content.history" :notes="content.notes" :element-options="elementOptions" :connection-options="connectionOptions" @select-connection="emit('select-connection', $event)" @select-edits="emit('select-edits', $event)" @update:model-value="writeSharedTask?.($event)" />
    <!-- Im Gruppenraum: die Notizen unter dem Text, wie in der Leiste. -->
    <div v-if="content.notes" class="shared-task-window__notes">
      <div class="shared-task-window__divider">
        <v-icon size="14">mdi-note-text-outline</v-icon>
        <span>Notes</span>
      </div>
      <editor-content :editor="content.notes" class="shared-task-window__notes-body" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { EditorContent } from '@tiptap/vue-3'
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import type { TaskConnectionOption, TaskElementOption } from '@/components/tasks/taskEditorExtensions'
import { sharedTaskContent as content, sharedTaskEdit, writeSharedTask } from './sharedTask'

/** The task of a room in the floating window: the text with its marks and, in a group room, the notes below. */
withDefaults(defineProps<{ elementOptions?: TaskElementOption[]; connectionOptions?: TaskConnectionOption[] }>(), { elementOptions: () => [], connectionOptions: () => [] })

const emit = defineEmits<{
  'select-connection': [reference: { languageId: string; connectionType: string }]
  'select-edits': [ids: string[]]
}>()
</script>

<style scoped>
.shared-task-window__notes {
  padding: 4px 16px 12px;
}
.shared-task-window__divider {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.6);
}
.shared-task-window__divider::before,
.shared-task-window__divider::after {
  content: '';
  flex: 1;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}
.shared-task-window__notes-body :deep(.ProseMirror) {
  min-height: 80px;
  padding: 8px 12px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  outline: none;
  font-size: 14px;
  line-height: 1.6;
}
.shared-task-window__notes-body :deep(.ProseMirror ul) {
  padding-left: 24px;
}
.shared-task-window__notes-body :deep(.ProseMirror-focused) {
  border-color: rgb(var(--v-theme-primary));
}
.shared-task-window__notes-body :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  height: 0;
  color: rgba(0, 0, 0, 0.38);
  pointer-events: none;
}
</style>
