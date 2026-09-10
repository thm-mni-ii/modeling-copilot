<template>
  <v-card class="pa-2" height="100%" width="100%">
    <v-card-text class="pa-1 canvas-content">
      <ModelingHeader v-if="props.showToolbar && props.modelManagement" class="mb-2">
        <template #controls>
          <CanvasToolbar
            ref="canvasToolbar"
            v-model:layer-view="activeLayerView"
            :connections="languageConnections"
            :connection-groups="props.connectionGroups"
            :connection-preferences="props.connectionPreferences"
            @select-all="selectAll"
            @clear-selection="clearSelection"
            @delete-selected="deleteSelected"
            @duplicate-selected="duplicateSelected"
            @align-left="alignLeft"
            @align-center-h="alignCenterH"
            @align-right="alignRight"
            @align-top="alignTop"
            @align-middle-v="alignMiddleV"
            @align-bottom="alignBottom"
            @select-connection="onConnectionSelected"
            @update:connection-preferences="updateConnectionPreferences"
          />
        </template>
        <template #save-tools>
          <v-btn icon="mdi-undo" size="x-small" :disabled="!canUndo" title="Undo (Ctrl+Z)" @click="undoGraph" />
          <v-btn icon="mdi-redo" size="x-small" :disabled="!canRedo" title="Redo (Ctrl+Y)" @click="redoGraph" />
        </template>
        <template #sidebar-toggle>
          <v-btn icon="mdi-dock-right" size="x-small" variant="text" :title="rightSidebarCollapsed ? 'Expand right sidebar' : 'Collapse right sidebar'" :aria-label="rightSidebarCollapsed ? 'Expand right sidebar' : 'Collapse right sidebar'" :aria-expanded="!rightSidebarCollapsed" @click="rightSidebarCollapsed = !rightSidebarCollapsed" />
        </template>
        <template #autonomy><AutonomyControls :mode="autonomyMode" @update:mode="updateAutonomyMode" /></template>
      </ModelingHeader>

      <!-- Erweiterte Toolbar für Einbettungen ohne Modellverwaltung -->
      <div v-else-if="props.showToolbar" class="toolbar-actions mb-2">
        <CanvasToolbar
          ref="canvasToolbar"
          v-model:layer-view="activeLayerView"
          :connections="languageConnections"
          :connection-groups="props.connectionGroups"
          :connection-preferences="props.connectionPreferences"
          @select-all="selectAll"
          @clear-selection="clearSelection"
          @delete-selected="deleteSelected"
          @duplicate-selected="duplicateSelected"
          @align-left="alignLeft"
          @align-center-h="alignCenterH"
          @align-right="alignRight"
          @align-top="alignTop"
          @align-middle-v="alignMiddleV"
          @align-bottom="alignBottom"
          @select-connection="onConnectionSelected"
          @update:connection-preferences="updateConnectionPreferences"
        />
        <AutonomyControls :mode="autonomyMode" @update:mode="updateAutonomyMode" />
      </div>

      <!-- Canvas Area: Sidebar + Graph -->
      <div class="canvas-area">
        <!-- Elements Sidebar -->
        <SidebarContainer v-if="props.showElements !== false && props.showModelSidebar !== false && props.showToolbar && (props.modelManagement || sidebarLanguages.length > 0)" :languages="sidebarLanguages" :model-management="props.modelManagement" />

        <!-- Graph Container -->
        <div ref="graphWrapper" class="graph-wrapper">
          <div ref="graphContainer" class="graph-container" tabindex="0" @pointerdown="focusGraphContainer">
            <!-- Separater Grid Container -->
            <div class="grid-container">
              <canvas ref="canvasGrid" class="grid-canvas"></canvas>
            </div>

            <GraphControls @zoom-in="zoomIn" @zoom-out="zoomOut" @fit-to-window="fitToWindow" @toggle-grid="toggleGrid" @force-grid-repaint="forceGridRepaint" />

            <!-- Graph Settings Component -->
            <GraphSettings @update:grid-size="updateGridSize" @update:tolerance="updateTolerance" @update:snap-to-grid="updateSnapToGrid" @update:use-grid-for-panning="updateUseGridForPanning" />

            <div class="shortcut-help-anchor" :class="{ 'hidden-during-pan': isPanning }">
              <v-tooltip location="left" transition="scale-transition">
                <template #activator="{ props: activatorProps }">
                  <v-btn v-bind="activatorProps" icon size="small" color="primary" variant="flat" class="shortcut-help-btn" aria-label="Show keyboard shortcuts">
                    <v-icon size="18">mdi-information-outline</v-icon>
                  </v-btn>
                </template>

                <div class="shortcut-tooltip-content">
                  <div><strong>Keyboard shortcuts</strong></div>
                  <div>Ctrl+A: Select all</div>
                  <div>Ctrl+C: Copy</div>
                  <div>Ctrl+V: Paste</div>
                  <div>Ctrl+D: Duplicate</div>
                  <div>Ctrl+Z: Undo</div>
                  <div>Ctrl+Y: Redo</div>
                  <div>Del: Delete</div>
                  <div>Esc: Clear selection</div>
                  <div>Mouse wheel on canvas: Zoom in/out</div>
                </div>
              </v-tooltip>
            </div>
          </div>

          <CanvasWindowHost ref="canvasWindowHost" :graph-container="graphContainer ?? null" :windows="props.canvasWindows" @window-removed="onWindowRemoved">
            <template #window-content="slotProps">
              <slot name="window-content" v-bind="slotProps">
                <div class="canvas-window-default-content">
                  {{ slotProps.definition.placeholder ?? 'Window ready. Content can be provided through the window-content slot or the window definition.' }}
                </div>
              </slot>
            </template>
          </CanvasWindowHost>

          <v-tooltip v-if="overlayTooltip.anchor" :model-value="overlayTooltip.visible" location="top" :open-on-hover="false" transition="scale-transition" @update:model-value="(value) => (overlayTooltip.visible = value)">
            <template #activator="{ props: activatorProps }">
              <div v-bind="activatorProps" class="canvas-tooltip-anchor" :style="overlayTooltipAnchorStyle"></div>
            </template>
            {{ overlayTooltip.text }}
          </v-tooltip>
        </div>
        <SidebarRightContainer v-if="props.showElements !== false && props.showModelSidebar !== false && props.showToolbar && props.modelManagement" :collapsed="rightSidebarCollapsed" :feedback-shapes="feedbackShapes" />
      </div>
      <!-- /canvas-area -->
    </v-card-text>

    <v-dialog v-model="validationDialogVisible" max-width="640">
      <v-card>
        <v-card-title>Validation Errors</v-card-title>
        <v-card-text>
          <ul class="validation-errors">
            <li v-for="(message, index) in validationMessages" :key="`validation-${index}`">
              {{ message }}
            </li>
          </ul>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" variant="text" @click="validationDialogVisible = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { Graph, InternalEvent, RubberBandHandler, Cell, CellOverlay, CellEditorHandler, SelectionCellsHandler, SelectionHandler, CellState, EdgeStyle, GraphDataModel, PanningHandler, ImageBox, Client, KeyHandler, TooltipHandler, FitPlugin, Clipboard, ConnectionConstraint } from '@maxgraph/core'
