import { computed, reactive } from 'vue'
import modelService from '@/services/model/model.service'
import type { TaskEditDocument, TaskEditVersionInfo } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { sharedTaskHistory } from '@/collab/worksheet/sharedTask'
import { loadTaskEditHistory } from '@/utils/taskEditTimeline'

/** Where the dialogs get the task history from: the open model with a task, or the task of a room. */
export const useTaskHistory = () => {
  const workspace = useModelWorkspaceStore()
  const room = computed(() => (workspace.taskVersion ? null : sharedTaskHistory.value))
  return reactive({
    /** Whether there is a task with a history to show. */
    active: computed(() => Boolean(workspace.taskVersion || room.value)),
    baseHtml: computed(() => workspace.taskVersion?.data.contentHtml ?? room.value?.contentHtml ?? ''),
    baseDocument: computed(() => workspace.taskVersion?.data.contentDocument ?? room.value?.contentDocument ?? null),
    /** The task document the local edits start from. */
    start: computed(() => workspace.model?.taskEdit?.document ?? workspace.taskVersion?.data.contentDocument),
    pending: computed(() => workspace.pendingTaskEditPatches),
    list: (): Promise<TaskEditVersionInfo[]> => (room.value ? room.value.list() : workspace.model ? loadTaskEditHistory(workspace.model.id) : Promise.resolve([])),
    stateOf: async (id: string): Promise<TaskEditDocument> => {
      if (room.value) return room.value.document(id)
      if (!workspace.model) throw new Error('No model is loaded.')
      return (await modelService.getTaskEditVersion(workspace.model.id, id)).data
    },
    restore: (snapshot: TaskEditDocument) => (room.value ? room.value.restore(snapshot.document) : workspace.adoptTaskEditSnapshot(snapshot))
  })
}
