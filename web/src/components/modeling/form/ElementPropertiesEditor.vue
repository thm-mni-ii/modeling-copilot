<template>
  <div>
    <!-- Grundeinstellungen -->
    <v-text-field v-model="localElement.type" label="Type Identifier" variant="outlined" density="compact" class="mb-3" hint="Unique identifier (e.g. 'uml-class')" persistent-hint @input="emitUpdate" />

    <v-text-field v-model="localElement.defaultLabel" label="Default Label" variant="outlined" density="compact" class="mb-3" hint="Default text for new instances" persistent-hint @input="emitUpdate" />

    <!-- Shape-Typ -->
    <v-select v-model="localElement.renderMode" :items="shapeTypes" item-title="title" item-value="value" label="Render Mode" variant="outlined" density="compact" class="mb-3" @update:model-value="onTypeChange" />

    <!-- Canvas2D Editor -->
    <v-textarea v-if="localElement.renderMode === 'canvas2d'" v-model="localElement.canvas" label="Canvas2D Commands" variant="outlined" density="compact" rows="4" class="mb-3" hint="Commands: MOVE x y, LINE x y, RECT x y w h, ELLIPSE x y w h" persistent-hint @input="emitUpdate" />

    <!-- Predefined Shape -->
    <v-select v-if="localElement.renderMode === 'predefined'" v-model="localElement.predefinedShape" :items="predefinedShapes" item-title="label" item-value="value" label="Predefined Shape" variant="outlined" density="compact" class="mb-3" @update:model-value="emitUpdate" />

    <!-- Swimlane Beschreibung -->
    <v-alert v-if="localElement.renderMode === 'swimlane'" type="info" variant="tonal" class="mb-3">
      <v-icon class="mr-2">mdi-view-column</v-icon>
      <strong>Swimlane Container Element</strong>
      <div class="text-caption mt-1">Swimlanes work well for containers such as class diagrams, use cases, and other structured Elements.</div>
    </v-alert>

    <!-- Position (nur für Child-Elemente) -->
    <div v-if="isChild && childElementData">
      <v-divider class="my-3" />
      <div class="text-subtitle-2 mb-2">Positioning</div>
      <v-row>
        <v-col cols="3">
          <v-text-field v-model.number="childElementData.position.x" label="X" variant="outlined" density="compact" type="number" step="0.1" @input="emitUpdate" />
        </v-col>
        <v-col cols="3">
          <v-text-field v-model.number="childElementData.position.y" label="Y" variant="outlined" density="compact" type="number" step="0.1" @input="emitUpdate" />
        </v-col>
        <v-col cols="3">
          <v-text-field v-model.number="childElementData.position.width" label="Width" variant="outlined" density="compact" type="number" @input="emitUpdate" />
        </v-col>
        <v-col cols="3">
          <v-text-field v-model.number="childElementData.position.height" label="Height" variant="outlined" density="compact" type="number" @input="emitUpdate" />
        </v-col>
      </v-row>
      <v-checkbox v-model="childElementData.position.relative" label="Relative Positioning" density="compact" class="mb-2" @update:model-value="emitUpdate" />
    </div>

    <!-- Dimensions (nur für Haupt-Elemente) -->
    <v-row v-if="!isChild && diagramElementData">
      <v-col cols="6">
        <v-text-field v-model.number="diagramElementData.width" label="Width" variant="outlined" density="compact" type="number" @input="emitUpdate" />
      </v-col>
      <v-col cols="6">
        <v-text-field v-model.number="diagramElementData.height" label="Height" variant="outlined" density="compact" type="number" @input="emitUpdate" />
      </v-col>
    </v-row>

    <!-- Erweiterte Einstellungen -->
    <v-expansion-panels variant="accordion" class="mt-3">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-format-paint</v-icon>
          Style Settings
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-row>
            <v-col cols="6">
              <ColorPickerField v-model="localElement.style.strokeColor" label="Border Color" @update:model-value="emitUpdate" />
            </v-col>
            <v-col cols="6">
              <ColorPickerField v-model="localElement.style.fillColor" label="Fill Color" @update:model-value="emitUpdate" />
            </v-col>
          </v-row>

          <v-slider v-model="localElement.style.strokeWidth" label="Border Width" min="1" max="10" step="1" thumb-label class="mb-3" @update:model-value="emitUpdate" />

          <v-slider v-model="localElement.style.fontSize" label="Font Size" min="8" max="24" step="1" thumb-label class="mb-3" @update:model-value="emitUpdate" />

          <ColorPickerField v-model="localElement.style.fontColor" label="Font Color" class="mb-3" @update:model-value="emitUpdate" />

          <v-text-field v-model="localElement.style.fontFamily" label="Font Family" variant="outlined" density="compact" class="mb-3" @input="emitUpdate" />

          <v-row>
            <v-col cols="6">
              <v-select v-model="localElement.style.align" :items="alignOptions" label="Horizontal Alignment" variant="outlined" density="compact" @update:model-value="emitUpdate" />
            </v-col>
            <v-col cols="6">
              <v-select v-model="localElement.style.verticalAlign" :items="verticalAlignOptions" label="Vertical Alignment" variant="outlined" density="compact" @update:model-value="emitUpdate" />
            </v-col>
          </v-row>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-pencil</v-icon>
          Editing
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox v-model="localElement.allowLabelEdit" label="Label Editable on Canvas" density="compact" hint="Double-click opens the editor when enabled" persistent-hint @update:model-value="emitUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Verbindungspunkte (nur für Haupt-Elemente) -->
      <v-expansion-panel v-if="!isChild && diagramElementData">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-target</v-icon>
          Connection Points
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="d-flex align-center mb-3">
            <span class="text-subtitle-2 mr-3">Anchor Points</span>
            <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addAnchorPoint"> Add </v-btn>
          </div>

          <v-switch v-model="showAutoAnchorGenerator" label="Distribute Anchor Points Automatically" density="compact" color="primary" class="mb-2" hint="Optionally create evenly distributed points along the shape outline" persistent-hint />

          <v-row v-if="showAutoAnchorGenerator" dense class="mb-3">
            <v-col cols="12" md="4">
              <v-text-field v-model.number="autoAnchorCount" label="Number of Points" variant="outlined" density="compact" type="number" min="1" max="128" @input="emitUpdate" />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field v-model.number="autoAnchorStartAngle" label="Start Angle" variant="outlined" density="compact" type="number" suffix="deg" hint="0 = right, 90 = top" persistent-hint @input="emitUpdate" />
            </v-col>
            <v-col cols="12" md="4" class="d-flex align-center">
              <v-btn color="primary" variant="flat" prepend-icon="mdi-auto-fix" @click="generateAnchorPoints"> Generate </v-btn>
            </v-col>
          </v-row>

          <div v-if="diagramElementData.anchorPoints && diagramElementData.anchorPoints.length > 0" class="mb-2">
            <div class="d-flex flex-wrap align-center ga-2 mb-2">
              <v-checkbox-btn :model-value="allAnchorRowsSelected" :indeterminate="someAnchorRowsSelected" @update:model-value="toggleSelectAllAnchorRows(Boolean($event))" />
              <span class="text-body-2">Select All</span>
              <v-chip size="small" variant="tonal">Selected: {{ selectedAnchorRows.length }}</v-chip>
              <v-btn color="error" variant="tonal" size="small" prepend-icon="mdi-delete" :disabled="selectedAnchorRows.length === 0" @click="removeSelectedAnchorPoints"> Delete Selection </v-btn>
            </div>

            <v-table density="compact" class="anchor-table">
              <thead>
                <tr>
                  <th style="width: 48px"></th>
                  <th style="width: 64px">#</th>
                  <th>X (0-1)</th>
                  <th>Y (0-1)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(point, index) in diagramElementData.anchorPoints" :key="index">
                  <td>
                    <v-checkbox-btn :model-value="selectedAnchorRows.includes(index)" @update:model-value="updateAnchorRowSelection(index, Boolean($event))" />
                  </td>
                  <td>{{ index + 1 }}</td>
                  <td>
                    <v-text-field v-model.number="point.x" variant="underlined" density="compact" type="number" step="0.1" min="0" max="1" hide-details @input="emitUpdate" />
                  </td>
                  <td>
                    <v-text-field v-model.number="point.y" variant="underlined" density="compact" type="number" step="0.1" min="0" max="1" hide-details @input="emitUpdate" />
                  </td>
                </tr>
              </tbody>
            </v-table>
          </div>

          <v-alert v-if="!diagramElementData.anchorPoints || diagramElementData.anchorPoints.length === 0" type="info" variant="tonal" class="mt-2"> No Connection points defined. Default points will be used. </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Verhalten -->
      <!-- Verhalten (nur für Haupt-Elemente) -->
      <v-expansion-panel v-if="!isChild && diagramElementData">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-cog</v-icon>
          Behavior
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox v-model="diagramElementData.connectable" label="Allow Connections" density="compact" @update:model-value="emitUpdate" />
          <v-checkbox v-model="diagramElementData.resizable" label="Resizable" density="compact" @update:model-value="emitUpdate" />
          <v-checkbox v-model="diagramElementData.movable" label="Movable" density="compact" @update:model-value="emitUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Verhalten für Child-Elemente (nur connectable) -->
      <v-expansion-panel v-if="isChild && childElementData">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-cog</v-icon>
          Behavior
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-checkbox v-model="childElementData.connectable" label="Allow Connections" density="compact" @update:model-value="emitUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Swimlane-Einstellungen (wenn renderMode = swimlane) -->
      <v-expansion-panel v-if="localElement.renderMode === 'swimlane'">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-view-column</v-icon>
          Swimlane Settings
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-row dense>
            <v-col cols="6">
              <v-text-field v-model.number="localElement.style.startSize" label="Start Size" variant="outlined" density="compact" type="number" hint="Size of the header or start column" persistent-hint @input="emitUpdate" />
            </v-col>
            <v-col cols="6">
              <v-checkbox v-model="localElement.style.horizontal" label="Horizontal" density="compact" hint="Swimlane orientation" @update:model-value="emitUpdate" />
            </v-col>
          </v-row>

          <v-row dense>
            <v-col cols="6">
              <v-select v-model="localElement.style.direction" :items="swimlaneDirections" label="Direction" variant="outlined" density="compact" hint="Orientation of the title/content region" persistent-hint clearable @update:model-value="emitUpdate" />
            </v-col>
            <v-col cols="6">
              <v-switch v-model="localElement.style.swimlaneLine" label="Title Separator Line" color="primary" density="compact" hint="Show the line between title and content region" persistent-hint @update:model-value="emitUpdate" />
            </v-col>
          </v-row>

          <v-row dense>
            <v-col cols="6">
              <ColorPickerField v-model="localElement.style.swimlaneFillColor" label="Content Fill Color" hint="Fill color of the content region (separate from the title fill color)" @update:model-value="emitUpdate" />
            </v-col>
            <v-col cols="6">
              <ColorPickerField v-model="localElement.style.separatorColor" label="Separator Color" hint="Color of the lane separator lines" @update:model-value="emitUpdate" />
            </v-col>
          </v-row>

          <v-divider class="my-4" />

          <div class="text-subtitle-2 mb-3">Auto-layout Options</div>

          <v-row dense>
            <v-col :cols="isCustomLayout ? 6 : 12">
              <v-select
                :model-value="localElement.style.layoutPreset ?? 'list'"
                :items="layoutPresets"
                item-title="title"
                item-value="value"
                label="Preset"
                variant="outlined"
                density="compact"
                hint="Free: no automatic arrangement (e.g. Activity pool/lane). List: ordered, auto-stacked (e.g. UML attributes). Custom: configure every option yourself."
                persistent-hint
                @update:model-value="setLayoutPreset"
              />
            </v-col>
            <v-col v-if="isCustomLayout" cols="6">
              <v-select :model-value="localElement.style.containerLayout ?? 'list'" :items="containerLayoutModes" item-title="title" item-value="value" label="Container Mode" variant="outlined" density="compact" @update:model-value="setContainerLayout" />
            </v-col>
          </v-row>

          <template v-if="(localElement.style.containerLayout ?? 'list') === 'list'">
            <v-row dense>
              <v-col cols="6">
                <v-select v-model="localElement.style.listDirection" :disabled="!isCustomLayout" :items="listDirections" item-title="title" item-value="value" label="Stack Direction" variant="outlined" density="compact" hint="Axis along which child Elements are stacked" persistent-hint @update:model-value="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-switch v-model="localElement.style.listStretchCrossAxis" :disabled="!isCustomLayout" label="Stretch Cross Axis" color="primary" density="compact" hint="Stretch child Elements across the container (e.g. full width)" persistent-hint @update:model-value="emitUpdate" />
              </v-col>
            </v-row>

            <v-row dense class="mt-2">
              <v-col cols="6">
                <v-switch v-model="localElement.style.resizeMainAxis" :disabled="!isCustomLayout" label="Resize Stack Axis" color="primary" density="compact" hint="Shrink/grow the container along the stack direction to fit its content" persistent-hint @update:model-value="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-switch v-model="localElement.style.resizeCrossAxis" :disabled="!isCustomLayout || localElement.style.listStretchCrossAxis" label="Resize Cross Axis" color="primary" density="compact" hint="Only relevant when Stretch Cross Axis is off" persistent-hint @update:model-value="emitUpdate" />
              </v-col>
            </v-row>

            <v-row dense class="mt-2">
              <v-col cols="6">
                <v-text-field v-model.number="localElement.style.listItemSpacing" :disabled="!isCustomLayout" label="Item Spacing" type="number" density="compact" variant="outlined" suffix="px" hint="Spacing between Elements along the stack direction" persistent-hint @input="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-text-field v-model.number="localElement.style.listCrossPadding" :disabled="!isCustomLayout" label="Cross Padding" type="number" density="compact" variant="outlined" suffix="px" hint="Padding across the stack direction" persistent-hint @input="emitUpdate" />
              </v-col>
            </v-row>

            <v-row dense class="mt-2">
              <v-col cols="6">
                <v-text-field v-model.number="localElement.style.minWidth" :disabled="!isCustomLayout" label="Min Width" type="number" density="compact" variant="outlined" suffix="px" hint="Lower bound for the container width" persistent-hint @input="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-text-field v-model.number="localElement.style.minHeight" :disabled="!isCustomLayout" label="Min Height" type="number" density="compact" variant="outlined" suffix="px" hint="Lower bound for the container height" persistent-hint @input="emitUpdate" />
              </v-col>
            </v-row>
          </template>

          <template v-else>
            <v-row dense>
              <v-col cols="6">
                <v-select v-model="localElement.style.resizeToContent" :disabled="!isCustomLayout" :items="resizeToContentOptions" item-title="title" item-value="value" label="Resize To Content" variant="outlined" density="compact" hint="'Grow': container only grows to fit content, never shrinks automatically" persistent-hint @update:model-value="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-text-field v-model.number="localElement.style.contentPadding" :disabled="!isCustomLayout" label="Content Padding" type="number" density="compact" variant="outlined" suffix="px" hint="Minimum distance of Elements to the border used for growth" persistent-hint @input="emitUpdate" />
              </v-col>
            </v-row>
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Collapse / Zusammenklappen -->
      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-folder-open-outline</v-icon>
          Collapse
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <CollapseSettings :element="localElement" @update="emitUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Rekursive Child Elemente -->
      <v-expansion-panel v-if="depth < maxDepth">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-family-tree</v-icon>
          Child Elements
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="d-flex align-center mb-3">
            <span class="text-subtitle-2 mr-3">Nested Elements</span>
            <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="addChildElement"> Add Child </v-btn>
          </div>

          <v-card v-for="(child, index) in localElement.children" :key="index" variant="outlined" class="mb-3">
            <v-card-title class="d-flex align-center justify-space-between py-2">
              <span class="text-subtitle-2">{{ child.defaultLabel }}</span>
              <v-btn icon="mdi-delete" variant="text" size="small" color="error" @click="removeChildElement(index)" />
            </v-card-title>

            <v-card-text>
              <!-- Rekursiver Aufruf der gleichen Komponente für Child -->
              <ElementPropertiesEditor :element="child" :is-child="true" :show-id="false" :depth="depth + 1" :max-depth="maxDepth" @update="emitUpdate" />
            </v-card-text>
          </v-card>

          <v-alert v-if="!localElement.children || localElement.children.length === 0" type="info" variant="tonal" class="mt-2"> No child Elements defined </v-alert>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import type { DiagramElement, ChildElement, ElementStyle } from '@/model/Element'
