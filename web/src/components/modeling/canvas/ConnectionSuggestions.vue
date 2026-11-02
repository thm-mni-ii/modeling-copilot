<template>
  <div v-if="source" class="visual-connections" @pointerdown.stop @click.stop>
    <button
      v-for="marker in pointMarkers"
      :key="marker.key"
      type="button"
      :aria-label="`Start connection at ${marker.label}`"
      :title="marker.label"
      :style="{ left: `${marker.x}px`, top: `${marker.y}px` }"
      class="connection-point"
      :class="{ 'connection-point--active': open && selectedPointKey === marker.key }"
      @pointerenter="enterPointMarker"
      @pointerleave="leavePointMarker"
      @focus="focusPointMarker"
      @blur="blurPointMarker"
      @click="openPoint(marker, $event)"
    />

    <v-menu :key="menuInstance" v-model="open" :activator="menuActivator" :close-on-content-click="false" :location="menuLocation" :offset="8" max-width="80vw">
      <v-card class="visual-picker" :class="{ 'visual-picker--choices': hasCompactChoices, 'visual-picker--horizontal': isHorizontalPoint, 'visual-picker--scrollable': !hasCompactChoices, 'visual-picker--point-map': selectedConnectionKey }" border @pointerdown.stop @click.stop @wheel.stop>
        <v-card-text :class="{ 'element-picker-content': hasCompactChoices }">
          <template v-if="!selectedTarget">
            <div v-if="availableTargets.length" class="element-picker">
              <button v-for="target in availableTargets" :key="target.element.type" type="button" class="element-choice" :aria-label="`Choose element ${target.element.defaultLabel || target.element.type}`" :title="target.element.defaultLabel || target.element.type" @click="selectTarget(target.element.type)">
                <DiagramPreviewItem :element="target.element" :width="80" :height="60" class="choice-preview" aria-hidden="true" />
                <span class="element-choice__label">{{ target.element.defaultLabel || target.element.type }}</span>
              </button>
            </div>
            <v-alert v-else type="info" variant="tonal" density="compact">No element can be connected here. Check the connection rules, point roles and occupied limits.</v-alert>
          </template>
          <template v-else-if="!selectedConnectionKey">
            <div v-if="lineChoices.length" class="element-picker">
              <button v-for="choice in lineChoices" :key="choice.key" type="button" class="element-choice" :aria-label="`Choose ${choice.connection.defaultLabel || choice.connection.type}, ${choice.outgoing ? 'from' : 'to'} this element`" :title="choice.connection.defaultLabel || choice.connection.type" @click="selectConnection(choice)">
                <ConnectionPreviewItem :connection="previewConnection(choice)" :width="80" :height="60" class="choice-preview" aria-hidden="true" />
                <span class="element-choice__label">{{ choice.connection.defaultLabel || choice.connection.type }}</span>
              </button>
            </div>
            <v-alert v-else type="info" variant="tonal" density="compact">No available connections for this element.</v-alert>
          </template>
          <template v-else>
            <div v-if="targetPointChoices.length && selectedTarget" class="target-point-map">
              <p class="target-point-map__prompt">Choose a point</p>
              <ConnectionPointMap
                :element="selectedTarget.element"
                :markers="targetPointMarkers"
                :aria-label="`${selectedTarget.element.defaultLabel || selectedTarget.element.type} connection points`"
                :width="100"
                :height="74"
                class="target-point-map__svg"
                @select="connectTargetPoint"
              />
            </div>
            <v-alert v-else type="info" variant="tonal" density="compact">No available target points.</v-alert>
          </template>
          <v-alert v-if="error" type="warning" variant="tonal" density="compact" class="mt-3">{{ error }}</v-alert>
        </v-card-text>
      </v-card>
    </v-menu>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { ConnectionConstraint, InternalEvent, Point, type Cell, type Graph, type MouseListenerSet } from '@maxgraph/core'
