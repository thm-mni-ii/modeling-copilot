<template>
  <v-container max-width="1150" class="py-8">
    <v-form ref="form" @submit.prevent="save">
      <div class="d-flex align-center ga-3 mb-4">
        <h1 class="text-h4">Learning path template</h1>
        <v-spacer /><v-btn to="/learning-path-templates">Back to overview</v-btn><v-btn color="primary" :loading="busy" :disabled="loading || !draft.name.trim()" @click="save">Save</v-btn>
      </div>
      <v-progress-linear v-if="loading" indeterminate />
      <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
      <v-alert type="info" variant="tonal" class="mb-4">Changes apply to existing runs. Started tasks remain accessible. Score conditions require a scoring integration that will be added later.</v-alert>
      <v-text-field v-model="draft.name" label="Title" />
      <v-textarea v-model="draft.description" label="Description" rows="2" />
      <div class="d-flex ga-6"><v-switch v-model="draft.published" label="Published" color="primary" /><v-switch v-model="draft.archived" label="Archived (no new runs)" /></div>
      <v-card variant="outlined" class="pa-4 mb-5">
        <v-card-title>Add task</v-card-title>
        <v-autocomplete v-model="taskId" :items="tasks" item-title="name" item-value="id" label="Search tasks" @update:model-value="loadVersions" />
        <v-select v-model="versionId" :items="versions.map((v) => ({ ...v, label: `${v.releaseName} (v${v.versionNumber})` }))" item-title="label" item-value="id" label="Task release" :disabled="!taskId" />
        <v-btn :disabled="!taskId || !versionId" prepend-icon="mdi-plus" @click="add">Add</v-btn>
      </v-card>
      <draggable v-model="draft.steps" item-key="id" handle=".step-handle">
        <template #item="{ element, index }">
          <v-card variant="outlined" class="mb-4 pa-4">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon class="step-handle" style="cursor: grab" aria-label="Move step">mdi-drag</v-icon><strong>{{ index + 1 }}.</strong><v-text-field v-model="element.title" label="Step title" hide-details density="compact" /><v-btn icon="mdi-arrow-up" variant="text" :disabled="index === 0" aria-label="Move up" @click="move(index, -1)" /><v-btn
                icon="mdi-arrow-down"
                variant="text"
                :disabled="index === draft.steps.length - 1"
                aria-label="Move down"
                @click="move(index, 1)"
              /><v-btn icon="mdi-delete-outline" variant="text" aria-label="Remove step" @click="remove(index)" />
            </div>
            <div class="d-flex align-center ga-3 mt-4">
              <h2 class="text-subtitle-1">Unlocking</h2>
              <v-select
                v-model="element.unlock.mode"
                :items="[
                  { title: 'All rules (AND)', value: 'all' },
                  { title: 'At least one rule (OR)', value: 'any' }
                ]"
                label="Rule combination"
                hide-details
                density="compact"
                style="max-width: 300px"
              />
            </div>
            <p v-if="!element.unlock.conditions.length" class="text-medium-emphasis my-3">Available immediately</p>
            <v-sheet v-for="(condition, ci) in element.unlock.conditions" :key="ci" border rounded class="pa-3 mt-3">
              <div class="d-flex ga-3 align-center"><v-select v-model="condition.type" :items="conditionTypes" label="Rule" hide-details @update:model-value="resetCondition(condition)" /><v-btn icon="mdi-close" variant="text" aria-label="Remove rule" @click="element.unlock.conditions.splice(ci, 1)" /></div>
              <v-select v-if="condition.type !== 'at'" v-model="condition.stepId" :items="sourceSteps(element.id, condition.type === 'after')" label="Prerequisite task / time reference" class="mt-3" hide-details />
              <v-text-field v-if="condition.type === 'score'" v-model.number="condition.value" type="number" min="0" max="100" label="Minimum score (%)" class="mt-3" hide-details />
              <v-text-field v-if="condition.type === 'after'" :model-value="(condition.seconds ?? 0) / 3600" type="number" min="0" step="0.25" label="Delay in hours" class="mt-3" hide-details @update:model-value="condition.seconds = Math.round(Number($event) * 3600)" />
              <v-text-field v-if="condition.type === 'at'" :model-value="localDate(condition.at)" type="datetime-local" :label="'Unlocking (' + timezone + ')'" class="mt-3" hide-details @update:model-value="setDate(condition, $event)" />
            </v-sheet>
            <v-btn class="mt-3" variant="tonal" prepend-icon="mdi-plus" @click="element.unlock.conditions.push(newCondition())">Add rule</v-btn>
            <ChallengeConfigEditor v-model="element.challenge" />
          </v-card>
        </template>
      </draggable>
      <v-empty-state v-if="!draft.steps.length && !loading" icon="mdi-map-marker-path" title="No tasks yet" text="Add tasks to build your learning path." />
      <v-dialog v-model="removeDialog" max-width="520"
        ><v-card title="Remove step?"
          ><v-card-text>Existing work is retained but hidden. Rules in other steps must no longer reference this step.</v-card-text><v-card-actions><v-btn @click="removeDialog = false">Cancel</v-btn><v-spacer /><v-btn color="error" @click="confirmRemove">Remove</v-btn></v-card-actions></v-card
        ></v-dialog
      >
    </v-form>
  </v-container>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import draggable from 'vuedraggable'
