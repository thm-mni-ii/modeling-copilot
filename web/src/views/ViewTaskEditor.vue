<template>
  <v-container fluid class="pa-3 task-view-container">
    <div class="d-flex align-center mb-3 ga-2">
      <div>
        <h1 class="text-h5">Tasks</h1>
        <p class="text-medium-emphasis mb-0">Shared, versioned tasks for all administrators.</p>
      </div>
      <v-spacer />
      <v-btn prepend-icon="mdi-plus" color="primary" @click="openCreate">New task</v-btn>
    </div>

    <div class="task-layout">
      <v-card class="task-sidebar" variant="outlined">
        <v-card-text class="pa-2">
          <v-text-field v-model="query" label="Search tasks" density="compact" prepend-inner-icon="mdi-magnify" clearable hide-details @update:model-value="searchTasks" />
        </v-card-text>
        <div class="task-scope-grid" role="tablist" aria-label="Task filters">
          <v-btn :color="taskScope === 'mine' ? 'primary' : undefined" :variant="taskScope === 'mine' ? 'tonal' : 'text'" @click="setTaskScope('mine')">My Tasks</v-btn>
          <v-btn :color="taskScope === 'all' ? 'primary' : undefined" :variant="taskScope === 'all' ? 'tonal' : 'text'" @click="setTaskScope('all')">All Tasks</v-btn>
          <v-btn :color="taskScope === 'archive' ? 'primary' : undefined" :variant="taskScope === 'archive' ? 'tonal' : 'text'" @click="setTaskScope('archive')">Archive</v-btn>
        </div>
        <div class="task-legend px-3 py-2">
          <span><i class="task-owner-dot task-owner-dot--mine" />My task</span>
          <span><i class="task-owner-dot task-owner-dot--other" />Others</span>
        </div>
        <v-divider />
        <v-list density="compact" nav class="task-list">
          <v-list-item v-for="task in tasks" :key="task.id" :active="task.id === currentTask?.id" color="primary" rounded="lg" @click="selectTask(task)">
            <template #prepend>
              <span class="task-owner-dot" :class="isOwnTask(task) ? 'task-owner-dot--mine' : 'task-owner-dot--other'" />
              <v-icon size="18">mdi-clipboard-text-outline</v-icon>
            </template>
            <v-list-item-title>{{ task.name }}</v-list-item-title>
            <v-list-item-subtitle>
              <span>{{ ownerLabel(task.ownerId) }}</span>
              <span class="mx-1">·</span>
              <span>{{ task.visibility === 'published' ? 'Published' : 'Private' }}</span>
              <span v-if="task.latestReleaseCreatedBy" class="d-block">Release by {{ ownerLabel(task.latestReleaseCreatedBy) }}</span>
            </v-list-item-subtitle>
            <template #append>
              <v-icon :color="task.visibility === 'published' ? 'success' : 'warning'" :title="task.visibility === 'published' ? 'Published for task users' : 'Private admin workspace'">
                {{ task.visibility === 'published' ? 'mdi-earth' : 'mdi-lock-outline' }}
              </v-icon>
            </template>
          </v-list-item>
          <v-list-item v-if="!loading && tasks.length === 0" disabled title="No tasks available." />
        </v-list>
      </v-card>

      <v-card v-if="currentTask" class="task-editor" variant="outlined">
        <v-card-title class="d-flex align-center ga-2">
          <v-text-field v-model="titleModel" label="Task name" density="compact" variant="outlined" hide-details @blur="saveMetadata" />
          <v-chip v-if="currentVersion" size="small" :color="currentVersion.kind === 'release' ? 'success' : 'warning'" variant="tonal">
            {{ versionLabel(currentVersion) }}
          </v-chip>
          <v-chip size="small" variant="tonal" prepend-icon="mdi-account-outline">Owner: {{ ownerLabel(currentTask.ownerId) }}</v-chip>
          <v-chip v-if="currentVersion?.kind === 'release'" size="small" variant="tonal" prepend-icon="mdi-account-check-outline">Release by {{ ownerLabel(currentVersion.createdBy) }}</v-chip>
          <v-btn icon="mdi-source-branch" variant="text" title="Create branch" :disabled="!currentVersion" @click="branchTask" />
          <v-btn :icon="visibilityIcon(visibilityModel)" :color="visibilityColor(visibilityModel)" variant="tonal" :title="visibilityModel === 'published' ? 'Published — click to make private' : 'Private — click to publish'" @click="toggleVisibility" />
          <v-btn :icon="currentTask.archivedAt ? 'mdi-archive-arrow-up-outline' : 'mdi-archive-outline'" variant="text" :title="currentTask.archivedAt ? 'Restore task' : 'Archive task'" @click="toggleArchiveTask" />
        </v-card-title>
        <v-divider />
        <v-card-text class="task-editor-content">
          <div class="task-settings">
            <div class="task-setting-field">
              <span id="task-workspace-languages-label" class="task-setting-field__label">Workspace languages</span>
              <v-select v-model="selectedLanguageKeys" :items="languageOptions" aria-labelledby="task-workspace-languages-label" multiple chips closable-chips density="compact" variant="outlined" hide-details @update:model-value="loadSelectedLanguages" />
            </div>
            <div class="task-behavior-field">
              <span id="task-modeling-behavior-label" class="task-setting-field__label">Modeling behavior</span>
              <AutonomyControls :mode="autonomyMode" @update:mode="autonomyMode = $event" />
            </div>
            <div class="task-setting-field">
              <span id="task-sample-solutions-label" class="task-setting-field__label">Sample solution releases</span>
              <v-select v-model="selectedSolutionKeys" :items="solutionOptions" aria-labelledby="task-sample-solutions-label" multiple chips closable-chips density="compact" variant="outlined" hide-details />
            </div>
          </div>

          <TaskRichEditor v-model="contentModel" :element-options="elementOptions" :connection-options="connectionOptions" class="task-rich-editor" />

          <div class="d-flex align-center ga-2 mt-3">
            <v-select v-model="selectedVersionId" :items="versionOptions" label="Loaded version" density="compact" variant="outlined" hide-details class="version-select" @update:model-value="loadVersion" />
            <v-spacer />
            <v-btn :loading="saving" variant="tonal" prepend-icon="mdi-content-save-outline" @click="saveVersion('checkpoint')">Save checkpoint</v-btn>
            <v-btn :loading="saving" color="primary" prepend-icon="mdi-tag-outline" @click="releaseDialog = true">Create release</v-btn>
          </div>
        </v-card-text>
      </v-card>

      <v-card v-else class="task-editor d-flex align-center justify-center" variant="outlined">
        <div class="text-center text-medium-emphasis">
          <v-icon size="48">mdi-clipboard-text-outline</v-icon>
          <div class="mt-2">Select a task or create a new one.</div>
        </div>
      </v-card>
    </div>

    <v-dialog v-model="createDialog" max-width="520">
      <v-card>
        <v-card-title>Create task</v-card-title>
        <v-card-text><v-text-field v-model="newTaskName" label="Task name" autofocus @keyup.enter="createTask" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="createDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!newTaskName.trim()" @click="createTask">Create</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="releaseDialog" max-width="560">
      <v-card>
        <v-card-title>Create task release</v-card-title>
        <v-card-text>
          <v-text-field v-model="releaseName" label="Release name" autofocus />
          <v-textarea v-model="releaseDescription" label="Description (optional)" rows="2" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="releaseDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!releaseName.trim()" @click="saveVersion('release')">Release</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import TaskRichEditor from '@/components/tasks/TaskRichEditor.vue'
