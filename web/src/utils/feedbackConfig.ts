import type { DiagramElement } from '@/model/Element'
import type { DiagramConnection } from '@/model/Connection'
import type { DiagramFeedbackConfig, FeedbackCanvasConfig, FeedbackCanvasElementConfig, FeedbackCanvasRulesConfig, FeedbackOverlayConfig, FeedbackTargetOverlays, FeedbackTargetType, FeedbackState } from '@/model/Feedback'
import { FEEDBACK_STATE_LABELS, FEEDBACK_STATES } from '@/model/Feedback'

const DEFAULT_IMAGE_SPECS: Record<FeedbackState, { src: string; width: number; height: number }> = {
  correct: { src: '/images/checkmark.gif', width: 26, height: 26 },
  incorrect: { src: '/images/error.gif', width: 26, height: 26 },
  hint: { src: '/images/warning.gif', width: 28, height: 28 }
}

const DEFAULT_ALIGNMENT: Record<FeedbackState, { align: FeedbackOverlayConfig['align']; verticalAlign: FeedbackOverlayConfig['verticalAlign'] }> = {
  correct: { align: 'left', verticalAlign: 'top' },
  incorrect: { align: 'right', verticalAlign: 'top' },
  hint: { align: 'right', verticalAlign: 'bottom' }
}

export const createDefaultFeedbackOverlay = (state: FeedbackState): FeedbackOverlayConfig => ({
  image: { ...DEFAULT_IMAGE_SPECS[state] },
  tooltip: FEEDBACK_STATE_LABELS[state],
  ...DEFAULT_ALIGNMENT[state],
  offset: { x: 0, y: 0 },
  cursor: 'pointer'
})

export const normalizeFeedbackOverlay = (state: FeedbackState, overlay?: Partial<FeedbackOverlayConfig>): FeedbackOverlayConfig => {
  if (!overlay) return createDefaultFeedbackOverlay(state)

  const base = createDefaultFeedbackOverlay(state)

  return {
    ...base,
    ...overlay,
    image: {
      ...base.image,
      ...(overlay.image ?? {})
    },
    offset: {
      x: overlay.offset?.x ?? base.offset?.x ?? 0,
      y: overlay.offset?.y ?? base.offset?.y ?? 0
    },
    tooltip: overlay.tooltip ?? base.tooltip,
    cursor: overlay.cursor ?? base.cursor,
    align: overlay.align ?? base.align,
    verticalAlign: overlay.verticalAlign ?? base.verticalAlign
  }
}

export const createDefaultTargetOverlays = (existing?: Partial<FeedbackTargetOverlays>): FeedbackTargetOverlays => {
  const result = {} as FeedbackTargetOverlays

  FEEDBACK_STATES.forEach((state) => {
    result[state] = normalizeFeedbackOverlay(state, existing?.[state])
  })

  return result
}

export const cloneFeedbackTargetOverlays = (overlays?: FeedbackTargetOverlays | null): FeedbackTargetOverlays => {
  return createDefaultTargetOverlays(overlays ?? undefined)
}