import type { DiagramElement, AnchorPoint } from '@/model/Element'
import type { DiagramConnection } from '@/model/Connection'
import type { DiagramSyntax } from '@/model/Syntax'
import { addCellToGraph, createCellFromElement, createConnectionStyle } from '@/utils/elementFactory'
import { availablePoints, elementTypeOf, endpointStyle, pointId, pointLabel } from '@/utils/connectionPoints'
import { isValidationPassActive, setValidationPassActive } from '@/utils/graphValidationRuntime'
import { buildContainmentFromSyntax, canContain } from '@/utils/containment'
import { applyConnectionAdditionalLabels, applyConnectionLabelOffset } from '@/utils/connectionLabelHelpers'
import ConnectionPointMap from '@/components/modeling/ConnectionPointMap.vue'
import DiagramPreviewItem from './DiagramPreviewItem.vue'
import ConnectionPreviewItem from './ConnectionPreviewItem.vue'

type Direction = 'up' | 'right' | 'down' | 'left'
interface PointMarker {
  key: string
  direction: Direction
  point: AnchorPoint | null
  label: string
  x: number
  y: number
}
interface Target {
  element: DiagramElement
  cell: Cell
  shiftX: number
  shiftY: number
}
interface Candidate {
  key: string
  connection: DiagramConnection
  edge: Cell
  source: Cell
  target: Cell
  fromPoint: AnchorPoint | null
  toPoint: AnchorPoint | null
  outgoing: boolean
  score: number
}

const props = defineProps<{ graph: Graph; elements: DiagramElement[]; connections: DiagramConnection[]; syntax: DiagramSyntax[] }>()
const source = shallowRef<Cell | null>(null)
const open = ref(false)
const revision = ref(0)
const menuInstance = ref(0)
const menuActivator = shallowRef<HTMLElement>()
const selectedDirection = ref<Direction>('right')
const selectedStartPoint = shallowRef<AnchorPoint | null>(null)
const selectedPointKey = ref<string | null>(null)
const selectedConnectionKey = ref<string | null>(null)
const targetKey = ref<string | null>(null)
const error = ref('')
const isHorizontalPoint = computed(() => selectedDirection.value === 'up' || selectedDirection.value === 'down')
const menuLocation = computed(() => ({
  up: 'top center',
  right: 'end center',
  down: 'bottom center',
  left: 'start center'
} as const)[selectedDirection.value])
const pointMarkerHovered = ref(false)
const pointMarkerFocused = ref(false)
let clearTimer: ReturnType<typeof setTimeout> | undefined
const definitionOf = (cell: Cell) => props.elements.find((e) => e.type === elementTypeOf(cell))
const cancelClear = () => {
  clearTimeout(clearTimer)
  clearTimer = undefined
}
const enterPointMarker = () => {
  pointMarkerHovered.value = true
  cancelClear()
}
const leavePointMarker = () => {
  pointMarkerHovered.value = false
  scheduleClear()
}
const focusPointMarker = () => {
  pointMarkerFocused.value = true
  cancelClear()
}
const blurPointMarker = () => {
  pointMarkerFocused.value = false
  scheduleClear()
}
const close = () => {
  open.value = false
  targetKey.value = null
  selectedConnectionKey.value = null
  error.value = ''
}
const scheduleClear = () => {
  cancelClear()
  if (!open.value && !pointMarkerHovered.value && !pointMarkerFocused.value)
    clearTimer = setTimeout(() => {
      source.value = null
    }, 500)
}
watch(open, (value) => {
  if (!value) {
    targetKey.value = null
    selectedConnectionKey.value = null
    scheduleClear()
  }
})

const directions: { direction: Direction; x: number; y: number }[] = [
  { direction: 'up', x: 0.5, y: 0 },
  { direction: 'right', x: 1, y: 0.5 },
  { direction: 'down', x: 0.5, y: 1 },
  { direction: 'left', x: 0, y: 0.5 }
]

