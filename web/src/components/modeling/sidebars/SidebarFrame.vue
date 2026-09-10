<template>
  <aside class="sidebar-frame" :class="[`sidebar-frame--${side}`, { 'sidebar-frame--collapsed': collapsed }]" :style="{ width: displayedWidth + 'px', minWidth: displayedWidth + 'px' }">
    <div v-if="!collapsed && showTabs && $slots.tabs" class="sidebar-frame__tabs">
      <slot name="tabs" />
    </div>
    <div v-if="!collapsed" class="sidebar-frame__body">
      <slot :width="width" />
    </div>
    <div v-if="!collapsed" class="sidebar-frame__resize" title="Adjust width" @mousedown.prevent="startResize">
      <v-icon size="12">mdi-drag-vertical</v-icon>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    width: number
    side: 'left' | 'right'
    collapsed?: boolean
    showTabs?: boolean
    collapsedWidth?: number
    minWidth?: number
    maxWidth?: number
  }>(),
  {
    collapsed: false,
    showTabs: true,
    collapsedWidth: 36,
    minWidth: 105,
    maxWidth: 315
  }
)

const emit = defineEmits<{
  'update:width': [value: number]
}>()

const displayedWidth = computed(() => (props.collapsed ? props.collapsedWidth : props.width))

const startResize = (event: MouseEvent) => {
  const startX = event.clientX
  const startWidth = props.width

  const onMove = (moveEvent: MouseEvent) => {
    const rawDelta = moveEvent.clientX - startX
    const delta = props.side === 'left' ? rawDelta : -rawDelta
    emit('update:width', Math.min(props.maxWidth, Math.max(props.minWidth, startWidth + delta)))
  }

  const onUp = () => {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>

<style scoped>
.sidebar-frame {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  background: #ffffff;
  user-select: none;
  flex-shrink: 0;
}

.sidebar-frame--left { border-right: 1px solid rgba(var(--v-theme-outline), 0.14); }
.sidebar-frame--right { border-left: 1px solid rgba(var(--v-theme-outline), 0.14); }

.sidebar-frame__tabs {
  display: flex;
  align-items: center;
  min-height: 41px;
  padding: 8px;
  background: #ffffff;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.14);
  flex-shrink: 0;
}

.sidebar-frame__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #ffffff;
}

.sidebar-frame__resize {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 6px;
  color: rgba(var(--v-theme-on-surface), 0.2);
  cursor: col-resize;
  transition: background 0.15s, color 0.15s;
  z-index: 10;
}

.sidebar-frame--left .sidebar-frame__resize { right: 0; }
.sidebar-frame--right .sidebar-frame__resize { left: 0; }

.sidebar-frame__resize:hover {
  color: rgba(var(--v-theme-primary), 0.7);
  background: rgba(var(--v-theme-primary), 0.1);
}
</style>
