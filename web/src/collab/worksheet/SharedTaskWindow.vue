<template>
  <div v-if="content" class="shared-task-window">
    <TaskEditEditor :base-html="content.contentHtml" :model-value="sharedTaskEdit?.document ?? null" mode="edit" shared :history="content.history" :notes="content.notes" :element-options="elementOptions" :connection-options="connectionOptions" @select-connection="emit('select-connection', $event)" @select-edits="emit('select-edits', $event)" @update:model-value="writeSharedTask?.($event)" />
    <!-- In a group room: the notes below the text, as in the bar. -->
    <SharedNotes v-if="content.notes" :editor="content.notes" />
  </div>
</template>

<script setup lang="ts">
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import type { TaskConnectionOption, TaskElementOption } from '@/components/tasks/taskEditorExtensions'
import SharedNotes from './SharedNotes.vue'
import { sharedTaskContent as content, sharedTaskEdit, writeSharedTask } from './sharedTask'

/** The task of a room in the floating window: the text with its marks and, in a group room, the notes below. */
withDefaults(defineProps<{ elementOptions?: TaskElementOption[]; connectionOptions?: TaskConnectionOption[] }>(), { elementOptions: () => [], connectionOptions: () => [] })

const emit = defineEmits<{
  'select-connection': [reference: { languageId: string; connectionType: string }]
  'select-edits': [ids: string[]]
}>()
</script>
