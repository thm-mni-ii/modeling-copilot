import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { cloneJson, createEmptyModelSnapshot, normalizeModelSnapshot, type ModelSnapshot } from '@/model/ModelSnapshot'
import languageService from '@/services/language/language.service'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { DiagramTask } from '@/model/Task'
import { languageReferenceKey, resolveWorkspaceLanguages, type ResolvedLanguageVersion } from '@/services/model/workspaceLanguageResolver'
import type { ApiId, JsonObject, LanguageVersionReference, TaskVersionReference } from '@/services/api/types/common'
import type { Model, ModelPatch, ModelVersion, ModelVersionKind, WorkspaceLanguageReference } from '@/services/api/types/model'
import type { Task, TaskVersion } from '@/services/api/types/task'
import { readDraft, removeDraft, writeDraft } from '@/utils/workspaceDrafts'
import { applyModelPatches, createModelPatch } from '@/utils/modelPatches'
import { serverNow, synchronizeServerTime } from '@/utils/serverTime'

export type WorkspaceLanguage = WorkspaceLanguageReference
export type ModelSyncState = 'synced' | 'dirty' | 'saving' | 'offline' | 'conflict'

export interface WorkspaceDiagramLanguage extends DiagramLanguage {
  id: ApiId
  name: string
  language: ResolvedLanguageVersion['language']
  version: ResolvedLanguageVersion['version']
}

const selectedLanguagesFrom = (version: ModelVersion): WorkspaceLanguage[] => cloneJson(version.workspaceLanguages)

const dirtySyncState = (): ModelSyncState => (typeof navigator === 'undefined' || navigator.onLine ? 'dirty' : 'offline')
const responseStatus = (error: unknown) => (error as { response?: { status?: number } }).response?.status