import { generateEvenlyDistributedAnchorPoints } from '@/utils/anchorPointGenerator'
import CollapseSettings from './CollapseSettings.vue'
import ColorPickerField from './ColorPickerField.vue'

defineOptions({ name: 'ElementPropertiesEditor' })

interface Props {
  element: DiagramElement | ChildElement
  isChild?: boolean
  depth?: number
  maxDepth?: number
}

const props = withDefaults(defineProps<Props>(), {
  isChild: false,
  depth: 0,
  maxDepth: 5
})

const emit = defineEmits<{
  (e: 'update'): void
}>()

const localElement = toRef(props, 'element')

function isDiagramElement(el: DiagramElement | ChildElement): el is DiagramElement {
  return 'width' in el
}

function isChildElement(el: DiagramElement | ChildElement): el is ChildElement {
  return 'position' in el
}

const diagramElementData = computed(() => (isDiagramElement(localElement.value) ? localElement.value : null))
const childElementData = computed(() => (isChildElement(localElement.value) ? localElement.value : null))

const shapeTypes = [
  { title: 'Canvas2D Shape', value: 'canvas2d' },
  { title: 'Predefined Shape', value: 'predefined' },
  { title: 'Swimlane Container', value: 'swimlane' }
]

const predefinedShapes = [
  { label: 'Rectangle', value: 'rectangle' },
  { label: 'Ellipse', value: 'ellipse' },
  { label: 'Diamond', value: 'rhombus' },
  { label: 'Label', value: 'label' },
  { label: 'Cloud', value: 'cloud' },
  { label: 'Actor', value: 'actor' },
  { label: 'Cylinder', value: 'cylinder' },
  { label: 'Hexagon', value: 'hexagon' },
  { label: 'Double Ellipse', value: 'doubleEllipse' },
  { label: 'Triangle', value: 'triangle' }
]