import type { GraphPluginConstructor } from '@maxgraph/core'
import type { JsonObject } from '@/services/api/types/common'
import { provideGraphContext } from '@/composables/useGraphContext'
import { useGraphOperations } from '@/composables/useGraphOperations'
import { useZoomOperations } from '@/composables/useZoomOperations'
import { useGridSettings } from '@/composables/useGridSettings'
import { useCanvasOverlays } from '@/composables/useCanvasOverlays'
import { setupDynamicGrid } from '@/utils/setupDynamicGrid'
import { createDefaultShapes, buildShapesFromElements, ensureGraphDropHandlers } from '@/utils/setupToolbar'
import { setupSwimlaneSupport } from '@/utils/setupSwimlaneSupport'
import { clearConnectionPreview, renderScenarioConnectionPreview, renderSimpleConnectionPreview, renderRoutingConnectionPreview } from '@/utils/connectionPreview'
import { CustomConnectionHandler } from '@/utils/CustomConnectionHandler'
import { setupUndoManager, type UndoManagerApi, type UndoManagerState } from '@/utils/setupUndoManager'
import { alignHorizontal, alignVertical } from '@/utils/alignCells'
import { clearValidationWarningOverlays, getGraphValidationMode, isValidationPassActive, setGraphValidationMode } from '@/utils/graphValidationRuntime'
import { createCellFromElement } from '@/utils/elementFactory'
import GraphSettings from './GraphSettings.vue'
import CanvasWindowHost from './CanvasWindowHost.vue'
import CanvasToolbar from '@/components/modeling/controls/CanvasToolbar.vue'
import GraphControls from '@/components/modeling/controls/GraphControls.vue'
import AutonomyControls from '@/components/modeling/controls/AutonomyControls.vue'
import type { CanvasLayerView } from '@/components/modeling/controls/LayerVisibilityControls.vue'
import ModelingHeader from '@/components/modeling/controls/ModelingHeader.vue'
import SidebarContainer from '@/components/modeling/sidebars/SidebarContainer.vue'
import SidebarRightContainer from '@/components/modeling/sidebars/SidebarRightContainer.vue'
import type { SidebarLanguage } from '@/components/modeling/sidebars/ElementsSidebar.vue'
import type { DiagramElement } from '@/model/Element'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'
import type { DiagramSyntax } from '@/model/Syntax'
import type { CanvasWindowDefinition, CanvasWindowPatch } from '@/model/CanvasWindow'
import { buildValidationRulesFromSyntax, DiagramValidator } from '@/utils/multiplicity'
import type { AutonomyMode } from '@/model/Autonomy'
import type { DiagramFeedbackConfig, FeedbackCanvasOverlayEntry } from '@/model/Feedback'
import { createDefaultFeedbackCanvasConfig } from '@/utils/feedbackConfig'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'

import img_rectangle from '@/assets/images/rectangle.gif'
import img_ellipse from '@/assets/images/ellipse.gif'
import img_rhombus from '@/assets/images/rhombus.gif'
import img_triangle from '@/assets/images/triangle.gif'
import img_cloud from '@/assets/images/cloud.gif'
import img_elementPlaceholder from '@/assets/images/rectangle.gif'

class MyCustomCellEditorHandler extends CellEditorHandler {
  // Custom CellEditorHandler - kann später erweitert werden
  // Beispiel: Anpassung der Editor-Darstellung, Validierung, etc.

  override startEditing(cell: Cell, trigger: MouseEvent | null) {
    super.startEditing(cell, trigger)

    // Optionale Anpassungen am Editor nach dem Start
    if (this.textarea != null) {
      // Hier können weitere Anpassungen vorgenommen werden, z.B.:
      // this.textarea.style.color = '#000000'
      // this.textarea.style.backgroundColor = '#ffffff'
    }
  }

  override stopEditing(cancel: boolean) {
    super.stopEditing(cancel)
  }
}

class MyCustomGraph extends Graph {
  constructor(container: HTMLElement, model?: GraphDataModel, plugins?: GraphPluginConstructor[]) {
    super(container, model, plugins)
    this.overlayAddedCallback = undefined
    this.overlayRemovedCallback = undefined

    const originalIsCellFoldable = this.isCellFoldable.bind(this)
    this.isCellFoldable = (cell: Cell, collapse: boolean): boolean => {
      const style = this.getCurrentCellStyle(cell) as Record<string, any> | null
      const foldableFlag = style?.foldable

      if (foldableFlag === false || foldableFlag === '0') {
        return false
      }

      if (foldableFlag === true || foldableFlag === 1 || foldableFlag === '1') {
        return true
      }

      return originalIsCellFoldable(cell, collapse)
    }
  }

