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
import type { Model, ModelPatch, ModelVersion, ModelVersionInfo, ModelVersionKind, TaskEditDocument, TaskEditPatch, WorkspaceLanguageReference } from '@/services/api/types/model'
import type { Task, TaskVersion } from '@/services/api/types/task'
import { readDraft, removeDraft, writeDraft } from '@/utils/workspaceDrafts'
import { applyModelPatches, createModelPatch } from '@/utils/modelPatches'
import { serverNow, synchronizeServerTime } from '@/utils/serverTime'
import type { TaskEditSyncState } from '@/utils/taskEdits'
import { applyJsonPatches, createJsonPatch } from '@/utils/jsonPatches'
import { loadTaskEditHistory } from '@/utils/taskEditTimeline'

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
const TASK_EDIT_SAVE_BATCH_SIZE = 100
const releaseState = (snapshot: ModelSnapshot, languages: WorkspaceLanguage[], taskDocument: JsonObject | null) => JSON.stringify([snapshot.xml, snapshot.name, languages, taskDocument])

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
  const taskEdit = ref<TaskEditDocument | null>(null)
  const taskEditDirty = ref(false)
  const pendingTaskEditPatches = ref<TaskEditPatch[]>([])
  const taskEditError = ref<string | null>(null)
  const taskEditSyncState = ref<TaskEditSyncState>('synced')
  const dirty = ref(false)
  const syncState = ref<ModelSyncState>('synced')
  const savedReleaseState = ref<string | null>(null)
  const versionSavePending = ref(false)
  const releasePending = ref(false)

  let initialDraftKey: string | null = null
  let preferenceSave = Promise.resolve()
  let taskEditSave: Promise<TaskEditDocument | null> | null = null
  let taskEditGeneration = 0

  const draftKey = computed(() => model.value?.id ?? 'new-model')
  const preferences = computed<JsonObject>(() => model.value?.preferences ?? pendingPreferences.value)
  const saving = computed(() => versionSavePending.value || releasePending.value)
  const hasReleaseChanges = computed(() => savedReleaseState.value !== null && savedReleaseState.value !== releaseState(data.value, languages.value, taskEdit.value?.document ?? null))
  const canRelease = computed(() => Boolean(model.value && baseVersionId.value) && hasReleaseChanges.value && !saving.value && syncState.value !== 'conflict' && syncState.value !== 'offline' && taskEditSyncState.value !== 'conflict')
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

  const loadAssignedTask = async (reference: TaskVersionReference | null) => {
    taskReference.value = reference ? cloneJson(reference) : null
    if (!reference) {
      task.value = null
      taskVersion.value = null
      return
    }
    const [loadedTask, loadedVersion] = await Promise.all([taskService.get(reference.taskId), taskService.getVersion(reference.taskId, reference.versionId)])
    task.value = loadedTask.data
    taskVersion.value = loadedVersion.data
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
    await Promise.all([loadLanguages(version.workspaceLanguages), loadAssignedTask(version.taskVersion)])
  }

  const rememberRelease = (version: ModelVersion, modelName: string) => {
    const snapshot = normalizeModelSnapshot(version.data, typeof version.data.name === 'string' ? version.data.name : modelName)
    savedReleaseState.value = releaseState(snapshot, version.workspaceLanguages, version.taskEditSnapshot?.document ?? null)
  }

  const loadReleaseState = async (currentModel: Model, version: ModelVersion) => {
    savedReleaseState.value = null
    const release = version.kind === 'release' ? version : version.baseReleaseId ? (await modelService.getVersion(currentModel, version.baseReleaseId)).data : null
    if (release) rememberRelease(release, currentModel.name)
  }

  const persistJournal = async () => {
    if (!dirty.value && !taskEditDirty.value) return
    const metadata: JsonObject = cloneJson(data.value)
    delete metadata.xml
    try {
      await writeDraft({
        key: draftKey.value,
        modelId: model.value?.id ?? null,
        modelDirty: dirty.value,
        baseVersionId: baseVersionId.value,
        baseReleaseId: baseReleaseId.value,
        savedAt: new Date().toISOString(),
        patches: cloneJson(pendingPatches.value),
        languages: cloneJson(languages.value),
        data: metadata,
        taskEdit: cloneJson(taskEdit.value),
        taskEditPatches: pendingTaskEditPatches.value.map(({ id, createdAt, operations }) => ({ id, createdAt, operations: cloneJson(operations) })),
        taskEditBaseDocument: cloneJson(model.value?.taskEdit?.document ?? taskVersion.value?.data.contentDocument ?? {})
      })
    } catch {
      taskEditError.value = 'The local recovery draft could not be written. Save your changes before closing this page.'
    }
  }

  // Nur für geteilte Modelle: collab-kit speichert jede Änderung, ein Checkpoint oder Release eines anderen
  // im Raum wird so die eigene Basis; es bleiben nur die Patches danach, wie nach dem eigenen Save.
  const rebaseOnVersion = async (version: ModelVersionInfo) => {
    if (baseVersionId.value === version.id) return
    baseVersionId.value = version.id
    baseReleaseId.value = version.kind === 'release' ? version.id : version.baseReleaseId
    const since = Date.parse(version.createdAt)
    pendingPatches.value = pendingPatches.value.filter((patch) => Date.parse(patch.createdAt) > since)
    dirty.value = pendingPatches.value.length > 0
    syncState.value = dirty.value ? dirtySyncState() : 'synced'
    if (dirty.value || taskEditDirty.value) await persistJournal()
    else await removeDraft(draftKey.value)
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
    taskEditGeneration++
    taskEditSave = null
    pendingTaskEditPatches.value = []
    taskEditError.value = null
    model.value = null
    baseVersionId.value = null
    baseReleaseId.value = null
    savedReleaseState.value = null
    pendingPatches.value = []
    pendingPreferences.value = {}
    taskReference.value = null
    task.value = null
    taskVersion.value = null
    taskEdit.value = null
    taskEditDirty.value = false
    taskEditSyncState.value = 'synced'
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
    savedReleaseState.value = null
    taskEditGeneration++
    taskEditSave = null
    const currentModel = (await modelService.get(modelId)).data
    const version = (await modelService.getVersion(currentModel, versionId ?? currentModel.latestVersionId)).data
    void synchronizeServerTime().catch(() => undefined)
    model.value = currentModel
    taskEdit.value = cloneJson(currentModel.taskEdit)
    pendingTaskEditPatches.value = []
    taskEditError.value = null
    taskEditDirty.value = false
    taskEditSyncState.value = 'synced'
    pendingPreferences.value = currentModel.preferences
    baseVersionId.value = version.id
    initialDraftKey = null
    await applyVersion(version, currentModel.name)
    await loadReleaseState(currentModel, version)
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

    // TODO: Validate existing model elements against the selected language release.
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
    const latest = (await modelService.getVersion(currentModel.data, currentModel.data.latestVersionId)).data
    model.value = currentModel.data
    baseVersionId.value = latest.id
    pendingPatches.value = []
    await applyVersion(latest, currentModel.data.name)
    await loadReleaseState(currentModel.data, latest)
    dirty.value = false
    syncState.value = 'synced'
    languages.value = cloneJson(snapshotLanguages)
    await loadLanguages(snapshotLanguages)
    setData(snapshotData)
    if (!dirty.value) markDirty()
  }

  const branchSnapshot = async (snapshotData: JsonObject, snapshotLanguages: WorkspaceLanguage[], name: string, snapshotTask: TaskVersionReference | null = null, snapshotTaskEdit: TaskEditDocument | null = null) => {
    resetIdentity()
    languages.value = cloneJson(snapshotLanguages)
    data.value = normalizeModelSnapshot(snapshotData, name)
    data.value = { ...data.value, name }
    await loadLanguages(snapshotLanguages)
    await loadAssignedTask(snapshotTask)
    if (snapshotTaskEdit) updateTaskEditDocument(snapshotTaskEdit.document)
    markDirty()
  }

  const branchVersion = async (sourceModel: Model, versionId: ApiId, name: string) => {
    const snapshot = (await modelService.getVersion(sourceModel, versionId)).data
    await branchSnapshot(snapshot.data, selectedLanguagesFrom(snapshot), name, snapshot.taskVersion, snapshot.taskEditSnapshot)
  }

  const updateTaskEditDocument = (document: JsonObject) => {
    if (!taskReference.value) return
    if (taskEdit.value && JSON.stringify(taskEdit.value.document) === JSON.stringify(document)) return
    const previous = taskEdit.value?.document ?? taskVersion.value?.data.contentDocument
    if (!previous) throw new Error('The task document has not finished loading.')
    const operations = createJsonPatch(previous, document)
    if (!operations.length) return
    const createdAt = new Date().toISOString()
    pendingTaskEditPatches.value.push({ id: crypto.randomUUID(), createdAt, document: cloneJson(document), operations: cloneJson(operations) })
    taskEdit.value = {
      schemaVersion: 1,
      versionId: taskEdit.value?.versionId ?? null,
      revision: taskEdit.value?.revision ?? 0,
      updatedAt: createdAt,
      document: cloneJson(document)
    }
    taskEditDirty.value = true
    if (!taskEditSave) taskEditSyncState.value = dirtySyncState()
    taskEditError.value = null
    void persistJournal()
  }

  const syncTaskEdit = (): Promise<TaskEditDocument | null> => {
    if (taskEditSave) return taskEditSave
    if (!model.value || !taskEdit.value || !pendingTaskEditPatches.value.length) return Promise.resolve(taskEdit.value)
    const modelId = model.value.id
    const generation = taskEditGeneration
    let baseRevision = taskEdit.value.revision
    const patches = cloneJson(pendingTaskEditPatches.value)
    taskEditSyncState.value = 'saving'
    taskEditError.value = null
    const request = (async () => {
      try {
        let saved: TaskEditDocument | null = null
        for (let offset = 0; offset < patches.length; offset += TASK_EDIT_SAVE_BATCH_SIZE) {
          const batch = patches.slice(offset, offset + TASK_EDIT_SAVE_BATCH_SIZE)
          saved = (await modelService.updateTaskEdit(modelId, { baseRevision, patches: batch })).data
          if (model.value?.id !== modelId || generation !== taskEditGeneration) return saved
          baseRevision = saved.revision
          const sentIds = new Set(batch.map((patch) => patch.id))
          pendingTaskEditPatches.value = pendingTaskEditPatches.value.filter((patch) => !sentIds.has(patch.id))
          taskEditDirty.value = pendingTaskEditPatches.value.length > 0
          taskEdit.value = taskEditDirty.value && taskEdit.value
            ? { ...taskEdit.value, versionId: saved.versionId, revision: saved.revision }
            : saved
          model.value = { ...model.value, taskEdit: saved }
          if (dirty.value || taskEditDirty.value) await persistJournal()
          else await removeDraft(draftKey.value)
        }
        taskEditSyncState.value = taskEditDirty.value ? dirtySyncState() : 'synced'
        return saved
      } catch (error) {
        if (model.value?.id === modelId && generation === taskEditGeneration) {
          taskEditSyncState.value = responseStatus(error) === 409 ? 'conflict' : dirtySyncState()
          taskEditError.value = (error as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'Task edits could not be saved. Your local editing actions have been retained.'
          await persistJournal()
        }
        throw error
      }
    })()
    taskEditSave = request
    void request.finally(() => { if (taskEditSave === request) taskEditSave = null }).catch(() => undefined)
    return request
  }

  const adoptTaskEditSnapshot = (snapshot: TaskEditDocument) => updateTaskEditDocument(snapshot.document)

  const save = async (kind: ModelVersionKind = 'checkpoint', releaseName?: string, description?: string) => {
    if (versionSavePending.value) throw new Error('A model version is already being saved.')
    if (kind === 'release' && !releaseName?.trim()) throw new Error('A release needs a name.')
    if (kind === 'release' && !hasReleaseChanges.value) throw new Error('Change the model before creating another release.')
    if (kind === 'release' && (dirty.value || pendingPatches.value.length > 0)) {
      throw new Error('Save the latest checkpoint before creating a release.')
    }
    versionSavePending.value = true
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

      await syncTaskEdit()
      currentModel = model.value ?? currentModel

      data.value = { ...data.value, name: currentModel.name }
      const actualKind: ModelVersionKind = baseVersionId.value ? kind : 'release'
      const patchCut = cloneJson(pendingPatches.value)
      const dataCut = cloneJson(data.value)
      const languagesCut = cloneJson(languages.value)
      const checkpointData: JsonObject = { ...dataCut }
      delete checkpointData.xml
      const savedVersion = (
        await modelService.createVersion(currentModel, {
          baseVersionId: baseVersionId.value,
          taskEditVersionId: currentModel.taskEdit?.versionId ?? null,
          baseReleaseId: actualKind === 'checkpoint' ? baseReleaseId.value : null,
          workspaceLanguages: languagesCut,
          taskVersion: taskReference.value,
          data: actualKind === 'release' ? dataCut : checkpointData,
          patches: actualKind === 'checkpoint' ? patchCut : [],
          kind: actualKind,
          ...(actualKind === 'release' ? { releaseName: kind === 'release' ? releaseName!.trim() : 'Initial release', description: description?.trim() || null } : {})
        })
      ).data

      baseVersionId.value = savedVersion.id
      baseReleaseId.value = savedVersion.kind === 'release' ? savedVersion.id : savedVersion.baseReleaseId
      if (savedVersion.kind === 'release') rememberRelease(savedVersion, currentModel.name)
      pendingPatches.value.splice(0, patchCut.length)
      dirty.value = pendingPatches.value.length > 0 || JSON.stringify(data.value) !== JSON.stringify(dataCut) || JSON.stringify(languages.value) !== JSON.stringify(languagesCut)
      syncState.value = dirty.value ? dirtySyncState() : 'synced'
      const journalKeys = [...new Set([initialDraftKey, draftKey.value].filter((key): key is string => Boolean(key)))]
      if (dirty.value || taskEditDirty.value) await persistJournal()
      else await Promise.all(journalKeys.map(removeDraft))
      initialDraftKey = null
      return savedVersion
    } catch (error: unknown) {
      syncState.value = responseStatus(error) === 409 ? 'conflict' : dirtySyncState()
      throw error
    } finally {
      versionSavePending.value = false
    }
  }

  const release = async (name?: string) => {
    if (!canRelease.value || !model.value) throw new Error('Change the model before creating another release.')
    releasePending.value = true
    const currentModel = model.value
    try {
      let releaseName = name?.trim()
      if (!releaseName) {
        let count = 0
        let skip = 0
        let total = 0
        do {
          const page = (await modelService.listVersions(currentModel, skip, 100)).data
          count += page.items.filter((version) => version.kind === 'release').length
          skip += page.items.length
          total = page.total
          if (!page.items.length) break
        } while (skip < total)
        releaseName = `V${count + 1}`
      }
      if (model.value?.id !== currentModel.id) throw new Error('The active model changed before releasing.')
      // Preserve editing steps before adding the full release snapshot.
      while (dirty.value || taskEditDirty.value) await save()
      return await save('release', releaseName)
    } finally {
      releasePending.value = false
    }
  }

  const getRecoveryDraft = async () => {
    const draft = await readDraft(draftKey.value)
    if (!draft || !Array.isArray(draft.patches) || !Array.isArray(draft.languages)) return null
    if (draft.modelId && draft.modelId !== model.value?.id) return null
    if (draft.baseVersionId !== baseVersionId.value && !draft.taskEditPatches?.length) return null
    return draft
  }
  const getRecoverySnapshot = async (): Promise<ModelSnapshot | null> => {
    const draft = await getRecoveryDraft()
    if (!draft) return null
    if (draft.baseVersionId !== baseVersionId.value) return cloneJson(data.value)
    const xml = applyModelPatches(data.value.xml, draft.patches)
    return normalizeModelSnapshot({ ...draft.data, xml }, model.value?.name ?? data.value.name)
  }
  const discardRecoveryDraft = () => removeDraft(draftKey.value)
  const restoreRecoveryDraft = async () => {
    const draft = await getRecoveryDraft()
    if (!draft) return false
    if (draft.baseVersionId === baseVersionId.value && draft.modelDirty !== false) {
      const xml = applyModelPatches(data.value.xml, draft.patches)
      languages.value = cloneJson(draft.languages) as unknown as WorkspaceLanguage[]
      data.value = normalizeModelSnapshot({ ...draft.data, xml }, model.value?.name ?? data.value.name)
      baseReleaseId.value = draft.baseReleaseId
      pendingPatches.value = cloneJson(draft.patches)
      dirty.value = true
      syncState.value = dirtySyncState()
    }
    if (draft.taskEdit && draft.taskEditPatches?.length && taskReference.value && draft.taskEditBaseDocument) {
      const sameRevision = draft.taskEdit.revision === (taskEdit.value?.revision ?? 0)
      const savedIds = new Set(!sameRevision && model.value ? (await loadTaskEditHistory(model.value.id)).map((event) => event.id) : [])
      let recovered = draft.taskEditBaseDocument
      let previous = taskEdit.value?.document ?? taskVersion.value!.data.contentDocument!
      pendingTaskEditPatches.value = draft.taskEditPatches.map((patch) => {
        recovered = applyJsonPatches(recovered, patch.operations)
        if (savedIds.has(patch.id)) return null
        const next = { ...cloneJson(patch), id: sameRevision ? patch.id : crypto.randomUUID(), document: recovered, operations: sameRevision ? patch.operations : createJsonPatch(previous, recovered) }
        previous = recovered
        return next
      }).filter((patch): patch is TaskEditPatch => Boolean(patch?.operations.length))
      taskEditDirty.value = pendingTaskEditPatches.value.length > 0
      if (taskEditDirty.value) {
        const revision = taskEdit.value?.revision ?? 0
        taskEdit.value = { ...cloneJson(draft.taskEdit), versionId: taskEdit.value?.versionId ?? null, revision, document: cloneJson(pendingTaskEditPatches.value[pendingTaskEditPatches.value.length - 1].document) }
      }
      taskEditSyncState.value = taskEditDirty.value ? dirtySyncState() : 'synced'
    }

    await loadLanguages(languages.value)
    if (dirty.value || taskEditDirty.value) await persistJournal()
    else await removeDraft(draftKey.value)
    return true
  }

  return {
    model,
    preferences,
    languages,
    data,
    dirty,
    syncState,
    saving,
    baseVersionId,
    baseReleaseId,
    pendingPatches,
    rebaseOnVersion,
    canRelease,
    editorLanguages,
    taskReference,
    task,
    taskVersion,
    taskEdit,
    taskEditDirty,
    pendingTaskEditPatches,
    taskEditError,
    taskEditSyncState,
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
    updateTaskEditDocument,
    syncTaskEdit,
    adoptTaskEditSnapshot,
    setData,
    save,
    release,
    getRecoveryDraft,
    getRecoverySnapshot,
    discardRecoveryDraft,
    restoreRecoveryDraft
  }
})