import { buildTaskConnectionOptions, buildTaskElementOptions, type TaskOptionLanguage } from '@/components/tasks/taskEditorExtensions'
import AutonomyControls from '@/components/modeling/controls/AutonomyControls.vue'
import type { AutonomyMode } from '@/model/Autonomy'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import languageService from '@/services/language/language.service'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import { useUserStore } from '@/stores/userStore'
import type { LanguageOverview, LanguageVersion } from '@/services/api/types/language'
import type { ModelVersionReference } from '@/services/api/types/common'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { Task, TaskVersion, TaskVersionInfo, TaskVersionKind, TaskVisibility } from '@/services/api/types/task'
import { notifyError } from '@/composables/useNotifications'

const tasks = ref<Task[]>([])
const currentTask = ref<Task | null>(null)
const currentVersion = ref<TaskVersion | null>(null)
const versions = ref<TaskVersionInfo[]>([])
const languages = ref<LanguageOverview[]>([])
const availableLanguageOptions = ref<{ title: string; value: string }[]>([])
const loadedLanguages = ref<Record<string, LanguageVersion<DiagramLanguage>>>({})
const solutionOptions = ref<{ title: string; value: string }[]>([])
const query = ref('')
const taskScope = ref<'mine' | 'all' | 'archive'>('mine')
const loading = ref(false)
const saving = ref(false)
const titleModel = ref('')
const contentModel = ref('')
const autonomyMode = ref<AutonomyMode>('free')
const selectedLanguageKeys = ref<string[]>([])
const selectedSolutionKeys = ref<string[]>([])
const selectedVersionId = ref<string | null>(null)
const createDialog = ref(false)
const newTaskName = ref('')
const releaseDialog = ref(false)
const releaseName = ref('')
const releaseDescription = ref('')
const visibilityModel = ref<TaskVisibility>('private')
const userStore = useUserStore()