const pointMarkers = computed<PointMarker[]>(() => {
  void revision.value
  const cell = source.value
  const definition = cell && definitionOf(cell)
  const state = cell && props.graph.view.getState(cell)
  if (!cell || !definition || !state || !props.graph.isEnabled()) return []
  const markers: PointMarker[] = []
  for (const point of availablePoints(definition)) {
    const pointDirections = point ? [null] : directions
    for (const side of pointDirections) {
      const directionPoint = side ?? directions[0]!
      const constraint = point
        ? new ConnectionConstraint(new Point(point.x, point.y), false, pointId(point))
        : new ConnectionConstraint(new Point(directionPoint.x, directionPoint.y), true)
      const position = props.graph.getConnectionPoint(state, constraint)
      if (!position) continue
      const offsetDx = position.x - state.getCenterX()
      const offsetDy = position.y - state.getCenterY()
      const offsetLength = Math.hypot(offsetDx, offsetDy)
      const offsetX = offsetLength ? offsetDx / offsetLength * 20 : 20
      const offsetY = offsetLength ? offsetDy / offsetLength * 20 : 0
      const dx = offsetDx / Math.max(state.width / 2, 1)
      const dy = offsetDy / Math.max(state.height / 2, 1)
      const direction = side?.direction ?? (Math.abs(dx) >= Math.abs(dy) ? (dx < 0 ? 'left' : 'right') : (dy < 0 ? 'up' : 'down'))
      const markerKey = point ? pointId(point) : `outline-${direction}`
      markers.push({
        key: markerKey,
        direction,
        point,
        label: point ? pointLabel(point) : `Outline (${direction})`,
        x: position.x + props.graph.panDx + offsetX - props.graph.container.scrollLeft,
        y: position.y + props.graph.panDy + offsetY - props.graph.container.scrollTop
      })
    }
  }
  return markers
})
const openPoint = (marker: PointMarker, event: MouseEvent) => {
  cancelClear()
  menuInstance.value++
  menuActivator.value = event.currentTarget as HTMLElement
  selectedDirection.value = marker.direction
  selectedStartPoint.value = marker.point
  selectedPointKey.value = marker.key
  targetKey.value = null
  selectedConnectionKey.value = null
  error.value = ''
  open.value = true
}

const targets = computed<Target[]>(() => {
  void revision.value
  const cell = source.value
  const geometry = cell?.getGeometry()
  if (!open.value || !cell || !geometry || !selectedPointKey.value) return []
  const parent = cell.getParent() ?? props.graph.getDefaultParent()
  const containment = buildContainmentFromSyntax(props.syntax)
  const siblings = parent
    .getChildren()
    .filter((c) => c.isVertex())
    .flatMap((c) => (c.getGeometry() ? [c.getGeometry()!] : []))
  return props.elements
    .filter((e) => e.connectable)
    .flatMap((element) => {
      const direction = selectedDirection.value
      const width = element.width ?? 120,
        height = element.height ?? 80
      let x = geometry.x + (geometry.width - width) / 2
      let y = geometry.y + (geometry.height - height) / 2
      if (direction === 'right') x = geometry.x + geometry.width + 60
      if (direction === 'left') x = geometry.x - width - 60
      if (direction === 'down') y = geometry.y + geometry.height + 60
      if (direction === 'up') y = geometry.y - height - 60
      let obstacle = siblings.find((g) => x < g.x + g.width + 20 && x + width + 20 > g.x && y < g.y + g.height + 20 && y + height + 20 > g.y)
      while (obstacle) {
        if (direction === 'right') x = obstacle.x + obstacle.width + 60
        if (direction === 'left') x = obstacle.x - width - 60
        if (direction === 'down') y = obstacle.y + obstacle.height + 60
        if (direction === 'up') y = obstacle.y - height - 60
        obstacle = siblings.find((g) => x < g.x + g.width + 20 && x + width + 20 > g.x && y < g.y + g.height + 20 && y + height + 20 > g.y)
      }
      const target = markRaw(createCellFromElement(element, x, y))
      return canContain(containment, parent, [target]) ? [{ element, cell: target, shiftX: Math.max(0, 20 - x), shiftY: Math.max(0, 20 - y) }] : []
    })
})

