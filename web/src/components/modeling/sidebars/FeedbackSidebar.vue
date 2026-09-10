<template>
  <div class="feedback-sidebar">
    <div class="sidebar-body">
      <div class="sidebar-section">
        <SidebarPanelHeader v-if="showHeader" title="Feedback" />

        <div class="sidebar-elements">
          <div v-for="shape in normalizedShapes" :key="shape.name" class="sidebar-element" draggable="true" :title="shape.label" @dragstart="(event) => onDragStart(event, shape.name)">
            <div class="preview-chip">
              <v-icon size="14">mdi-comment-text-outline</v-icon>
              <span class="preview-chip-text">Label</span>
            </div>
            <span class="element-label">{{ shape.label }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SidebarPanelHeader from './SidebarPanelHeader.vue'

const props = withDefaults(
  defineProps<{
    showHeader?: boolean
    feedbackShapes?: Array<{
      name: string
      label: string
      style?: Record<string, any>
    }>
  }>(),
  {
    showHeader: true,
    feedbackShapes: () => []
  }
)

const normalizedShapes = computed(() => {
  if (!props.feedbackShapes || props.feedbackShapes.length === 0) {
    return [{ name: '__feedback_label__', label: 'Feedback Label' }]
  }

  return props.feedbackShapes
})

const onDragStart = (event: DragEvent, shapeName: string) => {
  if (!event.dataTransfer) return
  event.dataTransfer.setData('text/plain', shapeName)
  event.dataTransfer.effectAllowed = 'copy'
}
</script>

<style scoped>
.feedback-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: transparent;
  overflow: hidden;
  user-select: none;
}

.sidebar-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: #ffffff;
}

.sidebar-elements {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
}

.sidebar-element {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 6px 7px;
  border-radius: 7px;
  cursor: grab;
  background: #ffffff;
  border: 1px solid rgba(var(--v-theme-outline), 0.13);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition:
    box-shadow 0.13s,
    border-color 0.13s,
    background 0.13s;
}

.sidebar-element:hover {
  background: rgba(var(--v-theme-primary), 0.03);
  box-shadow: 0 2px 7px rgba(0, 0, 0, 0.1);
  border-color: rgba(var(--v-theme-primary), 0.25);
}

.sidebar-element:active {
  cursor: grabbing;
}

.preview-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #f57c00;
  border-radius: 14px;
  background: #fff3e0;
  color: #5d4037;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 600;
}

.preview-chip-text {
  line-height: 1;
}

.element-label {
  font-size: 10px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.72);
  text-align: center;
}
</style>