  override getAllConnectionConstraints = (terminal: CellState | null, _source: boolean) => {
    void _source
    return (terminal?.cell?.geometry as any)?.constraints ?? null
  }

  /**
   * Behebt den MaxGraph Round-Trip-Bug: exitPerimeter/entryPerimeter wird als '0' (String)
   * gespeichert, aber '0' ist in JS truthy → perimeter=false Constraints verhalten sich wie true.
   */
  override getConnectionConstraint = (edge: CellState, terminal: CellState | null, source: boolean): ConnectionConstraint => {
    const constraint = super.getConnectionConstraint(edge, terminal, source)
    const p = (constraint as any).perimeter
    if (p === '0' || p === 0) {
      ;(constraint as any).perimeter = false
    }
    return constraint
  }

  override isCellEditable = (cell: Cell) => {
    const allow = (cell as any).allowLabelEdit

    if (allow === false) {
      return false
    }
    if (allow === true) {
      return true
    }
    return super.isCellEditable(cell)
  }

  override convertValueToString = (cell: Cell) => {
    return super.convertValueToString(cell)
  }

  override getEdgeValidationError = (edge: Cell | null, source: Cell | null, target: Cell | null): string | null => {
    const error = super.getEdgeValidationError(edge, source, target)
    const mode = getGraphValidationMode(this)
    if (mode === 'preventive') {
      return error
    }
    return isValidationPassActive(this) ? error : null
  }

  private overlayAddedCallback?: (cell: Cell, overlay: CellOverlay) => void
  private overlayRemovedCallback?: (cell: Cell, overlay: CellOverlay) => void

  setOverlayCallbacks(onAdd?: (cell: Cell, overlay: CellOverlay) => void, onRemove?: (cell: Cell, overlay: CellOverlay) => void) {
    this.overlayAddedCallback = onAdd
    this.overlayRemovedCallback = onRemove
  }

  override addCellOverlay = (cell: Cell, overlay: CellOverlay) => {
    const result = super.addCellOverlay(cell, overlay)
    this.overlayAddedCallback?.(cell, overlay)
    return result
  }

  override removeCellOverlay = (cell: Cell, overlay: CellOverlay | null) => {
    const removed = super.removeCellOverlay(cell, overlay)
    const target = overlay ?? removed ?? null
    if (target) {
      this.overlayRemovedCallback?.(cell, target)
    }
    return removed
  }

  override removeCellOverlays = (cell: Cell) => {
    const overlays = this.getCellOverlays(cell)
    const removed = super.removeCellOverlays(cell)
    overlays?.forEach((item) => this.overlayRemovedCallback?.(cell, item))
    return removed
  }
}

interface CanvasWindowHostApi {
  addWindow: (windowDefinition: CanvasWindowDefinition) => void
  updateWindow: (patch: CanvasWindowPatch) => void
  removeWindow: (id: string) => void
  clearWindows: () => void
  setWindows: (definitions: CanvasWindowDefinition[]) => void
}

interface CanvasToolbarApi {
  closeConnectionPalette: () => void
}

const props = withDefaults(
  defineProps<{
    model?: GraphDataModel
    allowEdit?: boolean
    showToolbar?: boolean
    showElements?: boolean
    showModelSidebar?: boolean
    modelManagement?: boolean
    contextMenu?: boolean
    languageName?: string
    languageElements?: DiagramElement[]
    languageConnections?: DiagramConnection[]
    connectionGroups?: DiagramConnectionGroup[]
    connectionPreferences?: JsonObject
    languageSyntax?: DiagramSyntax[]
    languages?: SidebarLanguage[]
    autonomyMode?: AutonomyMode
    previewConnection?: DiagramConnection
    previewMode?: 'simple' | 'scenario' | 'routing'
    overlays?: FeedbackCanvasOverlayEntry[]
    feedbackConfig?: DiagramFeedbackConfig
    canvasWindows?: CanvasWindowDefinition[]
  }>(),
  {
    allowEdit: true,
    showToolbar: true,
    showElements: true,
    showModelSidebar: true,
    modelManagement: false,
    contextMenu: false,
    languageName: undefined,
    languageElements: undefined,
    languageConnections: undefined,
    connectionGroups: undefined,
    connectionPreferences: undefined,
    languageSyntax: undefined,
    languages: undefined,
    autonomyMode: 'free',
    previewConnection: undefined,
    previewMode: 'simple',
    overlays: () => [],
    feedbackConfig: undefined,
    canvasWindows: undefined
  }
)

const emit = defineEmits<{
  'update:model': [GraphDataModel]
  'update:autonomyMode': [AutonomyMode]
  'update:connectionPreferences': [preferences: JsonObject]
}>()

const autonomyMode = ref<AutonomyMode>(props.autonomyMode ?? 'free')
const activeLayerView = ref<CanvasLayerView>('both')
const rightSidebarCollapsed = ref(false)

// Reaktive Variablen für Konfiguration
const gridSize = ref(10)
const snapToGrid = ref(true)
const tolerance = ref(10)
const isPanning = ref(false)
const useGridForPanning = ref(true)
const canUndo = ref(false)
const canRedo = ref(false)

const graphWrapper = ref<HTMLElement | null>(null)
const graphContainer = ref<HTMLElement>()
const canvasGrid = ref<HTMLCanvasElement>()
const canvasWindowHost = ref<CanvasWindowHostApi | null>(null)
const canvasToolbar = ref<CanvasToolbarApi | null>(null)
// shallowRef verhindert, dass Vue die Graph-Instanz in einen reactive()-Proxy einwickelt.
// Vue's deep reactive Proxy würde Cell-Objekte als Proxy zurückgeben, deren Identität
// von den originalen Cell-Objekten abweicht. maxGraph speichert CellStates in einer
// Map<Cell, CellState> mit originalen Cell-Referenzen als Schlüssel.
// Map.get(proxiedCell) schlägt fehl (proxy !== original), dadurch werden States nicht
// entfernt und SVG-Knoten bleiben als Geister-Elemente im DOM.
const graph = shallowRef<MyCustomGraph>()
const parent = shallowRef<Cell>()
const modelLayerCell = shallowRef<Cell>()
const feedbackLayerCell = shallowRef<Cell>()
const keyHandler = shallowRef<KeyHandler>()
const customConnectionHandler = shallowRef<CustomConnectionHandler>()
const plugins = ref<GraphPluginConstructor[]>([MyCustomCellEditorHandler, TooltipHandler, CustomConnectionHandler as unknown as GraphPluginConstructor, PanningHandler, SelectionCellsHandler, SelectionHandler, RubberBandHandler, FitPlugin])
const toolbarShapes = ref(
  createDefaultShapes({
    rectangle: img_rectangle,
    ellipse: img_ellipse,
    rhombus: img_rhombus,
    triangle: img_triangle,
    cloud: img_cloud
  })
)

