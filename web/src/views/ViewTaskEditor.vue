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

    <v-alert v-if="error" type="error" closable class="mb-3" @click:close="error = null">{{ error }}</v-alert>

    <div class="task-layout">
      <v-card class="task-sidebar" variant="outlined">
        <v-card-text class="pa-2">
          <v-text-field v-model="query" label="Search tasks" density="compact" prepend-inner-icon="mdi-magnify" clearable hide-details @update:model-value="searchTasks" />
        </v-card-text>
        <v-tabs v-model="showArchived" density="compact" grow @update:model-value="loadTasks"><v-tab :value="false">Active</v-tab><v-tab :value="true">Archive</v-tab></v-tabs>
        <v-divider />
        <v-list density="compact" nav class="task-list">
          <v-list-item v-for="task in tasks" :key="task.id" :active="task.id === currentTask?.id" color="primary" rounded="lg" @click="selectTask(task)">
            <template #prepend><v-icon size="18">mdi-clipboard-text-outline</v-icon></template>
            <v-list-item-title>{{ task.name }}</v-list-item-title>
            <v-list-item-subtitle>{{ task.latestReleaseId ? 'Published' : 'Draft only' }}</v-list-item-subtitle>
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
          <v-btn icon="mdi-source-branch" variant="text" title="Create branch" :disabled="!currentVersion" @click="branchTask" />
          <v-btn :icon="currentTask.archivedAt ? 'mdi-archive-arrow-up-outline' : 'mdi-archive-outline'" variant="text" :title="currentTask.archivedAt ? 'Restore task' : 'Archive task'" @click="toggleArchiveTask" />
        </v-card-title>
        <v-divider />
        <v-card-text class="task-editor-content">
          <div class="task-settings">
            <v-select v-model="selectedLanguageKeys" :items="languageOptions" label="Workspace languages" multiple chips closable-chips density="compact" variant="outlined" hide-details @update:model-value="loadSelectedLanguages" />
            <v-select v-model="autonomyMode" :items="autonomyOptions" label="Modeling behavior" density="compact" variant="outlined" hide-details />
            <v-select v-model="selectedSolutionKeys" :items="solutionOptions" label="Sample solution releases" multiple chips closable-chips density="compact" variant="outlined" hide-details />
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
import { computed, onMounted, ref } from 'vue'
import TaskRichEditor, { type TaskConnectionOption, type TaskElementOption } from '@/components/tasks/TaskRichEditor.vue'
import { AUTONOMY_MODES, type AutonomyMode } from '@/model/Autonomy'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import languageService from '@/services/language/language.service'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import type { LanguageOverview, LanguageVersion } from '@/services/api/types/language'
import type { ModelVersionReference } from '@/services/api/types/common'
import type { WorkspaceLanguageReference } from '@/services/api/types/model'
import type { Task, TaskVersion, TaskVersionInfo, TaskVersionKind } from '@/services/api/types/task'

const tasks = ref<Task[]>([])
const currentTask = ref<Task | null>(null)
const currentVersion = ref<TaskVersion | null>(null)
const versions = ref<TaskVersionInfo[]>([])
const languages = ref<LanguageOverview[]>([])
const availableLanguageOptions = ref<{ title: string; value: string }[]>([])
const loadedLanguages = ref<Record<string, LanguageVersion<DiagramLanguage>>>({})
const solutionOptions = ref<{ title: string; value: string }[]>([])
const query = ref('')
const showArchived = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
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

const autonomyOptions = AUTONOMY_MODES.map((mode) => ({ title: mode.title, value: mode.value }))
const languageKey = (languageId: string, versionId: string) => `${languageId}:${versionId}`
const parseReferenceKey = (value: string) => {
  const separator = value.indexOf(':')
  return { first: value.slice(0, separator), second: value.slice(separator + 1) }
}
const languageOptions = computed(() => availableLanguageOptions.value)
const versionOptions = computed(() => versions.value.map((version) => ({ title: versionLabel(version), value: version.id })))
const elementOptions = computed<TaskElementOption[]>(() =>
  selectedLanguageKeys.value.flatMap((key) => {
    const version = loadedLanguages.value[key]
    const { first: languageId } = parseReferenceKey(key)
    const languageName = languages.value.find((item) => item.id === languageId)?.name ?? languageId
    return (version?.data.elements ?? []).map((element) => ({ languageId, elementType: element.type, label: `${languageName}: ${element.defaultLabel || element.type}`, element }))
  })
)
const connectionOptions = computed<TaskConnectionOption[]>(() =>
  selectedLanguageKeys.value.flatMap((key) => {
    const version = loadedLanguages.value[key]
    const { first: languageId } = parseReferenceKey(key)
    const languageName = languages.value.find((item) => item.id === languageId)?.name ?? languageId
    return (version?.data.connections ?? []).map((connection) => ({ languageId, connectionType: connection.type, label: `${languageName}: ${connection.label || connection.type}`, connection }))
  })
)

