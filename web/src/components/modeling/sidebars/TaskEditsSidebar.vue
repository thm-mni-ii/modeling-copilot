<template>
  <div class="task-edits-sidebar">
    <div class="task-edits-sidebar__filters">
      <v-btn-toggle v-model="filter" mandatory density="compact" divided variant="outlined">
        <v-btn value="all" size="x-small">All</v-btn>
        <v-btn value="format" size="x-small">Format</v-btn>
        <v-btn value="insertion" size="x-small">Text</v-btn>
      </v-btn-toggle>
      <v-chip size="x-small" color="primary" variant="tonal">{{ entries.length }}</v-chip>
      <v-chip size="x-small" :color="syncState === 'conflict' || syncState === 'offline' ? 'warning' : undefined" variant="tonal">{{ syncLabel }}</v-chip>
    </div>
    <div v-if="filteredEntries.length" class="task-edits-sidebar__list">
      <v-expansion-panels variant="accordion" multiple>
        <v-expansion-panel v-for="entry in filteredEntries" :key="entry.id">
          <v-expansion-panel-title>
            <div class="task-edit-title">
              <span v-if="entry.color" class="task-edit-color" :style="{ background: entry.color }" />
              <v-icon v-else size="16">{{ iconFor(entry.type) }}</v-icon>
              <div class="task-edit-title__text">
                <strong>{{ labelFor(entry.type) }}</strong
                ><span>{{ entry.fragments[0] || 'Edit' }}</span>
              </div>
              <v-chip v-if="entry.fragments.length > 1" size="x-small" variant="tonal">{{ entry.fragments.length }}</v-chip>
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div class="task-edit-fragments">
              <button v-for="(fragment, index) in entry.fragments" :key="`${entry.id}-${index}`" type="button" class="task-edit-fragment" @click="emit('focus-edit', entry.id)">{{ fragment }}</button>
            </div>
            <div class="task-edit-actions">
              <v-btn size="x-small" variant="text" prepend-icon="mdi-crosshairs-gps" @click="emit('focus-edit', entry.id)">Show</v-btn>
              <v-btn size="x-small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="requestRemoval(entry)">Remove</v-btn>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </div>
    <div v-else class="task-edits-sidebar__empty">Activate Edit mode in the task bar to add formatting or text.</div>

    <v-dialog v-model="confirmDialog" max-width="500">
      <v-card>
        <v-card-title>Remove Edit?</v-card-title>
        <v-card-text>This removes all {{ pendingEntry?.fragments.length ?? 0 }} fragment(s) belonging to this Edit. Other Edits remain unchanged.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="confirmDialog = false">Cancel</v-btn><v-btn color="error" @click="confirmRemoval">Remove Edit</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
import { cloneTaskDocument, collectTaskEdits, type TaskEditListEntry, type TaskEditSyncState, type TaskEditType } from '@/utils/taskEdits'
import { notifySuccess } from '@/composables/useNotifications'

const props = withDefaults(defineProps<{ taskEdit: TaskEditDocument | null; syncState?: TaskEditSyncState }>(), { syncState: 'synced' })
const emit = defineEmits<{
  'remove-edit': [id: string]
  'restore-document': [document: JsonObject]
  'focus-edit': [id: string]
}>()

const filter = ref<'all' | 'format' | 'insertion'>('all')
const entries = computed(() => collectTaskEdits(props.taskEdit?.document))
const syncLabel = computed(() => ({ synced: 'Saved', dirty: 'Unsaved', saving: 'Saving…', offline: 'Offline', conflict: 'Conflict' })[props.syncState])
const filteredEntries = computed(() => entries.value.filter((entry) => filter.value === 'all' || (filter.value === 'insertion' ? entry.type === 'insertion' : entry.type !== 'insertion')))
const confirmDialog = ref(false)
const pendingEntry = ref<TaskEditListEntry | null>(null)
const undoDocument = ref<JsonObject | null>(null)

const labels: Record<TaskEditType, string> = { highlight: 'Highlight', bold: 'Bold', italic: 'Italic', underline: 'Underline', strike: 'Strikethrough', textColor: 'Text color', inlineCode: 'Inline code', insertion: 'Added text' }
const icons: Record<TaskEditType, string> = { highlight: 'mdi-marker', bold: 'mdi-format-bold', italic: 'mdi-format-italic', underline: 'mdi-format-underline', strike: 'mdi-format-strikethrough', textColor: 'mdi-format-color-text', inlineCode: 'mdi-code-tags', insertion: 'mdi-text-box-plus-outline' }
const labelFor = (type: TaskEditType) => labels[type]
const iconFor = (type: TaskEditType) => icons[type]

const requestRemoval = (entry: TaskEditListEntry) => {
  pendingEntry.value = entry
  confirmDialog.value = true
}
const confirmRemoval = () => {
  if (!pendingEntry.value || !props.taskEdit) return
  undoDocument.value = cloneTaskDocument(props.taskEdit.document)
  emit('remove-edit', pendingEntry.value.id)
  confirmDialog.value = false
  pendingEntry.value = null
  notifySuccess('Edit removed.', { timeout: 6000, action: { label: 'Undo', handler: undoRemoval } })
}
const undoRemoval = () => {
  if (undoDocument.value) emit('restore-document', undoDocument.value)
  undoDocument.value = null
}
</script>

<style scoped>
.task-edits-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.task-edits-sidebar__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.14);
}
.task-edits-sidebar__list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 6px;
}
.task-edits-sidebar__empty {
  padding: 16px 12px;
  color: rgba(var(--v-theme-on-surface), 0.62);
  font-size: 12px;
  line-height: 1.5;
}
.task-edit-title {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  min-width: 0;
}
.task-edit-title__text {
  min-width: 0;
  display: flex;
  flex: 1;
  flex-direction: column;
  font-size: 11px;
}
.task-edit-title__text span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(var(--v-theme-on-surface), 0.65);
}
.task-edit-color {
  width: 14px;
  height: 14px;
  flex: 0 0 14px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.2);
}
.task-edit-fragments {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.task-edit-fragment {
  border: 0;
  border-left: 2px solid rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.05);
  padding: 5px 7px;
  text-align: left;
  font-size: 11px;
  cursor: pointer;
}
.task-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 6px;
}
</style>
