import { shallowRef } from 'vue'
import type { Editor } from '@tiptap/core'
import type { JsonObject, TaskVersionReference } from '@/services/api/types/common'
import type { TaskEditDocument, TaskEditVersionInfo } from '@/services/api/types/model'
import type { AutonomyMode } from '@/model/Autonomy'

// Hier und nicht in der Komponente, weil Editor und Sidebar die Task des Raums beide brauchen und beim Teilen neu aufgebaut werden.

/** The task edits of the room as the editor shows them; null while no task of a room is shown. */
export const sharedTaskEdit = shallowRef<TaskEditDocument | null>(null)

/** Writes a whole document into the marks of the room; set while the task of a room is shown. */
export const writeSharedTask = shallowRef<((document: JsonObject) => void) | null>(null)

/** What the task prescribes for working on it, as the host's backend put it into the CK task; null while no task of a room is shown. */
export interface SharedTaskSettings {
  autonomyMode: AutonomyMode
  connectionPreviewAllowed: boolean | null
  evaluationWorkflows: string[]
  evaluationAvailable?: boolean
}
export const sharedTaskSettings = shallowRef<SharedTaskSettings | null>(null)

/** Which release of a task the room shows, so a visitor can try to keep the task along with the model; null while none is shown. */
export const sharedTaskReference = shallowRef<TaskVersionReference | null>(null)

/** What the dialogs of the task history need of a task of a room, in the shapes of the private history. */
export interface TaskHistorySource {
  contentHtml: string
  contentDocument: JsonObject | null
  /** The steps of the history, oldest first. */
  list(): Promise<TaskEditVersionInfo[]>
  /** The task state after a step. */
  document(id: string): Promise<TaskEditDocument>
  /** Takes a task state as the current one. */
  restore(document: JsonObject): void
}
export const sharedTaskHistory = shallowRef<TaskHistorySource | null>(null)

/** What the floating window of the task needs of a task of a room; null while no task of a room is shown. */
export interface SharedTaskContent {
  title: string
  contentHtml: string
  /** Im Gruppenraum der Editor der Notizen; er zieht ins Fenster, solange es offen ist. */
  notes: Editor | null
  history: TaskEditHistory
}
export interface TaskEditHistory {
  canUndo: boolean
  canRedo: boolean
  undo: () => void
  redo: () => void
  notes?: { canUndo: boolean; canRedo: boolean; undo: () => void; redo: () => void }
}
export const sharedTaskContent = shallowRef<SharedTaskContent | null>(null)