let undoManagerApi: UndoManagerApi | undefined
let graphContainerKeydownHandler: ((evt: KeyboardEvent) => void) | undefined
let graphContainerWheelHandler: ((evt: WheelEvent) => void) | undefined
const overlayEntries = computed(() => props.overlays ?? [])
const { overlayTooltip, overlayTooltipAnchorStyle, registerGraph, cleanup: cleanupCanvasOverlays } = useCanvasOverlays(graphWrapper, overlayEntries)
// Zentraler Validator für alle Diagramm-Regeln
const diagramValidator = new DiagramValidator()
const validationDialogVisible = ref(false)
const validationMessages = ref<string[]>([])

const normalizeErrorLines = (rawMessage: string): string[] =>
  rawMessage
    .split('\n')
    .map((line) => line.replace(/<[^>]*>/g, '').trim())
    .filter((line) => line.length > 0)

const focusGraphContainer = (evt: PointerEvent) => {
  const target = evt.target as Element | null
  if (target?.closest('button, input, textarea, select, [contenteditable="true"]')) {
    return
  }

  canvasToolbar.value?.closeConnectionPalette()
  graphContainer.value?.focus({ preventScroll: true })
}

const openValidationDialog = (messages: string[]) => {
  if (messages.length === 0) return
  validationMessages.value = [...new Set(messages)]
  validationDialogVisible.value = true
}

const updateAutonomyMode = (mode: AutonomyMode) => {
  autonomyMode.value = mode
  emit('update:autonomyMode', mode)
}

const applyValidationRulesToGraph = () => {
  const currentGraph = graph.value
  if (!currentGraph) {
    return
  }
  diagramValidator.applyToGraph(currentGraph, {
    liveValidation: autonomyMode.value !== 'free'
  })
}

const rebuildValidationRules = (rules?: DiagramSyntax[]) => {
  const validationRules = buildValidationRulesFromSyntax(rules ?? [])
  diagramValidator.addRules(validationRules)
  applyValidationRulesToGraph()
}

// Stelle Graph-Context für Child-Komponenten bereit
provideGraphContext({
  graph,
  isPanning,
  gridSize,
  snapToGrid,
  tolerance,
  useGridForPanning
})

// Initialisiere Composables
const { deleteSelected, duplicateSelected, selectAll, clearSelection } = useGraphOperations(graph, parent)
const { zoomIn, zoomOut, fitToWindow } = useZoomOperations(graph)
const { updateGridSize, updateSnapToGrid, updateTolerance, updateUseGridForPanning, toggleGrid, forceGridRepaint } = useGridSettings(graph, gridSize, snapToGrid, tolerance, useGridForPanning)
const feedbackCanvasConfig = computed(() => createDefaultFeedbackCanvasConfig(props.feedbackConfig?.canvas))
const feedbackElementConfigs = computed(() => feedbackCanvasConfig.value.configurableElements ?? [])
const activeFeedbackElementId = computed(() => {
  const configuredId = feedbackCanvasConfig.value.activeElementId
  if (configuredId && feedbackElementConfigs.value.some((entry) => entry.id === configuredId)) {
    return configuredId
  }
  return feedbackElementConfigs.value[0]?.id
})
const feedbackElementById = computed(() => {
  const map = new Map<string, (typeof feedbackElementConfigs.value)[number]>()
  feedbackElementConfigs.value.forEach((entry) => {
    map.set(entry.id, entry)
  })
  return map
})
const activeFeedbackElementEntry = computed(() => {
  const activeId = activeFeedbackElementId.value
  if (!activeId) return null
  return feedbackElementById.value.get(activeId) ?? null
})
const activeFeedbackConnectionDefinition = computed(() => activeFeedbackElementEntry.value?.connection ?? null)
const activeFeedbackRules = computed(() => feedbackCanvasConfig.value.rules)
const feedbackConnectionByElementId = computed<Record<string, DiagramConnection>>(() => {
  const map: Record<string, DiagramConnection> = {}
  feedbackElementConfigs.value.forEach((entry) => {
    if (entry.connection) {
      map[entry.id] = entry.connection
    }
  })
  return map
})

// Alignment-Hilfsfunktionen
const alignLeft = () => graph.value && alignHorizontal(graph.value, 'left')
const alignCenterH = () => graph.value && alignHorizontal(graph.value, 'center')
const alignRight = () => graph.value && alignHorizontal(graph.value, 'right')
const alignTop = () => graph.value && alignVertical(graph.value, 'top')
const alignMiddleV = () => graph.value && alignVertical(graph.value, 'middle')
const alignBottom = () => graph.value && alignVertical(graph.value, 'bottom')

const applyUndoState = (state: UndoManagerState) => {
  canUndo.value = state.canUndo
  canRedo.value = state.canRedo
}

const ensureGraphLayers = (graphInstance: MyCustomGraph): { modelLayer: Cell; feedbackLayer: Cell } => {
  const model = graphInstance.getDataModel()
  let root = model.getRoot() as Cell | null

  if (!root) {
    root = new Cell()
    model.setRoot(root)
  }

  while (root.getChildCount() < 2) {
    root.insert(new Cell())
  }

  return {
    modelLayer: root.getChildAt(0),
    feedbackLayer: root.getChildAt(1)
  }
}

