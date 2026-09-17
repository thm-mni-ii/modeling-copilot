import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { DiagramConnection, DiagramElement, DiagramLanguage, DiagramSyntax } from '@/model/DiagramLanguage'
import type { FeedbackCanvasConfig, FeedbackTargetOverlays, FeedbackTargetType } from '@/model/Feedback'
import type { MultiplicityRelation, MultiplicityRelationState, MultiplicityRule } from '@/model/Syntax'
import languageService from '@/services/language/language.service'
import type { ApiId } from '@/services/api/types/common'
import type { Language, LanguageVersion, LanguageVersionKind, LanguageVersionInfo } from '@/services/api/types/language'
import { cloneFeedbackCanvasConfig, createDefaultTargetOverlays, ensureFeedbackTargets } from '@/utils/feedbackConfig'
import { notifyError } from '@/composables/useNotifications'

const DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE = 'The Connection {source} -> {target} with Connection type {connection} violates the cardinality ({min}..{max}).'

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

export const useDiagramLanguageStore = defineStore('diagramLanguage', () => {
  const language = ref<Language | null>(null)
  const currentVersion = ref<LanguageVersion<DiagramLanguage> | null>(null)
  const restoredFromVersion = ref<LanguageVersionInfo | null>(null)
  const savedSnapshot = ref<string | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)
  const reportError = (caught: unknown, fallback: string) => {
    const message = caught instanceof Error ? caught.message : fallback
    error.value = message
    notifyError(message)
  }

  const definition = computed(() => currentVersion.value?.data ?? null)
  const isDirty = computed(() => restoredFromVersion.value !== null || (definition.value !== null && savedSnapshot.value !== JSON.stringify(definition.value)))

  const loadLanguage = async (languageId: ApiId, versionId?: ApiId) => {
    loading.value = true
    error.value = null
    try {
      const loadedLanguage = (await languageService.get(languageId)).data
      const selectedVersionId = versionId ?? loadedLanguage.latestVersionId
      if (!selectedVersionId) throw new Error('This language has no saved version yet.')

      const loadedVersion = (await languageService.getVersion<DiagramLanguage>(languageId, selectedVersionId)).data
      language.value = loadedLanguage
      currentVersion.value = loadedVersion
      restoredFromVersion.value = null
      savedSnapshot.value = JSON.stringify(loadedVersion.data)
    } catch (caught) {
      reportError(caught, 'Failed to load diagram language.')
      throw caught
    } finally {
      loading.value = false
    }
  }

  const saveCurrentLanguage = async (kind: LanguageVersionKind = 'checkpoint', releaseName?: string, description?: string) => {
    if (!language.value || !currentVersion.value) throw new Error('No language version is loaded.')
    if (kind === 'release' && !releaseName?.trim()) throw new Error('A release needs a name.')

    saving.value = true
    error.value = null
    try {
      const savedVersion = (
        await languageService.createVersion<DiagramLanguage>(language.value.id, {
          baseVersionId: currentVersion.value.id,
          kind,
          ...(kind === 'release' ? { releaseName: releaseName!.trim(), description: description?.trim() || null } : {}),
          includedLanguageVersions: clone(currentVersion.value.includedLanguageVersions),
          data: clone(currentVersion.value.data)
        })
      ).data

      currentVersion.value = savedVersion
      language.value.latestVersionId = savedVersion.id
      restoredFromVersion.value = null
      savedSnapshot.value = JSON.stringify(savedVersion.data)
      return savedVersion
    } catch (caught) {
      reportError(caught, 'Failed to save diagram language.')
      throw caught
    } finally {
      saving.value = false
    }
  }

  const discardCurrentChanges = async () => {
    if (language.value && currentVersion.value) await loadLanguage(language.value.id, currentVersion.value.id)
  }

  const restoreVersion = async (versionId: ApiId) => {
    if (!language.value?.latestVersionId) throw new Error('This language has no saved version yet.')

    loading.value = true
    error.value = null
    try {
      const latestVersionId = language.value.latestVersionId
      const latestRequest = languageService.getVersion<DiagramLanguage>(language.value.id, latestVersionId)
      const snapshotRequest = versionId === latestVersionId ? latestRequest : languageService.getVersion<DiagramLanguage>(language.value.id, versionId)
      const [latestResponse, snapshotResponse] = await Promise.all([latestRequest, snapshotRequest])
      const latestVersion = latestResponse.data
      const snapshot = snapshotResponse.data

      currentVersion.value = { ...latestVersion, data: clone(snapshot.data) }
      restoredFromVersion.value = versionId === latestVersionId ? null : snapshot
      savedSnapshot.value = JSON.stringify(latestVersion.data)
    } catch (caught) {
      reportError(caught, 'Failed to restore the language version.')
      throw caught
    } finally {
      loading.value = false
    }
  }

  const synchronizeFeedbackTargets = () => {
    if (!definition.value) return null
    ensureFeedbackTargets(
      definition.value.feedback,
      'element',
      definition.value.elements.map((element) => element.type)
    )
    ensureFeedbackTargets(
      definition.value.feedback,
      'connection',
      definition.value.connections.map((connection) => connection.type)
    )
    return definition.value.feedback
  }

  const addElementToLanguage = (element: DiagramElement) => {
    if (!definition.value) return
    definition.value.elements.push(element)
    synchronizeFeedbackTargets()
  }

  const updateElementInLanguage = (elementType: string, updates: Partial<DiagramElement>) => {
    if (!definition.value) return
    const index = definition.value.elements.findIndex((element) => element.type === elementType)
    if (index < 0) return
    definition.value.elements[index] = { ...definition.value.elements[index], ...updates }
    synchronizeFeedbackTargets()
  }

  const removeElementFromLanguage = (elementType: string) => {
    if (!definition.value) return
    definition.value.elements = definition.value.elements.filter((element) => element.type !== elementType)
    synchronizeFeedbackTargets()
  }

  const addConnectionToLanguage = (connection: DiagramConnection) => {
    if (!definition.value) return
    definition.value.connections.push(connection)
    synchronizeFeedbackTargets()
  }

  const updateConnectionInLanguage = (connectionType: string, updates: Partial<DiagramConnection>) => {
    if (!definition.value) return
    const index = definition.value.connections.findIndex((connection) => connection.type === connectionType)
    if (index < 0) return
    definition.value.connections[index] = { ...definition.value.connections[index], ...updates }
    synchronizeFeedbackTargets()
  }

  const removeConnectionFromLanguage = (connectionType: string) => {
    if (!definition.value) return
    definition.value.connections = definition.value.connections.filter((connection) => connection.type !== connectionType)
    synchronizeFeedbackTargets()
  }

  const updateFeedbackEntryForLanguage = (targetType: FeedbackTargetType, targetKey: string, overlays: FeedbackTargetOverlays) => {
    const feedback = synchronizeFeedbackTargets()
    if (!feedback) return
    const entries = targetType === 'element' ? feedback.elements : feedback.connections
    entries[targetKey] = createDefaultTargetOverlays(overlays)
  }

  const updateFeedbackCanvasConfigForLanguage = (canvasConfig: FeedbackCanvasConfig) => {
    const feedback = synchronizeFeedbackTargets()
    if (feedback) feedback.canvas = cloneFeedbackCanvasConfig(canvasConfig)
  }

  const addSyntaxToLanguage = (syntax: DiagramSyntax) => {
    if (!definition.value) return
    const index = definition.value.syntax.findIndex((rule) => rule.ruleType === syntax.ruleType)
    if (index >= 0) definition.value.syntax[index] = syntax
    else definition.value.syntax.push(syntax)
  }

  const updateSyntaxInLanguage = (syntax: MultiplicityRule) => addSyntaxToLanguage(syntax)

  const removeSyntaxFromLanguage = () => {
    if (definition.value) definition.value.syntax = definition.value.syntax.filter((rule) => rule.ruleType !== 'multiplicity')
  }

  const getMultiplicityRuleForLanguage = () => {
    if (!definition.value) return undefined
    const existing = definition.value.syntax.find((rule): rule is MultiplicityRule => rule.ruleType === 'multiplicity')
    if (existing) return existing

    const rule: MultiplicityRule = {
      ruleType: 'multiplicity',
      config: { messageTemplate: DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE, relations: [] }
    }
    definition.value.syntax.push(rule)
    return rule
  }

  const setMultiplicityRelationState = (sourceType: string, targetType: string, state: MultiplicityRelationState | 'unset') => {
    const rule = getMultiplicityRuleForLanguage()
    if (!rule) return
    const index = rule.config.relations.findIndex((relation) => relation.sourceType === sourceType && relation.targetType === targetType)
    if (state === 'unset') {
      if (index >= 0) rule.config.relations.splice(index, 1)
      return
    }
    if (index < 0) {
      const relation: MultiplicityRelation = {
        sourceType,
        targetType,
        state,
        refinement: { connectionTypes: [], cardinality: { min: 0, max: null } }
      }
      rule.config.relations.push(relation)
    } else {
      rule.config.relations[index].state = state
    }
  }

  return {
    language,
    currentVersion,
    restoredFromVersion,
    definition,
    loading,
    saving,
    error,
    isDirty,
    loadLanguage,
    saveCurrentLanguage,
    discardCurrentChanges,
    restoreVersion,
    addElementToLanguage,
    updateElementInLanguage,
    removeElementFromLanguage,
    addConnectionToLanguage,
    updateConnectionInLanguage,
    removeConnectionFromLanguage,
    updateFeedbackEntryForLanguage,
    updateFeedbackCanvasConfigForLanguage,
    addSyntaxToLanguage,
    updateSyntaxInLanguage,
    removeSyntaxFromLanguage,
    getMultiplicityRuleForLanguage,
    setMultiplicityRelationState
  }
})
