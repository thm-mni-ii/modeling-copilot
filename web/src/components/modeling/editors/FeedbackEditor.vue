<template>
  <v-container fluid class="pa-2 editor-surface">
    <v-row no-gutters class="editor-row">
      <!-- Ziel-Liste (links) -->
      <v-col cols="3" class="pr-2 editor-col">
        <div class="scroll-column">
          <EditorEntityList
            v-if="activeFeedbackEditorTab === 'overlay'"
            title="Feedback Targets"
            add-button-text=""
            :show-add-button="false"
            :show-delete-button="false"
            :items="feedbackTargets"
            :selected-index="selectedTargetIndex"
            empty-text="No Elements or Connections available"
            title-field="label"
            subtitle-field="subtitle"
            icon-field="targetType"
            color-field="targetType"
            :icon-map="targetIconMap"
            :color-map="targetColorMap"
            @select="selectTarget"
          />
          <EditorEntityList
            v-else
            title="Feedback Elements"
            add-button-text="Add"
            :show-add-button="true"
            :show-delete-button="true"
            :items="feedbackCanvasElementItems"
            :selected-index="selectedCanvasElementIndex"
            empty-text="No Feedback Elements available"
            title-field="label"
            subtitle-field="subtitle"
            icon-field="icon"
            color-field="color"
            @add="addCanvasElement"
            @delete="removeCanvasElement"
            @select="selectCanvasElement"
          />
        </div>
      </v-col>

      <!-- Konfigurationsformular -->
      <v-col cols="5" class="px-1 editor-col">
        <div class="scroll-column">
          <v-tabs v-model="activeFeedbackEditorTab" density="compact" color="primary" class="mb-3">
            <v-tab value="overlay">Overlay</v-tab>
            <v-tab value="canvas">Feedback Elements</v-tab>
          </v-tabs>

          <div v-show="activeFeedbackEditorTab === 'overlay'">
            <BasicEditorForm type="feedback" :selected-item="selectedTargetSummary">
              <FeedbackEditorForm v-if="selectedConfig" :config="selectedConfig" :state-definitions="stateDefinitions" @update="scheduleConfigUpdate" />
            </BasicEditorForm>
          </div>

          <div v-show="activeFeedbackEditorTab === 'canvas'">
            <BasicEditorForm type="feedback" :selected-item="selectedCanvasConfigSummary">
              <FeedbackCanvasConfiguratorForm v-if="selectedCanvasConfig" :config="selectedCanvasConfig" @update="scheduleCanvasConfigUpdate" />
            </BasicEditorForm>
          </div>
        </div>
      </v-col>

      <!-- Vorschau -->
      <v-col cols="4" class="pl-2 preview-column">
        <v-card class="preview-card">
          <v-card-title class="py-2 d-flex align-center">
            <v-btn icon="mdi-dock-left" size="small" variant="text" :title="previewSidebarVisible ? 'Hide element palette' : 'Show element palette'" :aria-label="previewSidebarVisible ? 'Hide element palette' : 'Show element palette'" :aria-expanded="previewSidebarVisible" @click="previewSidebarVisible = !previewSidebarVisible" />
            <span class="text-h6">Feedback Preview</span>
            <v-spacer />
            <v-btn-toggle v-model="previewState" density="compact" mandatory color="primary">
              <v-btn v-for="state in stateDefinitions" :key="state.key" :value="state.key">
                <v-icon start class="mr-1">{{ state.icon }}</v-icon>
                {{ state.shortLabel }}
              </v-btn>
            </v-btn-toggle>
          </v-card-title>

          <v-divider />

          <v-card-text>
            <div class="preview-canvas">
              <DrawingCanvas
                ref="drawingCanvasRef"
                :show-elements="previewSidebarVisible"
                :show-feedback-sidebar="false"
                :language-elements="languageElementsForCanvas"
                :language-connections="languageConnectionsForCanvas"
                :language-syntax="languageSyntaxForCanvas"
                :show-toolbar="true"
                :allow-edit="true"
                :context-menu="true"
                :overlays="previewCanvasOverlays"
                :feedback-config="previewFeedbackConfig"
              />
            </div>
            <v-alert v-if="activeFeedbackEditorTab === 'overlay' && !selectedTargetSummary" type="info" variant="tonal" class="mt-3"> Select an Element or Connection to test the feedback position. </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import EditorEntityList from '@/components/modeling/editors/EditorEntityList.vue'
