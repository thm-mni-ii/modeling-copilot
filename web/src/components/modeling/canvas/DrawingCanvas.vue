<template>
  <v-card class="px-2 py-1" height="100%" width="100%">
    <v-card-text class="pa-1 canvas-content">
      <ModelingHeader v-if="props.showToolbar && props.modelManagement" class="mb-1" :inert="props.helpSelectionMode || undefined">
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
            @format-text="formatSelectedText"
            @select-connection="onConnectionSelected"
            @update:connection-preferences="updateConnectionPreferences"
          />
        </template>
        <template #save-tools>
          <v-btn icon="mdi-undo" size="x-small" :disabled="!(sharedHistory?.canUndo ?? canUndo)" title="Undo (Ctrl+Z)" @click="undoGraph" />
          <v-btn icon="mdi-redo" size="x-small" :disabled="!(sharedHistory?.canRedo ?? canRedo)" title="Redo (Ctrl+Y)" @click="redoGraph" />
        </template>
        <template v-if="showRightSidebar && !$slots['sidebar-top']" #sidebar-toggle>
          <v-btn-group size="small" density="compact" variant="outlined"><v-btn icon="mdi-dock-right" :color="rightSidebarCollapsed ? 'medium-gray' : undefined" :title="rightSidebarCollapsed ? 'Expand right sidebar' : 'Collapse right sidebar'" :aria-label="rightSidebarCollapsed ? 'Expand right sidebar' : 'Collapse right sidebar'" :aria-controls="rightSidebarId" :aria-expanded="!rightSidebarCollapsed" @click="rightSidebarCollapsed = !rightSidebarCollapsed" /></v-btn-group>
        </template>
        <template #autonomy>
          <div class="canvas-mode-controls">
            <AutonomyControls :mode="autonomyMode" :disabled="props.lockAutonomyMode" @update:mode="updateAutonomyMode" />
            <ConnectionPreviewControl v-if="props.connectionPreviewAllowed" :model-value="connectionPreviewEnabled" :allowed="props.connectionPreviewAllowed" @update:model-value="connectionPreview = $event" />
          </div>
        </template>
      </ModelingHeader>

      <!-- Erweiterte Toolbar für Einbettungen ohne Modellverwaltung -->
      <div v-else-if="props.showToolbar" class="toolbar-actions mb-2" :inert="props.helpSelectionMode || undefined">
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
          @format-text="formatSelectedText"
          @select-connection="onConnectionSelected"
          @update:connection-preferences="updateConnectionPreferences"
        />
        <div class="canvas-mode-controls">
          <AutonomyControls :mode="autonomyMode" :disabled="props.lockAutonomyMode" @update:mode="updateAutonomyMode" />
          <ConnectionPreviewControl v-if="props.connectionPreviewAllowed" :model-value="connectionPreviewEnabled" :allowed="props.connectionPreviewAllowed" @update:model-value="connectionPreview = $event" />
        </div>
      </div>

      <!-- Canvas Area: Sidebar + Graph -->
      <div class="canvas-area" :class="{ 'canvas-area--help-selection': props.helpSelectionMode }">
        <!-- Elements Sidebar -->
        <SidebarContainer v-if="props.showElements !== false && props.showModelSidebar !== false && props.showToolbar && (props.modelManagement || sidebarLanguages.length > 0)" :inert="props.helpSelectionMode || undefined" :languages="sidebarLanguages" :model-management="props.modelManagement" />

        <!-- Graph Container -->
        <div ref="graphWrapper" class="graph-wrapper">
          <div v-if="$slots['canvas-top']" class="canvas-top">
            <slot name="canvas-top" />
          </div>
          <div class="graph-viewport">
            <!-- Separater Grid Container -->
            <div class="grid-container">
              <canvas ref="canvasGrid" class="grid-canvas"></canvas>
            </div>

            <!-- Only maxGraph owns this node's children. Fixed UI stays outside
                 its temporary panning preview containers. -->
            <div ref="graphContainer" class="graph-container" tabindex="0" @pointerdown="focusGraphContainer"></div>

            <ConnectionSuggestions v-if="graph && connectionPreviewEnabled && props.allowEdit && !props.helpSelectionMode && !props.previewConnection" :graph="graph" :elements="sidebarLanguages.flatMap((language) => language.elements)" :connections="languageConnections" :syntax="props.languageSyntax ?? []" />

            <div v-if="$slots['canvas-top-right']" class="canvas-top-right" @pointerdown.stop @click.stop @wheel.stop>
              <slot name="canvas-top-right" />
            </div>

            <!-- Messages without a cell of their own (validateCell of the root), e.g. "at least one cycle" -->
            <v-alert v-if="diagramWarnings.length" type="warning" variant="tonal" density="compact" class="canvas-diagram-warnings" @pointerdown.stop>
              <div v-for="message in diagramWarnings" :key="message">{{ message }}</div>
            </v-alert>

            <GraphControls @zoom-in="zoomIn" @zoom-out="zoomOut" @fit-to-window="fitToWindow" @toggle-grid="toggleGrid" @force-grid-repaint="forceGridRepaint" />

            <!-- Graph Settings Component -->
            <GraphSettings @update:grid-size="updateGridSize" @update:tolerance="updateTolerance" @update:snap-to-grid="updateSnapToGrid" @update:use-grid-for-panning="updateUseGridForPanning" />

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
        <SidebarRightContainer v-if="showRightSidebar" :id="rightSidebarId" :tools-disabled="props.helpSelectionMode" :help-flow-active="props.helpFlowActive" :collapsed="rightSidebarCollapsed" :has-journey="Boolean($slots['sidebar-top'])" :feedback-shapes="feedbackShapes" :task-active="props.taskActive" :task-edit="props.taskEdit" :task-edit-sync-state="props.taskEditSyncState" :selected-task-edit-ids="props.selectedTaskEditIds" :model-id="props.modelId" :open-evaluation-id="props.openEvaluationId" @focus-task-edit="emit('focusTaskEdit', $event)" @remove-task-edit="emit('removeTaskEdit', $event)" @update-task-edit-document="emit('updateTaskEditDocument', $event)">
          <template v-if="$slots['sidebar-top']" #top><slot name="sidebar-top" /></template>
        </SidebarRightContainer>
        <CollabConnector v-if="props.modelManagement" />
      </div>
      <!-- /canvas-area -->
    </v-card-text>

  </v-card>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { Graph, InternalEvent, RubberBandHandler, Cell, CellOverlay, CellEditorHandler, SelectionCellsHandler, SelectionHandler, CellState, EdgeStyle, GraphDataModel, PanningHandler, ImageBox, Client, KeyHandler, TooltipHandler, FitPlugin, Clipboard, ConnectionConstraint, Point } from '@maxgraph/core'
