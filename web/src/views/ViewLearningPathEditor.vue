<template>
  <v-container class="path-editor py-5" max-width="1440">
    <header class="editor-header">
      <div class="header-title">
        <router-link to="/learning-path-templates" class="overview-link"><v-icon size="16">mdi-arrow-left</v-icon> Learning path templates</router-link>
        <h1 class="text-overline mt-2">Learning path template</h1>
        <v-text-field v-model="draft.name" class="path-name" label="Path title" placeholder="Give your path a name" variant="plain" hide-details :error="attempted && !draft.name.trim()" maxlength="256" />
      </div>
      <div class="header-actions">
        <v-chip size="small" :color="draft.archived ? undefined : draft.published ? 'success' : undefined" variant="tonal">{{ draft.archived ? 'Archived' : draft.published ? 'Published' : 'Draft' }}</v-chip>
        <span class="save-state" role="status">{{ dirty ? 'Unsaved changes' : draft.id ? 'All changes saved' : 'Not saved yet' }}</span>
        <v-btn variant="text" prepend-icon="mdi-cog-outline" :disabled="!ready" @click="settingsDialog = true">Path settings</v-btn>
        <v-btn variant="tonal" prepend-icon="mdi-eye-outline" :disabled="!draft.steps.length" @click="previewDialog = true">Preview path</v-btn>
        <v-btn color="primary" variant="flat" :loading="busy" :disabled="loading || !ready" @click="save">Save</v-btn>
      </div>
    </header>
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}<v-btn v-if="!ready && !loading" variant="text" size="small" @click="load">Retry</v-btn></v-alert>
    <p v-if="draft.published" class="published-note mb-4"><v-icon size="16" class="mr-1">mdi-information-outline</v-icon> Saved changes apply to all runs, including paths already in progress.</p>

    <div class="editor-grid" :class="{ 'editor-grid--detail': showDetail }">
      <aside class="path-sidebar" aria-label="Path tasks">
        <div class="sidebar-header">
          <div>
            <h2 class="text-subtitle-1 font-weight-bold">Your path</h2>
            <span class="text-caption text-medium-emphasis">{{ draft.steps.length }} {{ draft.steps.length === 1 ? 'activity' : 'activities' }} · drag to reorder</span>
          </div>
        </div>
        <v-alert v-if="orderNotice" type="info" variant="tonal" density="compact" closable class="ma-3 text-caption" @click:close="orderNotice = ''">{{ orderNotice }}</v-alert>
        <draggable v-model="draft.steps" item-key="id" handle=".step-handle" class="step-list" ghost-class="step-row--ghost" :animation="150" @end="onReorder">
          <template #item="{ element, index }">
            <div class="step-row" :class="{ 'step-row--active': selectedId === element.id, 'step-row--error': issues[element.id]?.length }">
              <span class="step-handle" aria-hidden="true"><v-icon size="18">mdi-drag-vertical</v-icon></span>
              <button type="button" class="step-select" :aria-pressed="selectedId === element.id" @click="selectStep(element.id)">
                <span class="step-number">{{ index + 1 }}</span
                ><span class="step-copy"
                  ><strong
                    ><v-icon size="15">{{ element.type === 'survey' ? 'mdi-clipboard-list-outline' : 'mdi-pencil-outline' }}</v-icon> {{ element.title || 'Untitled task' }}</strong
                  ><span>{{ availabilitySummary(element, draft.steps) }}</span
                  ><span v-if="element.challenge" class="step-challenge"
                    ><v-icon size="13" :color="element.challenge.color ?? undefined">{{ element.challenge.icon }}</v-icon> {{ element.challenge.title }}</span
                  ></span
                >
                <v-icon v-if="issues[element.id]?.length" color="error" size="18" :aria-label="`${issues[element.id].length} errors`">mdi-alert-circle-outline</v-icon>
              </button>
              <v-menu
                ><template #activator="{ props }"><v-btn v-bind="props" icon="mdi-dots-vertical" size="x-small" variant="text" :aria-label="`Actions for step ${index + 1}`" /></template
                ><v-list density="compact"
                  ><v-list-item title="Move up" prepend-icon="mdi-arrow-up" :disabled="index === 0" @click="move(index, -1)" /><v-list-item title="Move down" prepend-icon="mdi-arrow-down" :disabled="index === draft.steps.length - 1" @click="move(index, 1)" /><v-list-item title="Duplicate" prepend-icon="mdi-content-copy" @click="duplicate(element)" /><v-list-item
                    title="Remove"
                    prepend-icon="mdi-delete-outline"
                    @click="removeId = element.id" /></v-list
              ></v-menu>
            </div>
          </template>
        </draggable>
        <div v-if="!draft.steps.length" class="sidebar-empty">
          <v-icon size="34" class="mb-3">mdi-map-marker-path</v-icon>
          <p>Start with a few tasks.</p>
          <p class="text-caption mt-1">You can add more at any time.</p>
        </div>
        <div class="pa-3">
          <p class="text-caption mb-2">Add activity</p>
          <div class="d-flex flex-wrap ga-2"><v-btn variant="tonal" prepend-icon="mdi-plus" :disabled="!ready || draft.steps.length >= 200" @click="openTaskPicker">Task</v-btn><v-btn variant="tonal" prepend-icon="mdi-clipboard-list-outline" :disabled="!ready || draft.steps.length >= 200" @click="surveyPickerDialog = true">Questionnaire</v-btn></div>
        </div>
      </aside>

      <section class="step-details" aria-label="Selected task settings">
        <template v-if="selected">
          <v-btn class="mobile-back mb-3" variant="text" prepend-icon="mdi-arrow-left" @click="showDetail = false">Back to path</v-btn>
          <div class="detail-heading">
            <div>
              <p class="text-overline text-medium-emphasis">STEP {{ selectedIndex + 1 }} OF {{ draft.steps.length }}</p>
              <h2 ref="detailHeading" tabindex="-1" class="text-h5">{{ selected.type === 'survey' ? 'Questionnaire settings' : 'Task settings' }}</h2>
            </div>
            <div><v-btn icon="mdi-content-copy" variant="text" aria-label="Duplicate selected task" @click="duplicate(selected)" /><v-btn icon="mdi-delete-outline" variant="text" aria-label="Remove selected task" @click="removeId = selected.id" /></div>
          </div>
          <v-alert v-if="issues[selected.id]?.length" type="error" variant="tonal" density="compact" class="mt-4"
            ><ul class="pl-4">
              <li v-for="issue in issues[selected.id]" :key="issue">{{ issue }}</li>
            </ul></v-alert
          >
          <div class="d-flex align-center ga-4 mt-5">
            <v-text-field v-model="selected.title" label="Step title" variant="outlined" class="flex-grow-1" maxlength="256" hide-details="auto" :error-messages="attempted && !selected.title.trim() ? 'A step title is required.' : []" /><v-switch v-if="selected.type === 'survey'" v-model="selected.required" label="Required" color="primary" hide-details class="flex-grow-0" />
          </div>
          <div v-if="selected.type !== 'survey'" class="task-source mt-3">
            <v-icon size="19">mdi-clipboard-text-outline</v-icon>
            <div>
              <strong>{{ taskName(selected) }}</strong
              ><span>{{ releaseLabel(selected) }}</span>
            </div>
            <v-spacer /><v-btn variant="text" size="small" :loading="loadingVersions === selected.taskVersion!.taskId" @click="openReleaseDialog">Change release</v-btn>
          </div>
          <template v-if="selected.type === 'survey'">
            <v-select :model-value="selected.surveyId" :items="surveyOptions" label="Published questionnaire" class="mt-4" @update:model-value="chooseSurvey" />
            <p class="text-caption">Uses the current published questionnaire. Optional questionnaires can be skipped.</p>
            <p class="text-body-2 mt-3">{{ availabilitySummary(selected, draft.steps) }}</p>
          </template>
          <div v-if="selected.type !== 'survey'" class="mt-5">
            <h3 class="text-subtitle-1 mb-2">Task questionnaires</h3>
            <v-select v-model="selected.beforeSurveyId" :items="surveyOptions" label="Before task" clearable hide-details class="mb-3" />
            <v-select v-model="selected.afterSurveyId" :items="surveyOptions" label="After task" clearable hide-details />
            <p class="text-caption mt-2">Required in the modeling view before working on or completing this task. Uses the current published questionnaire.</p>
          </div>
          <v-divider class="my-6" />
          <LearningPathAvailability :key="selected.id" v-model="selected.unlock" :step="selected" :steps="draft.steps" />
          <v-divider class="my-6" />
          <ChallengeConfigEditor v-if="selected.type !== 'survey'" :key="`challenge-${selected.id}`" v-model="selected.challenge" :show-errors="attempted" />
        </template>
        <div v-else class="detail-empty">
          <v-icon size="52" color="primary">mdi-map-marker-path</v-icon>
          <h2 class="text-h5 mt-5">Build your learning journey</h2>
          <p class="text-medium-emphasis mt-3">Choose tasks, arrange the path, and add a learning goal.</p>
          <v-btn color="primary" class="mt-5" prepend-icon="mdi-plus" :disabled="!ready" @click="openTaskPicker">Add your first tasks</v-btn>
        </div>
      </section>
    </div>

    <LearningPathTaskPicker v-model="pickerDialog" :tasks="tasks" :steps="draft.steps" :loading="loadingTasks" @add="addTasks" />
    <LearningPathSurveyPicker v-model="surveyPickerDialog" :surveys="surveyList" :steps="draft.steps" :loading="loadingTasks" @add="addSurveys" />
    <v-dialog v-model="settingsDialog" max-width="600"
      ><v-card title="Path settings"
        ><v-card-text
          ><v-textarea v-model="draft.description" label="Description" rows="3" variant="outlined" maxlength="5000" /><v-switch v-model="draft.published" label="Published" color="primary" hide-details />
          <p class="text-caption text-medium-emphasis mb-3">Published paths are available to learners. At least one activity is required.</p>
          <v-switch v-model="draft.archived" label="Archived" hide-details />
          <p class="text-caption text-medium-emphasis">Archived paths cannot start new runs. Changes are saved with the template.</p></v-card-text
        ><v-card-actions><v-spacer /><v-btn @click="settingsDialog = false">Done</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="releaseDialog" max-width="560"
      ><v-card title="Change task release"
        ><v-card-text
          ><p class="text-body-2 mb-4">The selected release is fixed when a learner starts a new run. Existing runs keep their original releases.</p>
          <v-select v-model="pendingVersion" :items="selectedVersions.map((version) => ({ title: `${version.releaseName} (v${version.versionNumber})`, value: version.id }))" label="Task release" variant="outlined" :loading="Boolean(loadingVersions)" /><v-alert v-if="!selectedVersions.length && !loadingVersions" type="info" variant="tonal">No accessible releases found.</v-alert></v-card-text
        ><v-card-actions><v-btn @click="releaseDialog = false">Cancel</v-btn><v-spacer /><v-btn color="primary" :disabled="!pendingVersion || !selectedVersions.some((version) => version.id === pendingVersion)" @click="applyRelease">Use release</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog
      :model-value="Boolean(removeId)"
      max-width="560"
      @update:model-value="
        (value) => {
          if (!value) removeId = null
        }
      "
      ><v-card title="Remove this step?"
        ><v-card-text
          ><template v-if="dependents.length"
            ><p class="mb-3">Update these tasks first. Their rules still reference this step:</p>
            <v-list density="compact"><v-list-item v-for="step in dependents" :key="step.id" :title="step.title" append-icon="mdi-arrow-right" @click="editDependent(step.id)" /></v-list
          ></template>
          <p v-else>Existing runs keep this activity and their learner work.</p></v-card-text
        ><v-card-actions><v-btn @click="removeId = null">Cancel</v-btn><v-spacer /><v-btn color="error" :disabled="Boolean(dependents.length)" @click="confirmRemove">Remove step</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="previewDialog" max-width="1100" scrollable
      ><v-card
        ><v-card-title class="d-flex align-center">{{ draft.name || 'Path preview' }}<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Close path preview" @click="previewDialog = false" /></v-card-title
        ><v-card-text
          ><v-alert type="info" variant="tonal" density="compact" class="mb-4">Preview of a new learner’s run. Select an available chest or treasure map to edit its settings.</v-alert
          ><TreasurePathBoard
            :run="previewRun"
            busy=""
            @open="
              (step) => {
                previewDialog = false
                selectStep(step.id)
              }
            " /></v-card-text></v-card
    ></v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import ChallengeConfigEditor from '@/components/learningPaths/ChallengeConfigEditor.vue'