import BasicEditorForm from '@/components/modeling/form/BasicEditorForm.vue'
import FeedbackEditorForm from '@/components/modeling/form/FeedbackEditorForm.vue'
import FeedbackCanvasConfiguratorForm from '@/components/modeling/form/FeedbackCanvasConfiguratorForm.vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import { createCellFromElement, addCellToGraph } from '@/utils/elementFactory'
import { clearConnectionPreview, renderSimpleConnectionPreview } from '@/utils/connectionPreview'
import type { DiagramElement, DiagramConnection } from '@/model/DiagramLanguage'
import type { DiagramFeedbackConfig, FeedbackCanvasConfig, FeedbackCanvasOverlayEntry, FeedbackState, FeedbackTargetOverlays } from '@/model/Feedback'
import { FEEDBACK_STATE_LABELS } from '@/model/Feedback'
import { cloneFeedbackCanvasConfig, cloneFeedbackTargetOverlays, createDefaultFeedbackCanvasConfig, createDefaultFeedbackCanvasElementConfig } from '@/utils/feedbackConfig'

const store = useDiagramLanguages()

const drawingCanvasRef = ref()
const previewSidebarVisible = ref(false)
const selectedTargetIndex = ref<number>(-1)
const selectedConfig = ref<FeedbackTargetOverlays | null>(null)
const selectedCanvasConfig = ref<FeedbackCanvasConfig | null>(null)
const previewState = ref<FeedbackState>('correct')
const previewCellId = ref<string | null>(null)
const activeFeedbackEditorTab = ref<'overlay' | 'canvas'>('overlay')

const hydratingConfig = ref(false)
const hydratingCanvasConfig = ref(false)
let storeUpdateTimeout: ReturnType<typeof setTimeout> | null = null
let canvasConfigUpdateTimeout: ReturnType<typeof setTimeout> | null = null

const languageElementsForCanvas = computed(() => store.definition?.elements ?? [])
const languageConnectionsForCanvas = computed(() => store.definition?.connections ?? [])
const languageSyntaxForCanvas = computed(() => store.definition?.syntax ?? [])

const previewCanvasOverlays = computed<FeedbackCanvasOverlayEntry[]>(() => {
  if (activeFeedbackEditorTab.value !== 'overlay') return []
  if (!previewCellId.value || !selectedConfig.value) return []
  const config = selectedConfig.value[previewState.value]
  if (!config) return []
  return [
    {
      id: `preview-${previewState.value}`,
      cellId: previewCellId.value,
      config
    }
  ]
})

const previewFeedbackConfig = computed<DiagramFeedbackConfig | undefined>(() => {
  const feedback = store.definition?.feedback
  if (!feedback) return undefined

  return {
    ...feedback,
    canvas: selectedCanvasConfig.value ? cloneFeedbackCanvasConfig(selectedCanvasConfig.value) : createDefaultFeedbackCanvasConfig(feedback.canvas)
  }
})

interface FeedbackTargetItem {
  type: string
  label: string
  subtitle: string
  targetType: 'element' | 'connection'
  id: string
}

const feedbackTargets = computed<FeedbackTargetItem[]>(() => {
  const language = store.definition
  if (!language) return []

  const elementTargets = language.elements.map((element) => ({
    type: `element:${element.type}`,
    label: element.defaultLabel || element.type,
    subtitle: 'Element',
    targetType: 'element' as const,
    id: element.type
  }))

  const connectionTargets = language.connections.map((connection) => ({
    type: `connection:${connection.type}`,
    label: connection.label || connection.type,
    subtitle: 'Connection',
    targetType: 'connection' as const,
    id: connection.type
  }))

  return [...elementTargets, ...connectionTargets]
})