import ChallengeConfigEditor from '@/components/learningPaths/ChallengeConfigEditor.vue'
import paths, { type Condition, type PathTemplate } from '@/services/learningPaths'
import taskService from '@/services/task/task.service'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
const route = useRoute(),
  router = useRouter()
const draft = ref<PathTemplate>({ id: '', name: '', description: '', published: false, archived: false, updatedAt: null, steps: [] })
const tasks = ref<Task[]>([]),
  versions = ref<TaskVersionInfo[]>([])
const taskId = ref<string | null>(null),
  versionId = ref<string | null>(null)
const busy = ref(false),
  loading = ref(true),
  error = ref(''),
  saved = ref('')
const removeDialog = ref(false),
  removeIndex = ref(-1)
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
const form = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const conditionTypes = [
  { title: 'Task completed', value: 'completed' },
  { title: 'Minimum score (future integration)', value: 'score' },
  { title: 'Fixed date and time', value: 'at' },
  { title: 'Relative delay', value: 'after' }
]
const message = (e: unknown) => (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The action could not be completed.'
const sourceSteps = (id: string, includeStart: boolean) => [...(includeStart ? [{ title: 'Start of the run', value: null }] : []), ...draft.value.steps.filter((s) => s.id !== id).map((s) => ({ title: s.title, value: s.id }))]
const newCondition = (): Condition => ({ type: 'completed', stepId: null, value: null, at: null, seconds: null, timezone })
const resetCondition = (c: Condition) => {
  c.stepId = null
  c.value = c.type === 'score' ? 50 : null
  c.at = null
  c.seconds = c.type === 'after' ? 0 : null
  c.timezone = timezone
}
const localDate = (iso: string | null) => {
  if (!iso) return ''
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const setDate = (c: Condition, value: string) => {
  c.at = value ? new Date(value).toISOString() : null
  c.timezone = timezone
}
const loadVersions = async () => {
  versions.value = []
  versionId.value = null
  const selected = taskId.value
  if (!selected) return
  try {
    let skip = 0
    const result: TaskVersionInfo[] = []
    for (;;) {
      const page = (await taskService.listVersions(selected, skip, 100)).data
      result.push(...page.items.filter((v) => v.kind === 'release'))
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    if (taskId.value !== selected) return
    versions.value = result
    versionId.value = tasks.value.find((t) => t.id === selected)?.latestReleaseId ?? result[0]?.id ?? null
  } catch (e) {
    error.value = message(e)
  }
}
const add = () => {
  if (!taskId.value || !versionId.value) return
  const previous = draft.value.steps[draft.value.steps.length - 1]
  const c = newCondition()
  c.stepId = previous?.id ?? null
  draft.value.steps.push({ id: crypto.randomUUID(), title: tasks.value.find((t) => t.id === taskId.value)?.name ?? 'Task', taskVersion: { taskId: taskId.value, versionId: versionId.value }, unlock: { mode: 'all', conditions: previous ? [c] : [] } })
}
const move = (index: number, delta: number) => {
  const [item] = draft.value.steps.splice(index, 1)
  draft.value.steps.splice(index + delta, 0, item)
}
const remove = (index: number) => {
  removeIndex.value = index
  removeDialog.value = true
}
const confirmRemove = () => {
  draft.value.steps.splice(removeIndex.value, 1)
  removeDialog.value = false
}
const save = async () => {
  if (busy.value || !(await form.value?.validate())?.valid) return
  busy.value = true
  error.value = ''
  try {
    draft.value = (await paths.save(draft.value)).data
    saved.value = JSON.stringify(draft.value)
    await router.replace(`/learning-path-templates/${draft.value.id}/edit`)
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
  }
}
onBeforeRouteLeave(() => saved.value === JSON.stringify(draft.value) || window.confirm('Discard unsaved changes?'))
onMounted(async () => {
  try {
    if (route.params.id) draft.value = (await paths.template(String(route.params.id))).data
    saved.value = JSON.stringify(draft.value)
    let skip = 0
    for (;;) {
      const page = (await taskService.list(skip, 100)).data
      tasks.value.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
  } catch (e) {
    error.value = message(e)
  } finally {
    loading.value = false
  }
})
</script>
