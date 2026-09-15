<template>
  <v-container fluid class="pa-4 modeling-view">
    <v-progress-linear v-if="loading" indeterminate class="model-loading" />
    <v-alert v-if="loadError" type="error" variant="tonal" density="compact" closable class="model-load-error" @click:close="loadError = null">{{ loadError }}</v-alert>
    <DrawingCanvas ref="canvas" v-model:model="graphModel" class="editor-canvas" model-management :languages="workspace.editorLanguages" :language-connections="connections" :connection-groups="connectionGroups" :connection-preferences="workspace.preferences" :language-syntax="syntax" :autonomy-mode="workspace.taskVersion?.data.autonomyMode ?? 'free'" :lock-autonomy-mode="Boolean(workspace.taskVersion)" :canvas-windows="taskWindows" @window-removed="onWindowRemoved" @update:model="captureCanvas" @update:connection-preferences="workspace.updatePreferences">
      <template #canvas-top>
        <div v-if="workspace.diagramTask" class="task-area">
          <TaskTopBar :task="workspace.diagramTask" :window-open="taskWindowOpen" :content-html="workspace.taskContentHtml" :element-options="taskElementOptions" :connection-options="taskConnectionOptions" @pop-out="taskWindowOpen = true" @select-connection="selectTaskConnection" @update:content-html="workspace.updateTaskContent" />
          <v-btn v-if="sampleSolutions.length" size="small" variant="text" prepend-icon="mdi-lightbulb-on-outline" @click="openSampleSolution(0)">Sample solutions ({{ sampleSolutions.length }})</v-btn>
        </div>
      </template>
      <template #window-content="{ definition }">
        <TaskRichEditor v-if="definition.role === 'task'" :model-value="workspace.taskContentHtml" readonly :element-options="taskElementOptions" :connection-options="taskConnectionOptions" class="canvas-task-window-content" @select-connection="selectTaskConnection" />
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
    <v-dialog v-model="sampleDialog" max-width="1000">
      <v-card>
        <v-card-title class="d-flex align-center">Sample solution {{ sampleIndex + 1 }}<v-spacer /><v-btn icon="mdi-chevron-left" :disabled="sampleIndex <= 0" @click="openSampleSolution(sampleIndex - 1)" /><v-btn icon="mdi-chevron-right" :disabled="sampleIndex >= sampleSolutions.length - 1" @click="openSampleSolution(sampleIndex + 1)" /></v-card-title>
        <v-card-text><ModelSnapshotPreview :data="sampleData" :height="600" /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="sampleDialog = false">Close</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { GraphDataModel } from '@maxgraph/core'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import TaskTopBar from '@/components/modeling/controls/TaskTopBar.vue'
import TaskRichEditor, { type TaskConnectionOption, type TaskElementOption } from '@/components/tasks/TaskRichEditor.vue'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { JsonObject } from '@/services/api/types/common'
import type { CanvasWindowDefinition } from '@/model/CanvasWindow'
import taskService from '@/services/task/task.service'

interface Props {
  modelId?: string
}
const props = defineProps<Props>()
const router = useRouter()
const workspace = useModelWorkspaceStore()
const canvas = ref<{ serializeModel: () => JsonObject; loadPersistedModel: (data: JsonObject) => void; selectConnectionByType: (languageId: string, connectionType: string) => boolean } | null>(null)
const graphModel = ref<GraphDataModel>()
const recoveryDialog = ref(false)
const recoveryData = ref<JsonObject | null>(null)
const hydrating = ref(false)
const loading = ref(false)
const loadError = ref<string | null>(null)
const taskWindowOpen = ref(false)
const sampleDialog = ref(false)
const sampleIndex = ref(0)
const sampleData = ref<JsonObject | null>(null)
const sampleSolutions = computed(() => workspace.taskVersion?.data.sampleSolutions ?? [])
const taskWindows = computed<CanvasWindowDefinition[]>(() =>
  taskWindowOpen.value && workspace.diagramTask
    ? [{ id: 'task-description', title: workspace.diagramTask.title, x: 260, y: 120, width: 520, height: 360, role: 'task' }]
    : []
)
const connections = computed(() => workspace.editorLanguages.flatMap((language) => language.connections))
const taskElementOptions = computed<TaskElementOption[]>(() =>
  workspace.editorLanguages.flatMap((language) =>
    language.elements.map((element) => ({
      languageId: language.id,
      elementType: element.type,
      label: `${language.name}: ${element.defaultLabel || element.type}`,
      element
    }))
  )
)
const taskConnectionOptions = computed<TaskConnectionOption[]>(() =>
  workspace.editorLanguages.flatMap((language) =>
    language.connections.map((connection) => ({
      languageId: language.id,
      connectionType: connection.type,
      label: `${language.name}: ${connection.label || connection.type}`,
      connection
    }))
  )
)
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
  if (!hydrating.value && canvas.value) workspace.setData({ ...canvas.value.serializeModel(), name: workspace.model?.name ?? workspace.data.name })
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
const openSampleSolution = async (index: number) => {
  const reference = sampleSolutions.value[index]
  const taskReference = workspace.taskReference
  if (!reference || !taskReference) return
  sampleIndex.value = index
  sampleDialog.value = true
  sampleData.value = (await taskService.getSampleSolution(taskReference.taskId, taskReference.versionId, reference.modelId, reference.versionId)).data.data
}
onMounted(async () => {
  loading.value = true
  loadError.value = null
  try {
    if (props.modelId) {
      await workspace.load(props.modelId)
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
    loadError.value = 'The model could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.modeling-view {
  position: relative;
  /* Keep the editor usable even when the footer extends below the viewport. */
  height: max(900px, calc(100vh - var(--v-layout-top, 0px)));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.model-loading {
  position: absolute;
  inset: 0 0 auto;
  z-index: 20;
}
.model-load-error {
  position: absolute;
  top: 24px;
  left: 50%;
  z-index: 20;
  width: min(480px, calc(100% - 48px));
  transform: translateX(-50%);
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