const alignOptions = ['left', 'center', 'right']
const verticalAlignOptions = ['top', 'middle', 'bottom']
const swimlaneDirections = [
  { title: 'East (default)', value: 'east' },
  { title: 'West', value: 'west' },
  { title: 'North', value: 'north' },
  { title: 'South', value: 'south' }
]
const layoutPresets = [
  { title: 'Free (no automatic arrangement)', value: 'free' },
  { title: 'List (ordered, auto-stacked)', value: 'list' },
  { title: 'Custom', value: 'custom' }
]
const containerLayoutModes = [
  { title: 'Free', value: 'free' },
  { title: 'List', value: 'list' }
]
const listDirections = [
  { title: 'Vertical', value: 'vertical' },
  { title: 'Horizontal', value: 'horizontal' }
]
const resizeToContentOptions = [
  { title: 'None (manual size only)', value: 'none' },
  { title: 'Grow (never shrinks automatically)', value: 'grow' }
]

// Merkt sich die zuletzt manuell (im Custom-Modus) gesetzten Layout-Werte pro Element,
// damit sie beim Zurückwechseln auf "Custom" wiederhergestellt werden können.
const customLayoutStash = new WeakMap<ElementStyle, Partial<ElementStyle>>()

const isCustomLayout = computed(() => (localElement.value.style.layoutPreset ?? 'list') === 'custom')

