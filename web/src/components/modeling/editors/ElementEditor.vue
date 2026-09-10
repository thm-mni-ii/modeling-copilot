<template>
  <v-container fluid class="pa-2 editor-surface">
    <v-row no-gutters class="editor-row">
      <!-- Element-Liste (links) -->
      <v-col cols="3" class="pr-2 editor-col">
        <div class="scroll-column">
          <EditorEntityList title="Elements" add-button-text="New Element" :items="elements" :selected-index="selectedElementIndex" empty-text="No Elements defined" title-field="type" subtitle-field="defaultLabel" icon-field="renderMode" color-field="renderMode" :icon-map="elementIconMap" :color-map="elementColorMap" @add="addNewElement" @select="selectElement" @delete="deleteElement" />
        </div>
      </v-col>

      <!-- Element-Editor (mitte) -->
      <v-col cols="5" class="px-1 editor-col">
        <div class="scroll-column">
          <BasicEditorForm type="element" :selected-item="selectedElement">
            <ElementPropertiesEditor v-if="selectedElement" :element="selectedElement" @update="updateAll" />
          </BasicEditorForm>
        </div>
      </v-col>

      <!-- Canvas Vorschau (rechts) -->
      <v-col cols="4" class="pl-2 preview-column">
        <v-card class="preview-card">
          <v-card-title class="py-2">
            <span class="text-h6">Preview</span>
          </v-card-title>

          <v-divider />

          <v-card-text>
            <div class="preview-canvas">
              <DrawingCanvas ref="drawingCanvasRef" :show-elements="false" :model="canvasModel" :language-elements="languageElementsForCanvas" :language-connections="languageConnectionsForCanvas" :language-syntax="languageSyntaxForCanvas" />
            </div>

            <v-alert v-if="!selectedElement" type="info" variant="tonal" class="mt-3"> Select an Element to see a preview </v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import { Shape, AbstractCanvas2D } from '@maxgraph/core'
import { createCellFromElement, addCellToGraph } from '@/utils/elementFactory'
import { ShapeRegistry } from '@maxgraph/core'
import type { GraphDataModel } from '@maxgraph/core'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { DiagramElement, ChildElement } from '@/model/Element'
import EditorEntityList from './EditorEntityList.vue'
import BasicEditorForm from '../form/BasicEditorForm.vue'
import ElementPropertiesEditor from '../form/ElementPropertiesEditor.vue'

// Props
const store = useDiagramLanguages()

// State
const selectedElementIndex = ref<number>(-1)
const canvasModel = ref<GraphDataModel>()
const drawingCanvasRef = ref()

// Zusätzliche Refs für Canvas-Integration
const elementDefinition = ref<DiagramElement | null>(null)

// Computed
const elements = computed(() => store.definition?.elements || [])

const languageElementsForCanvas = computed(() => store.definition?.elements ?? [])
const languageConnectionsForCanvas = computed(() => store.definition?.connections ?? [])
const languageSyntaxForCanvas = computed(() => store.definition?.syntax ?? [])

const selectedElement = computed(() => elements.value[selectedElementIndex.value])

// Methods
const selectElement = (elementIndex: number) => {
  selectedElementIndex.value = elementIndex
  // Kleine Verzögerung für UI-Update
  nextTick(() => {
    setTimeout(() => renderElementPreview(), 50)
  })
}

const addNewElement = () => {
  if (!store.definition) return

  const newElement: DiagramElement = {
    type: `element_${Date.now()}`,
    defaultLabel: 'New Element',
    renderMode: 'canvas2d',
    x: 50,
    y: 50,
    width: 100,
    height: 60,
    canvas: 'RECT 0 0 1 1',
    style: {
      strokeColor: '#000000',
      fillColor: '#ffffff',
      strokeWidth: 2,
      fontSize: 12,
      fontColor: '#000000',
      fontFamily: 'Arial',
      align: 'center',
      verticalAlign: 'middle'
    },
    anchorPoints: [
      { x: 0.5, y: 0 },
      { x: 1, y: 0.5 },
      { x: 0.5, y: 1 },
      { x: 0, y: 0.5 }
    ],
    children: [],
    connectable: true,
    resizable: true,
    movable: true
  }

  store.addElementToLanguage(newElement)
  selectedElementIndex.value = elements.value.length - 1
}

const deleteElement = (elementIndex: number) => {
  if (!store.definition) return

  const element = elements.value[elementIndex]
  store.removeElementFromLanguage(element.type)

  // Auswahl zurücksetzen
  selectedElementIndex.value = -1
  elementDefinition.value = null

  // Canvas leeren
  if (drawingCanvasRef.value) {
    drawingCanvasRef.value.clearCanvas()
  }
}

// Icon und Color Maps für EntityList
const elementIconMap = {
  canvas2d: 'mdi-draw',
  predefined: 'mdi-shape',
  swimlane: 'mdi-view-column'
}

const elementColorMap = {
  canvas2d: 'indigo',
  predefined: 'cyan',
  swimlane: 'deep-purple'
}

/**
 * Rendert die Element-Vorschau im Canvas
 * Zentrale Funktion - wird sowohl beim initialen Laden als auch bei Updates verwendet
 */
const renderElementPreview = () => {
  const element = elementDefinition.value || selectedElement.value

  if (!element) return

  if (!drawingCanvasRef.value?.graph) {
    console.warn('⚠️ Canvas or graph is not available yet')
    return
  }

  const graph = drawingCanvasRef.value.graph
  const parent = graph.getDefaultParent()

  if (!parent) {
    console.warn('⚠️ No default parent available')
    return
  }

  try {
    // Canvas leeren
    drawingCanvasRef.value.clearCanvas()

    // Element mit zentraler Methode erstellen und hinzufügen
    graph.batchUpdate(() => {
      const createdCell = createCellFromElement(element, 50, 50)
      addCellToGraph(graph, createdCell, element, parent)
      graph.setSelectionCell(createdCell)
    })
  } catch (error) {
    console.error('❌ Failed to render Element preview:', error)
  }
}