const validate = (candidate: Candidate): string | null => {
  const active = isValidationPassActive(props.graph)
  setValidationPassActive(props.graph, true)
  try {
    return props.graph.getEdgeValidationError(candidate.edge, candidate.source, candidate.target)
  } finally {
    setValidationPassActive(props.graph, active)
  }
}
const pointScore = (point: AnchorPoint | null, direction: Direction, opposite = false) => {
  if (!point) return 0
  const side = directions.find((d) => d.direction === direction)!
  const x = opposite ? 1 - side.x : side.x,
    y = opposite ? 1 - side.y : side.y
  return (point.x - x) ** 2 + (point.y - y) ** 2
}
const candidatesFor = (target: Target, firstOnly = false): Candidate[] => {
  const start = source.value
  if (!start || !selectedPointKey.value) return []
  const candidates: Candidate[] = []
  for (const connection of props.connections) {
    for (const outgoing of connection.undirected ? [true] : [true, false]) {
      for (const otherPoint of availablePoints(target.element)) {
        const from = outgoing ? start : target.cell,
          to = outgoing ? target.cell : start
        const fromPoint = outgoing ? selectedStartPoint.value : otherPoint,
          toPoint = outgoing ? otherPoint : selectedStartPoint.value
        const edge = props.graph.createEdge(null, '', connection.defaultLabel ?? '', from, to, { ...createConnectionStyle(connection), ...endpointStyle(fromPoint, true), ...endpointStyle(toPoint, false) })
        edge.setTerminal(from, true)
        edge.setTerminal(to, false)
        Object.assign(edge, { connectionId: connection.type, connectionUndirected: connection.undirected === true })
        const candidate = { key: JSON.stringify([connection.type, outgoing]), connection, edge, source: from, target: to, fromPoint, toPoint, outgoing, score: pointScore(selectedStartPoint.value, selectedDirection.value) + pointScore(otherPoint, selectedDirection.value, true) }
        if (validate(candidate) === null) {
          candidates.push(candidate)
          if (firstOnly) return candidates
        }
      }
    }
  }
  return candidates.sort((a, b) => a.score - b.score)
}
const availableTargets = computed(() => targets.value.filter((target) => candidatesFor(target, true).length))
const selectedTarget = computed(() => availableTargets.value.find((t) => t.element.type === targetKey.value))
const lineChoices = computed(() => {
  const result = new Map<string, Candidate>()
  for (const candidate of selectedTarget.value ? candidatesFor(selectedTarget.value) : []) if (!result.has(candidate.key)) result.set(candidate.key, candidate)
  return [...result.values()]
})
const targetPointOf = (candidate: Candidate) => candidate.outgoing ? candidate.toPoint : candidate.fromPoint
const targetPointKeyOf = (candidate: Candidate) => {
  const point = targetPointOf(candidate)
  return point ? pointId(point) : 'outline'
}
const targetPointLabel = (point: AnchorPoint | null) => {
  if (!point) return 'Element outline'
  if (point.name?.trim()) return point.name.trim()
  const horizontal = point.x < 0.33 ? 'left' : point.x > 0.67 ? 'right' : ''
  const vertical = point.y < 0.33 ? 'top' : point.y > 0.67 ? 'bottom' : ''
  if (vertical && horizontal) return `${vertical}-${horizontal}`
  if (vertical) return `${vertical} side`
  if (horizontal) return `${horizontal} side`
  return 'Center'
}
const targetPointChoices = computed(() => {
  const choices = new Map<string, { key: string; label: string; point: AnchorPoint | null; candidate: Candidate }>()
  for (const candidate of selectedTarget.value ? candidatesFor(selectedTarget.value) : []) {
    if (candidate.key !== selectedConnectionKey.value) continue
    const point = targetPointOf(candidate)
    const key = targetPointKeyOf(candidate)
    if (!choices.has(key)) choices.set(key, { key, label: targetPointLabel(point), point, candidate })
  }
  return [...choices.values()]
})
const targetPointMarkers = computed(() => targetPointChoices.value.map((choice) => {
  let point = choice.point
  if (!point) {
    const outlinePosition = {
      up: { x: 0.5, y: 1 },
      right: { x: 0, y: 0.5 },
      down: { x: 0.5, y: 0 },
      left: { x: 1, y: 0.5 }
    }[selectedDirection.value]
    point = { x: outlinePosition.x, y: outlinePosition.y }
  }
  return {
    id: choice.key,
    label: choice.label,
    point
  }
}))
const connectTargetPoint = (id: string) => {
  const choice = targetPointChoices.value.find((candidate) => candidate.key === id)
  if (choice) connect(choice.candidate)
}
const hasCompactChoices = computed(() => !selectedTarget.value
  ? availableTargets.value.length > 0
  : selectedConnectionKey.value
    ? targetPointChoices.value.length > 0
    : lineChoices.value.length > 0)