import { CellHighlight, eventUtils, type EdgeStyleFunction, type MouseListenerSet, type GraphPluginConstructor } from '@maxgraph/core'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
import type { TaskEditFocus, TaskEditSyncState } from '@/utils/taskEdits'
import { provideGraphContext } from '@/composables/useGraphContext'
import { useGraphOperations } from '@/composables/useGraphOperations'
import { useZoomOperations } from '@/composables/useZoomOperations'
import { useGridSettings } from '@/composables/useGridSettings'
import { useCanvasOverlays } from '@/composables/useCanvasOverlays'
import { notifyError } from '@/composables/useNotifications'
import { setupDynamicGrid } from '@/utils/setupDynamicGrid'
import { StablePanningHandler } from '@/utils/StablePanningHandler'
import { createDefaultShapes, buildShapesFromElements, ensureGraphDropHandlers } from '@/utils/setupToolbar'
import { isContainerSectionTarget, setupSwimlaneSupport } from '@/utils/setupSwimlaneSupport'
import { clearConnectionPreview, isPreviewEdge, renderScenarioConnectionPreview, renderSimpleConnectionPreview, renderRoutingConnectionPreview, updateConnectionPreview } from '@/utils/connectionPreview'
import { AnchorConstraintHandler, CustomConnectionHandler } from '@/utils/CustomConnectionHandler'
import { setupUndoManager, type UndoManagerApi, type UndoManagerState } from '@/utils/setupUndoManager'
import { alignHorizontal, alignVertical } from '@/utils/alignCells'
import { clearValidationWarningOverlays, getGraphValidationMode, isValidationPassActive, setGraphValidationMode } from '@/utils/graphValidationRuntime'
import { createCellFromElement } from '@/utils/elementFactory'
import { registerElementShapes } from '@/utils/shapeRegistry'
import { editorHtmlToLabel, enableLabelPadding, formatText, labelToEditorHtml, protectHtmlLabels, type TextFormat } from '@/utils/htmlLabels'
import GraphSettings from './GraphSettings.vue'
import CanvasWindowHost from './CanvasWindowHost.vue'
import CanvasToolbar from '@/components/modeling/controls/CanvasToolbar.vue'
import GraphControls from '@/components/modeling/controls/GraphControls.vue'
import AutonomyControls from '@/components/modeling/controls/AutonomyControls.vue'
import ConnectionPreviewControl from '@/components/modeling/controls/ConnectionPreviewControl.vue'
import { useConnectionPreviewPreference } from '@/composables/useConnectionPreviewPreference'
import type { CanvasLayerView } from '@/components/modeling/controls/LayerVisibilityControls.vue'
import ModelingHeader from '@/components/modeling/controls/ModelingHeader.vue'
import SidebarContainer from '@/components/modeling/sidebars/SidebarContainer.vue'
import SidebarRightContainer from '@/components/modeling/sidebars/SidebarRightContainer.vue'
import CollabConnector from '@/collab/connection/CollabConnector.vue'
import { sharedHistory } from '@/collab/editing/sharedHistory'
import type { SidebarLanguage } from '@/components/modeling/sidebars/ElementsSidebar.vue'
import type { DiagramElement } from '@/model/Element'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'
import type { DiagramSyntax } from '@/model/Syntax'
import type { CanvasWindowDefinition, CanvasWindowPatch } from '@/model/CanvasWindow'
import { buildValidationRulesForLanguages, DiagramValidator, type ValidationLanguage } from '@/utils/multiplicity'
import { constraintStyle, elementTypeOf, pointId } from '@/utils/connectionPoints'
import ConnectionSuggestions from './ConnectionSuggestions.vue'
import { buildContainmentFromSyntax, canContain, type ContainmentMap } from '@/utils/containment'
import { buildAcyclicFromSyntax, closesCycle, isOnCycle, renderAcyclicMessage, renderCycleRequiredMessage, type AcyclicSettings } from '@/utils/acyclic'
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

  // Rich Text: Formatierungen (Cmd/Strg+B, I, U) bleiben im Label erhalten
  override getInitialValue(state: CellState, trigger: MouseEvent | null): string {
    if (!this.graph.isHtmlLabel(state.cell)) return super.getInitialValue(state, trigger)
    return labelToEditorHtml(this.graph.getEditingValue(state.cell, trigger) ?? '')
  }

  override getCurrentValue(state: CellState): string | null {
    if (!this.textarea || !this.graph.isHtmlLabel(state.cell)) return super.getCurrentValue(state)
    return editorHtmlToLabel(this.textarea)
  }
}