const LAYOUT_KEYS = ['containerLayout', 'listDirection', 'listItemSpacing', 'listCrossPadding', 'listStretchCrossAxis', 'resizeMainAxis', 'resizeCrossAxis', 'minWidth', 'minHeight', 'resizeToContent', 'contentPadding'] as const

function applyListDefaults(style: ElementStyle) {
  if (style.listDirection === undefined) style.listDirection = 'vertical'
  if (style.listItemSpacing === undefined) style.listItemSpacing = 10
  if (style.listCrossPadding === undefined) style.listCrossPadding = 10
  if (style.listStretchCrossAxis === undefined) style.listStretchCrossAxis = true
  if (style.resizeMainAxis === undefined) style.resizeMainAxis = true
  if (style.resizeCrossAxis === undefined) style.resizeCrossAxis = false
}

function applyFreeDefaults(style: ElementStyle) {
  if (style.resizeToContent === undefined) style.resizeToContent = 'grow'
  if (style.contentPadding === undefined) style.contentPadding = 20
}

function setLayoutPreset(preset: 'free' | 'list' | 'custom') {
  const style = localElement.value.style as ElementStyle
  const previousPreset = style.layoutPreset ?? 'list'

  // Aktuelle Werte sichern, solange wir Custom verlassen
  if (previousPreset === 'custom' && preset !== 'custom') {
    const stash: Partial<ElementStyle> = {}
    LAYOUT_KEYS.forEach((key) => {
      ;(stash as any)[key] = style[key]
    })
    customLayoutStash.set(style, stash)
  }

  if (preset === 'free') {
    style.containerLayout = 'free'
    applyFreeDefaults(style)
  } else if (preset === 'list') {
    style.containerLayout = 'list'
    applyListDefaults(style)
  } else if (preset === 'custom') {
    const stash = customLayoutStash.get(style)
    if (stash) Object.assign(style, stash)
    else if (!style.containerLayout) style.containerLayout = 'list'
  }

  style.layoutPreset = preset
  emitUpdate()
}