const syncLayerReferences = (graphInstance: MyCustomGraph) => {
  const { modelLayer, feedbackLayer } = ensureGraphLayers(graphInstance)
  const didChange = modelLayer !== modelLayerCell.value || feedbackLayer !== feedbackLayerCell.value
  modelLayerCell.value = modelLayer
  feedbackLayerCell.value = feedbackLayer

  // Alle Sidebar-Elemente landen aktuell ausschließlich im Modell-Layer (Layer 1)
  parent.value = modelLayer
  return didChange
}

const applyLayerVisibility = () => {
  const currentGraph = graph.value
  const modelLayer = modelLayerCell.value
  const feedbackLayer = feedbackLayerCell.value

  if (!currentGraph || !modelLayer || !feedbackLayer) {
    return
  }

  const dataModel = currentGraph.getDataModel()
  const showModelLayer = activeLayerView.value !== 'feedback'
  const showFeedbackLayer = activeLayerView.value !== 'model'

  const currentModelVisible = (modelLayer as any).isVisible?.() ?? true
  const currentFeedbackVisible = (feedbackLayer as any).isVisible?.() ?? true
  const requiresModelLayerUpdate = currentModelVisible !== showModelLayer
  const requiresFeedbackLayerUpdate = currentFeedbackVisible !== showFeedbackLayer

  if (!requiresModelLayerUpdate && !requiresFeedbackLayerUpdate) {
    return
  }

  dataModel.beginUpdate()
  try {
    if (requiresModelLayerUpdate) {
      dataModel.setVisible(modelLayer, showModelLayer)
    }
    if (requiresFeedbackLayerUpdate) {
      dataModel.setVisible(feedbackLayer, showFeedbackLayer)
    }
  } finally {
    dataModel.endUpdate()
  }

  currentGraph.refresh()
  currentGraph.view.validate()
}

const undoGraph = () => {
  if (!graph.value || !undoManagerApi?.canUndo()) {
    return
  }

  undoManagerApi.undo()
  graph.value.refresh()
  graph.value.view.validate()
  emitUpdatedModel()
}

const copySelected = () => {
  if (!graph.value || graph.value.isSelectionEmpty()) {
    return
  }

  Clipboard.copy(graph.value)
}

const pasteFromClipboard = () => {
  if (!graph.value) {
    return
  }

  const pastedCells = Clipboard.paste(graph.value)
  if (pastedCells && pastedCells.length > 0) {
    graph.value.refresh()
    graph.value.view.validate()
    emitUpdatedModel()
  }
}

const redoGraph = () => {
  if (!graph.value || !undoManagerApi?.canRedo()) {
    return
  }

  undoManagerApi.redo()
  graph.value.refresh()
  graph.value.view.validate()
  emitUpdatedModel()
}

// Compute the list of sidebar language sections
const sidebarLanguages = computed<SidebarLanguage[]>(() => {
  if (props.languages && props.languages.length > 0) {
    return props.languages
  }
  if (props.languageElements && props.languageElements.length > 0) {
    return [{ id: '_default', name: props.languageName || 'Elements', elements: props.languageElements }]
  }
  return []
})

// Computed für Verbindungen
const languageConnections = computed(() => props.languageConnections ?? [])

watch(
  () => props.languageSyntax,
  (newSyntax) => {
    rebuildValidationRules(newSyntax ?? [])
  },
  { deep: true, immediate: true }
)

// Handler für Verbindungsauswahl
const onConnectionSelected = (connection: DiagramConnection) => {
  if (customConnectionHandler.value) {
    customConnectionHandler.value.setSelectedConnection(connection)
    customConnectionHandler.value.setFeedbackElementConnections(feedbackConnectionByElementId.value)
    customConnectionHandler.value.setFeedbackConnection(activeFeedbackRules.value.enforceDedicatedConnection ? activeFeedbackConnectionDefinition.value : null)
    customConnectionHandler.value.setFeedbackRules(activeFeedbackRules.value)
  }
}

const updateConnectionPreferences = (preferences: JsonObject) => {
  emit('update:connectionPreferences', preferences)
}

onMounted(() => {
  initGraph()

  // Initialisiere Toolbar mit Verzögerung, um sicherzustellen dass Container verfügbar ist
  nextTick(() => {
    setTimeout(() => {
      initializeToolbar()
    }, 100)
  })

  graph.value!.getDataModel().addListener(InternalEvent.CHANGE, () => {
    const currentGraph = graph.value
    if (currentGraph?.getDataModel().updateLevel && currentGraph.getDataModel().updateLevel > 0) {
      return
    }

    // Nach Imports/Root-Updates Layer-Referenzen neu aufbauen.
    if (currentGraph) {
      const didChangeLayers = syncLayerReferences(currentGraph)
      if (didChangeLayers) {
        applyLayerVisibility()
      }
    }

    currentGraph?.refresh()
    currentGraph?.view.validate()

    if (currentGraph && autonomyMode.value !== 'free') {
      diagramValidator.validateGraph(currentGraph)
    } else if (currentGraph) {
      clearValidationWarningOverlays(currentGraph)
    }

    emitUpdatedModel()
  })

  // Wenn eine einzelne Verbindung als Vorschau ausgewählt ist, zeige nur diese
  if (props.previewConnection) {
    renderConnectionPreviewOnly(props.previewConnection)
  }
})

onUnmounted(() => {
  if (graphContainer.value && graphContainerKeydownHandler) {
    graphContainer.value.removeEventListener('keydown', graphContainerKeydownHandler)
  }
  graphContainerKeydownHandler = undefined
  if (graphContainer.value && graphContainerWheelHandler) {
    graphContainer.value.removeEventListener('wheel', graphContainerWheelHandler)
  }
  graphContainerWheelHandler = undefined
  ;(keyHandler.value as any)?.destroy?.()
  keyHandler.value = undefined
  undoManagerApi?.destroy()
  undoManagerApi = undefined
  canUndo.value = false
  canRedo.value = false
  cleanupCanvasOverlays()
})