const versionLabel = (version: TaskVersionInfo) => (version.kind === 'release' ? `${version.releaseName} · v${version.versionNumber}` : `Checkpoint · v${version.versionNumber}`)
const workspaceLanguages = (): WorkspaceLanguageReference[] => selectedLanguageKeys.value.map((key) => {
  const { first: languageId, second: versionId } = parseReferenceKey(key)
  return { languageId, versionId, source: 'required' }
})
const sampleSolutions = (): ModelVersionReference[] => selectedSolutionKeys.value.map((key) => {
  const { first: modelId, second: versionId } = parseReferenceKey(key)
  return { modelId, versionId }
})

const loadTasks = async () => {
  loading.value = true
  try {
    tasks.value = (await taskService.list(0, 100, { q: query.value || undefined, archived: showArchived.value })).data.items
  } catch {
    error.value = 'Tasks could not be loaded.'
  } finally {
    loading.value = false
  }
}
let searchTimer: ReturnType<typeof setTimeout> | undefined
const searchTasks = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadTasks(), 250)
}
const selectTask = async (task: Task) => {
  currentTask.value = task
  titleModel.value = task.name
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
  selectedLanguageKeys.value = version.workspaceLanguages.map((item) => languageKey(item.languageId, item.versionId))
  selectedSolutionKeys.value = version.data.sampleSolutions.map((item) => languageKey(item.modelId, item.versionId))
  await loadSelectedLanguages()
}
const loadSelectedLanguages = async () => {
  await Promise.all(selectedLanguageKeys.value.map(async (key) => {
    if (loadedLanguages.value[key]) return
    const { first: languageId, second: versionId } = parseReferenceKey(key)
    loadedLanguages.value[key] = (await languageService.getVersion<DiagramLanguage>(languageId, versionId)).data
  }))
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
    error.value = 'The task could not be created.'
  }
}
const saveMetadata = async () => {
  if (!currentTask.value || !titleModel.value.trim() || titleModel.value.trim() === currentTask.value.name) return
  try {
    currentTask.value = (await taskService.update(currentTask.value.id, { name: titleModel.value.trim() })).data
    await loadTasks()
  } catch {
    error.value = 'The task name could not be saved.'
  }
}
const saveVersion = async (kind: TaskVersionKind) => {
  if (!currentTask.value) return
  saving.value = true
  try {
    const saved = (await taskService.createVersion(currentTask.value.id, {
      baseVersionId: currentTask.value.latestVersionId,
      kind,
      ...(kind === 'release' ? { releaseName: releaseName.value.trim(), description: releaseDescription.value.trim() || null } : {}),
      workspaceLanguages: workspaceLanguages(),
      data: { contentHtml: contentModel.value, autonomyMode: autonomyMode.value, sampleSolutions: sampleSolutions() }
    })).data
    currentTask.value = (await taskService.get(currentTask.value.id)).data
    versions.value = (await taskService.listVersions(currentTask.value.id, 0, 100)).data.items
    currentVersion.value = saved
    selectedVersionId.value = saved.id
    releaseDialog.value = false
    releaseName.value = ''
    releaseDescription.value = ''
    await loadTasks()
  } catch (caught) {
    error.value = (caught as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The task version could not be saved.'
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
    error.value = 'The task branch could not be created.'
  }
}
const toggleArchiveTask = async () => {
  if (!currentTask.value) return
  try {
    await taskService.update(currentTask.value.id, { archived: !currentTask.value.archivedAt })
    currentTask.value = null
    await loadTasks()
  } catch {
    error.value = 'The task archive state could not be changed.'
  }
}
const loadCatalogs = async () => {
  languages.value = (await languageService.list(0, 100, { archived: false })).data.items
  const languageReleases = await Promise.all(languages.value.map(async (language) => ({ language, versions: (await languageService.listVersions(language.id, 0, 100)).data.items.filter((version) => version.kind === 'release') })))
  availableLanguageOptions.value = languageReleases.flatMap(({ language, versions: entries }) => entries.map((version) => ({ title: `${language.name} · ${version.releaseName ?? 'Release'} · v${version.versionNumber}`, value: languageKey(language.id, version.id) })))
  const models = (await modelService.list(0, 100, { archived: false })).data.items
  const releases = await Promise.all(models.map(async (model) => ({ model, versions: (await modelService.listVersions(model.id, 0, 100)).data.items.filter((version) => version.kind === 'release') })))
  solutionOptions.value = releases.flatMap(({ model, versions: entries }) => entries.map((version) => ({ title: `${model.name} · ${version.releaseName ?? `v${version.versionNumber}`}`, value: languageKey(model.id, version.id) })))
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadCatalogs()])
})
</script>

<style scoped>
.task-view-container { height: calc(100vh - var(--v-layout-top, 0px)); display: flex; flex-direction: column; }
.task-layout { display: flex; flex: 1; min-height: 0; gap: 12px; }
.task-sidebar { width: 280px; min-width: 240px; display: flex; flex-direction: column; }
.task-list { flex: 1; overflow-y: auto; }
.task-editor { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.task-editor-content { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.task-settings { display: grid; grid-template-columns: 2fr 1fr 2fr; gap: 10px; margin-bottom: 10px; }
.task-rich-editor { flex: 1; min-height: 300px; }
.version-select { max-width: 300px; }
</style>