function setContainerLayout(mode: 'free' | 'list') {
  const style = localElement.value.style as ElementStyle
  style.containerLayout = mode
  if (mode === 'list') applyListDefaults(style)
  else applyFreeDefaults(style)
  emitUpdate()
}

const showAutoAnchorGenerator = ref(false)
const autoAnchorCount = ref(8)
const autoAnchorStartAngle = ref(0)
const selectedAnchorRows = ref<number[]>([])

const allAnchorRowsSelected = computed(() => {
  const points = diagramElementData.value?.anchorPoints ?? []
  return points.length > 0 && selectedAnchorRows.value.length === points.length
})

const someAnchorRowsSelected = computed(() => {
  const points = diagramElementData.value?.anchorPoints ?? []
  return selectedAnchorRows.value.length > 0 && selectedAnchorRows.value.length < points.length
})

function updateAnchorRowSelection(index: number, selected: boolean) {
  const current = new Set(selectedAnchorRows.value)
  if (selected) {
    current.add(index)
  } else {
    current.delete(index)
  }
  selectedAnchorRows.value = Array.from(current).sort((a, b) => a - b)
}

function toggleSelectAllAnchorRows(selected: boolean) {
  const points = diagramElementData.value?.anchorPoints ?? []
  if (!selected || points.length === 0) {
    selectedAnchorRows.value = []
    return
  }

  selectedAnchorRows.value = points.map((_, index) => index)
}