export const createDefaultFeedbackCanvasElement = (): DiagramElement => ({
  type: '__feedback_label__',
  defaultLabel: 'Feedback',
  renderMode: 'swimlane',
  predefinedShape: 'rectangle',
  x: 0,
  y: 0,
  width: 180,
  height: 72,
  style: {
    shape: 'swimlane',
    rounded: 0,
    strokeColor: '#f57c00',
    fillColor: '#fff8e1',
    strokeWidth: 1,
    fontSize: 12,
    fontColor: '#5d4037',
    fontFamily: 'Arial',
    fontStyle: 1,
    align: 'left',
    verticalAlign: 'middle',
    startSize: 28,
    horizontal: true,
    labelBackgroundColor: '#ffe0b2',
    spacingLeft: 10,
    whiteSpace: 'wrap',
    cellRole: 'feedback',
    lockToLayer: 1
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
  movable: true,
  allowLabelEdit: false
})

export const createDefaultFeedbackCanvasConnection = (): DiagramConnection => ({
  type: '__feedback_note_link__',
  label: 'Feedback Connection',
  defaultLabel: '',
  connectionType: 'feedback-note',
  connectable: false,
  style: {
    shape: 'connector',
    strokeColor: '#9e9e9e',
    strokeWidth: 1,
    strokeOpacity: 100,
    dashed: true,
    dashPattern: '4 4',
    startArrow: 'none',
    endArrow: 'none',
    startFill: true,
    endFill: true,
    align: 'center',
    verticalAlign: 'middle',
    labelPosition: 'center',
    fontColor: '#9e9e9e',
    fontSize: 9
  },
  additionalLabels: []
})

const cloneFeedbackCanvasElementConfig = (entry: FeedbackCanvasElementConfig): FeedbackCanvasElementConfig => {
  const baseElement = createDefaultFeedbackCanvasElement()
  const baseConnection = createDefaultFeedbackCanvasConnection()

  return {
    id: entry.id,
    element: {
      ...baseElement,
      ...(entry.element ?? {}),
      style: {
        ...baseElement.style,
        ...(entry.element?.style ?? {})
      },
      anchorPoints: [...(entry.element?.anchorPoints ?? baseElement.anchorPoints)],
      children: [...(entry.element?.children ?? baseElement.children)]
    },
    connection: {
      ...baseConnection,
      ...(entry.connection ?? {}),
      style: {
        ...baseConnection.style,
        ...(entry.connection?.style ?? {})
      },
      additionalLabels: (entry.connection?.additionalLabels ?? baseConnection.additionalLabels ?? []).map((label) => ({
        ...label,
        type: label.type || 'connection-label'
      }))
    }
  }
}

const createFeedbackElementEntryId = (index: number): string => `feedback-element-${index}`

export const createDefaultFeedbackCanvasElementConfig = (index = 1): FeedbackCanvasElementConfig => {
  const element = createDefaultFeedbackCanvasElement()
  const connection = createDefaultFeedbackCanvasConnection()
  const id = createFeedbackElementEntryId(index)

  element.type = `${element.type}_${index}`
  element.defaultLabel = 'Feedback'
  connection.type = `${connection.type}_${index}`
  connection.label = index === 1 ? 'Feedback Connection' : `Feedback Connection ${index}`

  return {
    id,
    element,
    connection
  }
}

export const createDefaultFeedbackCanvasRules = (): FeedbackCanvasRulesConfig => ({
  onlyFeedbackAsSource: true,
  allowTargetElements: true,
  allowTargetConnections: true,
  forbidFeedbackAsTarget: true,
  enforceDedicatedConnection: true,
  preventContainerDrop: true
})

export const createDefaultFeedbackCanvasConfig = (existing?: Partial<FeedbackCanvasConfig>): FeedbackCanvasConfig => {
  const baseRules = createDefaultFeedbackCanvasRules()
  const defaultEntry = createDefaultFeedbackCanvasElementConfig(1)

  const normalizedElements = Array.isArray(existing?.configurableElements) && existing.configurableElements.length > 0 ? existing.configurableElements.map(cloneFeedbackCanvasElementConfig) : [defaultEntry]

  const activeElementId = (() => {
    const requestedId = existing?.activeElementId
    if (requestedId && normalizedElements.some((entry) => entry.id === requestedId)) {
      return requestedId
    }
    return normalizedElements[0]?.id
  })()

  return {
    activeElementId,
    configurableElements: normalizedElements,
    rules: {
      ...baseRules,
      ...(existing?.rules ?? {})
    }
  }
}

export const cloneFeedbackCanvasConfig = (config?: FeedbackCanvasConfig | null): FeedbackCanvasConfig => {
  return createDefaultFeedbackCanvasConfig(config ?? undefined)
}

export const createEmptyFeedbackConfig = (): DiagramFeedbackConfig => ({
  elements: {},
  connections: {},
  canvas: createDefaultFeedbackCanvasConfig()
})

export const ensureFeedbackTargets = (config: DiagramFeedbackConfig, targetType: FeedbackTargetType, keys: string[]): void => {
  const container = targetType === 'element' ? (config.elements ??= {}) : (config.connections ??= {})

  keys.forEach((key) => {
    if (!container[key]) {
      container[key] = createDefaultTargetOverlays()
    }
  })

  // Nicht mehr existierende entfernen
  Object.keys(container).forEach((key) => {
    if (!keys.includes(key)) {
      delete container[key]
    }
  })
}