// Watch für previewConnection (nur für Preview-Modus)
watch(
  () => props.previewConnection,
  (newConn) => {
    if (graph.value) {
      renderConnectionPreviewOnly(newConn)
    }
  },
  { immediate: true, deep: true }
)

watch(
  () => props.previewMode,
  () => {
    if (graph.value) {
      renderConnectionPreviewOnly(props.previewConnection)
    }
  }
)

// Watch für languageConnections - aktualisiere ConnectionHandler
watch(
  () => props.languageConnections,
  (newConnections) => {
    if (customConnectionHandler.value) {
      const safeConnections = newConnections ?? []

      if (safeConnections.length > 0) {
        customConnectionHandler.value.setSelectedConnection(safeConnections[0])
      } else {
        customConnectionHandler.value.setSelectedConnection(null)
      }

      customConnectionHandler.value.setFeedbackElementConnections(feedbackConnectionByElementId.value)
      customConnectionHandler.value.setFeedbackConnection(activeFeedbackRules.value.enforceDedicatedConnection ? activeFeedbackConnectionDefinition.value : null)
      customConnectionHandler.value.setFeedbackRules(activeFeedbackRules.value)
    }
  },
  { deep: true }
)

watch(
  () => props.feedbackConfig?.canvas,
  () => {
    if (customConnectionHandler.value) {
      customConnectionHandler.value.setFeedbackElementConnections(feedbackConnectionByElementId.value)
      customConnectionHandler.value.setFeedbackConnection(activeFeedbackRules.value.enforceDedicatedConnection ? activeFeedbackConnectionDefinition.value : null)
      customConnectionHandler.value.setFeedbackRules(activeFeedbackRules.value)
    }

    if (graph.value) {
      initializeToolbar()
    }
  },
  { deep: true }
)

watch(
  () => autonomyMode.value,
  (mode) => {
    if (graph.value) {
      setGraphValidationMode(graph.value, mode)
    }
    if (mode === 'free' && graph.value) {
      clearValidationWarningOverlays(graph.value)
    }
    applyValidationRulesToGraph()
  },
  { immediate: true }
)

watch(
  () => props.autonomyMode,
  (mode) => {
    if (!mode) return
    if (mode !== autonomyMode.value) {
      autonomyMode.value = mode
    }
  }
)

watch(activeLayerView, () => {
  applyLayerVisibility()
})

// Vorschau nur für eine Verbindung (nutzt zentrale Preview-Hilfen)
function renderConnectionPreviewOnly(connection?: DiagramConnection | null) {
  const g = graph.value
  if (!g) return

  if (!connection) {
    clearConnectionPreview(g)
    return
  }

  if (props.previewMode === 'scenario') {
    renderScenarioConnectionPreview(g, connection)
    return
  }

  if (props.previewMode === 'routing') {
    renderRoutingConnectionPreview(g, connection)
    return
  }

  renderSimpleConnectionPreview(g, connection)
}