function removeSelectedAnchorPoints() {
  if (!isDiagramElement(localElement.value)) {
    return
  }

  if (selectedAnchorRows.value.length === 0) {
    return
  }

  const selected = new Set(selectedAnchorRows.value)
  localElement.value.anchorPoints = localElement.value.anchorPoints.filter((_, index) => !selected.has(index))
  selectedAnchorRows.value = []
  emitUpdate()
}

function generateAnchorPoints() {
  if (!isDiagramElement(localElement.value)) {
    return
  }

  const generated = generateEvenlyDistributedAnchorPoints({
    renderMode: localElement.value.renderMode,
    predefinedShape: localElement.value.predefinedShape,
    style: localElement.value.style,
    count: autoAnchorCount.value,
    startAngleDeg: autoAnchorStartAngle.value
  })

  autoAnchorCount.value = generated.length

  localElement.value.anchorPoints = generated
  selectedAnchorRows.value = []
  emitUpdate()
}

watch(
  localElement,
  (newVal) => {
    if (!newVal) {
      return
    }

    const style = newVal.style as ElementStyle & Partial<ElementStyle>
    if (!style.strokeColor) style.strokeColor = '#000000'
    if (!style.fillColor) style.fillColor = '#ffffff'
    if (style.strokeWidth === undefined) style.strokeWidth = 1
    if (style.fontSize === undefined) style.fontSize = 12
    if (!style.fontColor) style.fontColor = '#000000'
    if (!style.fontFamily) style.fontFamily = 'Helvetica'
    if (!style.align) style.align = 'center'
    if (!style.verticalAlign) style.verticalAlign = 'middle'

    if (newVal.renderMode === 'swimlane') {
      if (style.startSize === undefined) style.startSize = 30
      if (style.horizontal === undefined) style.horizontal = false
      if (style.swimlaneLine === undefined) style.swimlaneLine = true
      if (style.layoutPreset === undefined) style.layoutPreset = 'list'
      if (style.containerLayout === undefined) style.containerLayout = 'list'
      applyListDefaults(style)
    }

    if (!Array.isArray(newVal.children)) {
      newVal.children = []
    }

    // Anchor Points nur für DiagramElement (nicht für ChildElement)
    if (isDiagramElement(newVal)) {
      if (!Array.isArray(newVal.anchorPoints)) {
        newVal.anchorPoints = []
      }

      if (newVal.resizable === undefined) {
        newVal.resizable = true
      }

      if (newVal.movable === undefined) {
        newVal.movable = true
      }
    }

    if (newVal.connectable === undefined) {
      newVal.connectable = true
    }

    if (newVal.allowLabelEdit === undefined) {
      newVal.allowLabelEdit = true
    }
  },
  { immediate: true, deep: true }
)