const versionReferenceKey = (entityId: string, versionId: string) => `${entityId}:${versionId}`
const parseReferenceKey = (value: string) => {
  const separator = value.indexOf(':')
  return { entityId: value.slice(0, separator), versionId: value.slice(separator + 1) }
}
const languageOptions = computed(() => availableLanguageOptions.value)
const versionOptions = computed(() => versions.value.map((version) => ({ title: versionLabel(version), value: version.id })))
const selectedTaskLanguages = computed<TaskOptionLanguage[]>(() =>
  selectedLanguageKeys.value.flatMap((key) => {
    const version = loadedLanguages.value[key]
    if (!version) return []
    const { entityId: languageId } = parseReferenceKey(key)
    const languageName = languages.value.find((item) => item.id === languageId)?.name ?? languageId
    return [
      {
        id: languageId,
        name: languageName,
        elements: version.data.elements,
        connections: version.data.connections
      }
    ]
  })
)
const elementOptions = computed(() => buildTaskElementOptions(selectedTaskLanguages.value))
const connectionOptions = computed(() => buildTaskConnectionOptions(selectedTaskLanguages.value))
const isOwnTask = (task: Task) => task.ownerId === userStore.userId
const ownerLabel = (ownerId: string | null | undefined) => ownerId || 'System catalog'
const visibilityIcon = (visibility: TaskVisibility) => (visibility === 'published' ? 'mdi-earth' : 'mdi-lock-outline')
const visibilityColor = (visibility: TaskVisibility) => (visibility === 'published' ? 'success' : 'warning')

const versionLabel = (version: TaskVersionInfo) => (version.kind === 'release' ? `${version.releaseName} · v${version.versionNumber}` : `Checkpoint · v${version.versionNumber}`)
const workspaceLanguages = (): WorkspaceLanguageReference[] =>
  selectedLanguageKeys.value.map((key) => {
    const { entityId: languageId, versionId } = parseReferenceKey(key)
    return { languageId, versionId, source: 'required' }
  })
const sampleSolutions = (): ModelVersionReference[] =>
  selectedSolutionKeys.value.map((key) => {
    const { entityId: modelId, versionId } = parseReferenceKey(key)
    return { modelId, versionId }
  })