watch(availableTargets, (targets) => {
  if (!targets.some((t) => t.element.type === targetKey.value)) {
    targetKey.value = null
    selectedConnectionKey.value = null
  }
})
watch(lineChoices, (choices) => {
  if (selectedConnectionKey.value && !choices.some((choice) => choice.key === selectedConnectionKey.value)) selectedConnectionKey.value = null
})
const previewConnection = (choice: Candidate): DiagramConnection =>
  choice.outgoing
    ? choice.connection
    : {
        ...choice.connection,
        style: { ...choice.connection.style, startArrow: choice.connection.style.endArrow ?? 'none', endArrow: choice.connection.style.startArrow ?? 'none', startFill: choice.connection.style.endFill ?? true, endFill: choice.connection.style.startFill ?? true }
      }

const selectTarget = (key: string) => {
  targetKey.value = key
  selectedConnectionKey.value = null
  error.value = ''
}
const selectConnection = (choice: Candidate) => {
  const candidates = selectedTarget.value ? candidatesFor(selectedTarget.value).filter((candidate) => candidate.key === choice.key) : []
  const pointOptions = new Map<string, Candidate>()
  for (const candidate of candidates) if (!pointOptions.has(targetPointKeyOf(candidate))) pointOptions.set(targetPointKeyOf(candidate), candidate)
  if (pointOptions.size <= 1) {
    const [candidate] = pointOptions.values()
    if (candidate) connect(candidate)
    return
  }
  selectedConnectionKey.value = choice.key
  error.value = ''
}

const connect = (candidate: Candidate) => {
  const target = selectedTarget.value
  const start = source.value
  if (!target || !start) return
  const warning = validate(candidate)
  if (warning !== null) {
    error.value = warning || 'This connection is no longer allowed.'
    revision.value++
    return
  }
  const parent = start.getParent() ?? props.graph.getDefaultParent()
  props.graph.batchUpdate(() => {
    // Make room at the top/left boundary while preserving all existing relative positions.
    if (target.shiftX || target.shiftY) {
      props.graph.moveCells(parent.getChildren(), target.shiftX, target.shiftY)
      const geometry = target.cell.getGeometry()!.clone()
      geometry.x += target.shiftX
      geometry.y += target.shiftY
      target.cell.setGeometry(geometry)
    }
    addCellToGraph(props.graph, target.cell, target.element, parent)
    props.graph.addCell(candidate.edge, parent, undefined, candidate.source, candidate.target)
    candidate.edge.setConnectable(candidate.connection.connectable !== false)
    Object.assign(candidate.edge, { connectionLabelOffset: candidate.connection.labelOffset })
    applyConnectionLabelOffset(candidate.edge, candidate.connection.labelOffset)
    applyConnectionAdditionalLabels(props.graph, candidate.edge, candidate.connection)
  })
  close()
  source.value = null
  props.graph.setSelectionCell(target.cell)
  props.graph.scrollCellToVisible(target.cell)
}