function emitUpdate() {
  emit('update')
}

function applySwimlaneDefaults() {
  const current = localElement.value
  if (!current || current.renderMode !== 'swimlane') {
    return
  }

  const style = current.style as ElementStyle & Partial<ElementStyle>
  if (style.startSize === undefined) style.startSize = 30
  if (style.horizontal === undefined) style.horizontal = false
  if (style.swimlaneLine === undefined) style.swimlaneLine = true
  if (style.layoutPreset === undefined) style.layoutPreset = 'list'
  if (style.containerLayout === undefined) style.containerLayout = 'list'
  applyListDefaults(style)
}

function onTypeChange() {
  applySwimlaneDefaults()
  emitUpdate()
}

function addAnchorPoint() {
  if (!isDiagramElement(localElement.value)) {
    return
  }

  if (!Array.isArray(localElement.value.anchorPoints)) {
    localElement.value.anchorPoints = []
  }
  localElement.value.anchorPoints.push({ x: 0.5, y: 0.5 })
  emitUpdate()
}

function createDefaultChild(index: number): ChildElement {
  return {
    type: `child-${index}`,
    defaultLabel: `Child ${index + 1}`,
    renderMode: 'predefined',
    predefinedShape: 'rectangle',
    position: {
      x: 1,
      y: 1,
      width: 100,
      height: 50,
      relative: true
    },
    style: {
      strokeColor: '#000000',
      fillColor: '#ffffff',
      strokeWidth: 1,
      fontSize: 12,
      fontColor: '#000000',
      fontFamily: 'Helvetica',
      align: 'center',
      verticalAlign: 'middle'
    },
    children: [],
    connectable: true,
    allowLabelEdit: true
  }
}

function addChildElement() {
  if (!Array.isArray(localElement.value.children)) {
    localElement.value.children = []
  }

  const nextIndex = localElement.value.children.length
  const newChild = createDefaultChild(nextIndex)
  localElement.value.children.push(newChild)
  emitUpdate()
}

function removeChildElement(index: number) {
  localElement.value.children.splice(index, 1)
  emitUpdate()
}
</script>

<style scoped>
.v-expansion-panel-text {
  padding: 16px;
}
</style>
