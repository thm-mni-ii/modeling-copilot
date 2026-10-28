import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { UnitChange, Workpiece } from '@/collab/kit/collabKitV1'
import { joinModel, type SharedCell } from './modelCells'
import { languagesOf } from './workpiece'

/** The languages of the model, as one unit beside the cells. */
export const LANGUAGES_KEY = '@languages'
/** Kept free for the task edits, written once models with a task move. */
export const TASK_EDIT_KEY = '@taskEdit'

/** What a unit of a Copilot workpiece holds: a cell, or the languages beside them. */
export type ModelUnit = SharedCell | WorkspaceLanguageReference[]

/** Whether a key names a cell; the whole keys, as a label cell takes its ID from a type named in the language. */
export const isCellKey = (key: string) => key !== LANGUAGES_KEY && key !== TASK_EDIT_KEY

/** Only the cells, as splitModel, joinModel and applyCells take them. */
export const cellsOf = (units: Iterable<[string, ModelUnit]>) => {
  const cells = new Map<string, SharedCell>()
  for (const [key, unit] of units) if (isCellKey(key)) cells.set(key, unit as SharedCell)
  return cells
}

/** The model XML of the units; null without a root cell. */
export const xmlOf = (units: Iterable<[string, ModelUnit]>) => joinModel(cellsOf(units))

/** The languages of the units; a workpiece without them keeps those it was created with. */
export const languagesIn = (units: ReadonlyMap<string, ModelUnit>, workpiece: Workpiece) => (units.get(LANGUAGES_KEY) as WorkspaceLanguageReference[] | undefined) ?? languagesOf(workpiece)

/** The change that writes the languages. */
export const languagesChange = (languages: WorkspaceLanguageReference[]): UnitChange<ModelUnit> => ({ set: { [LANGUAGES_KEY]: languages } })