import LearningPathAvailability from '@/components/learningPaths/LearningPathAvailability.vue'
import LearningPathTaskPicker from '@/components/learningPaths/LearningPathTaskPicker.vue'
import LearningPathSurveyPicker from '@/components/learningPaths/LearningPathSurveyPicker.vue'
import TreasurePathBoard from '@/components/learningPaths/TreasurePathBoard.vue'
import paths, { type PathRun, type PathStep, type PathTemplate } from '@/services/learningPaths'
import surveys, { type Survey } from '@/services/surveys'
import taskService from '@/services/task/task.service'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
import { availabilitySummary, conditionSummary, validatePathSteps } from '@/utils/learningPathEditor'

const route = useRoute(),
  router = useRouter()
const draft = ref<PathTemplate>({ id: '', name: '', description: '', published: false, archived: false, revision: 0, updatedAt: null, steps: [] })
const tasks = ref<Task[]>([]),
  versions = ref<Record<string, TaskVersionInfo[]>>({})
const selectedId = ref<string | null>(null),
  selected = computed(() => draft.value.steps.find((step) => step.id === selectedId.value) ?? null)
const selectedIndex = computed(() => draft.value.steps.findIndex((step) => step.id === selectedId.value))
const busy = ref(false),
  loading = ref(true),
  loadingTasks = ref(true),
  ready = ref(false),
  error = ref(''),
  saved = ref(''),
  attempted = ref(false)