/**
 * Behandelt Element-Updates und rendert die Vorschau neu
 */
const handleElementUpdate = () => {
  if (drawingCanvasRef.value?.graph) {
    registerCustomShapes()
    renderElementPreview()
  } else {
    // Canvas noch nicht bereit, versuche es erneut
    setTimeout(() => {
      handleElementUpdate()
    }, 500)
  }
}

// ALTE createElementFromDefinition Funktion wurde entfernt (ca. 180 Zeilen)!
// Die gesamte Element-Erstellung läuft jetzt über die zentrale Methode
// in elementFactory.ts (createCellFromElement + addCellToGraph).
// Dies stellt sicher, dass Toolbar und Preview identisch funktionieren.

const registerCustomShapes = (definition?: DiagramElement | ChildElement | null) => {
  const target = definition ?? elementDefinition.value
  if (!target) return

  registerShapesRecursive(target)
}

const registerShapesRecursive = (definition: DiagramElement | ChildElement | undefined) => {
  if (!definition) return

  if ('renderMode' in definition && definition.renderMode === 'canvas2d' && 'canvas' in definition && definition.canvas) {
    registerCustomShape(definition.type, definition.canvas)
  }

  if ('children' in definition && definition.children && definition.children.length > 0) {
    definition.children.forEach((child) => registerShapesRecursive(child))
  }
}

const registerCustomShape = (shapeId: string, canvasCommands: string) => {
  class DynamicCustomShape extends Shape {
    override paintBackground(c: AbstractCanvas2D, x: number, y: number, w: number, h: number) {
      c.translate(x, y)

      const lines = canvasCommands.trim().split('\n')
      let pathStarted = false

      for (const line of lines) {
        const [cmd, ...args] = line.trim().split(/\s+/)
        const nums = args.map(Number)

        if (nums.some((n) => isNaN(n))) {
          console.warn(`Invalid numbers in: ${line}`)
          continue
        }

        switch (cmd.toUpperCase()) {
          case 'MOVE':
            if (pathStarted) {
              c.stroke()
              c.end()
              pathStarted = false
            }
            c.begin()
            c.moveTo(w * nums[0], h * nums[1])
            pathStarted = true
            break

          case 'LINE':
            if (nums.length === 2) {
              c.lineTo(w * nums[0], h * nums[1])
            } else if (nums.length === 4) {
              if (pathStarted) {
                c.stroke()
                c.end()
                pathStarted = false
              }
              c.begin()
              c.moveTo(w * nums[0], h * nums[1])
              c.lineTo(w * nums[2], h * nums[3])
              c.stroke()
              c.end()
            }
            break

          case 'RECT':
            if (nums.length === 4) {
              if (pathStarted) {
                c.stroke()
                c.end()
                pathStarted = false
              }
              c.begin()
              c.rect(w * nums[0], h * nums[1], w * nums[2], h * nums[3])
              c.fillAndStroke()
              c.end()
            }
            break

          case 'ELLIPSE':
            if (nums.length === 4) {
              if (pathStarted) {
                c.stroke()
                c.end()
                pathStarted = false
              }
              c.begin()
              c.ellipse(w * nums[0], h * nums[1], w * nums[2], h * nums[3])
              c.fillAndStroke()
              c.end()
            }
            break
        }
      }

      if (pathStarted) {
        c.stroke()
        c.end()
      }
    }
  }

  ShapeRegistry.add(shapeId, DynamicCustomShape)
}

// getCustomGeometry wurde entfernt - nicht mehr benötigt.
// Anchor Points werden jetzt in elementFactory.ts als ConnectionConstraints gesetzt.

// Watchers mit Debouncing
let updateTimeout: number | null = null

const debouncedUpdate = () => {
  if (updateTimeout) {
    clearTimeout(updateTimeout)
  }
  updateTimeout = setTimeout(() => {
    renderElementPreview()
  }, 150)
}

const debouncedStoreUpdate = () => {
  if (selectedElement.value && store.definition) {
    store.updateElementInLanguage(selectedElement.value.type, selectedElement.value)
  }
}

// Combined function for both canvas and store updates
const updateAll = () => {
  debouncedUpdate()
  debouncedStoreUpdate()
}

watch(
  languageElementsForCanvas,
  (elements) => {
    elements.forEach((element) => registerCustomShapes(element))
  },
  { immediate: true, deep: true }
)

// Watch für selectedElement -> elementDefinition sync und Updates
watch(
  selectedElement,
  (newElement) => {
    if (newElement) {
      elementDefinition.value = { ...newElement }
      handleElementUpdate()
      debouncedUpdate()
    }
  },
  { immediate: true, deep: true }
)

onMounted(() => {
  // Canvas initialisieren mit mehreren Versuchen
  const initializeCanvas = (attempts = 0) => {
    if (attempts > 10) {
      console.warn('Failed to initialize canvas after 10 attempts')
      return
    }

    if (drawingCanvasRef.value?.graph) {
      // Canvas ist bereit, lade Vorschau
      handleElementUpdate()
    } else {
      // Versuche es nach kurzer Zeit erneut
      setTimeout(() => initializeCanvas(attempts + 1), 200)
    }
  }

  // Starte die Initialisierung
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
  border-radius: 4px;
  overflow: hidden;
}
</style>