const selectedTarget = computed<FeedbackTargetItem | undefined>(() => {
  if (selectedTargetIndex.value < 0) return undefined
  return feedbackTargets.value[selectedTargetIndex.value]
})

const selectedTargetSummary = computed(() => {
  if (!selectedTarget.value) return undefined
  const suffix = selectedTarget.value.targetType === 'element' ? 'Element' : 'Connection'
  return {
    name: `${selectedTarget.value.label} (${suffix})`
  }
})

const selectedCanvasConfigSummary = computed(() => {
  if (!store.language) return undefined
  return {
    name: `Feedback Elements (${store.language.name})`
  }
})

const activeFeedbackCanvasElement = computed(() => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig || !Array.isArray(canvasConfig.configurableElements) || canvasConfig.configurableElements.length === 0) {
    return null
  }

  const activeId = canvasConfig.activeElementId
  if (activeId) {
    const selected = canvasConfig.configurableElements.find((entry) => entry.id === activeId)
    if (selected) return selected
  }

  return canvasConfig.configurableElements[0] ?? null
})

const feedbackCanvasElementItems = computed(() => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig || !Array.isArray(canvasConfig.configurableElements)) return []

  return canvasConfig.configurableElements.map((entry, index) => ({
    type: entry.id,
    id: entry.id,
    label: entry.element.defaultLabel || entry.element.type || `Feedback ${index + 1}`,
    subtitle: entry.connection.label || entry.connection.type || 'Connection',
    icon: 'mdi-comment-text-outline',
    color: 'orange-darken-2'
  }))
})

const selectedCanvasElementIndex = computed(() => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig || !Array.isArray(canvasConfig.configurableElements) || canvasConfig.configurableElements.length === 0) {
    return -1
  }

  const activeId = canvasConfig.activeElementId
  if (!activeId) return 0
  const index = canvasConfig.configurableElements.findIndex((entry) => entry.id === activeId)
  return index >= 0 ? index : 0
})

const stateDefinitions = [
  { key: 'correct' as FeedbackState, label: FEEDBACK_STATE_LABELS.correct, shortLabel: FEEDBACK_STATE_LABELS.correct, color: 'success', icon: 'mdi-check-circle-outline' },
  { key: 'incorrect' as FeedbackState, label: FEEDBACK_STATE_LABELS.incorrect, shortLabel: FEEDBACK_STATE_LABELS.incorrect, color: 'error', icon: 'mdi-close-circle-outline' },
  { key: 'hint' as FeedbackState, label: FEEDBACK_STATE_LABELS.hint, shortLabel: FEEDBACK_STATE_LABELS.hint, color: 'warning', icon: 'mdi-alert-circle-outline' }
]

const targetIconMap = {
  element: 'mdi-shape',
  connection: 'mdi-vector-line'
}

const targetColorMap = {
  element: 'indigo',
  connection: 'teal-darken-2'
}

let renderPreviewTimeout: ReturnType<typeof setTimeout> | null = null

const triggerRenderPreview = () => {
  nextTick(() => {
    if (renderPreviewTimeout) {
      clearTimeout(renderPreviewTimeout)
    }
    renderPreviewTimeout = setTimeout(() => {
      renderPreview()
    }, 50)
  })
}

const selectTarget = (index: number) => {
  if (drawingCanvasRef.value?.clearCanvas) {
    drawingCanvasRef.value.clearCanvas()
  }
  previewCellId.value = null
  selectedTargetIndex.value = index
  triggerRenderPreview()
}

