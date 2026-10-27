<template>
  <v-container fluid class="pa-4 modeling-view">
    <v-alert v-if="stepRun?.removed" type="info" variant="tonal" class="mb-3">This station was removed from the learning path. Your model is still available.</v-alert>
    <v-alert v-if="pulseEnabled && pulse.pollError.value" type="warning" variant="tonal" density="compact" class="mb-3">Impuls-Fragen konnten nicht abgefragt werden: {{ pulse.pollError.value }} Die Abfrage wird automatisch wiederholt.</v-alert>
    <v-progress-linear v-if="loading" indeterminate class="model-loading" />
    <ChallengeOverlay v-if="!loading && !activeSurvey && stepRun?.challenge" :key="stepRun.id" :attempt="stepRun.challenge" :stopping="challengeBusy" @stop="stopChallenge" />
    <div v-if="activeSurvey && stepRun" class="task-survey-layout">
      <section class="task-survey pa-4">
        <h1 class="text-h5 mb-2">{{ surveyPhase === 'before' ? 'Before you start' : 'Complete your task' }}</h1>
        <p class="mb-4">{{ surveyPhase === 'before' ? 'Submit this questionnaire to begin working on the task.' : 'Submit this questionnaire to complete the task.' }}</p>
        <SurveyRenderer :key="`${surveyPhase}:${activeSurvey.surveyId}`" ref="taskSurvey" :survey-id="activeSurvey.surveyId" :activity="{ runId: stepRun.runId, stepId: stepRun.stepId, phase: surveyPhase }" @completed="taskSurveyCompleted" />
      </section>
      <aside class="task-survey-journey"><LearningJourneyDock :coins="stepRun.coins ?? 0" :completed="Boolean(stepRun.completedAt)" :complete-disabled="loading || Boolean(activeSurvey) || stepRun.removed" :busy="pathBusy" @leave="returnToPath(false)" @complete="returnToPath(true)" /></aside>
    </div>
    <DrawingCanvas
      v-show="!loading && !activeSurvey && !pathLoadFailed"
      ref="canvas"
      v-model:model="graphModel"
      class="editor-canvas"
      model-management
      :model-id="workspace.model?.id ?? null"
      :open-evaluation-id="startedEvaluationId"
      :languages="workspace.editorLanguages"
      :language-connections="connections"
      :connection-groups="connectionGroups"
      :connection-preferences="workspace.preferences"
      :language-syntax="syntax"
      :autonomy-mode="workspace.taskVersion?.data.autonomyMode ?? 'free'"
      :lock-autonomy-mode="Boolean(workspace.taskVersion)"
      :canvas-windows="taskWindows"
      :task-active="Boolean(workspace.taskReference)"
      :task-edit="workspace.taskEdit"
      :task-edit-sync-state="workspace.taskEditSyncState"
      @window-removed="onWindowRemoved"
      @update:model="captureCanvas"
      @update:connection-preferences="workspace.updatePreferences"
      @remove-task-edit="removeTaskEditById"
      @update-task-edit-document="workspace.updateTaskEditDocument"
      @focus-task-edit="focusTaskEdit"
    >
      <template v-if="stepRun" #sidebar-top>
        <LearningJourneyDock :coins="stepRun.coins ?? 0" :completed="Boolean(stepRun.completedAt)" :complete-disabled="loading || Boolean(activeSurvey) || stepRun.removed" :busy="pathBusy" @leave="returnToPath(false)" @complete="returnToPath(true)">
          <template #pulse><PulseSurveyPirate v-if="stepRun && pulseEnabled" :run-id="stepRun.runId" :step-id="stepRun.stepId" :visible="pulse.visible.value" :offer="pulse.offer.value" :offer-opened="pulse.offerOpened.value" :reward-coins="pulse.rewardCoins.value" :coin-balance="pulse.coinBalance.value" :state="pulse.state.value" :busy="pulse.busy.value" :error="pulse.error.value" @open="pulse.open" @dismiss="pulse.dismiss" @answered="pulse.answered" @expired="pulse.expire" /></template>
        </LearningJourneyDock>
      </template>
      <template #canvas-top>
        <div v-if="workspace.diagramTask" class="task-area">
          <TaskTopBar
            :task="workspace.diagramTask"
            :window-open="taskWindowOpen"
            :content-html="workspace.taskVersion?.data.contentHtml ?? ''"
            :task-edit="workspace.taskEdit"
            :element-options="taskElementOptions"
            :connection-options="taskConnectionOptions"
            :evaluation-workflows="workspace.taskVersion?.data.evaluationWorkflows ?? []"
            @pop-out="taskWindowOpen = true"
            @start-evaluation="startEvaluation"
            @select-connection="selectTaskConnection"
            @update:task-edit-document="workspace.updateTaskEditDocument"
          />
        </div>
      </template>
      <template #window-content="{ definition }">
        <TaskEditEditor v-if="definition.role === 'task'" :base-html="workspace.taskVersion?.data.contentHtml ?? ''" :model-value="workspace.taskEdit?.document ?? null" mode="edit" :element-options="taskElementOptions" :connection-options="taskConnectionOptions" class="canvas-task-window-content" @select-connection="selectTaskConnection" @update:model-value="workspace.updateTaskEditDocument" />
      </template>
    </DrawingCanvas>

    <v-dialog v-model="recoveryDialog" max-width="1000" persistent
      ><v-card
        ><v-card-title>Unsaved changes found</v-card-title
        ><v-card-text
          ><p class="mb-3">A local draft is available. Review it before choosing whether to restore it.</p>
          <ModelSnapshotPreview :data="recoveryData" />
          <p class="text-caption text-medium-emphasis mt-2">The preview is read-only and does not change the server version.</p></v-card-text
        ><v-card-actions><v-btn @click="discardDraft">Open server version</v-btn><v-spacer /><v-btn color="primary" @click="restoreDraft">Restore local draft</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
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
import { removeTaskEdit } from '@/utils/taskEdits'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import paths, { type PathModelContext } from '@/services/learningPaths'
import evaluationService from '@/services/evaluation/evaluation.service'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import ChallengeOverlay from '@/components/learningPaths/ChallengeOverlay.vue'
import LearningJourneyDock from '@/components/learningPaths/LearningJourneyDock.vue'
import PulseSurveyPirate from '@/components/learningPaths/PulseSurveyPirate.vue'
import { usePulseSurvey } from '@/composables/usePulseSurvey'

