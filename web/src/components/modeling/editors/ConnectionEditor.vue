<template>
  <v-container fluid class="pa-2 editor-surface">
    <v-row no-gutters class="editor-row">
      <!-- Liste der Verbindungen (links) -->
      <v-col cols="3" class="pr-2 editor-col">
        <div class="scroll-column">
          <EditorEntityList title="Connections" add-button-text="New Connection" :items="connections" :selected-index="selectedConnectionIndex" empty-text="No Connections defined" title-field="type" subtitle-field="label" :show-prepend-icon="false" @add="addNewConnection" @select="selectConnection" @delete="deleteConnection" />
        </div>
      </v-col>

      <!-- Editor (mitte) -->
      <v-col cols="5" class="px-1 editor-col">
        <div class="scroll-column">
          <BasicEditorForm type="connection" :selected-item="selectedConnection">
            <ConnectionEditorForm v-if="selectedConnection" v-model:preview-mode="previewMode" :selected-connection="selectedConnection" @update="updateAll" />
          </BasicEditorForm>
        </div>
      </v-col>

      <!-- Canvas Vorschau (rechts, wie im ElementEditor) -->
      <v-col cols="4" class="pl-2 preview-column">
        <v-card class="preview-card">
          <v-card-title class="py-2">
            <span class="text-h6">Preview</span>
          </v-card-title>
          <v-divider />
          <v-card-text>
            <div class="preview-canvas">
              <DrawingCanvas ref="drawingCanvasRef" :show-elements="false" :model="canvasModel" :preview-connection="selectedConnection" :preview-mode="previewMode" :language-connections="connections" :language-elements="elements" :language-syntax="languageSyntaxForCanvas" />
            </div>
            <v-alert v-if="!selectedConnection" type="info" variant="tonal" class="mt-3"> Select a Connection to see a preview </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import type { GraphDataModel } from '@maxgraph/core'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import EditorEntityList from './EditorEntityList.vue'
import BasicEditorForm from '../form/BasicEditorForm.vue'
import ConnectionEditorForm from '../form/ConnectionEditorForm.vue'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import { clearConnectionPreview, renderScenarioConnectionPreview, renderSimpleConnectionPreview, renderRoutingConnectionPreview, type ConnectionPreviewMode } from '@/utils/connectionPreview'

// Props
const store = useDiagramLanguages()

// State
const selectedConnectionIndex = ref<number>(-1)
const canvasModel = ref<GraphDataModel>()
const drawingCanvasRef = ref()
const previewMode = ref<ConnectionPreviewMode>('simple')

// Computed - Verbindungen aus Store
const connections = computed(() => store.definition?.connections || [])
const elements = computed(() => store.definition?.elements || [])
const languageSyntaxForCanvas = computed(() => store.definition?.syntax ?? [])
const selectedConnection = computed<DiagramConnection | undefined>(() => {
  if (selectedConnectionIndex.value < 0) return undefined
  return connections.value[selectedConnectionIndex.value]
})

// Methods
const updateAll = () => {
  // Update-Logik für die Vorschau (analog zu ElementEditor)
  debouncedUpdate()
  debouncedStoreUpdate()
}
const selectConnection = (connectionIndex: number) => {
  selectedConnectionIndex.value = connectionIndex
  nextTick(() => {
    setTimeout(() => renderConnectionPreview(), 50)
  })
}

const addNewConnection = () => {
  if (!store.definition) return

  const newConnection: DiagramConnection = {
    type: `connection_${Date.now()}`,
    label: 'New Connection',
    defaultLabel: '',
    connectionType: 'association',
    style: {
      shape: 'connector',
      strokeColor: '#000000',
      strokeWidth: 2,
      strokeOpacity: 100,
      dashed: false,
      fixDash: false,
      startArrow: 'none',
      startFill: true,
      endArrow: 'none',
      endFill: true,
      align: 'center',
      verticalAlign: 'middle',
      fontColor: '#000000',
      fontSize: 12,
      rounded: false,
      curved: false
    },
    labelOffset: {},
    additionalLabels: []
  }

  store.addConnectionToLanguage(newConnection)
  selectedConnectionIndex.value = connections.value.length - 1
}

const deleteConnection = (connectionIndex: number) => {
  if (!store.definition) return

  const connection = connections.value[connectionIndex]
  if (!connection) return

  store.removeConnectionFromLanguage(connection.type)
  selectedConnectionIndex.value = -1
}

// Vorschau-Logik wie im ElementEditor
const getPreviewGraph = () => {
  const canvas = drawingCanvasRef.value as { graph?: any } | undefined
  if (!canvas?.graph) return null
  const exposed = canvas.graph
  return exposed && 'value' in exposed ? exposed.value : exposed
}

const renderConnectionPreview = () => {
  const graphInstance = getPreviewGraph()
  const connection = selectedConnection.value

  if (!graphInstance) return

  if (!connection) {
    clearConnectionPreview(graphInstance)
    return
  }

  if (previewMode.value === 'scenario') {
    renderScenarioConnectionPreview(graphInstance, connection)
    return
  }

  if (previewMode.value === 'routing') {
    renderRoutingConnectionPreview(graphInstance, connection)
    return
  }

  renderSimpleConnectionPreview(graphInstance, connection)
}

// Debounced Update für Vorschau und Store
let updateTimeout: number | null = null
const debouncedUpdate = () => {
  if (updateTimeout) {
    clearTimeout(updateTimeout)
  }
  updateTimeout = setTimeout(() => {
    renderConnectionPreview()
  }, 150)
}

const debouncedStoreUpdate = () => {
  if (selectedConnection.value && store.definition) {
    store.updateConnectionInLanguage(selectedConnection.value.type, selectedConnection.value)
  }
}

// Watchers
watch(
  selectedConnection,
  (newConn) => {
    if (newConn) {
      renderConnectionPreview()
      debouncedUpdate()
    } else {
      renderConnectionPreview()
    }
  },
  { immediate: true, deep: true }
)

watch(
  previewMode,
  () => {
    renderConnectionPreview()
  },
  { immediate: true }
)

// Lifecycle
onMounted(() => {
  // Canvas initialisieren mit mehreren Versuchen (wie im ElementEditor)
  const initializeCanvas = (attempts = 0) => {
    if (attempts > 10) {
      console.warn('Failed to initialize canvas after 10 attempts')
      return
    }
    if (drawingCanvasRef.value?.graph) {
      renderConnectionPreview()
    } else {
      setTimeout(() => initializeCanvas(attempts + 1), 200)
    }
  }
  nextTick(() => {
    setTimeout(() => initializeCanvas(), 100)
  })
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}

.editor-surface {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.editor-row {
  flex: 1;
  min-height: 0;
}

.editor-col,
.preview-column {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.scroll-column {
  height: 100%;
  max-height: 100%;
  overflow-y: auto;
  padding-right: 4px;
}

.preview-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-card :deep(.v-card-text) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.preview-canvas {
  flex: 1;
  min-height: 280px;
  max-height: 100%;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.preview-canvas :deep(.v-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.preview-canvas :deep(.v-card-text) {
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.preview-canvas :deep(.graph-container) {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
}

.preview-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background-color: rgba(255, 255, 255, 0.9);
  text-align: center;
}

.preview-overlay .v-icon {
  color: var(--v-theme-primary);
}
</style>
