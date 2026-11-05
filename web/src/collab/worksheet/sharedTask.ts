import { shallowRef } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
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
}
export const sharedTaskSettings = shallowRef<SharedTaskSettings | null>(null)
