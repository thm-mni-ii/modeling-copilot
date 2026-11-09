<template>
  <div v-if="task">
    <TaskTopBar
      :task="task"
      :window-open="false"
      :content-html="contentHtml"
      :task-edit="taskEdit"
      :element-options="elementOptions"
      :connection-options="connectionOptions"
      :history="history"
      :evaluation-workflows="evaluationWorkflows"
      shared
      :notes="notes ?? null"
      @select-connection="emit('select-connection', $event)"
      @select-task-edits="emit('select-task-edits', $event)"
      @start-evaluation="emit('start-evaluation')"
      @update:task-edit-document="write"
    >
      <div class="shared-notes">
        <!-- Trennlinie mit Beschriftung statt eigener Leiste; formatiert wird über die Leiste des Textes. -->
        <div class="shared-notes__divider">
          <v-icon size="14">mdi-note-text-outline</v-icon>
          <span>Notes</span>
        </div>
        <editor-content :editor="notes" class="shared-notes__body" />
      </div>
    </TaskTopBar>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import TaskTopBar from '@/components/modeling/controls/TaskTopBar.vue'
import type { TaskConnectionOption, TaskElementOption } from '@/components/tasks/taskEditorExtensions'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import type { DiagramTask } from '@/model/Task'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
import { collabErrorMessage, loadCollabKit } from '@/collab/kit/collabKit'
import type { Session, SharedText } from '@/collab/kit/collabKitV1'
import { bindNotes, notesExtensions } from '@/collab/worksheet/notesBinding'
import { marksOf, withMarks, type SharedMark, type SharedMarks } from '@/collab/converters/task/marks'
import { MARKS_MAP, NOTES_TEXT, taskLinkOf } from '@/collab/converters/task/taskLink'
import { baseOf, taskHistoryOf } from '@/collab/sharing/shareTask'
import { linkOf } from '@/collab/storage/workpiece'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { currentShare } from '@/collab/sharing/shareModel'
import type { TaskVersionReference } from '@/services/api/types/common'
import { sharedTaskEdit, sharedTaskHistory, sharedTaskReference, sharedTaskSettings, writeSharedTask, type SharedTaskSettings } from './sharedTask'

/**
 * The task shared along with a model of a room: its text fixed in a CK task, the marks on it as
 * one unit per edit and the notes below as one shared text, both in the task workpiece.
 */
const props = withDefaults(
  defineProps<{
    /** The model workpiece, whose contract names the task. */
    workpieceId: string
    elementOptions?: TaskElementOption[]
    connectionOptions?: TaskConnectionOption[]
  }>(),
  { elementOptions: () => [], connectionOptions: () => [] }
)

const emit = defineEmits<{
  'select-connection': [reference: { languageId: string; connectionType: string }]
  'select-task-edits': [ids: string[]]
  'start-evaluation': []
}>()

const workspace = useModelWorkspaceStore()
const task = ref<DiagramTask | null>(null)
const contentHtml = ref('')
const document = shallowRef<JsonObject | null>(null)
const mayWrite = ref(false)
const notes = useEditor({ extensions: notesExtensions('Notes for everyone in the room'), editable: false })

// The editor of the task reads a whole document; the marks are laid over the fixed text for it.
const taskEdit = computed<TaskEditDocument | null>(() => (document.value ? { schemaVersion: 1, revision: 0, updatedAt: '', document: document.value } : null))

// Only the host evaluates, so only the host gets the button.
const evaluationWorkflows = computed(() => (currentShare.value?.privateModelId ? sharedTaskSettings.value?.evaluationWorkflows ?? [] : []))

// The sidebar lists the edits of the room as it does the private ones.
watch(taskEdit, (value) => (sharedTaskEdit.value = value), { immediate: true })

// Undo and redo take back the own steps only; what others set since stays.
const canUndo = ref(false)
const canRedo = ref(false)
// Die Notizen haben ihren eigenen Verlauf im geteilten Text; die Leiste nimmt ihn, wenn die Notizen aktiv sind.
const canUndoNotes = ref(false)
const canRedoNotes = ref(false)
const refreshHistory = () => {
  canUndo.value = session?.units.canUndo() ?? false
  canRedo.value = session?.units.canRedo() ?? false
  canUndoNotes.value = notesText?.canUndo() ?? false
  canRedoNotes.value = notesText?.canRedo() ?? false
}
const step = (kind: 'undo' | 'redo') => {
  try {
    session?.units[kind]()
  } catch (error) {
    notifyWarning(`Nothing could be taken back: ${collabErrorMessage(error)}`)
  }
  refreshHistory()
}
const stepNotes = (kind: 'undo' | 'redo') => {
  notesText?.[kind]()
  refreshHistory()
}
const history = computed(() => ({
  canUndo: canUndo.value,
  canRedo: canRedo.value,
  undo: () => step('undo'),
  redo: () => step('redo'),
  notes: { canUndo: canUndoNotes.value, canRedo: canRedoNotes.value, undo: () => stepNotes('undo'), redo: () => stepNotes('redo') }
}))

