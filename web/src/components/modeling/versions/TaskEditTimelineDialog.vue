<template>
  <v-dialog :model-value="modelValue" max-width="1000" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Task edit history</v-card-title>
      <v-progress-linear :active="loading" absolute indeterminate />
      <v-card-text>
        <v-alert v-if="error" type="error" variant="tonal">{{ error }}</v-alert>
        <v-alert v-if="historyError" type="warning" variant="tonal">{{ historyError }}</v-alert>
        <TaskEditEditor v-if="task.active && preview" :key="workspace.taskReference?.versionId ?? 'room'" :base-html="task.baseHtml" :base-document="task.baseDocument" :model-value="preview.document" mode="read" class="task-history-preview" />
        <v-slider v-if="steps.length" v-model="selected" :min="0" :max="steps.length" :step="1" :ticks="ticks" show-ticks="always" class="mt-7 mx-8" />
        <p class="text-caption">{{ label }}</p>
        <p class="text-caption text-medium-emphasis">Restoring adds a local task edit. Model versions remain unchanged. Press Save to synchronize.</p>
      </v-card-text>
      <v-card-actions>
        <v-btn :disabled="loading || !preview || Boolean(error) || workspace.syncState === 'saving'" prepend-icon="mdi-history" @click="restore">Use this task state</v-btn>
        <v-spacer /><v-btn @click="emit('update:modelValue', false)">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { TaskEditDocument, TaskEditVersionInfo } from '@/services/api/types/model'
import { buildTaskEditTimeline } from '@/utils/taskEditTimeline'
import { useTaskHistory } from '@/collab/historyBuilder/useTaskHistory'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const workspace = useModelWorkspaceStore()
const task = useTaskHistory()
const history = ref<TaskEditVersionInfo[]>([])
const selected = ref(0)
const preview = ref<TaskEditDocument | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const historyError = ref<string | null>(null)
const steps = computed(() => buildTaskEditTimeline(history.value, task.pending, task.start))
const ticks = computed(() => ({ 0: 'Original task', [history.value.length]: history.value.length ? 'Last save' : 'Original task', ...(steps.value.length > history.value.length ? { [steps.value.length]: 'Local edits' } : {}) }))
const label = computed(() => {
  const step = steps.value[selected.value - 1]
  return step ? `${step.saved ? 'Saved' : 'Local'} · ${new Date(step.createdAt).toLocaleString()} · ${step.label}` : 'Original task'
})
let generation = 0
const updatePreview = async () => {
  const request = ++generation
  loading.value = true
  error.value = null
  // The last preview stays until the next is there, so the dialog does not collapse on every move of the slider.
  try {
    const step = steps.value[selected.value - 1]
    const document = step?.patch?.document ?? (!step ? task.baseDocument : null)
    const next = document ? { schemaVersion: 1 as const, revision: workspace.taskEdit?.revision ?? 0, updatedAt: new Date().toISOString(), document }
      : step ? await task.stateOf(step.id) : null
    if (request === generation) preview.value = next
  } catch {
    if (request === generation) error.value = 'This task state could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}
const restore = () => {
  if (preview.value) task.restore(preview.value)
  emit('update:modelValue', false)
}
watch(() => props.modelValue, async (open) => {
  if (!open) { generation++; return }
  loading.value = true
  error.value = null
  historyError.value = null
  history.value = []
  preview.value = null
  try {
    history.value = await task.list()
  } catch {
    historyError.value = 'Saved history could not be loaded. Local task edits remain available.'
  }
  selected.value = steps.value.length
  await updatePreview()
})
watch(selected, () => { if (props.modelValue) void updatePreview() })
</script>

<style scoped>
.task-history-preview { height: 480px; max-height: 60vh; overflow-y: auto; }
</style>