const initGraph = () => {
  if (props.model) {
    graph.value = new MyCustomGraph(graphContainer.value!, props.model, plugins.value)
  } else {
    const root = new Cell()
    root.insert(new Cell()) // Layer 1 (Modell)
    root.insert(new Cell()) // Layer 2 (Feedback)
    graph.value = new MyCustomGraph(graphContainer.value!, new GraphDataModel(root), plugins.value)
  }
  syncLayerReferences(graph.value)
  applyLayerVisibility()
  registerGraph(graph.value)
  applyValidationRulesToGraph()

  // Hole den CustomConnectionHandler aus den registrierten Plugins
  const handler = graph.value?.getPlugin('ConnectionHandler')
  customConnectionHandler.value = handler instanceof CustomConnectionHandler ? handler : undefined

  // Setze die erste Verbindung als Standard, falls vorhanden
  if (customConnectionHandler.value && props.languageConnections && props.languageConnections.length > 0) {
    customConnectionHandler.value.setSelectedConnection(props.languageConnections[0])
  }
  customConnectionHandler.value?.setFeedbackElementConnections(feedbackConnectionByElementId.value)
  customConnectionHandler.value?.setFeedbackConnection(activeFeedbackRules.value.enforceDedicatedConnection ? activeFeedbackConnectionDefinition.value : null)
  customConnectionHandler.value?.setFeedbackRules(activeFeedbackRules.value)
  setGraphValidationMode(graph.value, autonomyMode.value)

  graph.value.validationAlert = (message: string) => {
    if (autonomyMode.value === 'validating') {
      openValidationDialog(normalizeErrorLines(message))
      return
    }
  }

  // Enable editing
  graph.value.setEnabled(props.allowEdit)
  graph.value.setConnectable(true)
  graph.value.setConnectableEdges(true)
  graph.value.setCellsEditable(props.allowEdit)
  graph.value.setCellsMovable(props.allowEdit)
  graph.value.setCellsResizable(props.allowEdit)
  graph.value.setCellsDeletable(props.allowEdit)
  graph.value.setCellsCloneable(props.allowEdit)
  graph.value.setAllowNegativeCoordinates(false)
  graph.value.setHtmlLabels(true)
  graph.value.border = 20

  undoManagerApi?.destroy()
  undoManagerApi = setupUndoManager(graph.value, applyUndoState)

  // Aktiviere Panning mit Standard-Implementierung (Rechtsklick oder mittlere Maustaste)
  graph.value.setPanning(true)

  // Configure PanningHandler
  const panningHandler = graph.value.getPlugin<PanningHandler>('PanningHandler')
  if (panningHandler) {
    panningHandler.useLeftButtonForPanning = false
    panningHandler.useGrid = useGridForPanning.value

    // Event Listeners direkt am PanningHandler registrieren
    panningHandler.addListener(InternalEvent.PAN_START, () => {
      isPanning.value = true
    })

    panningHandler.addListener(InternalEvent.PAN_END, () => {
      isPanning.value = false

      // Graph nach Panning aktualisieren und validieren
      if (graph.value) {
        graph.value.refresh()
        graph.value.view.validate()
      }
    })
  }

  // Configure selection handler like in Grid.js
  const selectionHandler = graph.value.getPlugin<SelectionHandler>('SelectionHandler')
  if (selectionHandler) {
    ;(selectionHandler as any).scaleGrid = true
  }

  // Enable tooltips
  graph.value.setTooltips(true)

  // Kontextmenü konfigurieren
  if (!props.contextMenu) {
    InternalEvent.disableContextMenu(graphContainer.value!)
  }

  // Graph-Container-Hintergrund transparent machen
  if (graphContainer.value) {
    graphContainer.value.style.backgroundColor = 'transparent'
  }

  // MaxGraph-Container selbst transparent machen
  if (graph.value.container) {
    graph.value.container.style.backgroundColor = 'transparent'
    graph.value.container.style.background = 'transparent'
  }

  // Auch den SVG-Container transparent machen (falls vorhanden)
  setTimeout(() => {
    const svgElement = graph.value?.container.querySelector('svg')
    if (svgElement) {
      svgElement.style.backgroundColor = 'transparent'
      svgElement.style.background = 'transparent'
    }
  }, 100)

  // Raster-Konfiguration
  graph.value.setGridEnabled(true)
  graph.value.gridSize = gridSize.value
  graph.value.setGridSize(gridSize.value)

  // Snap-to-Grid aktivieren
  if (snapToGrid.value) {
    graph.value.setGridEnabled(true)
  }

  // Collapse/Expand Icons konfigurieren (wie in configure.js aus den Beispielen)
  // ImageBasePath setzen
  Client.setImageBasePath('/images')

  // Collapse/Expand Images setzen
  graph.value.options.collapsedImage = new ImageBox(`${Client.imageBasePath}/collapsed.gif`, 9, 9)
  graph.value.options.expandedImage = new ImageBox(`${Client.imageBasePath}/expanded.gif`, 9, 9)

  // Folding explizit aktivieren
  graph.value.options.foldingEnabled = true

  // collapseToPreferredSize aktivieren - nutzt alternateBounds beim Collapse
  // Im Folding-Beispiel wird es auf false gesetzt, aber für alternateBounds brauchen wir true (Standard)
  graph.value.options.collapseToPreferredSize = true

  graph.value.getStylesheet().getDefaultEdgeStyle().edgeStyle = EdgeStyle.OrthConnector

  // Tastaturbefehle nur innerhalb des fokussierten Modellierungsbereichs behandeln.
  // Ohne explizites Ziel registriert maxGraph den KeyHandler am gesamten Dokument.
  if (graphContainer.value) {
    keyHandler.value = new KeyHandler(graph.value, graphContainer.value)
    keyHandler.value.bindControlKey(65, () => selectAll())
    keyHandler.value.bindControlKey(67, () => copySelected())
    keyHandler.value.bindControlKey(86, () => pasteFromClipboard())
    keyHandler.value.bindControlKey(68, () => duplicateSelected())
    keyHandler.value.bindControlKey(90, () => undoGraph())
    keyHandler.value.bindControlKey(89, () => redoGraph())
    keyHandler.value.bindKey(46, () => deleteSelected())
    ;(keyHandler.value as any)?.bindControlShiftKey?.(90, () => redoGraph())
  }

  // Escape zusätzlich direkt am Container behandeln, da KeyHandler Escape intern speziell verarbeitet.
  if (graphContainer.value) {
    graphContainerKeydownHandler = (evt: KeyboardEvent) => {
      if (evt.key !== 'Escape' || graph.value?.isEditing()) {
        return
      }

      const target = evt.target as Element | null
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) {
        return
      }

      clearSelection()
    }
    graphContainer.value.addEventListener('keydown', graphContainerKeydownHandler)

    graphContainerWheelHandler = (evt: WheelEvent) => {
      if (!graph.value || !graph.value.isEnabled()) {
        return
      }

      evt.preventDefault()
      if (evt.deltaY < 0) {
        zoomIn()
      } else if (evt.deltaY > 0) {
        zoomOut()
      }
    }
    graphContainer.value.addEventListener('wheel', graphContainerWheelHandler, { passive: false })
  }

  // Swimlane-Unterstützung aktivieren
  setupSwimlaneSupport(graph.value)

  parent.value = modelLayerCell.value ?? graph.value.getDefaultParent()

  // Setup dynamisches Grid
  setupDynamicGrid(graph, canvasGrid, graphContainer, gridSize, snapToGrid)

  // Forciere das Raster sofort nach der Graph-Initialisierung
  nextTick(() => {
    setTimeout(() => {
      if (graph.value && snapToGrid.value) {
        graph.value.view.validateBackground()
        // Zusätzlicher direkter Repaint-Aufruf
        if ((graph.value as any).repaintGrid) {
          ;(graph.value as any).repaintGrid()
        }
      }
    }, 100)
  })

  applyValidationRulesToGraph()
}

const buildLanguageShapes = computed(() => {
  const allElements = sidebarLanguages.value.flatMap((l) => l.elements)
  if (allElements.length === 0) {
    return createDefaultShapes({
      rectangle: img_rectangle,
      ellipse: img_ellipse,
      rhombus: img_rhombus,
      triangle: img_triangle,
      cloud: img_cloud
    })
  }
  return buildShapesFromElements(allElements, img_elementPlaceholder)
})