let base: JsonObject = { type: 'doc' }
// The marks as the editor was last given them or last wrote them.
let shown: SharedMarks = {}
let session: Session<SharedMark> | null = null
let unbindNotes: (() => void) | null = null
let notesText: SharedText | null = null
let stops: (() => void)[] = []
let unmounted = false

const sameMarks = (left: SharedMarks, right: SharedMarks) => Object.keys(left).length === Object.keys(right).length && Object.entries(left).every(([id, mark]) => JSON.stringify(mark) === JSON.stringify(right[id]))

const show = () => {
  if (!session) return
  shown = Object.fromEntries(session.units.entries())
  document.value = withMarks(base, shown)
}

/** Writes what changed against the marks the editor had: new and changed ones whole, removed ones deleted. */
const write = (next: JsonObject) => {
  if (!session) return
  if (!mayWrite.value) {
    notifyWarning('Marking the task needs the right to edit.')
    show()
    return
  }
  const after = marksOf(next)
  const set: SharedMarks = {}
  for (const [id, mark] of Object.entries(after)) if (JSON.stringify(mark) !== JSON.stringify(shown[id])) set[id] = mark
  const removed = Object.keys(shown).filter((id) => !(id in after))
  if (!Object.keys(set).length && !removed.length) return
  try {
    session.units.update({ set, delete: removed })
    shown = after
    // Also from the sidebar: the editor and the list take what was written.
    document.value = next
    refreshHistory()
  } catch (error) {
    notifyError(`The mark could not be saved: ${collabErrorMessage(error)}`)
    show()
  }
}

onMounted(async () => {
  try {
    const ck = await loadCollabKit()
    const link = taskLinkOf(await ck.workpieces.get(props.workpieceId))
    if (!link || unmounted) return
    const shared = await ck.tasks.get(link.taskId)
    const html = typeof shared.detail?.contentHtml === 'string' ? shared.detail.contentHtml : ''
    if (unmounted) return
    base = baseOf(html)
    contentHtml.value = html
    sharedTaskSettings.value = (shared.detail?.settings as SharedTaskSettings | undefined) ?? null
    sharedTaskReference.value = (shared.detail?.taskVersion as TaskVersionReference | undefined) ?? null
    task.value = { id: shared._id, title: shared.title, content: html, createdAt: shared.createdAt, updatedAt: shared.createdAt }

    // The host's model shows the private history first, and the history of the room after it.
    const host = () => {
      const own = linkOf(workspace.preferences)?.host
      return own ? { modelId: own.modelId, after: own.taskUpdate } : undefined
    }
    sharedTaskHistory.value = taskHistoryOf(ck, link.workpieceId, base, html, (restored) => write(restored), host)
    const opened = ck.open<SharedMark>(link.workpieceId, { map: MARKS_MAP })
    session = opened
    await opened.synced
    if (unmounted) return
    mayWrite.value = opened.mayWrite
    show()
    stops.push(
      opened.units.onChange((_, remote) => {
        // Own marks are in the editor already; loading them again would only move the selection.
        if (remote && !sameMarks(Object.fromEntries(opened.units.entries()), shown)) show()
        refreshHistory()
      })
    )
    // Locked while the host leaves, edit comes back on reopening; the session tells after reconnecting.
    stops.push(
      opened.on('status', () => {
        mayWrite.value = opened.mayWrite
        notes.value?.setEditable(opened.mayWrite)
      })
    )
    notesText = opened.text(NOTES_TEXT)
    // Der Verlauf trägt den Schritt erst nach der Änderung ein, daher einen Takt später lesen.
    stops.push(notesText.onChange(() => queueMicrotask(refreshHistory)))
    if (notes.value) unbindNotes = bindNotes(notes.value, notesText, () => opened.mayWrite)
  } catch (error) {
    if (!unmounted) notifyError(`The task of the room could not be loaded: ${collabErrorMessage(error)}`)
  }
})

writeSharedTask.value = write

onBeforeUnmount(() => {
  unmounted = true
  sharedTaskEdit.value = null
  sharedTaskSettings.value = null
  sharedTaskReference.value = null
  sharedTaskHistory.value = null
  writeSharedTask.value = null
  unbindNotes?.()
  notesText = null
  stops.forEach((stop) => stop())
  stops = []
  session?.close()
  session = null
})
</script>

<style scoped>
.shared-notes {
  padding: 4px 16px 12px;
  background: #fff;
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