// Containment rules of the syntax, read by MyCustomGraph.isValidDropTarget
let containment: ContainmentMap = new Map()

// Cycle rules of every language, read by the native graph validation hooks.
let acyclic: AcyclicSettings[] = []

class MyCustomGraph extends Graph {
  constructor(container: HTMLElement, model?: GraphDataModel, plugins?: GraphPluginConstructor[]) {
    super(container, model, plugins)
    // getEdgeValidationError decides loops per connection instead of globally
    this.setAllowLoops(true)
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

  override getAllConnectionConstraints = (terminal: CellState | null, _source: boolean): ConnectionConstraint[] | null => {
    void _source
    const element = sidebarLanguages.value.flatMap((language) => language.elements).find((e) => e.type === elementTypeOf(terminal?.cell ?? null))
    if (element) return element.anchorPoints.map((p) => new ConnectionConstraint(new Point(p.x, p.y), false, pointId(p)))
    return (terminal?.cell?.geometry as any)?.constraints ?? null
  }

  override setConnectionConstraint = (edge: Cell, terminal: Cell | null, source = false, constraint: ConnectionConstraint | null = null) => {
    this.batchUpdate(() => {
      super.setConnectionConstraint(edge, terminal, source, constraint)
      if (constraint) this.getDataModel().setStyle(edge, { ...edge.getStyle(), [source ? 'exitPointId' : 'entryPointId']: constraint.name ?? undefined })
    })
  }

  /**
   * Behebt den MaxGraph Round-Trip-Bug: exitPerimeter/entryPerimeter wird als '0' (String)
   * gespeichert, aber '0' ist in JS truthy → perimeter=false Constraints verhalten sich wie true.
   */
  override getConnectionConstraint = (edge: CellState, terminal: CellState | null, source: boolean): ConnectionConstraint => {
    const constraint = super.getConnectionConstraint(edge, terminal, source)
    const id = (edge.cell.getStyle() as Record<string, unknown>)[source ? 'exitPointId' : 'entryPointId']
    const named = id ? this.getAllConnectionConstraints(terminal, source)?.find((c) => c.name === id) : null
    if (named) return new ConnectionConstraint(named.point, named.perimeter, named.name, constraint.dx, constraint.dy)
    const p = (constraint as any).perimeter
    if (p === '0' || p === 0) {
      ;(constraint as any).perimeter = false
    }
    return constraint
  }

  override isCellEditable = (cell: Cell) => {
    // Edges: "Label Editable on Canvas" of the connection; elements and additional labels: their own allowLabelEdit
    const allow = cell.isEdge() ? this.getConnectionOf(cell)?.allowLabelEdit : (cell as any).allowLabelEdit

    if (allow === false) {
      return false
    }
    if (allow === true) {
      return true
    }
    return super.isCellEditable(cell)
  }

  /**
   * Only containers accept elements, and only the types the containment rule allows.
   * MaxGraph would otherwise accept any cell with children, e.g. a SERM entity because of its attribute list.
   */
  override isValidDropTarget = (cell: Cell, cells?: Cell[]): boolean => {
    return !!cell && !cell.isEdge() && (this.isSwimlane(cell) || isContainerSectionTarget(cell)) && canContain(containment, cell, cells ?? [])
  }

  /**
   * Edges only accept connections if their connection allows "Connectable Line".
   * setConnectableEdges(true) would otherwise apply to all edges of every language.
   */
  override isValidSource = (cell: Cell | null): boolean => {
    if (cell?.isEdge() && this.getConnectionOf(cell)?.connectable === false) return false
    return super.isValidSource(cell)
  }

  getConnectionOf = (edge: Cell) => languageConnections.value.find((c) => c.type === (edge as any).connectionId)

  // Without "Allow Loose Ends" an edge stays connected at both ends; the editor preview stays freely deformable
  allowsLooseEnds = (edge: Cell) => isPreviewEdge(edge) || this.getConnectionOf(edge)?.allowLooseEnds !== false

  // Moving the whole edge only detaches its ends if loose ends are allowed
  override disconnectGraph = (cells: Cell[]) => {
    super.disconnectGraph(cells.filter((cell) => !cell.isEdge() || this.allowsLooseEnds(cell)))
  }

  /**
   * Reconnecting edge ends snaps like new edges (Connection Docking of the element).
   * outline = false: maxGraph hardcodes it to true and would otherwise place the end at the mouse position, even inside the element.
   */
  override createEdgeHandler = (state: CellState, edgeStyle: EdgeStyleFunction | null) => {
    const handler = super.createEdgeHandler(state, edgeStyle)
    handler.constraintHandler.onDestroy()
    handler.constraintHandler = new AnchorConstraintHandler(this)
    handler.outline = false
    handler.validateConnection = (source, target) => {
      const edge = state.cell
      const probe = edge.clone()
      probe.setTerminal(source, true)
      probe.setTerminal(target, false)
      probe.setStyle({ ...edge.getStyle(), ...constraintStyle(handler.constraintHandler.currentConstraint, handler.isSource), [handler.isSource ? 'exitPointId' : 'entryPointId']: handler.constraintHandler.currentConstraint?.name ?? '' })
      if (!handler.constraintHandler.currentConstraint?.point) probe.setStyle({ ...probe.getStyle(), [handler.isSource ? 'exitX' : 'entryX']: undefined, [handler.isSource ? 'exitY' : 'entryY']: undefined })
      // Ignore the original edge while counting an operation that only reconnects it.
      ;(probe as any).replacesEdge = edge
      return this.getEdgeValidationError(probe, source, target)
    }
    // Dragging an end into empty space snaps back without "Allow Loose Ends"
    const changeTerminalPoint = handler.changeTerminalPoint.bind(handler)
    handler.changeTerminalPoint = (edge, point, isSource, clone) => (this.allowsLooseEnds(edge) ? changeTerminalPoint(edge, point, isSource, clone) : edge)
    return handler
  }

  override convertValueToString = (cell: Cell) => {
    return super.convertValueToString(cell)
  }

  override getEdgeValidationError = (edge: Cell | null, source: Cell | null, target: Cell | null): string | null => {
    // Edges that must not be docked onto block in every mode, also when reconnecting an edge end
    if ((source?.isEdge() && !this.isValidSource(source)) || (target?.isEdge() && !this.isValidTarget(target))) return ''
    // Like the native allowLoops check (ValidationMixin.js:35), but per connection: "Allow Loops" (default: blocked).
    // With a message instead of '', because ConnectionHandler.mouseUp treats an empty error as valid
    const connection = edge ? this.getConnectionOf(edge) : undefined
    const blockedLoop = !!source && source === target && connection?.allowLoops !== true
    const blockedLooseEnd = edge && !isPreviewEdge(edge) && connection?.allowLooseEnds === false && (!source || !target)
    const error = blockedLooseEnd ? 'This connection must be attached at both ends.\n' : blockedLoop ? `The Connection ${connection?.type ?? '-'} may not connect ${(source as any).diagramElementType ?? '-'} to itself.\n` : super.getEdgeValidationError(edge, source, target)
    const mode = getGraphValidationMode(this)
    if (mode === 'preventive') {
      return error
    }
    return isValidationPassActive(this) ? error : null
  }

  // Extend native validation with every active language's cycle rules.
  override validateEdge = (edge: Cell, source: Cell, target: Cell): string | null => {
    const errors = [super.validateEdge(edge, source, target)]
    if (!source.isEdge() && !target.isEdge()) {
      for (const settings of acyclic) {
        if (settings.mode === 'forbid' && closesCycle(edge, source, target, settings.connectionTypes, settings.ignoreDirection, settings.scopeConnectionTypes)) errors.push(renderAcyclicMessage(settings.message, source, target))
      }
    }
    return errors.filter(Boolean).join('') || null
  }

  override validateCell = (cell: Cell, context: CellState): string | null => {
    const errors = [super.validateCell(cell, context)]
    const isElement = (candidate: Cell) => candidate.isVertex() && candidate.isConnectable() && !!elementTypeOf(candidate)
    for (const settings of acyclic) {
      const inScope = (candidate: Cell) => !settings.scopeElementTypes || settings.scopeElementTypes.includes(elementTypeOf(candidate) ?? '')
      if (settings.mode === 'every' && isElement(cell) && inScope(cell) && (!settings.elementTypes.length || settings.elementTypes.includes(elementTypeOf(cell)!)) && !isOnCycle(cell, settings)) {
        errors.push(renderCycleRequiredMessage(settings.message, cell))
      }
      if (settings.mode === 'any' && cell === this.getDataModel().getRoot()) {
        const hasCycle = Object.values(this.getDataModel().cells ?? {}).some((candidate) => isElement(candidate) && inScope(candidate) && isOnCycle(candidate, settings))
        if (!hasCycle) errors.push(renderCycleRequiredMessage(settings.message))
      }
    }
    return errors.filter(Boolean).join('') || null
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
  selectConnectionByReference: (languageId: string, connectionType: string) => boolean
}

const props = withDefaults(
  defineProps<{
    model?: GraphDataModel
    allowEdit?: boolean
    helpSelectionMode?: boolean
    helpFlowActive?: boolean
    helpCellIds?: string[]
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
    languages?: (SidebarLanguage & Partial<ValidationLanguage>)[]
    autonomyMode?: AutonomyMode
    connectionPreviewAllowed?: boolean
    lockAutonomyMode?: boolean
    taskActive?: boolean
    taskEdit?: TaskEditDocument | null
    taskEditSyncState?: TaskEditSyncState
    selectedTaskEditIds?: string[]
    modelId?: string | null
    openEvaluationId?: string | null
    previewConnection?: DiagramConnection
    previewMode?: 'simple' | 'scenario' | 'routing'
    overlays?: FeedbackCanvasOverlayEntry[]
    feedbackConfig?: DiagramFeedbackConfig
    canvasWindows?: CanvasWindowDefinition[]
  }>(),
  {
    allowEdit: true,
    helpSelectionMode: false,
    helpCellIds: () => [],
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
    connectionPreviewAllowed: false,
    lockAutonomyMode: false,
    taskActive: false,
    taskEdit: null,
    taskEditSyncState: 'synced',
    selectedTaskEditIds: () => [],
    modelId: null,
    openEvaluationId: null,
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
  'window-removed': [id: string]
  'removeTaskEdit': [id: string]
  'updateTaskEditDocument': [document: JsonObject]
  'update:helpCellIds': [ids: string[]]
  'focusTaskEdit': [target: TaskEditFocus]
}>()

const autonomyMode = ref<AutonomyMode>(props.autonomyMode ?? 'free')
const connectionPreview = useConnectionPreviewPreference()
const connectionPreviewEnabled = computed(() => props.connectionPreviewAllowed && connectionPreview.value)
const activeLayerView = ref<CanvasLayerView>('both')
const rightSidebarCollapsed = ref(false)
const rightSidebarId = `model-tools-${globalThis.crypto.randomUUID()}`
const showRightSidebar = computed(() => props.showElements !== false && props.showModelSidebar !== false && props.showToolbar && props.modelManagement)

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
let cleanupGrid: (() => void) | undefined
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
const helpHighlights: CellHighlight[] = []
const refreshHelpHighlights = () => {
  helpHighlights.splice(0).forEach((highlight) => highlight.destroy())
  const current = graph.value
  if (!current || !props.helpSelectionMode) return
  for (const id of props.helpCellIds) {
    const cell = current.getDataModel().getCell(id)
    const state = cell ? current.view.getState(cell) : null
    if (!state) continue
    const highlight = new CellHighlight(current, '#b27b20', 3)
    highlight.highlight(state)
    if (highlight.shape?.node) highlight.shape.node.style.pointerEvents = 'none'
    helpHighlights.push(highlight)
  }
}
const helpMouseListener: MouseListenerSet = {
  mouseDown(_sender, me) {
    if (!props.helpSelectionMode || !eventUtils.isLeftMouseButton(me.getEvent())) return
    const cell = me.getCell()
    const id = cell?.getId()
    if (cell && id && (cell.isVertex() || cell.isEdge())) {
      const ids = props.helpCellIds.includes(id) ? props.helpCellIds.filter((value) => value !== id) : [...props.helpCellIds, id]
      emit('update:helpCellIds', ids)
    }
    me.consume()
  },
  mouseMove() {}, mouseUp() {}
}
watch([() => props.helpSelectionMode, () => props.allowEdit], () => {
  graph.value?.setEnabled(props.allowEdit && !props.helpSelectionMode)
  if (props.helpSelectionMode) graph.value?.clearSelection()
  refreshHelpHighlights()
})
watch(() => props.helpCellIds, refreshHelpHighlights, { deep: true })
let pendingPersistedModel: Record<string, unknown> | null = null
const plugins = ref<GraphPluginConstructor[]>([MyCustomCellEditorHandler, TooltipHandler, CustomConnectionHandler as unknown as GraphPluginConstructor, StablePanningHandler, SelectionCellsHandler, SelectionHandler, RubberBandHandler, FitPlugin])
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
// Validation messages for the whole diagram, shown as a notice above the canvas
const diagramWarnings = ref<string[]>([])

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
  notifyError([...new Set(messages)].join('\n'))
}

const updateAutonomyMode = (mode: AutonomyMode) => {
  if (props.lockAutonomyMode) return
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
  diagramWarnings.value = autonomyMode.value !== 'free' ? diagramValidator.validateGraph(currentGraph) : []
}

const rebuildValidationRules = (rules?: DiagramSyntax[]) => {
  const languages: ValidationLanguage[] = props.languages?.length && props.languages.every((language) => language.syntax !== undefined && language.connections !== undefined)
    ? props.languages.map((language) => ({ syntax: language.syntax!, elements: language.elements, connections: language.connections! }))
    : [{ syntax: rules ?? [], elements: sidebarLanguages.value.flatMap((language) => language.elements), connections: languageConnections.value }]
  containment = buildContainmentFromSyntax(languages.flatMap((language) => language.syntax))
  acyclic = languages.flatMap((language) => buildAcyclicFromSyntax(language.syntax, { elementTypes: language.elements.map((element) => element.type), connectionTypes: language.connections.map((connection) => connection.type) }))
  const validationRules = buildValidationRulesForLanguages(languages)
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

const formatSelectedText = (format: TextFormat) => props.allowEdit && graph.value && formatText(graph.value, format)

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
  // Ein Modell aus einem Raum nimmt nur eigene Schritte zurück, über collab-kit.
  if (sharedHistory.value) {
    sharedHistory.value.undo()
    return
  }
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
  if (sharedHistory.value) {
    sharedHistory.value.redo()
    return
  }
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

// Canvas2D-Formen der Sprachen registrieren, damit auch geladene Modelle sie zeichnen
watch(
  sidebarLanguages,
  (languages) => {
    languages.forEach((language) => language.elements.forEach((element) => registerElementShapes(element)))
    graph.value?.refresh()
  },
  { immediate: true, deep: true }
)

// Computed für Verbindungen
const languageConnections = computed(() => props.languageConnections ?? [])

watch(
  [() => props.languageSyntax, sidebarLanguages, languageConnections],
  () => {
    rebuildValidationRules(props.languageSyntax ?? [])
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
      diagramWarnings.value = diagramValidator.validateGraph(currentGraph)
    } else if (currentGraph) {
      diagramWarnings.value = []
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
  cleanupGrid?.()
  cleanupGrid = undefined
  helpHighlights.splice(0).forEach((highlight) => highlight.destroy())
  graph.value?.destroy()
  graph.value = undefined
})

// Watch for previewConnection (preview mode only): apply changes to the existing preview,
// so moved elements stay in place. It is only rebuilt when there is no preview yet.
watch(
  () => props.previewConnection,
  (newConn) => {
    if (!graph.value) return
    if (newConn && updateConnectionPreview(graph.value, newConn)) return
    renderConnectionPreviewOnly(newConn)
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
  graph.value.setEnabled(props.allowEdit && !props.helpSelectionMode)
  graph.value.addMouseListener(helpMouseListener)
  graph.value.setConnectable(true)
  graph.value.setConnectableEdges(true)
  graph.value.setCellsEditable(props.allowEdit)
  graph.value.setCellsMovable(props.allowEdit)
  graph.value.setCellsResizable(props.allowEdit)
  graph.value.setCellsDeletable(props.allowEdit)
  graph.value.setCellsCloneable(props.allowEdit)
  graph.value.setAllowNegativeCoordinates(false)
  graph.value.setHtmlLabels(true)
  protectHtmlLabels(graph.value)
  enableLabelPadding(graph.value)
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
  cleanupGrid?.()
  cleanupGrid = setupDynamicGrid(graph, canvasGrid, graphContainer, gridSize, snapToGrid)

  applyValidationRulesToGraph()

  if (pendingPersistedModel) {
    const pending = pendingPersistedModel
    pendingPersistedModel = null
    loadPersistedModel(pending)
  }
}

const buildLanguageShapes = computed(() => {
  if (sidebarLanguages.value.every((language) => language.elements.length === 0)) {
    return createDefaultShapes({
      rectangle: img_rectangle,
      ellipse: img_ellipse,
      rhombus: img_rhombus,
      triangle: img_triangle,
      cloud: img_cloud
    })
  }
  return sidebarLanguages.value.flatMap((language) => buildShapesFromElements(language.elements, img_elementPlaceholder, language.id))
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
            ;(feedbackCell as any).feedbackConnectionType = entry.connection.type
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

const selectConnectionByType = (languageId: string, connectionType: string): boolean => {
  const graphInstance = graph.value
  if (!graphInstance) return false

  const connectionExistsInLanguage = (props.connectionGroups ?? []).some(
    (group) => group.id === languageId && group.connections.some((connection) => connection.type === connectionType)
  )
  if (!connectionExistsInLanguage) return false

  canvasToolbar.value?.selectConnectionByReference(languageId, connectionType)

  const parentCell = modelLayerCell.value ?? graphInstance.getDefaultParent()
  const edges = parentCell.filterDescendants((cell) => cell.isEdge())
  const matchingEdge = edges.find((edge) => (edge as any).connectionId === connectionType)
  if (!matchingEdge) return false

  graphInstance.setSelectionCell(matchingEdge)
  graphInstance.scrollCellToVisible?.(matchingEdge, true)
  return true
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
  if (typeof data.xml !== 'string') return
  if (!graph.value) {
    pendingPersistedModel = data
    return
  }

  pendingPersistedModel = null
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

const onWindowRemoved = (id: string) => emit('window-removed', id)
defineExpose({
  graph,
  clearCanvas,
  addCanvasWindow,
  updateCanvasWindow,
  removeCanvasWindow,
  clearCanvasWindows,
  setCanvasWindows,
  selectConnectionByType,
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

.graph-viewport {
  position: relative;
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 0;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
  isolation: isolate;
}

.canvas-area--help-selection .graph-viewport { outline: 2px solid #c79b4b; outline-offset: -2px; }
.canvas-area--help-selection .graph-container { cursor: crosshair; }

.graph-container {
  position: absolute;
  inset: 0;
  z-index: 1;
  overflow: hidden;
  background: transparent;
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

.canvas-top {
  flex-shrink: 0;
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

.canvas-top-right {
  position: absolute;
  top: 0;
  right: 5px;
  z-index: 10;
  max-width: calc(100% - 20px);
}

.canvas-diagram-warnings {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  width: max-content;
  max-width: calc(100% - 16px);
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
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}

.grid-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: block;
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

.toolbar-actions :deep(.canvas-toolbar) { flex: 1 1 400px; }
.canvas-mode-controls { display: flex; flex-wrap: nowrap; align-items: center; gap: 8px; flex: 0 0 auto; margin-left: auto; align-self: flex-end; order: 99; }

</style>