const feedbackShapes = computed(() =>
  feedbackElementConfigs.value.map((entry) => {
    const feedbackElementDefinition = entry.element
    const width = feedbackElementDefinition.width ?? 180
    const height = feedbackElementDefinition.height ?? 72
    const shapeName = feedbackElementDefinition.type || entry.id

    return {
      name: shapeName,
      label: feedbackElementDefinition.defaultLabel || shapeName,
      width,
      height,
      style: {
        shape: feedbackElementDefinition.predefinedShape ?? 'rectangle',
        ...(feedbackElementDefinition.style ?? {}),
        cellRole: 'feedback',
        lockToLayer: activeFeedbackRules.value.preventContainerDrop ? 1 : 0
      },
      tooltip: feedbackElementDefinition.defaultLabel || shapeName,
      image: img_elementPlaceholder,
      dropHandler: (graphInstance: Graph, _parentCell: Cell | undefined, position: { x?: number; y?: number }) => {
        if (activeLayerView.value === 'model') {
          activeLayerView.value = 'both'
        }

        const targetLayer = feedbackLayerCell.value ?? graphInstance.getDefaultParent()
        const x = (position.x ?? 0) - width / 2
        const y = (position.y ?? 0) - height / 2

        let feedbackCell: Cell | null = null
        graphInstance.batchUpdate(() => {
          feedbackCell = createCellFromElement(feedbackElementDefinition, x, y)
          graphInstance.addCell(feedbackCell, targetLayer)

          if (feedbackCell) {
            ;(feedbackCell as any).feedbackElementId = entry.id
            ;(feedbackCell as any).feedbackConnectionId = entry.connection.type
            ;(feedbackCell as any).feedbackConnectionType = entry.connection.connectionType ?? entry.connection.type
            ;(feedbackCell as any).lockToLayer = activeFeedbackRules.value.preventContainerDrop ? 1 : 0
            ;(feedbackCell as any).cellRole = 'feedback'
            ;(feedbackCell as any).canvasRole = 'feedback'
          }
        })

        if (feedbackCell) {
          graphInstance.setSelectionCell(feedbackCell)
        }
      }
    }
  })
)

const initializeToolbar = () => {
  if (!graph.value) {
    return
  }

  toolbarShapes.value = [...buildLanguageShapes.value, ...feedbackShapes.value]
  ensureGraphDropHandlers(graph.value, parent, toolbarShapes.value)
}

watch(
  () => [props.languageElements, props.languages],
  () => {
    nextTick(() => {
      setTimeout(() => initializeToolbar(), 50)
    })
  },
  { deep: true }
)

// Entfernte Shape-Toolbar-Funktionen - werden nicht mehr verwendet
// createToolbarShape, createDropHandler, setupDraggableIcon, setupIconSelectionHighlight
// sind entfernt worden da die Vue-basierte Shape-Toolbar entfernt wurde

const emitUpdatedModel = () => {
  emit('update:model', graph.value!.getDataModel())
}

/**
 * Leert den Canvas - entfernt alle Zellen
 * Wiederverwendbare Methode für alle Editoren
 */
const clearCanvas = () => {
  if (!graph.value) {
    return
  }

  const layers = [modelLayerCell.value, feedbackLayerCell.value].filter((layer): layer is Cell => Boolean(layer))
  const parentsToClear = layers.length > 0 ? layers : [graph.value.getDefaultParent()]

  for (const targetParent of parentsToClear) {
    const childCells = graph.value.getChildCells(targetParent)
    if (childCells && childCells.length > 0) {
      graph.value.removeCells(childCells)
    }
  }
}

const addCanvasWindow = (windowDefinition: CanvasWindowDefinition) => {
  canvasWindowHost.value?.addWindow(windowDefinition)
}

const updateCanvasWindow = (patch: CanvasWindowPatch) => {
  canvasWindowHost.value?.updateWindow(patch)
}

const removeCanvasWindow = (id: string) => {
  canvasWindowHost.value?.removeWindow(id)
}

const clearCanvasWindows = () => {
  canvasWindowHost.value?.clearWindows()
}

const setCanvasWindows = (definitions: CanvasWindowDefinition[]) => {
  canvasWindowHost.value?.setWindows(definitions)
}

const serializeModel = (): Record<string, unknown> => {
  if (!graph.value) return {}
  return {
    format: 'maxgraph-xml',
    version: 1,
    xml: exportModelAsXml(graph.value, false)
  }
}

const loadPersistedModel = (data: Record<string, unknown>) => {
  if (!graph.value || typeof data.xml !== 'string') return
  try {
    importModelFromXml(graph.value, data.xml)
    syncLayerReferences(graph.value)
    initializeToolbar()
  } catch (error) {
    // A malformed historical snapshot must not prevent the editor shell from
    // opening. The caller can keep the server data untouched and show a small
    // recoverable notice instead.
    console.warn('Unable to import model snapshot.', error)
  }
}

const onWindowRemoved = () => {}
defineExpose({
  graph,
  clearCanvas,
  addCanvasWindow,
  updateCanvasWindow,
  removeCanvasWindow,
  clearCanvasWindows,
  setCanvasWindows,
  serializeModel,
  loadPersistedModel
})
</script>

<style scoped>
.canvas-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.graph-container {
  position: relative;
  width: 100%;
  height: auto;
  flex: 1;
  min-height: 0;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: transparent;
  overflow: hidden;
}

.graph-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  min-height: 0;
}

.canvas-area {
  display: flex;
  flex-direction: row;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.canvas-tooltip-anchor {
  position: absolute;
  pointer-events: none;
  z-index: 5;
}

.shortcut-help-anchor {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 8;
}

.shortcut-help-btn {
  min-width: 30px !important;
  width: 30px;
  height: 30px;
}

.hidden-during-pan {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.shortcut-tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
}

.canvas-window-default-content {
  padding: 8px;
  font-size: 13px;
  color: #424242;
  line-height: 1.4;
}

.canvas-task-window-content {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: auto;
}

.grid-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  pointer-events: none;
  overflow: hidden;
}

.grid-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  pointer-events: none;
  opacity: 1;
  background: transparent;
}

.toolbar-actions {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  min-height: 48px;
  padding: 8px 12px;
  background: #ffffff;
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: 4px;
  gap: 8px;
  flex-wrap: wrap;
}

.validation-errors {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Responsives Design für kleinere Bildschirme */
@media (max-width: 768px) {
  .graph-container {
    height: calc(100vh - 250px);
  }
}
</style>
