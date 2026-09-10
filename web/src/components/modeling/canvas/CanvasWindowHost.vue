<template>
  <div class="canvas-window-host">
    <Teleport v-for="entry in windowEntries" :key="entry.definition.id" :to="`#${entry.contentTargetId}`" :disabled="!entry.isMounted">
      <slot name="window-content" :window="entry" :definition="entry.definition">
        <div class="window-placeholder-content">{{ entry.definition.placeholder ?? 'Window content' }}</div>
      </slot>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { InternalEvent, MaxWindow } from '@maxgraph/core'
import { onBeforeUnmount, ref, watch } from 'vue'
import type { CanvasWindowBehavior, CanvasWindowDefinition, CanvasWindowPatch } from '@/model/CanvasWindow'

interface CanvasWindowEntry {
  definition: CanvasWindowDefinition
  contentTargetId: string
  isMounted: boolean
}

interface CanvasWindowRuntime {
  window: MaxWindow
}

const props = defineProps<{
  graphContainer?: HTMLElement | null
  windows?: CanvasWindowDefinition[]
}>()

const emit = defineEmits<{
  'window-created': [CanvasWindowDefinition]
  'window-removed': [string]
}>()

const windowEntries = ref<CanvasWindowEntry[]>([])
const runtimes = new Map<string, CanvasWindowRuntime>()

const sanitizeWindowId = (id: string) => id.replace(/[^a-zA-Z0-9_-]/g, '_')
const contentTargetFor = (id: string) => `canvas-window-content-${sanitizeWindowId(id)}`

const normalizeBehavior = (behavior?: CanvasWindowBehavior): Required<CanvasWindowBehavior> => ({
  visible: behavior?.visible ?? true,
  resizable: behavior?.resizable ?? true,
  maximizable: behavior?.maximizable ?? true,
  closable: behavior?.closable ?? true,
  scrollable: behavior?.scrollable ?? true
})

const normalizeWindowDefinition = (definition: CanvasWindowDefinition): CanvasWindowDefinition => ({
  ...definition,
  behavior: normalizeBehavior(definition.behavior)
})

const findEntryIndex = (id: string) => windowEntries.value.findIndex((entry) => entry.definition.id === id)

const mountWindow = (entry: CanvasWindowEntry) => {
  if (!props.graphContainer || runtimes.has(entry.definition.id)) {
    return
  }

  const behavior = normalizeBehavior(entry.definition.behavior)
  const contentRoot = document.createElement('div')
  contentRoot.id = entry.contentTargetId
  contentRoot.className = 'canvas-window-content-root'
  contentRoot.style.width = '100%'
  contentRoot.style.height = '100%'

  const wnd = new MaxWindow(entry.definition.title, contentRoot, entry.definition.x, entry.definition.y, entry.definition.width, entry.definition.height ?? null, true, true)

  wnd.setMaximizable(behavior.maximizable)
  wnd.setScrollable(behavior.scrollable)
  wnd.setResizable(behavior.resizable)
  wnd.setClosable(behavior.closable)
  wnd.setVisible(behavior.visible)
  ;(wnd as any).addListener?.(InternalEvent.CLOSE, () => {
    removeWindow(entry.definition.id)
  })

  runtimes.set(entry.definition.id, { window: wnd })
  entry.isMounted = true
  emit('window-created', entry.definition)
}

const unmountWindow = (id: string) => {
  const runtime = runtimes.get(id)
  if (!runtime) {
    return
  }

  runtime.window.destroy()
  runtimes.delete(id)

  const index = findEntryIndex(id)
  if (index >= 0) {
    windowEntries.value[index].isMounted = false
  }
}

const recreateWindow = (id: string) => {
  const entry = windowEntries.value.find((item) => item.definition.id === id)
  if (!entry) {
    return
  }

  unmountWindow(id)
  mountWindow(entry)
}

const addWindow = (definition: CanvasWindowDefinition) => {
  const normalized = normalizeWindowDefinition(definition)
  const existingIndex = findEntryIndex(normalized.id)

  if (existingIndex >= 0) {
    windowEntries.value[existingIndex].definition = normalized
    recreateWindow(normalized.id)
    return
  }

  const entry: CanvasWindowEntry = {
    definition: normalized,
    contentTargetId: contentTargetFor(normalized.id),
    isMounted: false
  }

  windowEntries.value = [...windowEntries.value, entry]
  mountWindow(entry)
}

const updateWindow = (patch: CanvasWindowPatch) => {
  const index = findEntryIndex(patch.id)
  if (index < 0) {
    return
  }

  const nextDefinition = normalizeWindowDefinition({
    ...windowEntries.value[index].definition,
    ...patch,
    behavior: {
      ...windowEntries.value[index].definition.behavior,
      ...patch.behavior
    }
  })

  windowEntries.value[index].definition = nextDefinition
  recreateWindow(patch.id)
}

const removeWindow = (id: string) => {
  unmountWindow(id)
  windowEntries.value = windowEntries.value.filter((entry) => entry.definition.id !== id)
  emit('window-removed', id)
}

const clearWindows = () => {
  const ids = windowEntries.value.map((entry) => entry.definition.id)
  ids.forEach((id) => unmountWindow(id))
  windowEntries.value = []
}

const setWindows = (definitions: CanvasWindowDefinition[]) => {
  const incomingIds = new Set(definitions.map((item) => item.id))

  windowEntries.value.filter((entry) => !incomingIds.has(entry.definition.id)).forEach((entry) => removeWindow(entry.definition.id))

  definitions.forEach((definition) => {
    if (findEntryIndex(definition.id) >= 0) {
      updateWindow(definition)
    } else {
      addWindow(definition)
    }
  })
}

watch(
  () => props.graphContainer,
  (container) => {
    if (!container) {
      return
    }

    windowEntries.value.forEach((entry) => {
      if (!entry.isMounted) {
        mountWindow(entry)
      }
    })
  },
  { immediate: true }
)

watch(
  () => props.windows,
  (definitions) => {
    if (!definitions) {
      return
    }
    setWindows(definitions)
  },
  { deep: true, immediate: true }
)

onBeforeUnmount(() => {
  clearWindows()
})

defineExpose({
  addWindow,
  updateWindow,
  removeWindow,
  clearWindows,
  setWindows,
  windows: windowEntries
})
</script>

<style scoped>
.canvas-window-host {
  display: contents;
}

.window-placeholder-content {
  padding: 8px;
  color: #424242;
  font-size: 13px;
  line-height: 1.4;
}

:global(.canvas-window-content-root) {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}
</style>