const loadTasks = async () => {
  loading.value = true
  try {
    tasks.value = (
      await taskService.list(0, 100, {
        q: query.value || undefined,
        archived: taskScope.value === 'archive',
        mine: taskScope.value === 'mine'
      })
    ).data.items
  } catch {
    notifyError('Tasks could not be loaded.')
  } finally {
    loading.value = false
  }
}
const setTaskScope = (scope: 'mine' | 'all' | 'archive') => {
  if (taskScope.value === scope) return
  taskScope.value = scope
  void loadTasks()
}
let searchTimer: ReturnType<typeof setTimeout> | undefined
const searchTasks = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadTasks(), 250)
}
const selectTask = async (task: Task) => {
  currentTask.value = task
  titleModel.value = task.name
  visibilityModel.value = task.visibility
  versions.value = (await taskService.listVersions(task.id, 0, 100)).data.items
  const target = task.latestVersionId ?? versions.value[0]?.id ?? null
  selectedVersionId.value = target
  if (target) await loadVersion(target)
  else resetEditor()
}
const resetEditor = () => {
  currentVersion.value = null
  contentModel.value = '<p></p>'
  autonomyMode.value = 'free'
  selectedLanguageKeys.value = []
  selectedSolutionKeys.value = []
}
const loadVersion = async (versionId: string | null) => {
  if (!currentTask.value || !versionId) return
  const version = (await taskService.getVersion(currentTask.value.id, versionId)).data
  currentVersion.value = version
  selectedVersionId.value = version.id
  contentModel.value = version.data.contentHtml
  autonomyMode.value = version.data.autonomyMode
  selectedLanguageKeys.value = version.workspaceLanguages.map((item) => versionReferenceKey(item.languageId, item.versionId))
  selectedSolutionKeys.value = version.data.sampleSolutions.map((item) => versionReferenceKey(item.modelId, item.versionId))
  await loadSelectedLanguages()
}
const loadSelectedLanguages = async () => {
  await Promise.all(
    selectedLanguageKeys.value.map(async (key) => {
      if (loadedLanguages.value[key]) return
      const { entityId: languageId, versionId } = parseReferenceKey(key)
      loadedLanguages.value[key] = (await languageService.getVersion<DiagramLanguage>(languageId, versionId)).data
    })
  )
}
const openCreate = () => {
  newTaskName.value = ''
  createDialog.value = true
}
const createTask = async () => {
  if (!newTaskName.value.trim()) return
  try {
    const task = (await taskService.create({ name: newTaskName.value.trim() })).data
    createDialog.value = false
    await loadTasks()
    await selectTask(task)
  } catch {
    notifyError('The task could not be created.')
  }
}
const saveMetadata = async () => {
  if (!currentTask.value || !titleModel.value.trim() || titleModel.value.trim() === currentTask.value.name) return
  try {
    currentTask.value = (await taskService.update(currentTask.value.id, { name: titleModel.value.trim() })).data
    await loadTasks()
  } catch {
    notifyError('The task name could not be saved.')
  }
}
const saveVisibility = async () => {
  if (!currentTask.value || visibilityModel.value === currentTask.value.visibility) return
  try {
    currentTask.value = (await taskService.update(currentTask.value.id, { visibility: visibilityModel.value })).data
    await loadTasks()
  } catch {
    visibilityModel.value = currentTask.value.visibility
    notifyError('The task visibility could not be saved.')
  }
}
const toggleVisibility = () => {
  visibilityModel.value = visibilityModel.value === 'published' ? 'private' : 'published'
  void saveVisibility()
}
const saveVersion = async (kind: TaskVersionKind) => {
  if (!currentTask.value) return
  saving.value = true
  try {
    const saved = (
      await taskService.createVersion(currentTask.value.id, {
        baseVersionId: currentTask.value.latestVersionId,
        kind,
        ...(kind === 'release' ? { releaseName: releaseName.value.trim(), description: releaseDescription.value.trim() || null } : {}),
        workspaceLanguages: workspaceLanguages(),
        data: { contentHtml: contentModel.value, autonomyMode: autonomyMode.value, sampleSolutions: sampleSolutions() }
      })
    ).data
    currentTask.value = (await taskService.get(currentTask.value.id)).data
    visibilityModel.value = currentTask.value.visibility
    versions.value = (await taskService.listVersions(currentTask.value.id, 0, 100)).data.items
    currentVersion.value = saved
    selectedVersionId.value = saved.id
    releaseDialog.value = false
    releaseName.value = ''
    releaseDescription.value = ''
    await loadTasks()
  } catch (caught) {
    notifyError((caught as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The task version could not be saved.')
  } finally {
    saving.value = false
  }
}
const branchTask = async () => {
  if (!currentTask.value || !currentVersion.value) return
  try {
    const branch = (await taskService.create({ name: `${currentTask.value.name} – Branch`, parent: { taskId: currentTask.value.id, versionId: currentVersion.value.id } })).data
    await loadTasks()
    await selectTask(branch)
  } catch {
    notifyError('The task branch could not be created.')
  }
}
const toggleArchiveTask = async () => {
  if (!currentTask.value) return
  try {
    await taskService.update(currentTask.value.id, { archived: !currentTask.value.archivedAt })
    currentTask.value = null
    await loadTasks()
  } catch {
    notifyError('The task archive state could not be changed.')
  }
}
const loadCatalogs = async () => {
  languages.value = (await languageService.list(0, 100, { archived: false })).data.items
  const languageReleases = await Promise.all(languages.value.map(async (language) => ({ language, versions: (await languageService.listVersions(language.id, 0, 100)).data.items.filter((version) => version.kind === 'release') })))
  availableLanguageOptions.value = languageReleases.flatMap(({ language, versions: entries }) => entries.map((version) => ({ title: `${language.name} · ${version.releaseName ?? 'Release'} · v${version.versionNumber}`, value: versionReferenceKey(language.id, version.id) })))
  const models = (await modelService.list(0, 100, { archived: false })).data.items
  const releases = await Promise.all(models.map(async (model) => ({ model, versions: (await modelService.listVersions(model.id, 0, 100)).data.items.filter((version) => version.kind === 'release') })))
  solutionOptions.value = releases.flatMap(({ model, versions: entries }) => entries.map((version) => ({ title: `${model.name} · ${version.releaseName ?? `v${version.versionNumber}`}`, value: versionReferenceKey(model.id, version.id) })))
}

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

onMounted(async () => {
  try {
    await userStore.ensureGlobalRole()
    await Promise.all([loadTasks(), loadCatalogs()])
  } catch {
    notifyError('The task catalog could not be initialized.')
  }
})
</script>

<style scoped>
.task-view-container {
  height: calc(100vh - var(--v-layout-top, 0px));
  display: flex;
  flex-direction: column;
}
.task-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 12px;
}
.task-sidebar {
  width: 300px;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: stretch;
}
.task-list {
  flex: 1;
  overflow-y: auto;
  align-content: flex-start;
}
.task-list :deep(.v-list) {
  align-content: flex-start;
}
.task-scope-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(86px, 1fr));
  gap: 4px;
  padding: 6px 8px;
}
.task-scope-grid :deep(.v-btn) {
  min-width: 0;
  min-height: 36px;
  padding-inline: 6px;
  white-space: normal;
  line-height: 1.1;
  text-transform: none;
}
.task-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: 11px;
}
.task-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.task-owner-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  margin-right: 7px;
  border-radius: 50%;
  flex: 0 0 9px;
}
.task-owner-dot--mine {
  background: rgb(var(--v-theme-primary));
}
.task-owner-dot--other {
  background: rgb(var(--v-theme-secondary));
}
.task-editor {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.task-editor-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.task-settings {
  display: grid;
  grid-template-columns: 2fr minmax(190px, 1fr) 2fr;
  gap: 10px;
  margin-bottom: 10px;
  align-items: start;
}
.task-setting-field,
.task-behavior-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.task-setting-field__label {
  color: rgba(var(--v-theme-on-surface), 0.66);
  font-size: 14px;
  line-height: 16px;
}
.task-behavior-field :deep(.autonomy-trigger) {
  justify-content: flex-start;
  width: 100%;
  min-height: 40px;
}
.task-rich-editor {
  flex: 1;
  min-height: 300px;
}
.version-select {
  max-width: 300px;
}
</style>
