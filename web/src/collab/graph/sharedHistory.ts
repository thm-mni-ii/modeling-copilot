import { shallowRef } from 'vue'

/** Undo and redo of the own steps in a model of a room; what others changed since stays. */
export interface SharedHistory {
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
}

/**
 * Set while the editor holds a model of a room, else null; for a reader there is nothing to undo.
 * The editor's undo and redo take it instead of their own history then; a new object on every
 * change, so the buttons follow.
 */
export const sharedHistory = shallowRef<SharedHistory | null>(null)