const scheduleConfigUpdate = () => {
  if (hydratingConfig.value || !selectedConfig.value || !store.definition || !selectedTarget.value) return
  if (storeUpdateTimeout) {
    clearTimeout(storeUpdateTimeout)
  }
  const targetType = selectedTarget.value.targetType
  const targetId = selectedTarget.value.id
  const configSnapshot = cloneFeedbackTargetOverlays(selectedConfig.value)
  storeUpdateTimeout = setTimeout(() => {
    store.updateFeedbackEntryForLanguage(targetType, targetId, configSnapshot)
  }, 180)
}

const scheduleCanvasConfigUpdate = () => {
  if (hydratingCanvasConfig.value || !selectedCanvasConfig.value || !store.definition) return
  if (canvasConfigUpdateTimeout) {
    clearTimeout(canvasConfigUpdateTimeout)
  }
  const canvasConfigSnapshot = cloneFeedbackCanvasConfig(selectedCanvasConfig.value)
  canvasConfigUpdateTimeout = setTimeout(() => {
    store.updateFeedbackCanvasConfigForLanguage(canvasConfigSnapshot)
  }, 180)
}

const findNextCanvasElementIndex = () => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig) return 1
  let index = canvasConfig.configurableElements.length + 1
  const existingIds = new Set(canvasConfig.configurableElements.map((entry) => entry.id))
  while (existingIds.has(`feedback-element-${index}`)) {
    index += 1
  }
  return index
}

const selectCanvasElement = (index: number) => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig) return
  const selected = canvasConfig.configurableElements[index]
  if (!selected) return
  canvasConfig.activeElementId = selected.id
  triggerRenderPreview()
}

const addCanvasElement = () => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig) return
  const nextIndex = findNextCanvasElementIndex()
  const entry = createDefaultFeedbackCanvasElementConfig(nextIndex)
  canvasConfig.configurableElements.push(entry)
  canvasConfig.activeElementId = entry.id
  triggerRenderPreview()
}

const removeCanvasElement = (index: number) => {
  const canvasConfig = selectedCanvasConfig.value
  if (!canvasConfig) return
  if (index < 0 || index >= canvasConfig.configurableElements.length) return

  canvasConfig.configurableElements.splice(index, 1)
  if (canvasConfig.configurableElements.length === 0) {
    const fallback = createDefaultFeedbackCanvasElementConfig(1)
    canvasConfig.configurableElements.push(fallback)
    canvasConfig.activeElementId = fallback.id
  } else if (!canvasConfig.activeElementId || !canvasConfig.configurableElements.some((entry) => entry.id === canvasConfig.activeElementId)) {
    canvasConfig.activeElementId = canvasConfig.configurableElements[Math.min(index, canvasConfig.configurableElements.length - 1)].id
  }

  triggerRenderPreview()
}

const loadSelectedConfig = () => {
  if (!selectedTarget.value || !store.definition) {
    selectedConfig.value = null
    previewCellId.value = null
    return
  }

  const feedback = store.definition.feedback
  const container = selectedTarget.value.targetType === 'element' ? feedback?.elements : feedback?.connections
  const source = container?.[selectedTarget.value.id] ?? null

  hydratingConfig.value = true
  selectedConfig.value = cloneFeedbackTargetOverlays(source ?? undefined)
  nextTick(() => {
    hydratingConfig.value = false
  })
}

const loadCanvasConfig = () => {
  const feedback = store.definition?.feedback

  hydratingCanvasConfig.value = true
  selectedCanvasConfig.value = cloneFeedbackCanvasConfig(feedback?.canvas)
  nextTick(() => {
    hydratingCanvasConfig.value = false
    if (activeFeedbackEditorTab.value === 'canvas') {
      triggerRenderPreview()
    }
  })
}

