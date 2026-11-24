<template>
  <div class="shared-notes">
    <!-- A labeled divider instead of a bar of their own; formatting goes through the bar of the text. -->
    <div class="shared-notes__divider">
      <v-icon size="14">mdi-note-text-outline</v-icon>
      <span>Notes</span>
    </div>
    <editor-content :editor="editor" class="shared-notes__body" />
  </div>
</template>

<script setup lang="ts">
import type { Editor } from '@tiptap/core'
import { EditorContent } from '@tiptap/vue-3'

/** The notes of a group room below the task, in the bar or in the floating window; an editor shows in one place only. */
defineProps<{ editor: Editor | undefined }>()
</script>

<style scoped>
.shared-notes {
  padding: 4px 16px 12px;
}
.shared-notes__divider {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.6);
}
.shared-notes__divider::before,
.shared-notes__divider::after {
  content: '';
  flex: 1;
  border-top: 1px solid rgba(0, 0, 0, 0.12);
}
.shared-notes__body :deep(.ProseMirror) {
  min-height: 80px;
  padding: 8px 12px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 6px;
  outline: none;
  font-size: 14px;
  line-height: 1.6;
}
.shared-notes__body :deep(.ProseMirror ul) {
  padding-left: 24px;
}
.shared-notes__body :deep(.ProseMirror-focused) {
  border-color: rgb(var(--v-theme-primary));
}
.shared-notes__body :deep(.ProseMirror p.is-editor-empty:first-child::before) {
  content: attr(data-placeholder);
  float: left;
  height: 0;
  color: rgba(0, 0, 0, 0.38);
  pointer-events: none;
}
</style>