interface Props {
  modelId?: string
}
const props = defineProps<Props>()
const router = useRouter()
const route = useRoute()
const workspace = useModelWorkspaceStore()
const canvas = ref<{ serializeModel: () => JsonObject; loadPersistedModel: (data: JsonObject) => void; selectConnectionByType: (languageId: string, connectionType: string) => boolean } | null>(null)
const graphModel = ref<GraphDataModel>()
const recoveryDialog = ref(false)
const recoveryData = ref<JsonObject | null>(null)
const hydrating = ref(false)
const loading = ref(false)
const pathBusy = ref(false)
const stepRun = ref<PathModelContext | null>(null)
const pathLoadFailed = ref(false)
const completing = ref(route.query.complete === '1')
const taskSurvey = ref<InstanceType<typeof SurveyRenderer> | null>(null)
const surveyPhase = computed<'before' | 'after'>(() => (stepRun.value?.beforeSurvey && !stepRun.value.beforeSurvey.completed ? 'before' : 'after'))
const activeSurvey = computed(() => {
  const path = stepRun.value
  if (!path || path.completedAt) return null
  if (path.beforeSurvey && !path.beforeSurvey.completed) return path.beforeSurvey
  return path.completionRequested && path.afterSurvey && !path.afterSurvey.completed ? path.afterSurvey : null
})
const pulseEnabled = computed(() => Boolean(stepRun.value && !stepRun.value.removed && !stepRun.value.completedAt && !stepRun.value.completionRequested && !activeSurvey.value && !loading.value && !pathLoadFailed.value && !recoveryDialog.value))
const pulse = usePulseSurvey(computed(() => stepRun.value?.runId), computed(() => stepRun.value?.stepId), pulseEnabled)
watch(pulse.coinBalance, (coins) => {
  if (stepRun.value && coins !== null) stepRun.value.coins = coins
})
onBeforeRouteLeave(async () => {
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
const returnToPath = async (complete: boolean) => {
  const path = stepRun.value
  if (!path) return
  pathBusy.value = true
  try {
    captureCanvas()
    if (workspace.dirty || workspace.taskEditDirty) await workspace.save()
    if (complete) {
      completing.value = true
      if (path.beforeSurvey && !path.beforeSurvey.completed) return
      await paths.complete(path.runId, path.stepId)
      stepRun.value = (await paths.resumeStep(path.runId, path.stepId)).data
      if (!stepRun.value.completedAt) return
    }
    if (taskSurvey.value && !(await taskSurvey.value.saveDraft())) return
    await router.push(`/learning-path-runs/${path.runId}`)
  } catch {
    await refreshPathContext()
    notifyError('The task could not be completed or the learning path opened. Review the current path settings and try again.')
  } finally {
    pathBusy.value = false
  }
}
const startedEvaluationId = ref<string | null>(null)
const taskWindowOpen = ref(false)
const taskWindows = computed<CanvasWindowDefinition[]>(() => (taskWindowOpen.value && workspace.diagramTask ? [{ id: 'task-description', title: workspace.diagramTask.title, x: 260, y: 120, width: 520, height: 360, role: 'task' }] : []))
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
  if (!hydrating.value && !loading.value && !activeSurvey.value && canvas.value) workspace.setData({ ...canvas.value.serializeModel(), name: workspace.model?.name ?? workspace.data.name })
}
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
}
const discardDraft = async () => {
  await workspace.discardRecoveryDraft()
  recoveryDialog.value = false
}
const onWindowRemoved = (id: string) => {
  if (id === 'task-description') taskWindowOpen.value = false
}
const selectTaskConnection = (reference: { languageId: string; connectionType: string }) => {
  canvas.value?.selectConnectionByType(reference.languageId, reference.connectionType)
}
const removeTaskEditById = (id: string) => {
  if (workspace.taskEdit) workspace.updateTaskEditDocument(removeTaskEdit(workspace.taskEdit.document, id))
}
const focusTaskEdit = (id: string) => {
  const targets = [...document.querySelectorAll<HTMLElement>(`[data-task-edit-id="${CSS.escape(id)}"]`)]
  targets[0]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  targets.forEach((target) => target.animate([{ outline: '2px solid rgb(25, 118, 210)' }, { outline: '2px solid transparent' }], { duration: 1400 }))
}
const startEvaluation = async () => {
  if (!workspace.model || !workspace.taskVersion) return
  if (!workspace.taskVersion.data.evaluationWorkflows[0]) return
  try {
    // A checkpoint creates an immutable submission reference whenever canvas
    // changes have not been persisted yet.
    if (workspace.dirty) await workspace.save('checkpoint')
    const evaluation = (await evaluationService.start(workspace.model.id)).data
    startedEvaluationId.value = evaluation.id
    notifySuccess('Evaluation started.')
  } catch (error) {
    notifyError((error as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The evaluation could not be started.')
  }
}
const refreshPathContext = async () => {
  if (!props.modelId || loading.value || taskSurvey.value?.saving) return
  try {
    stepRun.value = (await paths.modelContext(props.modelId)).data
  } catch {
    notifyError('The learning path settings could not be refreshed.')
  }
}
onMounted(async () => {
  loading.value = true
  try {
    if (props.modelId) {
      await workspace.load(props.modelId)
      stepRun.value = (await paths.modelContext(props.modelId)).data
      if (stepRun.value && !stepRun.value.removed) stepRun.value = (await paths.resumeStep(stepRun.value.runId, stepRun.value.stepId)).data
      if (completing.value && stepRun.value && !stepRun.value.removed) await returnToPath(true)
      await syncCanvas()
      const recoverySnapshot = await workspace.getRecoverySnapshot()
      if (recoverySnapshot) {
        recoveryData.value = recoverySnapshot
        recoveryDialog.value = true
      }
    } else if (workspace.languages.length === 0) {
      await router.replace('/')
    }
  } catch {
    pathLoadFailed.value = true
    notifyError('The model could not be loaded.')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.modeling-view {
  position: relative;
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
.task-survey-layout { display: flex; flex: 1; min-height: 0; gap: 12px; }
.task-survey-journey { width: 280px; flex-shrink: 0; }
.task-survey {
  min-width: 0;
  overflow-y: auto;
  flex: 1;
}
.editor-canvas {
  flex: 1;
  min-height: 0;
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