const showDetail = ref(false),
  detailHeading = ref<HTMLElement | null>(null),
  orderNotice = ref('')
const openTaskPicker = () => {
  pickerDialog.value = true
}
const surveyList = ref<Survey[]>([])
const surveyOptions = computed(() => surveyList.value.filter((item) => item.activeReleaseId).map((item) => ({ title: item.title, value: item.id })))
const surveyPickerDialog = ref(false)
const addSurveys = (ids: string[]) => {
  if (draft.value.steps.length + ids.length > 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  let first: string | null = null
  for (const id of ids) {
    const survey = surveyList.value.find((item) => item.id === id)
    if (!survey?.activeReleaseId) continue
    const step: PathStep = { id: crypto.randomUUID(), type: 'survey', title: survey.title, taskVersion: null, surveyId: id, required: true, unlock: { mode: 'sequence', conditions: [] }, challenge: null }
    draft.value.steps.push(step)
    first ??= step.id
  }
  surveyPickerDialog.value = false
  if (first) void selectStep(first)
}
const chooseSurvey = (id: string) => {
  if (!selected.value) return
  selected.value.surveyId = id
}
const pickerDialog = ref(false),
  settingsDialog = ref(false),
  releaseDialog = ref(false),
  previewDialog = ref(false),
  removeId = ref<string | null>(null)
const pendingVersion = ref<string | null>(null),
  loadingVersions = ref('')
const dirty = computed(() => ready.value && saved.value !== JSON.stringify(draft.value))
const issues = computed(() => {
  if (!attempted.value) return {}
  const result = validatePathSteps(draft.value.steps)
  if (draft.value.published && !loadingTasks.value) {
    for (const step of draft.value.steps) {
      if (step.type !== 'survey' && tasks.value.find((task) => task.id === step.taskVersion?.taskId)?.visibility !== 'published') {
        ;(result[step.id] ??= []).push('Publish the source task and make sure it is not archived before publishing this path.')
      }
    }
  }
  return result
})
const dependents = computed(() => draft.value.steps.filter((step) => step.id !== removeId.value && step.unlock.conditions.some((condition) => condition.stepId === removeId.value)))
const selectedVersions = computed(() => (selected.value?.taskVersion ? versions.value[selected.value.taskVersion.taskId] ?? [] : []))
const message = (e: unknown) => (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The action could not be completed.'
const taskName = (step: PathStep) => tasks.value.find((task) => task.id === step.taskVersion?.taskId)?.name ?? step.title
const releaseLabel = (step: PathStep) => {
  const version = versions.value[step.taskVersion?.taskId ?? '']?.find((version) => version.id === step.taskVersion?.versionId)
  return version ? `${version.releaseName} · v${version.versionNumber}` : tasks.value.find((task) => task.id === step.taskVersion?.taskId)?.latestReleaseId === step.taskVersion?.versionId ? 'Latest release' : 'Saved release'
}
const selectStep = async (id: string) => {
  selectedId.value = id
  showDetail.value = true
  await nextTick()
  detailHeading.value?.focus({ preventScroll: true })
}
const addTasks = (ids: string[]) => {
  if (draft.value.steps.length + ids.length > 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  let first: string | null = null
  for (const id of ids) {
    const task = tasks.value.find((task) => task.id === id)
    if (!task?.latestReleaseId) continue
    const step: PathStep = { id: crypto.randomUUID(), title: task.name, taskVersion: { taskId: id, versionId: task.latestReleaseId }, unlock: { mode: 'sequence', conditions: [] }, challenge: null }
    draft.value.steps.push(step)
    first ??= step.id
  }
  pickerDialog.value = false
  if (first) void selectStep(first)
}
const onReorder = () => {
  orderNotice.value = 'Display order changed. Existing prerequisite links were kept.'
}
const move = (index: number, delta: number) => {
  const [step] = draft.value.steps.splice(index, 1)
  draft.value.steps.splice(index + delta, 0, step)
  onReorder()
}
const duplicate = (source: PathStep) => {
  if (draft.value.steps.length >= 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  const step: PathStep = { ...JSON.parse(JSON.stringify(source)), id: crypto.randomUUID(), title: `${source.title.slice(0, 249)} (copy)`, unlock: { mode: 'sequence', conditions: [] } }
  draft.value.steps.splice(draft.value.steps.findIndex((item) => item.id === source.id) + 1, 0, step)
  orderNotice.value = 'Task duplicated. The copy becomes available after the original task is completed.'
  void selectStep(step.id)
}
const editDependent = (id: string) => {
  removeId.value = null
  void selectStep(id)
}
const confirmRemove = () => {
  if (!removeId.value || dependents.value.length) return
  const index = draft.value.steps.findIndex((step) => step.id === removeId.value)
  if (index < 0) return
  const wasSelected = selectedId.value === removeId.value
  draft.value.steps.splice(index, 1)
  removeId.value = null
  if (wasSelected) {
    selectedId.value = draft.value.steps[Math.min(index, draft.value.steps.length - 1)]?.id ?? null
    if (!selectedId.value) showDetail.value = false
  }
}
const pendingLoads = new Map<string, Promise<void>>()
const loadVersions = async (taskId: string) => {
  if (versions.value[taskId]) return
  if (pendingLoads.has(taskId)) return pendingLoads.get(taskId)
  const request = (async () => {
    loadingVersions.value = taskId
    try {
      const result: TaskVersionInfo[] = []
      for (let skip = 0; ; ) {
        const page = (await taskService.listVersions(taskId, skip, 100)).data
        result.push(...page.items.filter((version) => version.kind === 'release'))
        skip += page.items.length
        if (skip >= page.total || !page.items.length) break
      }
      versions.value[taskId] = result
    } catch (e) {
      error.value = message(e)
    } finally {
      pendingLoads.delete(taskId)
      if (loadingVersions.value === taskId) loadingVersions.value = ''
    }
  })()
  pendingLoads.set(taskId, request)
  return request
}
const openReleaseDialog = async () => {
  if (!selected.value) return
  pendingVersion.value = selected.value.taskVersion!.versionId
  releaseDialog.value = true
  await loadVersions(selected.value.taskVersion!.taskId)
}
const applyRelease = () => {
  if (selected.value && pendingVersion.value && selectedVersions.value.some((version) => version.id === pendingVersion.value)) selected.value.taskVersion!.versionId = pendingVersion.value
  releaseDialog.value = false
}
watch(
  () => selected.value?.taskVersion?.taskId,
  (id) => {
    if (id) void loadVersions(id)
  }
)
const save = async () => {
  if (busy.value || !ready.value) return
  attempted.value = true
  error.value = ''
  if (!draft.value.name.trim()) {
    error.value = 'Give your learning path a title.'
    return
  }
  if (draft.value.published && !draft.value.steps.length) {
    error.value = 'Add at least one activity before publishing.'
    settingsDialog.value = true
    return
  }
  const invalid = Object.keys(issues.value)[0]
  if (invalid) {
    error.value = 'Review the highlighted task settings before saving.'
    await selectStep(invalid)
    return
  }
  busy.value = true
  try {
    // Keep edits made during the request; the returned revision is still needed for the next save.
    const submitted = JSON.stringify(draft.value)
    const result = (await paths.save(JSON.parse(submitted))).data
    if (JSON.stringify(draft.value) === submitted) draft.value = result
    else {
      draft.value.id = result.id
      draft.value.revision = result.revision
      draft.value.updatedAt = result.updatedAt
    }
    saved.value = JSON.stringify(result)
    await router.replace(`/learning-path-templates/${result.id}/edit`)
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
  }
}
const previewRun = computed<PathRun>(() => ({
  id: 'template-preview',
  templateRevision: draft.value.revision,
  templateId: draft.value.id,
  name: draft.value.name,
  description: draft.value.description,
  completed: 0,
  total: draft.value.steps.length,
  progress: 0,
  steps: draft.value.steps.map((step, index) => {
    if (step.unlock.mode === 'sequence') {
      const waiting = draft.value.steps.slice(0, index).some((item) => item.type !== 'survey' || item.required !== false)
      return { ...step, modelId: null, status: waiting ? 'locked' : 'available', availableAt: null, reasons: waiting ? ['After all previous required activities are completed'] : [] }
    }
    const satisfied = step.unlock.conditions.map((condition) => (condition.type === 'at' ? Boolean(condition.at && Date.parse(condition.at) <= Date.now()) : condition.type === 'after' && !condition.stepId && condition.seconds === 0))
    const available = !satisfied.length || (step.unlock.mode === 'all' ? satisfied.every(Boolean) : satisfied.some(Boolean))
    return { ...step, modelId: null, status: available ? 'available' : 'locked', availableAt: null, reasons: step.unlock.conditions.map((condition) => conditionSummary(condition, draft.value.steps)) }
  })
}))
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    if (route.params.id) draft.value = (await paths.template(String(route.params.id))).data
    saved.value = JSON.stringify(draft.value)
    ready.value = true
    selectedId.value = draft.value.steps[0]?.id ?? null
  } catch (e) {
    error.value = message(e)
  } finally {
    loading.value = false
  }
  loadingTasks.value = true
  try {
    const result: Task[] = []
    for (let skip = 0; ; ) {
      const page = (await taskService.list(skip, 100)).data
      result.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    tasks.value = result
    const questionnaires: Survey[] = []
    for (let skip = 0; ; ) {
      const page = (await surveys.list(skip)).data
      questionnaires.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    surveyList.value = questionnaires
  } catch (e) {
    error.value = message(e)
  } finally {
    loadingTasks.value = false
  }
}
const beforeUnload = (event: BeforeUnloadEvent) => {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onBeforeRouteLeave(() => !dirty.value || window.confirm('Discard unsaved changes?'))
onMounted(() => {
  void load()
  window.addEventListener('beforeunload', beforeUnload)
})
onUnmounted(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.editor-header {
  position: sticky;
  top: var(--v-layout-top, 64px);
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0 20px;
  margin-bottom: 16px;
  background: rgb(var(--v-theme-background));
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
}
.header-title {
  min-width: 180px;
  flex: 1;
}
.overview-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: rgb(var(--v-theme-on-surface), 0.65);
  text-decoration: none;
  font-size: 0.78rem;
}
.header-title h1 {
  line-height: 1.4;
}
.path-name {
  max-width: 540px;
}
.path-name :deep(input) {
  font-size: 1.4rem;
  font-weight: 650;
  padding-top: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.save-state {
  font-size: 0.72rem;
  opacity: 0.65;
}
.published-note {
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface), 0.65);
}
.editor-grid {
  display: grid;
  grid-template-columns: minmax(270px, 340px) minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}
.path-sidebar {
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08);
}
.step-list {
  min-height: 12px;
}
.step-row {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 12px 8px 12px 4px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.07);
  border-left: 3px solid transparent;
}
.step-row--active {
  background: rgb(var(--v-theme-primary), 0.08);
  border-left-color: rgb(var(--v-theme-primary));
}
.step-row--error {
  border-left-color: rgb(var(--v-theme-error));
}
.step-row--ghost {
  opacity: 0.4;
}
.step-handle {
  color: rgb(var(--v-theme-on-surface), 0.35);
  cursor: grab;
}
.step-select {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  flex: 1;
  text-align: left;
  border-radius: 6px;
  padding: 3px 1px;
}
.step-select:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 3px;
}
.step-number {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 25px;
  height: 25px;
  border-radius: 8px;
  background: rgb(var(--v-theme-on-surface), 0.06);
  font-size: 0.75rem;
  font-weight: 700;
}
.step-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-copy strong {
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}
.step-copy > span {
  font-size: 0.69rem;
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 225px;
}
.step-copy .step-challenge {
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.85;
}
.sidebar-add {
  margin: 8px 0;
}
.sidebar-empty {
  padding: 30px 18px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
}
.step-details {
  min-width: 0;
  padding: 24px 28px 32px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
}
.detail-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.detail-heading h2:focus {
  outline: none;
}
.task-source {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgb(var(--v-theme-on-surface), 0.035);
}
.task-source strong,
.task-source span {
  display: block;
  font-size: 0.75rem;
  overflow-wrap: anywhere;
}
.task-source span {
  opacity: 0.6;
  font-size: 0.7rem;
  margin-top: 2px;
}
.detail-empty {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 30px;
}
.mobile-back {
  display: none;
}
@media (max-width: 1000px) {
  .editor-header {
    flex-wrap: wrap;
    position: static;
  }
  .header-actions {
    justify-content: flex-start;
  }
  .editor-grid {
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 16px;
  }
  .step-details {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .editor-grid {
    display: block;
  }
  .step-details {
    display: none;
  }
  .editor-grid--detail .path-sidebar {
    display: none;
  }
  .editor-grid--detail .step-details {
    display: block;
  }
  .mobile-back {
    display: inline-flex;
  }
  .step-copy > span {
    max-width: 65vw;
  }
  .header-actions {
    gap: 4px;
  }
  .save-state {
    flex-basis: 100%;
  }
  .task-source {
    flex-wrap: wrap;
  }
}
</style>
