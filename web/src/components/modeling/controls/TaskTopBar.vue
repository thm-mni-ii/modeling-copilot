<template>
  <transition name="task-topbar-slide">
    <div v-if="task" class="task-topbar">
      <!-- Header – immer sichtbar -->
      <div class="task-topbar__header">
        <button type="button" class="task-topbar__toggle" :title="expanded ? 'Collapse' : 'Show task'" @click="expanded = !expanded">
          <v-icon size="15" color="primary">mdi-clipboard-text-outline</v-icon>
          <span class="task-topbar__task-title">{{ task.title }}</span>
          <v-icon size="16" class="task-topbar__chevron" :class="{ 'task-topbar__chevron--open': expanded }">mdi-chevron-down</v-icon>
        </button>

        <div class="task-topbar__header-actions">
          <v-chip v-if="windowOpen" size="x-small" color="primary" variant="tonal" class="task-topbar__window-chip">
            <v-icon start size="12">mdi-open-in-new</v-icon>
            Open in window
          </v-chip>
          <v-btn v-if="!windowOpen" size="x-small" variant="text" density="compact" title="Highlight mode" class="task-topbar__action-btn" :color="markMode ? 'primary' : undefined" @click="markMode = !markMode">
            <v-icon size="15">mdi-marker</v-icon>
          </v-btn>
          <v-btn v-if="!windowOpen" size="x-small" variant="text" density="compact" title="Open as a free-floating window" class="task-topbar__action-btn" @click="emit('pop-out')">
            <v-icon size="15">mdi-open-in-new</v-icon>
          </v-btn>
        </div>
      </div>

      <!-- Body – nur wenn expanded und kein Fenster offen -->
      <transition name="task-topbar-body">
        <div v-if="expanded" class="task-topbar__body" :style="bodyStyle">
          <div v-if="windowOpen" class="task-topbar__window-hint">
            <v-icon size="16" color="primary">mdi-open-in-new</v-icon>
            The task text is open in a window. Close the window to display it here.
          </div>
          <TaskRichEditor v-else :model-value="contentHtml" :readonly="!markMode" class="task-topbar__editor" :style="editorStyle" @update:model-value="onContentUpdated" />

          <div class="task-topbar__resize-handle" title="Adjust height" @mousedown.prevent="startResize">
            <v-icon size="12">mdi-drag-horizontal</v-icon>
          </div>
        </div>
      </transition>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import TaskRichEditor from '@/components/tasks/TaskRichEditor.vue'
import type { DiagramTask } from '@/model/Task'

const props = defineProps<{
  task: DiagramTask | null
  windowOpen: boolean
  contentHtml: string
}>()

const emit = defineEmits<{
  'pop-out': []
  'update:contentHtml': [string]
}>()

const expanded = ref(true)
const markMode = ref(false)
const DEFAULT_HEIGHT = 220
const MIN_HEIGHT = 120
const MAX_HEIGHT = 420
const topbarHeight = ref(DEFAULT_HEIGHT)

const bodyStyle = computed(() => ({
  height: `${topbarHeight.value}px`,
  maxHeight: `${topbarHeight.value}px`
}))

const editorStyle = computed(() => ({
  height: `${topbarHeight.value - 8}px`,
  maxHeight: `${topbarHeight.value - 8}px`
}))

const startResize = (event: MouseEvent) => {
  const startY = event.clientY
  const startHeight = topbarHeight.value

  const onMove = (moveEvent: MouseEvent) => {
    const delta = moveEvent.clientY - startY
    topbarHeight.value = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, startHeight + delta))
  }

  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

// Automatisch ausklappen wenn eine neue Aufgabe gesetzt wird
watch(
  () => props.task?.id,
  () => {
    if (props.task) {
      expanded.value = true
      markMode.value = false
    }
  }
)

watch(
  () => props.windowOpen,
  (isOpen) => {
    if (isOpen) {
      expanded.value = false
      return
    }

    if (props.task) {
      expanded.value = true
    }
  }
)

const onContentUpdated = (value: string) => {
  emit('update:contentHtml', value)
}
</script>

<style scoped>
.task-topbar {
  border: 1px solid rgba(var(--v-theme-primary), 0.22);
  border-radius: 6px;
  background: #fafafa;
  margin-bottom: 6px;
  overflow: hidden;
  flex-shrink: 0;
}

.task-topbar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 8px 5px 10px;
  background: rgba(var(--v-theme-primary), 0.05);
  border-bottom: 1px solid rgba(var(--v-theme-primary), 0.12);
  min-height: 34px;
}

.task-topbar__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  color: rgba(var(--v-theme-on-surface), 0.85);
  flex: 1;
  min-width: 0;
  text-align: left;
}

.task-topbar__toggle:hover .task-topbar__task-title {
  color: rgba(var(--v-theme-primary), 1);
}

.task-topbar__task-title {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.task-topbar__chevron {
  transition: transform 0.2s ease;
  flex-shrink: 0;
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.task-topbar__chevron--open {
  transform: rotate(180deg);
}

.task-topbar__header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.task-topbar__action-btn {
  opacity: 0.6;
  transition: opacity 0.13s;
}

.task-topbar__action-btn:hover {
  opacity: 1;
}

.task-topbar__window-chip {
  font-size: 11px;
}

.task-topbar__body {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.task-topbar__editor {
  border: none !important;
  border-radius: 0 !important;
  min-height: 0;
}

.task-topbar__resize-handle {
  width: 100%;
  height: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: row-resize;
  color: rgba(var(--v-theme-on-surface), 0.25);
  border-top: 1px solid rgba(var(--v-theme-outline), 0.12);
  background: rgba(var(--v-theme-on-surface), 0.02);
  transition:
    background 0.15s,
    color 0.15s;
}

.task-topbar__resize-handle:hover {
  background: rgba(var(--v-theme-primary), 0.1);
  color: rgba(var(--v-theme-primary), 0.7);
}

.task-topbar__window-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-style: italic;
}

/* Transitions */
.task-topbar-slide-enter-active,
.task-topbar-slide-leave-active {
  transition: opacity 0.2s ease;
}

.task-topbar-slide-enter-from,
.task-topbar-slide-leave-to {
  opacity: 0;
}

.task-topbar-body-enter-active,
.task-topbar-body-leave-active {
  transition:
    max-height 0.22s ease,
    opacity 0.18s ease;
}

.task-topbar-body-enter-from,
.task-topbar-body-leave-to {
  max-height: 0;
  opacity: 0;
}

.task-topbar-body-enter-to,
.task-topbar-body-leave-from {
  max-height: 420px;
  opacity: 1;
}
</style>