const renderPreview = () => {
  const canvas = drawingCanvasRef.value
  if (!canvas?.graph) return

  canvas.clearCanvas()
  clearConnectionPreview(canvas.graph)
  previewCellId.value = null

  if (activeFeedbackEditorTab.value === 'canvas') {
    const activeCanvasElement = activeFeedbackCanvasElement.value
    if (!activeCanvasElement) return

    const graph = canvas.graph
    graph.batchUpdate(() => {
      const created = createCellFromElement(activeCanvasElement.element, 80, 60)
      addCellToGraph(graph, created, activeCanvasElement.element as DiagramElement, graph.getDefaultParent())
      previewCellId.value = created.getId?.() ?? null
      graph.setSelectionCell(created)
    })
    return
  }

  const target = selectedTarget.value
  const language = store.definition
  if (!target || !language) return

  if (target.targetType === 'element') {
    const element = language.elements.find((el) => el.type === target.id)
    if (!element) return
    const graph = canvas.graph
    graph.batchUpdate(() => {
      const created = createCellFromElement(element, 60, 40)
      addCellToGraph(graph, created, element as DiagramElement, graph.getDefaultParent())
      previewCellId.value = created.getId?.() ?? null
      graph.setSelectionCell(created)
    })
  } else {
    const connection = language.connections.find((conn) => conn.type === target.id)
    if (!connection) return
    const edge = renderSimpleConnectionPreview(canvas.graph, connection as DiagramConnection)
    if (edge) {
      previewCellId.value = edge.getId?.() ?? null
      canvas.graph.setSelectionCell(edge)
    }
  }
}

watch(
  feedbackTargets,
  (targets) => {
    if (targets.length === 0) {
      selectedTargetIndex.value = -1
      selectedConfig.value = null
      previewCellId.value = null
      if (drawingCanvasRef.value?.clearCanvas) {
        drawingCanvasRef.value.clearCanvas()
      }
      return
    }
    if (selectedTargetIndex.value < 0 || selectedTargetIndex.value >= targets.length) {
      selectedTargetIndex.value = 0
      triggerRenderPreview()
    }
  },
  { immediate: true }
)

watch(selectedTarget, () => {
  loadSelectedConfig()
  previewCellId.value = null
  triggerRenderPreview()
})

watch(activeFeedbackEditorTab, () => {
  triggerRenderPreview()
})

watch(
  () => store.currentVersion?.id,
  () => {
    if (storeUpdateTimeout) {
      clearTimeout(storeUpdateTimeout)
      storeUpdateTimeout = null
    }
    if (canvasConfigUpdateTimeout) {
      clearTimeout(canvasConfigUpdateTimeout)
      canvasConfigUpdateTimeout = null
    }
    loadCanvasConfig()
  },
  { immediate: true }
)

watch(
  selectedConfig,
  () => {
    if (hydratingConfig.value || !selectedConfig.value) return
    scheduleConfigUpdate()
  },
  { deep: true }
)

watch(
  selectedCanvasConfig,
  () => {
    if (hydratingCanvasConfig.value || !selectedCanvasConfig.value) return
    scheduleCanvasConfigUpdate()
    if (activeFeedbackEditorTab.value === 'canvas') {
      triggerRenderPreview()
    }
  },
  { deep: true }
)

onMounted(() => {
  const initializeCanvas = (attempts = 0) => {
    if (attempts > 10) {
      console.warn('Feedback preview could not be initialized')
      return
    }
    if (drawingCanvasRef.value?.graph) {
      renderPreview()
    } else {
      setTimeout(() => initializeCanvas(attempts + 1), 200)
    }
  }

  nextTick(() => {
    setTimeout(() => initializeCanvas(), 100)
  })
})

onUnmounted(() => {
  if (storeUpdateTimeout) {
    clearTimeout(storeUpdateTimeout)
    storeUpdateTimeout = null
  }
  if (renderPreviewTimeout) {
    clearTimeout(renderPreviewTimeout)
    renderPreviewTimeout = null
  }
  if (canvasConfigUpdateTimeout) {
    clearTimeout(canvasConfigUpdateTimeout)
    canvasConfigUpdateTimeout = null
  }
})
</script>

<style scoped>
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
  border-radius: 4px;
  overflow: hidden;
}
</style>