const hoverCell = (cell: Cell | null): Cell | null => {
  while (cell && !definitionOf(cell)) cell = cell.getParent()
  return cell?.isVertex() && cell.isConnectable() && cell.isVisible() && (cell as any).cellRole !== 'feedback' ? cell : null
}
const mouseListener: MouseListenerSet = {
  mouseDown() {
    cancelClear()
    close()
    source.value = null
  },
  mouseMove(_sender, event) {
    if (props.graph.isMouseDown || !props.graph.isEnabled()) {
      if (!open.value) source.value = null
      return
    }
    if (open.value) return
    const cell = hoverCell(event.getCell())
    if (cell) {
      cancelClear()
      source.value = markRaw(cell)
    } else scheduleClear()
  },
  mouseUp() {}
}
let detach = () => {}
watch(
  () => props.graph,
  (graph) => {
    detach()
    cancelClear()
    close()
    source.value = null
    const update = () => {
      revision.value++
      if (source.value && !graph.getDataModel().contains(source.value)) {
        close()
        source.value = null
      }
    }
    const observer = new ResizeObserver(update)
    observer.observe(graph.container)
    graph.addMouseListener(mouseListener)
    graph.getDataModel().addListener(InternalEvent.CHANGE, update)
    for (const event of [InternalEvent.SCALE, InternalEvent.TRANSLATE, InternalEvent.SCALE_AND_TRANSLATE]) graph.view.addListener(event, update)
    graph.addListener(InternalEvent.PAN, update)
    graph.container.addEventListener('mouseleave', scheduleClear)
    graph.container.addEventListener('scroll', update)
    detach = () => {
      observer.disconnect()
      graph.removeMouseListener(mouseListener)
      graph.getDataModel().removeListener(update)
      graph.view.removeListener(update)
      graph.removeListener(update)
      graph.container.removeEventListener('mouseleave', scheduleClear)
      graph.container.removeEventListener('scroll', update)
    }
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  detach()
  cancelClear()
})
</script>

<style scoped>
.visual-connections {
  position: absolute;
  inset: 0;
  z-index: 5;
  pointer-events: none;
}
.connection-point {
  position: absolute;
  transform: translate(-50%, -50%);
  pointer-events: auto;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  transition: opacity 100ms ease, transform 100ms ease, background-color 100ms ease;
}
.connection-point::before {
  position: absolute;
  inset: 8px;
  border: 1px solid rgb(var(--v-theme-primary));
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.45);
  content: '';
  transition: inset 100ms ease, background-color 100ms ease, opacity 100ms ease;
}
.connection-point:hover,
.connection-point:focus-visible,
.connection-point--active {
  z-index: 1;
  transform: translate(-50%, -50%) scale(1.35);
}
.connection-point:hover::before,
.connection-point:focus-visible::before,
.connection-point--active::before {
  inset: 6px;
  background: rgb(var(--v-theme-primary));
  opacity: 1;
}
.connection-point:focus-visible {
  outline: 2px solid rgba(var(--v-theme-primary), 0.25);
  outline-offset: 2px;
}
.visual-picker {
  width: 340px;
  max-width: calc(100vw - 24px);
  max-height: min(520px, 75vh);
  overflow: hidden;
}
.visual-picker--scrollable {
  overflow-y: auto;
}
.visual-picker--choices {
  width: 112px;
  min-width: 0;
  overflow: hidden;
  border-radius: 14px;
}
.visual-picker--horizontal {
  width: max-content;
  max-width: calc(100vw - 24px);
  overflow: hidden;
}
.visual-picker--point-map {
  width: 112px;
  min-width: 0;
  max-width: calc(100vw - 24px);
  overflow: hidden;
  border-radius: 14px;
}
.visual-picker--point-map .v-card-text {
  padding: 6px;
}
.element-picker-content {
  padding: 4px !important;
}
.element-picker {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: min(520px, 75vh);
  overflow-y: auto;
}
.visual-picker--horizontal .element-picker {
  flex-direction: row;
  width: max-content;
  max-width: calc(100vw - 40px);
  overflow-x: auto;
  overflow-y: hidden;
}
.element-choice {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex: 0 0 100px;
  width: 100px;
  height: 100px;
  padding: 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}
.element-choice__label {
  max-width: 100%;
  overflow: hidden;
  color: rgb(var(--v-theme-on-surface));
  font-size: 11px;
  line-height: 14px;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.element-choice:hover,
.element-choice:focus-visible {
  background: rgba(var(--v-theme-primary), 0.1);
  outline: 1px solid rgba(var(--v-theme-primary), 0.45);
}
.choice-preview {
  pointer-events: none;
  max-width: 100%;
  border: 0;
  background: transparent;
}
.target-point-map__prompt {
  margin: 0 0 4px;
  color: rgba(var(--v-theme-on-surface), 0.75);
  font-size: 10px;
  line-height: 12px;
  text-align: center;
}
.target-point-map__svg {
  margin: 0 auto;
}
</style>
