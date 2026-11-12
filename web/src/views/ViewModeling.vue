<template>
  <v-container fluid class="modeling-view">
    <v-alert v-if="stepRun?.removed" type="info" variant="tonal" class="mb-3">This station was removed from the learning path. Your model is still available.</v-alert>
    <v-alert v-if="pulseEnabled && pulse.pollError.value" type="warning" variant="tonal" density="compact" class="mb-3">Impuls-Fragen konnten nicht abgefragt werden: {{ pulse.pollError.value }} Die Abfrage wird automatisch wiederholt.</v-alert>
    <v-alert v-if="workspace.taskEditError" type="error" variant="tonal" class="mb-3">{{ workspace.taskEditError }}</v-alert>
    <v-alert v-if="completionNotice" type="info" variant="tonal" density="compact" class="mb-3 flex-grow-0 flex-shrink-0" role="status">{{ completionNotice }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate class="model-loading" />
    <ChallengeOverlay v-if="!loading && !activeSurvey && stepRun?.challenge" :key="stepRun.id" :attempt="stepRun.challenge" :stopping="challengeBusy" @stop="stopChallenge" />
    <div v-if="activeSurvey && stepRun" class="task-survey-layout">
      <section class="task-survey pa-4">
        <h1 class="text-h5 mb-2">{{ surveyPhase === 'before' ? 'Before you start' : 'Complete your task' }}</h1>
        <p class="mb-4">{{ surveyPhase === 'before' ? 'Submit this questionnaire to begin working on the task.' : 'Submit this questionnaire to complete the task.' }}</p>
        <SurveyRenderer :key="`${surveyPhase}:${activeSurvey.surveyId}`" ref="taskSurvey" :survey-id="activeSurvey.surveyId" :activity="{ runId: stepRun.runId, stepId: stepRun.stepId, phase: surveyPhase }" @completed="taskSurveyCompleted" />
      </section>
      <aside class="task-survey-journey"><LearningJourneyDock :coins="stepRun.coins ?? 0" :completed="Boolean(stepRun.completedAt)" :complete-disabled="loading || Boolean(activeSurvey) || stepRun.removed" :busy="pathBusy" :evaluation-required="stepRun.minimumScorePercent != null || laboratoryCompletionBlocked" @leave="returnToPath(false)" @complete="returnToPath(true)" /></aside>
    </div>
    <DrawingCanvas
      v-show="!loading && !activeSurvey && !pathLoadFailed"
      ref="canvas"
      v-model:model="graphModel"
      v-model:help-cell-ids="helpCellIds"
      class="editor-canvas"
      :class="{ 'help-snapshot-loading': helpMarking && (!helpSnapshot || helpSnapshotLoading) }"
      :allow-edit="!helpMarking"
      :help-selection-mode="helpMarking"
      :help-flow-active="Boolean(currentHelp)"
      model-management
      :model-id="workspace.model?.id ?? null"
      :open-evaluation-id="startedEvaluationId"
      :evaluation-perspective="evaluationPerspective"
      :languages="workspace.editorLanguages"
      :language-connections="connections"
      :connection-groups="connectionGroups"
      :connection-preferences="workspace.preferences"
      :language-syntax="syntax"
      :autonomy-mode="workspace.taskVersion?.data.autonomyMode ?? sharedTaskSettings?.autonomyMode ?? 'free'"
      :lock-autonomy-mode="Boolean(workspace.taskVersion || sharedTaskSettings)"
      :connection-preview-allowed="workspace.taskVersion?.data.connectionPreviewAllowed ?? sharedTaskSettings?.connectionPreviewAllowed ?? false"
      :canvas-windows="taskWindows"
      :task-active="Boolean(workspace.taskReference || linkedWorkpieceId)"
      :task-edit="taskEdit"
      :task-edit-sync-state="workspace.taskEditSyncState"
      :selected-task-edit-ids="selectedTaskEditIds"
      @evaluation-updated="completionResult = $event"
      @window-removed="onWindowRemoved"
      @update:model="captureCanvas"
      @update:connection-preferences="workspace.updatePreferences"
      @remove-task-edit="removeTaskEditById"
      @update-task-edit-document="workspace.updateTaskEditDocument"
      @focus-task-edit="focusTaskEdit"
    >
      <template v-if="stepRun" #sidebar-top>
        <LearningJourneyDock v-show="!currentHelp" v-model:completion-dialog="completionDialog" :coins="stepRun.coins ?? 0" :completed="Boolean(stepRun.completedAt)" :complete-disabled="loading || Boolean(activeSurvey) || stepRun.removed" :busy="pathBusy || helpBusy" :evaluation-required="stepRun.minimumScorePercent != null || laboratoryCompletionBlocked" @leave="returnToPath(false)" @complete="returnToPath(true)">
          <template #pulse
            ><PulseSurveyPirate
              v-if="stepRun && pulseEnabled"
              :run-id="stepRun.runId"
              :step-id="stepRun.stepId"
              :visible="pulse.visible.value"
              :offer="pulse.offer.value"
              :offer-opened="pulse.offerOpened.value"
              :reward-coins="pulse.rewardCoins.value"
              :coin-balance="pulse.coinBalance.value"
              :state="pulse.state.value"
              :busy="pulse.busy.value"
              :error="pulse.error.value"
              @open="pulse.open"
              @dismiss="pulse.dismiss"
              @answered="pulse.answered"
              @expired="pulse.expire"
          /></template>
        </LearningJourneyDock>
        <HelpRequestFlow v-if="currentHelp" v-model:request="currentHelp" :cell-ids="helpCellIds" :text-ranges="helpTextRanges" :snapshot-loading="helpSnapshotLoading" :snapshot-error="helpSnapshotError" :feedback-busy="evaluationStarting" @remove-text="helpTextRanges.splice($event, 1)" @retry-snapshot="loadHelpSnapshot" @close="closeHelp" @automatic-feedback="requestAutomaticFeedback" />
      </template>
      <template v-if="helpEnabled" #canvas-top-right>
        <LearningPathHelp :busy="helpBusy" :disabled="helpActive || pathBusy || workspace.syncState === 'saving' || recoveryDialog" @request="requestHelp" />
      </template>
      <template #canvas-top>
        <div v-if="workspace.diagramTask" class="task-area">
          <TaskTopBar
            :task="workspace.diagramTask"
            :window-open="taskWindowOpen"
            :content-html="workspace.taskVersion?.data.contentHtml ?? ''"
            :base-document="workspace.taskVersion?.data.contentDocument"
            :task-edit="workspace.taskEdit"
            :element-options="taskElementOptions"
            :connection-options="taskConnectionOptions"
            :evaluation-available="Boolean(workspace.taskVersion?.data.sampleSolutions.length)"
            :help-selection-mode="helpMarking"
            :help-task-document="helpSnapshot?.taskEditSnapshot?.document ?? null"
            :help-text-ranges="helpTextRanges"
            @mark-help-text="markHelpText"
            @pop-out="taskWindowOpen = true"
            @start-evaluation="startEvaluation"
            @select-connection="selectTaskConnection"
            @select-task-edits="selectTaskEdits"
            @update:task-edit-document="workspace.updateTaskEditDocument"
          />
        </div>
        <!-- Modell eines Raums: die mitgeteilte Aufgabe, sofern der Host eine geteilt hat. -->
        <SharedTask v-else-if="linkedWorkpieceId" :key="linkedWorkpieceId" :workpiece-id="linkedWorkpieceId" :element-options="taskElementOptions" :connection-options="taskConnectionOptions" :window-open="taskWindowOpen" class="task-area" @pop-out="taskWindowOpen = true" @select-connection="selectTaskConnection" @select-task-edits="selectTaskEdits" @start-evaluation="startEvaluation" />
      </template>
      <template #window-content="{ definition }">
        <TaskEditEditor v-if="definition.role === 'task' && workspace.diagramTask" :key="workspace.taskReference?.versionId" :base-html="workspace.taskVersion?.data.contentHtml ?? ''" :base-document="workspace.taskVersion?.data.contentDocument" :model-value="workspace.taskEdit?.document ?? null" mode="edit" :element-options="taskElementOptions" :connection-options="taskConnectionOptions" class="canvas-task-window-content" @select-connection="selectTaskConnection" @select-edits="selectTaskEdits" @update:model-value="workspace.updateTaskEditDocument" />
        <!-- Modell eines Raums: die Task des Raums mit den Notizen der Gruppe. -->
        <SharedTaskWindow v-else-if="definition.role === 'task' && sharedTaskContent" :element-options="taskElementOptions" :connection-options="taskConnectionOptions" class="canvas-task-window-content" @select-connection="selectTaskConnection" @select-edits="selectTaskEdits" />
      </template>
    </DrawingCanvas>

    <v-dialog v-model="recoveryDialog" max-width="1000" persistent
      ><v-card
        ><v-card-title>Unsaved changes found</v-card-title
        ><v-card-text
          ><p class="mb-3">A local draft is available. Review it before choosing whether to restore it.</p>
          <v-alert v-if="recoveryModelChanged" type="info" variant="tonal" class="mb-3">The model has changed since this draft. Only the local task edits will be restored.</v-alert>
          <TaskEditEditor v-if="workspace.taskVersion" :base-html="workspace.taskVersion.data.contentHtml" :base-document="workspace.taskVersion.data.contentDocument" :model-value="recoveryTaskEdit?.document ?? workspace.taskEdit?.document ?? null" mode="read" class="recovery-task-preview" />
          <ModelSnapshotPreview :data="recoveryData" />
          <p class="text-caption text-medium-emphasis mt-2">The preview is read-only and does not change the server version.</p></v-card-text
        ><v-card-actions><v-btn @click="discardDraft">Open server version</v-btn><v-spacer /><v-btn color="primary" @click="restoreDraft">Restore local draft</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import type { GraphDataModel } from '@maxgraph/core'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import TaskTopBar from '@/components/modeling/controls/TaskTopBar.vue'
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import { buildTaskConnectionOptions, buildTaskElementOptions } from '@/components/tasks/taskEditorExtensions'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { JsonObject } from '@/services/api/types/common'
import type { CanvasWindowDefinition } from '@/model/CanvasWindow'
import { collectTaskEdits, flashTaskEdits, removeTaskEdit, type TaskEditFocus } from '@/utils/taskEdits'
import type { TaskEditDocument } from '@/services/api/types/model'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import paths, { laboratoryCompletionBlockedStepId, laboratoryCompletionUnavailableMessage, type PathModelContext, type HelpRequest, type HelpTextRange } from '@/services/learningPaths'
import modelService from '@/services/model/model.service'
import type { ModelVersion } from '@/services/api/types/model'
import evaluationService from '@/services/evaluation/evaluation.service'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import ChallengeOverlay from '@/components/learningPaths/ChallengeOverlay.vue'
import LearningJourneyDock from '@/components/learningPaths/LearningJourneyDock.vue'
import PulseSurveyPirate from '@/components/learningPaths/PulseSurveyPirate.vue'
import LearningPathHelp from '@/components/learningPaths/LearningPathHelp.vue'
import HelpRequestFlow from '@/components/learningPaths/HelpRequestFlow.vue'
import { usePulseSurvey } from '@/composables/usePulseSurvey'
import { useModelActivity } from '@/composables/useModelActivity'
import { provideModelFileContext } from '@/composables/useModelFileContext'
import SharedTask from '@/collab/worksheet/SharedTask.vue'
import SharedTaskWindow from '@/collab/worksheet/SharedTaskWindow.vue'
import { sharedTaskContent, sharedTaskEdit, sharedTaskSettings, writeSharedTask } from '@/collab/worksheet/sharedTask'
import { saveRoomCheckpoint } from '@/collab/sharing/shareModel'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'

interface Props {
  modelId?: string
}
const props = defineProps<Props>()
const emit = defineEmits<{ 'learning-path-model': [modelId: string | null] }>()
const router = useRouter()
const route = useRoute()
const workspace = useModelWorkspaceStore()
const activityReady = ref(false)
useModelActivity(activityReady)
const { linkedWorkpieceId } = useCollabConnection()
// The task edits of the open model, or of the room if it shows one.
const taskEdit = computed(() => workspace.taskEdit ?? sharedTaskEdit.value)
const selectedTaskEditIds = ref<string[]>([])
const selectTaskEdits = (ids: string[]) => {
  const selected = [...new Set(ids)]
  if (JSON.stringify(selected) !== JSON.stringify(selectedTaskEditIds.value)) selectedTaskEditIds.value = selected
}
watch(() => taskEdit.value?.document, (document) => {
  const ids = new Set(collectTaskEdits(document).map((entry) => entry.id))
  selectTaskEdits(selectedTaskEditIds.value.filter((id) => ids.has(id)))
})
watch([() => workspace.model?.id, () => workspace.taskReference?.versionId], () => selectTaskEdits([]))
const canvas = ref<{ serializeModel: () => JsonObject; loadPersistedModel: (data: JsonObject) => void; resetUndoHistory: () => void; fitToWindow: () => void; selectConnectionByType: (languageId: string, connectionType: string) => boolean } | null>(null)
const graphModel = ref<GraphDataModel>()
const recoveryDialog = ref(false)
const recoveryData = ref<JsonObject | null>(null)
const recoveryTaskEdit = ref<TaskEditDocument | null>(null)
const recoveryModelChanged = ref(false)
const hydrating = ref(false)
const loading = ref(false)
const pathBusy = ref(false)
const helpBusy = ref(false)
const currentHelp = ref<HelpRequest | null>(null)
const helpActive = computed(() => Boolean(currentHelp.value && !['completed', 'cancelled'].includes(currentHelp.value.stage)))
const helpMarking = computed(() => currentHelp.value?.stage === 'marking')
const fileImportDisabledReason = computed(() => loading.value || hydrating.value || workspace.saving ? 'Wait until the model has finished loading or saving.' : helpMarking.value ? 'This model is currently read-only.' : '')
provideModelFileContext({
  disabledReason: fileImportDisabledReason,
  workspaceLanguages: computed(() => workspace.languages.map(({ languageId, versionId }) => ({ languageId, versionId }))),
  languages: computed(() => workspace.editorLanguages.map(({ language, version }) => ({
    languageId: language.id, versionId: version.id, name: language.name,
    data: version.data, includedLanguageVersions: version.includedLanguageVersions
  }))),
  importModel: async (model, references) => {
    if (fileImportDisabledReason.value) throw new Error(fileImportDisabledReason.value)
    hydrating.value = true
    try {
      await workspace.importFile({ format: 'maxgraph-xml', version: 1, xml: model.model.xml, name: workspace.data.name }, references)
      await nextTick()
      canvas.value?.loadPersistedModel(workspace.data)
      canvas.value?.fitToWindow()
      await nextTick()
      canvas.value?.resetUndoHistory()
    } finally {
      hydrating.value = false
    }
  }
})
const helpCellIds = ref<string[]>([])
const helpTextRanges = ref<HelpTextRange[]>([])
const helpSnapshot = ref<ModelVersion | null>(null)
const helpSnapshotLoading = ref(false)
const helpSnapshotError = ref('')
let helpSnapshotGeneration = 0
// Keep the same saved version and request ID when retrying a failed event write.
const pendingHelp = ref<{ requestId: string; modelVersionId: string } | null>(null)
const stepRun = ref<PathModelContext | null>(null)
const laboratoryCompletionBlocked = computed(() => stepRun.value?.stepId === laboratoryCompletionBlockedStepId && !stepRun.value.completedAt && !stepRun.value.removed)
watch(stepRun, (path) => emit('learning-path-model', path && !path.removed ? props.modelId ?? null : null), { immediate: true })
onBeforeUnmount(() => emit('learning-path-model', null))
const pathLoadFailed = ref(false)
const completing = ref(false)
const completionDialog = ref(false)
const pendingCompletion = ref(route.query.complete === '1')
const completionEvaluationId = ref<string | null>(null)
const completionResult = ref<EvaluationDetail | null>(null)
const completionNotice = ref('')
const taskSurvey = ref<InstanceType<typeof SurveyRenderer> | null>(null)
const surveyPhase = computed<'before' | 'after'>(() => (stepRun.value?.beforeSurvey && !stepRun.value.beforeSurvey.completed ? 'before' : 'after'))
const activeSurvey = computed(() => {
  const path = stepRun.value
  if (!path || path.completedAt) return null
  if (path.beforeSurvey && !path.beforeSurvey.completed) return path.beforeSurvey
  return path.completionRequested && path.afterSurvey && !path.afterSurvey.completed ? path.afterSurvey : null
})
const pulseEnabled = computed(() => Boolean(!currentHelp.value && stepRun.value && !stepRun.value.removed && !stepRun.value.completedAt && !stepRun.value.completionRequested && !activeSurvey.value && !loading.value && !pathLoadFailed.value && !recoveryDialog.value))
const helpEnabled = computed(() => Boolean(stepRun.value?.helpRequests?.enabled && !stepRun.value.removed && !stepRun.value.completedAt && !stepRun.value.completionRequested && !activeSurvey.value && !loading.value && !pathLoadFailed.value))
const pulse = usePulseSurvey(
  computed(() => stepRun.value?.runId),
  computed(() => stepRun.value?.stepId),
  pulseEnabled
)
watch(pulse.coinBalance, (coins) => {
  if (stepRun.value && coins !== null) stepRun.value.coins = coins
})
onBeforeRouteLeave(async () => {
  if (helpBusy.value || helpActive.value) return false
  if (taskSurvey.value?.saving) return false
  return (await taskSurvey.value?.saveDraft()) !== false
})
const taskSurveyCompleted = async () => {
  if (!stepRun.value || !props.modelId) return
  try {
    stepRun.value = (await paths.resumeStep(stepRun.value.runId, stepRun.value.stepId)).data
    if (completing.value || stepRun.value?.completedAt) await returnToPath(true)
  } catch {
    notifyError('The task status could not be loaded. Please reload the page.')
  }
}
const challengeBusy = ref(false)
const stopChallenge = async () => {
  if (!stepRun.value || challengeBusy.value) return
  challengeBusy.value = true
  try {
    stepRun.value = (await paths.stopChallenge(stepRun.value.runId, stepRun.value.stepId)).data
  } catch {
    notifyError('The challenge could not be ended. Please try again.')
  } finally {
    challengeBusy.value = false
  }
}
const returnToPath = async (complete: boolean, evaluationId?: string) => {
  const path = stepRun.value
  if (!path || helpActive.value || pathBusy.value) return
  if (complete && laboratoryCompletionBlocked.value) {
    notifyWarning(laboratoryCompletionUnavailableMessage, { timeout: 10000 })
    return
  }
  if (complete && completionEvaluationId.value && !evaluationId) return
  if (!complete) completionEvaluationId.value = null
  pathBusy.value = true
  try {
    captureCanvas()
    if (workspace.dirty || workspace.taskEditDirty) await workspace.save()
    if (complete) {
      completing.value = true
      if (path.beforeSurvey && !path.beforeSurvey.completed) return
      if (path.minimumScorePercent != null && !evaluationId && !path.completedAt) {
        completionNotice.value = ''
        const evaluation = await startEvaluation('student')
        if (evaluation) completionEvaluationId.value = evaluation.id
        else completionNotice.value = 'Die Auswertung konnte nicht gestartet werden. Versuche den Abschluss erneut.'
        return
      }
      await paths.complete(path.runId, path.stepId, evaluationId)
      stepRun.value = (await paths.resumeStep(path.runId, path.stepId)).data
      if (!stepRun.value.completedAt) return
    }
    if (taskSurvey.value && !(await taskSurvey.value.saveDraft())) return
    await router.push(`/learning-path-runs/${path.runId}`)
  } catch (error) {
    await refreshPathContext()
    const code = (error as { response?: { data?: { code?: string } } }).response?.data?.code
    completionNotice.value = ({
      EVALUATION_REQUIRED: 'Für den Abschluss ist eine Auswertung erforderlich. Versuche den Abschluss erneut.',
      EVALUATION_OUTDATED: 'Dein Modell wurde geändert. Starte den Abschluss erneut, um den aktuellen Stand auszuwerten.',
      EVALUATION_INCOMPLETE: 'Die Auswertung ist noch nicht abgeschlossen.',
      EVALUATION_UNAVAILABLE: laboratoryCompletionUnavailableMessage,
      EVALUATION_SCORE_PENDING: 'Der Durchlauf ist abgeschlossen. Ein Bewertungswert ist noch nicht verfügbar. Der Aufgabenabschluss wartet auf die Anbindung der Modellbewertung.',
      EVALUATION_MINIMUM_NOT_MET: 'Die erforderliche Mindestbewertung wurde noch nicht erreicht. Überarbeite dein Modell und versuche den Abschluss erneut.'
    } as Record<string, string>)[code ?? ''] ?? ''
    if (!completionNotice.value) notifyError('The task could not be completed or the learning path opened. Review the current path settings and try again.')
  } finally {
    pathBusy.value = false
  }
}
const startedEvaluationId = ref<string | null>(null)
const evaluationPerspective = ref<'service' | 'student'>('service')
const evaluationStarting = ref(false)
const taskWindowOpen = ref(false)
const taskWindowTitle = computed(() => workspace.diagramTask?.title ?? sharedTaskContent.value?.title)
const taskWindows = computed<CanvasWindowDefinition[]>(() => (taskWindowOpen.value && taskWindowTitle.value ? [{ id: 'task-description', title: taskWindowTitle.value, x: 260, y: 120, width: 520, height: 360, role: 'task' }] : []))
// Ohne Task, etwa nach dem Verlassen des Raums, geht das Fenster zu.
watch(taskWindowTitle, (title) => {
  if (!title) taskWindowOpen.value = false
})
const connections = computed(() => workspace.editorLanguages.flatMap((language) => language.connections))
const taskElementOptions = computed(() => buildTaskElementOptions(workspace.editorLanguages))
const taskConnectionOptions = computed(() => buildTaskConnectionOptions(workspace.editorLanguages))
const connectionGroups = computed(() =>
  workspace.editorLanguages
    .filter((language) => language.connections.length > 0)
    .map((language) => ({
      id: language.id,
      label: `${language.name} · v${language.version.versionNumber}`,
      connections: language.connections
    }))
)
const syntax = computed(() => workspace.editorLanguages.flatMap((language) => language.syntax))
const captureCanvas = () => {
  if (!helpMarking.value && !helpSnapshot.value && !hydrating.value && !loading.value && !activeSurvey.value && canvas.value) workspace.setData({ ...canvas.value.serializeModel(), name: workspace.model?.name ?? workspace.data.name })
}
const requestHelp = async () => {
  const path = stepRun.value
  if (!path || currentHelp.value || !helpEnabled.value || helpBusy.value || pathBusy.value || recoveryDialog.value || workspace.syncState === 'saving') return
  helpBusy.value = true
  try {
    if (!pendingHelp.value) {
      captureCanvas()
      const version = await workspace.save('checkpoint')
      pendingHelp.value = { requestId: version.id, modelVersionId: version.id }
    }
    currentHelp.value = (await paths.requestHelp(path.runId, path.stepId, pendingHelp.value.requestId, pendingHelp.value.modelVersionId)).data
    pendingHelp.value = null
  } catch {
    notifyError('Die Hilfe-Anfrage konnte nicht gespeichert werden. Bitte versuche es erneut.')
    await refreshPathContext()
  } finally {
    helpBusy.value = false
  }
}
const markHelpText = (range: HelpTextRange) => {
  if (helpMarking.value && helpSnapshot.value && !helpTextRanges.value.some((item) => item.start === range.start && item.end === range.end)) helpTextRanges.value.push(range)
}
const closeHelp = () => {
  currentHelp.value = null
}
const loadActiveHelp = async () => {
  const path = stepRun.value
  if (!path || path.removed || path.completedAt) return
  try {
    currentHelp.value = (await paths.activeHelp(path.runId, path.stepId)).data
  } catch {
    notifyError('Ein offener Hilfe-Ablauf konnte nicht geladen werden. Bitte lade die Seite erneut.')
  }
}
const loadHelpSnapshot = async () => {
  const request = currentHelp.value
  if (!request || request.stage !== 'marking') return
  const generation = ++helpSnapshotGeneration
  helpSnapshotLoading.value = true
  helpSnapshotError.value = ''
  try {
    const model = workspace.model?.id === request.modelId ? workspace.model : (await modelService.get(request.modelId)).data
    const version = (await modelService.getVersion(model, request.modelVersionId)).data
    if (generation !== helpSnapshotGeneration || !helpMarking.value) return
    helpSnapshot.value = version
    hydrating.value = true
    await nextTick()
    canvas.value?.loadPersistedModel(version.data)
    await nextTick()
  } catch {
    helpSnapshotError.value = 'Der gespeicherte Modellstand konnte nicht geladen werden.'
  } finally {
    if (generation === helpSnapshotGeneration) {
      helpSnapshotLoading.value = false
      hydrating.value = false
    }
  }
}
watch(
  () => currentHelp.value?.id,
  () => {
    helpCellIds.value = []
    helpTextRanges.value = []
  }
)
watch(
  () => currentHelp.value?.stage,
  async (stage) => {
    if (stage === 'marking') {
      taskWindowOpen.value = false
      await loadHelpSnapshot()
    } else {
      helpSnapshotGeneration++
      helpSnapshotLoading.value = false
      if (helpSnapshot.value) {
        helpSnapshot.value = null
        await syncCanvas()
      }
      if (stage === 'cancelled') currentHelp.value = null
    }
  }
)
const syncCanvas = async () => {
  hydrating.value = true
  try {
    await nextTick()
    canvas.value?.loadPersistedModel(workspace.data)
    await nextTick()
  } finally {
    hydrating.value = false
  }
}
const restoreDraft = async () => {
  if (await workspace.restoreRecoveryDraft()) await syncCanvas()
  recoveryDialog.value = false
  await loadActiveHelp()
}
const discardDraft = async () => {
  await workspace.discardRecoveryDraft()
  recoveryDialog.value = false
  await loadActiveHelp()
}
const onWindowRemoved = (id: string) => {
  if (id === 'task-description') taskWindowOpen.value = false
}
const selectTaskConnection = (reference: { languageId: string; connectionType: string }) => {
  canvas.value?.selectConnectionByType(reference.languageId, reference.connectionType)
}
const removeTaskEditById = (id: string) => {
  if (workspace.taskEdit) workspace.updateTaskEditDocument(removeTaskEdit(workspace.taskEdit.document, id))
  else if (sharedTaskEdit.value) writeSharedTask.value?.(removeTaskEdit(sharedTaskEdit.value.document, id))
}
const focusTaskEdit = (target: TaskEditFocus) => {
  const host = document.querySelector<HTMLElement>(taskWindowOpen.value ? '.canvas-task-window-content .tiptap' : '.task-topbar__editor .tiptap')
  if (!host) { selectTaskEdits([target.id]); return }
  const editor = (host as HTMLElement & { editor?: import('@tiptap/core').Editor }).editor
  const fragment = collectTaskEdits(taskEdit.value?.document).find((entry) => entry.id === target.id)?.fragments[0]
  const from = target.from ?? fragment?.from, to = target.to ?? fragment?.to
  if (editor && from !== undefined && to !== undefined) {
    editor.commands.setTextSelection({ from, to })
    const coordinates = editor.view.coordsAtPos(from)
    host.parentElement?.scrollBy({ top: coordinates.top - host.parentElement.getBoundingClientRect().top - 40, behavior: 'smooth' })
  } else host.querySelector<HTMLElement>(`[data-task-edit-id="${CSS.escape(target.id)}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  flashTaskEdits(host, [target.id])
  selectTaskEdits([target.id])
}

const startEvaluation = async (perspective: 'service' | 'student' = 'service') => {
  // In a room only the host evaluates, on the private model that has the task; the state of the room goes in as its newest version.
  const room = !workspace.taskVersion && sharedTaskSettings.value
  if (evaluationStarting.value || !room && (!workspace.model || !workspace.taskVersion)) return null
  if (!(room ? sharedTaskSettings.value!.evaluationAvailable : workspace.taskVersion!.data.sampleSolutions.length)) {
    notifyWarning('Für diese Aufgabe ist noch keine Musterlösung zur Auswertung hinterlegt.')
    return null
  }
  evaluationStarting.value = true
  try {
    // A checkpoint creates an immutable submission reference whenever canvas
    // changes have not been persisted yet.
    let modelId: string
    if (room) modelId = await saveRoomCheckpoint()
    else {
      captureCanvas()
      if (workspace.dirty || workspace.taskEditDirty) await workspace.save('checkpoint')
      modelId = workspace.model!.id
    }
    const evaluation = (await evaluationService.start(modelId)).data
    evaluationPerspective.value = perspective
    startedEvaluationId.value = evaluation.id
    if (evaluation.state === 'failed') notifyError('The evaluation start was rejected. See the evaluation details.')
    else if (evaluation.state === 'unknown') notifyWarning('The evaluation start could not be confirmed. Its run ID is retained for clarification.')
    return evaluation
  } catch (error) {
    notifyError((error as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The evaluation could not be started.')
    return null
  } finally {
    evaluationStarting.value = false
  }
}
const requestAutomaticFeedback = async () => {
  const evaluation = await startEvaluation('student')
  if (evaluation) closeHelp()
}
watch([completionResult, pathBusy], ([evaluation, busy]) => {
  if (busy || !evaluation || evaluation.id !== completionEvaluationId.value) return
  if (evaluation.state === 'failed' || evaluation.state === 'cancelled') {
    completionEvaluationId.value = null
    completionNotice.value = 'Die Auswertung wurde nicht abgeschlossen. Versuche den Aufgabenabschluss erneut.'
    return
  }
  if (evaluation.state !== 'succeeded') return
  completionEvaluationId.value = null
  const minimum = stepRun.value?.minimumScorePercent
  if (minimum == null) return
  if (workspace.dirty || workspace.taskEditDirty || evaluation.submission.versionId !== workspace.model?.latestVersionId) {
    completionNotice.value = 'Dein Modell wurde geändert. Starte den Abschluss erneut, um den aktuellen Stand auszuwerten.'
  } else if (evaluation.scorePercent == null) {
    completionNotice.value = 'Der Durchlauf ist abgeschlossen. Ein Bewertungswert ist noch nicht verfügbar. Der Aufgabenabschluss wartet auf die Anbindung der Modellbewertung.'
  } else if (evaluation.scorePercent < minimum) {
    completionNotice.value = `Dein Modell erreicht ${evaluation.scorePercent} %. Für den Abschluss sind mindestens ${minimum} % erforderlich. Überarbeite dein Modell und versuche es erneut.`
  } else {
    completionNotice.value = ''
    void returnToPath(true, evaluation.id)
  }
})
const refreshPathContext = async () => {
  if (!props.modelId || loading.value || taskSurvey.value?.saving) return
  try {
    stepRun.value = (await paths.modelContext(props.modelId)).data
  } catch {
    notifyError('The learning path settings could not be refreshed.')
  }
}
watch(
  [loading, stepRun, activeSurvey, helpActive, helpBusy, pathBusy, recoveryDialog, pathLoadFailed],
  () => {
    if (!pendingCompletion.value || loading.value || !stepRun.value || stepRun.value.removed || stepRun.value.completedAt || activeSurvey.value || helpActive.value || helpBusy.value || pathBusy.value || recoveryDialog.value || pathLoadFailed.value) return
    pendingCompletion.value = false
    if (stepRun.value.minimumScorePercent != null || laboratoryCompletionBlocked.value) void returnToPath(true)
    else completionDialog.value = true
    const query = { ...route.query }
    delete query.complete
    void router.replace({ query })
  },
  { flush: 'post' }
)
onMounted(async () => {
  loading.value = true
  try {
    if (props.modelId) {
      await workspace.load(props.modelId)
      stepRun.value = (await paths.modelContext(props.modelId)).data
      if (stepRun.value && !stepRun.value.removed) stepRun.value = (await paths.resumeStep(stepRun.value.runId, stepRun.value.stepId)).data
      await syncCanvas()
      const recoverySnapshot = await workspace.getRecoverySnapshot()
      if (recoverySnapshot) {
        recoveryData.value = recoverySnapshot
        const draft = await workspace.getRecoveryDraft()
        recoveryTaskEdit.value = draft?.taskEdit ?? null
        recoveryModelChanged.value = draft?.baseVersionId !== workspace.baseVersionId
        recoveryDialog.value = true
      } else await loadActiveHelp()
    } else if (workspace.languages.length === 0) {
      await router.replace({ name: 'Models' })
    }
  } catch {
    pathLoadFailed.value = true
    notifyError('The model could not be loaded.')
  } finally {
    loading.value = false
    activityReady.value = !pathLoadFailed.value
  }
})
</script>

<style scoped>
.recovery-task-preview { max-height: 260px; overflow-y: auto; margin-bottom: 16px; }
.modeling-view {
  position: relative;
  padding: 8px 12px;
  height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.model-loading {
  position: absolute;
  inset: 0 0 auto;
  z-index: 20;
}
.task-survey-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  gap: 12px;
}
.task-survey-journey {
  width: 280px;
  flex-shrink: 0;
}
.task-survey {
  min-width: 0;
  overflow-y: auto;
  flex: 1;
}
.editor-canvas {
  flex: 1;
  min-height: 0;
}
.help-snapshot-loading :deep(.graph-wrapper) {
  pointer-events: none;
  opacity: 0.6;
}
.task-area {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.task-area :deep(.task-topbar) {
  flex: 1;
}
.canvas-task-window-content {
  width: 100%;
  height: 100%;
}
</style>