export const useModelWorkspaceStore = defineStore('modelWorkspace', () => {
  const model = ref<Model | null>(null)
  const baseVersionId = ref<ApiId | null>(null)
  const baseReleaseId = ref<ApiId | null>(null)
  const pendingPatches = ref<ModelPatch[]>([])
  const languages = ref<WorkspaceLanguage[]>([])
  const effectiveLanguages = ref<LanguageVersionReference[]>([])
  const languageDefinitions = ref<Record<string, ResolvedLanguageVersion>>({})
  const data = ref<ModelSnapshot>(createEmptyModelSnapshot('Untitled model'))
  const pendingPreferences = ref<JsonObject>({})
  const taskReference = ref<TaskVersionReference | null>(null)
  const task = ref<Task | null>(null)
  const taskVersion = ref<TaskVersion | null>(null)
  const taskContentHtml = ref('')
  const dirty = ref(false)
  const syncState = ref<ModelSyncState>('synced')

  let initialDraftKey: string | null = null
  let preferenceSave = Promise.resolve()

  const draftKey = computed(() => model.value?.id ?? 'new-model')
  const preferences = computed<JsonObject>(() => model.value?.preferences ?? pendingPreferences.value)
  const canRelease = computed(() => Boolean(model.value && baseVersionId.value) && !dirty.value && pendingPatches.value.length === 0 && syncState.value === 'synced')
  const resolvedLanguages = computed(() => effectiveLanguages.value.map((reference) => languageDefinitions.value[languageReferenceKey(reference)]).filter((entry): entry is ResolvedLanguageVersion => Boolean(entry)))
  const editorLanguages = computed<WorkspaceDiagramLanguage[]>(() =>
    resolvedLanguages.value.map(({ language, version }) => ({
      ...version.data,
      id: language.id,
      name: language.name,
      language,
      version
    }))
  )
  const diagramTask = computed<DiagramTask | null>(() =>
    task.value && taskVersion.value
      ? {
          id: task.value.id,
          title: task.value.name,
          content: taskVersion.value.data.contentHtml,
          createdAt: taskVersion.value.createdAt,
          updatedAt: taskVersion.value.createdAt
        }
      : null
  )

  const loadAssignedTask = async (reference: TaskVersionReference | null, annotations?: JsonObject | null) => {
    taskReference.value = reference ? cloneJson(reference) : null
    if (!reference) {
      task.value = null
      taskVersion.value = null
      taskContentHtml.value = ''
      return
    }
    const [loadedTask, loadedVersion] = await Promise.all([taskService.get(reference.taskId), taskService.getVersion(reference.taskId, reference.versionId)])
    task.value = loadedTask.data
    taskVersion.value = loadedVersion.data
    taskContentHtml.value = typeof annotations?.contentHtml === 'string' ? annotations.contentHtml : loadedVersion.data.data.contentHtml
  }

  const loadLanguages = async (references: LanguageVersionReference[]) => {
    const resolved = await resolveWorkspaceLanguages(references)
    effectiveLanguages.value = resolved.references
    languageDefinitions.value = resolved.definitions
  }

  const applyVersion = async (version: ModelVersion, modelName: string) => {
    languages.value = selectedLanguagesFrom(version)
    data.value = normalizeModelSnapshot(version.data, modelName)
    baseReleaseId.value = version.kind === 'release' ? version.id : version.baseReleaseId
    await Promise.all([loadLanguages(version.workspaceLanguages), loadAssignedTask(version.taskVersion, version.annotations)])
  }

  const persistJournal = async () => {
    if (!dirty.value) return
    const metadata: JsonObject = cloneJson(data.value)
    delete metadata.xml
    try {
      await writeDraft({
        key: draftKey.value,
        modelId: model.value?.id ?? null,
        baseVersionId: baseVersionId.value,
        baseReleaseId: baseReleaseId.value,
        savedAt: new Date().toISOString(),
        patches: cloneJson(pendingPatches.value),
        languages: cloneJson(languages.value),
        data: metadata
      })
    } catch {
      // localStorage may be unavailable; server persistence remains usable.
    }
  }

  const markDirty = () => {
    dirty.value = true
    syncState.value = dirtySyncState()
    void persistJournal()
  }

  const setData = (next: JsonObject) => {
    const name = model.value?.name ?? (typeof next.name === 'string' ? next.name : data.value.name)
    const normalized = normalizeModelSnapshot(next, name)
    if (JSON.stringify(normalized) === JSON.stringify(data.value)) return
    if (normalized.xml !== data.value.xml) {
      const xml = createModelPatch(data.value.xml, normalized.xml)
      if (xml) pendingPatches.value.push({ createdAt: new Date(serverNow()).toISOString(), xml })
    }
    data.value = normalized
    markDirty()
  }

  const resetIdentity = () => {
    model.value = null
    baseVersionId.value = null
    baseReleaseId.value = null
    pendingPatches.value = []
    pendingPreferences.value = {}
    taskReference.value = null
    task.value = null
    taskVersion.value = null
    taskContentHtml.value = ''
    initialDraftKey = null
  }

  const startNew = async (name: string, initialLanguages: WorkspaceLanguage[], initialTask: TaskVersionReference | null = null) => {
    resetIdentity()
    void synchronizeServerTime().catch(() => undefined)
    languages.value = cloneJson(initialLanguages)
    data.value = createEmptyModelSnapshot(name)
    await Promise.all([loadLanguages(initialLanguages), loadAssignedTask(initialTask)])
    markDirty()
  }

  const load = async (modelId: ApiId, versionId?: ApiId) => {
    const currentModel = (await modelService.get(modelId)).data
    const targetVersionId = versionId ?? currentModel.latestVersionId
    if (!targetVersionId) throw new Error('This model has no saved version yet.')

    const version = (await modelService.getVersion(modelId, targetVersionId)).data
    void synchronizeServerTime().catch(() => undefined)
    model.value = currentModel
    pendingPreferences.value = currentModel.preferences
    baseVersionId.value = version.id
    initialDraftKey = null
    await applyVersion(version, currentModel.name)
    pendingPatches.value = []
    dirty.value = false
    syncState.value = 'synced'
  }

  const addLanguage = async (languageId: ApiId, versionId?: ApiId) => {
    const language = (await languageService.get(languageId)).data
    const selectedVersionId = versionId ?? language.latestVersionId
    if (!selectedVersionId) throw new Error('The selected language has no version.')
    if (languages.value.some((item) => item.languageId === languageId)) return

    const updatedLanguages: WorkspaceLanguage[] = [...languages.value, { languageId, versionId: selectedVersionId, source: 'additional' }]
    await loadLanguages(updatedLanguages)
    languages.value = updatedLanguages
    markDirty()
  }

  const changeLanguageVersion = async (languageId: ApiId, versionId: ApiId) => {
    const index = languages.value.findIndex((item) => item.languageId === languageId)
    if (index < 0 || languages.value[index].versionId === versionId) return
    if (languages.value[index].source === 'required') throw new Error('Task languages cannot be changed.')

    // TODO: Validate compatibility and migrate existing model elements before changing a language release.
    const updatedLanguages = cloneJson(languages.value)
    updatedLanguages[index] = { ...updatedLanguages[index], versionId }
    await loadLanguages(updatedLanguages)
    languages.value = updatedLanguages
    markDirty()
  }

  const removeLanguage = async (languageId: ApiId) => {
    if (languages.value.some((item) => item.languageId === languageId && item.source === 'required')) throw new Error('Task languages cannot be removed.')
    const updatedLanguages = languages.value.filter((item) => item.languageId !== languageId)
    if (updatedLanguages.length === languages.value.length) return
    await loadLanguages(updatedLanguages)
    languages.value = updatedLanguages
    markDirty()
  }

  const moveLanguage = async (languageId: ApiId, offset: -1 | 1) => {
    const from = languages.value.findIndex((item) => item.languageId === languageId)
    const to = from + offset
    if (from < 0 || to < 0 || to >= languages.value.length) return
    const updatedLanguages = cloneJson(languages.value)
    const [moved] = updatedLanguages.splice(from, 1)
    updatedLanguages.splice(to, 0, moved)
    await loadLanguages(updatedLanguages)
    languages.value = updatedLanguages
    markDirty()
  }

  const rename = async (name: string) => {
    if (!model.value) throw new Error('No model is loaded.')
    const updated = (await modelService.update(model.value.id, { name: name.trim() })).data
    model.value = updated
    data.value = { ...data.value, name: updated.name }
    markDirty()
  }

  const updatePreferences = (preferences: JsonObject) => {
    pendingPreferences.value = preferences
    if (!model.value) return
    const modelId = model.value.id
    model.value = { ...model.value, preferences }
    preferenceSave = preferenceSave
      .catch(() => undefined)
      .then(async () => {
        const updated = (await modelService.update(modelId, { preferences })).data
        if (model.value?.id === modelId && model.value.preferences === preferences) {
          model.value = updated
        }
      })
    return preferenceSave
  }

  const restoreSnapshot = async (snapshotData: JsonObject, snapshotLanguages: WorkspaceLanguage[]) => {
    if (!model.value) throw new Error('No model is loaded.')
    const currentModel = await modelService.get(model.value.id)
    if (!currentModel.data.latestVersionId) throw new Error('This model has no current version.')
    const latest = (await modelService.getVersion(model.value.id, currentModel.data.latestVersionId)).data
    model.value = currentModel.data
    baseVersionId.value = currentModel.data.latestVersionId
    pendingPatches.value = []
    await applyVersion(latest, currentModel.data.name)
    dirty.value = false
    syncState.value = 'synced'
    languages.value = cloneJson(snapshotLanguages)
    await loadLanguages(snapshotLanguages)
    setData(snapshotData)
    if (!dirty.value) markDirty()
  }

  const branchSnapshot = async (snapshotData: JsonObject, snapshotLanguages: WorkspaceLanguage[], name: string) => {
    resetIdentity()
    languages.value = cloneJson(snapshotLanguages)
    data.value = normalizeModelSnapshot(snapshotData, name)
    data.value = { ...data.value, name }
    await loadLanguages(snapshotLanguages)
    markDirty()
  }

  const branchVersion = async (modelId: ApiId, versionId: ApiId, name: string) => {
    const snapshot = (await modelService.getVersion(modelId, versionId)).data
    await branchSnapshot(snapshot.data, selectedLanguagesFrom(snapshot), name)
    await loadAssignedTask(snapshot.taskVersion, snapshot.annotations)
  }

  const updateTaskContent = (contentHtml: string) => {
    if (!taskReference.value || contentHtml === taskContentHtml.value) return
    taskContentHtml.value = contentHtml
    markDirty()
  }

  const save = async (kind: ModelVersionKind = 'checkpoint', releaseName?: string, description?: string) => {
    if (kind === 'release' && !releaseName?.trim()) throw new Error('A release needs a name.')
    if (kind === 'release' && (dirty.value || pendingPatches.value.length > 0)) {
      throw new Error('Save the latest checkpoint before creating a release.')
    }
    syncState.value = 'saving'

    try {
      let currentModel = model.value
      if (!currentModel) {
        initialDraftKey ??= draftKey.value
        currentModel = (await modelService.create({ name: data.value.name, taskVersion: taskReference.value })).data
        model.value = currentModel
        if (Object.keys(pendingPreferences.value).length > 0) {
          currentModel = (await modelService.update(currentModel.id, { preferences: pendingPreferences.value })).data
          model.value = currentModel
        }
      }

      data.value = { ...data.value, name: currentModel.name }
      const actualKind: ModelVersionKind = baseVersionId.value ? kind : 'release'
      const patchCut = cloneJson(pendingPatches.value)
      const dataCut = cloneJson(data.value)
      const languagesCut = cloneJson(languages.value)
      const checkpointData: JsonObject = { ...dataCut }
      delete checkpointData.xml
      const savedVersion = (
        await modelService.createVersion(currentModel.id, {
          baseVersionId: baseVersionId.value,
          baseReleaseId: actualKind === 'checkpoint' ? baseReleaseId.value : null,
          workspaceLanguages: languagesCut,
          taskVersion: taskReference.value,
          data: actualKind === 'release' ? dataCut : checkpointData,
          patches: actualKind === 'checkpoint' ? patchCut : [],
          annotations: taskReference.value ? { contentHtml: taskContentHtml.value } : null,
          kind: actualKind,
          ...(actualKind === 'release' ? { releaseName: kind === 'release' ? releaseName!.trim() : 'Initial release', description: description?.trim() || null } : {})
        })
      ).data

      baseVersionId.value = savedVersion.id
      baseReleaseId.value = savedVersion.kind === 'release' ? savedVersion.id : savedVersion.baseReleaseId
      pendingPatches.value.splice(0, patchCut.length)
      dirty.value = pendingPatches.value.length > 0 || JSON.stringify(data.value) !== JSON.stringify(dataCut) || JSON.stringify(languages.value) !== JSON.stringify(languagesCut)
      syncState.value = dirty.value ? dirtySyncState() : 'synced'
      const journalKeys = [...new Set([initialDraftKey, draftKey.value].filter((key): key is string => Boolean(key)))]
      if (dirty.value) await persistJournal()
      else await Promise.all(journalKeys.map(removeDraft))
      initialDraftKey = null
      return savedVersion
    } catch (error: unknown) {
      syncState.value = responseStatus(error) === 409 ? 'conflict' : dirtySyncState()
      throw error
    }
  }

  const getRecoveryDraft = async () => {
    const draft = await readDraft(draftKey.value)
    if (!draft || !Array.isArray(draft.patches) || !Array.isArray(draft.languages)) return null
    if (draft.modelId && draft.modelId !== model.value?.id) return null
    if (draft.baseVersionId !== baseVersionId.value) return null
    return draft
  }
  const getRecoverySnapshot = async (): Promise<ModelSnapshot | null> => {
    const draft = await getRecoveryDraft()
    if (!draft) return null
    const xml = applyModelPatches(data.value.xml, draft.patches)
    return normalizeModelSnapshot({ ...draft.data, xml }, model.value?.name ?? data.value.name)
  }
  const discardRecoveryDraft = () => removeDraft(draftKey.value)
  const restoreRecoveryDraft = async () => {
    const draft = await getRecoveryDraft()
    if (!draft) return false
    const xml = applyModelPatches(data.value.xml, draft.patches)
    languages.value = cloneJson(draft.languages) as unknown as WorkspaceLanguage[]
    data.value = normalizeModelSnapshot({ ...draft.data, xml }, model.value?.name ?? data.value.name)
    baseReleaseId.value = draft.baseReleaseId
    pendingPatches.value = cloneJson(draft.patches)
    await loadLanguages(languages.value)
    dirty.value = true
    syncState.value = dirtySyncState()
    await persistJournal()
    return true
  }

  return {
    model,
    preferences,
    languages,
    data,
    dirty,
    syncState,
    baseVersionId,
    baseReleaseId,
    pendingPatches,
    canRelease,
    editorLanguages,
    taskReference,
    task,
    taskVersion,
    taskContentHtml,
    diagramTask,
    startNew,
    load,
    addLanguage,
    changeLanguageVersion,
    removeLanguage,
    moveLanguage,
    rename,
    updatePreferences,
    restoreSnapshot,
    branchSnapshot,
    branchVersion,
    updateTaskContent,
    setData,
    save,
    getRecoveryDraft,
    getRecoverySnapshot,
    discardRecoveryDraft,
    restoreRecoveryDraft
  }
})
