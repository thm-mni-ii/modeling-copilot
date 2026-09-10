<template>
  <div class="elements-sidebar" :style="{ width: sidebarWidth + 'px', minWidth: sidebarWidth + 'px' }">
    <div class="sidebar-topbar">
      <div class="search-wrapper">
        <v-icon class="search-icon" size="13">mdi-magnify</v-icon>
        <input v-model="searchQuery" class="search-input" placeholder="Search..." />
        <button v-if="searchQuery" class="search-clear" title="Clear search" @click="searchQuery = ''">
          <v-icon size="13">mdi-close</v-icon>
        </button>
      </div>
      <div class="topbar-controls">
        <div class="view-toggles">
          <button v-for="mode in viewModes" :key="mode.value" class="view-toggle" :class="{ 'view-toggle--active': viewMode === mode.value }" :title="mode.label" @click="viewMode = mode.value">
            <v-icon size="14">{{ mode.icon }}</v-icon>
          </button>
        </div>
        <button class="view-toggle" :class="{ 'view-toggle--active': showLabels }" title="Toggle names" @click="showLabels = !showLabels">
          <v-icon size="14">mdi-label{{ showLabels ? '' : '-off' }}</v-icon>
        </button>
      </div>
    </div>

    <!-- Scroll container for all sections -->
    <div class="sidebar-body">
      <!-- Search results -->
      <template v-if="searchQuery.trim()">
        <div class="sidebar-section">
          <div class="sidebar-header sidebar-header--static">
            <span class="sidebar-title">Search Results ({{ searchResults.length }})</span>
          </div>
          <div v-if="searchResults.length > 0" class="sidebar-elements" :class="elementsClass">
            <div v-for="item in searchResults" :key="`${item.langId}-${item.element.type}`" class="sidebar-element" :class="elementClass" :style="tileCardStyle" draggable="true" :title="item.element.defaultLabel || item.element.type" @dragstart="onDragStart($event, item.element)">
              <div v-if="viewMode !== 'list'" class="preview-box">
                <DiagramPreviewItem :key="`${item.element.type}-${viewMode}-${previewW}-${previewH}`" :element="item.element" :width="previewW" :height="previewH" />
              </div>
              <span v-if="showLabels" class="element-label">{{ item.element.defaultLabel || item.element.type }}</span>
            </div>
          </div>
          <div v-else class="no-results">No results</div>
        </div>
      </template>

      <!-- Normal sections per language -->
      <template v-else>
        <div v-for="lang in languages" :key="lang.id" class="sidebar-section">
          <button class="sidebar-header" :aria-expanded="isOpen(lang.id)" @click="toggleSection(lang.id)">
            <span class="sidebar-title" :title="lang.name">{{ lang.name }}</span>
            <v-icon class="expand-icon" :class="{ 'expand-icon--open': isOpen(lang.id) }" size="14">mdi-chevron-down</v-icon>
          </button>
          <transition name="collapse">
            <div v-if="isOpen(lang.id)" class="sidebar-elements" :class="elementsClass">
              <div v-for="element in lang.elements" :key="element.type" class="sidebar-element" :class="elementClass" :style="tileCardStyle" draggable="true" :title="element.defaultLabel || element.type" @dragstart="onDragStart($event, element)">
                <div v-if="viewMode !== 'list'" class="preview-box">
                  <DiagramPreviewItem :key="`${element.type}-${viewMode}-${previewW}-${previewH}`" :element="element" :width="previewW" :height="previewH" />
                </div>
                <span v-if="showLabels" class="element-label">{{ element.defaultLabel || element.type }}</span>
              </div>
            </div>
          </transition>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import type { DiagramElement } from '@/model/Element'
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'

export interface SidebarLanguage {
  id: string
  name: string
  elements: DiagramElement[]
}

type ViewMode = 'list' | 'preview' | 'tile'

const props = withDefaults(
  defineProps<{
    languages?: SidebarLanguage[]
    sidebarWidth?: number
  }>(),
  { languages: () => [], sidebarWidth: 210 }
)

const searchQuery = ref('')
const viewMode = ref<ViewMode>('preview')
const showLabels = ref(true)
// Default closed: empty map means isOpen returns false
const expandedMap = reactive<Record<string, boolean>>({})

const viewModes: { value: ViewMode; icon: string; label: string }[] = [
  { value: 'list', icon: 'mdi-format-list-bulleted', label: 'List (preview only)' },
  { value: 'preview', icon: 'mdi-card-outline', label: 'Preview' },
  { value: 'tile', icon: 'mdi-view-grid', label: 'Tiles (2 per row)' }
]

// Default closed: only true if explicitly set to true
const isOpen = (id: string) => expandedMap[id] === true

const toggleSection = (id: string) => {
  expandedMap[id] = !isOpen(id)
}

const searchResults = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return []
  const results: { langId: string; element: DiagramElement }[] = []
  for (const lang of props.languages) {
    for (const el of lang.elements) {
      const label = (el.defaultLabel || el.type).toLowerCase()
      if (label.includes(q) || el.type.toLowerCase().includes(q)) {
        results.push({ langId: lang.id, element: el })
      }
    }
  }
  return results
})

const elementsClass = computed(() => ({
  'sidebar-elements--list': viewMode.value === 'list',
  'sidebar-elements--tile': viewMode.value === 'tile',
  'sidebar-elements--no-labels': !showLabels.value
}))

const elementClass = computed(() => ({
  'sidebar-element--list': viewMode.value === 'list',
  'sidebar-element--tile': viewMode.value === 'tile'
}))

const previewW = computed(() => {
  if (viewMode.value === 'tile') return Math.round((props.sidebarWidth - 22) / 2 - 10)
  return props.sidebarWidth - 24
})
const previewH = computed(() => (viewMode.value === 'tile' ? 44 : 56))

// Fixed tile card width so justify-items:center in the grid actually works
const tileCardStyle = computed(() => (viewMode.value === 'tile' ? { width: previewW.value + 8 + 'px' } : {}))

const onDragStart = (event: DragEvent, element: DiagramElement) => {
  if (!event.dataTransfer) return
  event.dataTransfer.setData('text/plain', element.type)
  event.dataTransfer.effectAllowed = 'copy'
}
</script>

<style scoped>
/* ── Sidebar content ─────────────────────────────────── */
.elements-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: transparent;
  overflow: hidden;
  user-select: none;
}

/* ── Top bar ─────────────────────────────────────────── */
.sidebar-topbar {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px 16px 6px 8px;
  background: #ffffff;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.14);
  flex-shrink: 0;
}

.search-wrapper {
  display: flex;
  align-items: center;
  gap: 5px;
  background: rgba(var(--v-theme-on-surface), 0.04);
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 7px;
  padding: 4px 8px;
  transition: border-color 0.15s;
}

.search-wrapper:focus-within {
  border-color: rgba(var(--v-theme-primary), 0.5);
  background: #ffffff;
}

.search-icon {
  color: rgba(var(--v-theme-on-surface), 0.35);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.87);
  min-width: 0;
}

.search-input::placeholder {
  color: rgba(var(--v-theme-on-surface), 0.3);
}

.search-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  color: rgba(var(--v-theme-on-surface), 0.35);
  flex-shrink: 0;
}

.search-clear:hover {
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.topbar-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.view-toggles {
  display: flex;
  gap: 2px;
}

.view-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 5px;
  border: 1px solid transparent;
  background: none;
  cursor: pointer;
  color: rgba(var(--v-theme-on-surface), 0.38);
  transition:
    background 0.12s,
    color 0.12s,
    border-color 0.12s;
}

.view-toggle:hover {
  background: rgba(var(--v-theme-primary), 0.07);
  color: rgba(var(--v-theme-primary), 0.9);
}

.view-toggle--active {
  background: rgba(var(--v-theme-primary), 0.1);
  border-color: rgba(var(--v-theme-primary), 0.3);
  color: rgba(var(--v-theme-primary), 1);
}

/* ── Scrollable body ─────────────────────────────────── */
.sidebar-body {
  flex: 1;
  min-height: 0;
  overflow-y: scroll;
  overflow-x: hidden;
  background: #ffffff;
  padding-right: 0; /* scrollbar sits inside the padding box */
}

.sidebar-body::-webkit-scrollbar {
  width: 5px;
}

.sidebar-body::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-body::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 3px;
}

.sidebar-body::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--v-theme-on-surface), 0.35);
}

/* ── Section ─────────────────────────────────────────── */
.sidebar-section {
  display: flex;
  flex-direction: column;
}

.sidebar-section + .sidebar-section {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.1);
}

/* Language header with left accent bar */
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 9px 10px 9px 12px;
  background: #ffffff;
  border: none;
  border-left: 3px solid rgba(var(--v-theme-primary), 0.7);
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
  cursor: pointer;
  gap: 6px;
  font-family: inherit;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 1;
  transition: background 0.12s;
}

.sidebar-header--static {
  cursor: default;
  border-left-color: rgba(var(--v-theme-on-surface), 0.25);
}

.sidebar-header:not(.sidebar-header--static):hover {
  background: rgba(var(--v-theme-primary), 0.05);
}

.sidebar-title {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.82);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  text-align: left;
}

.expand-icon {
  color: rgba(var(--v-theme-primary), 0.55);
  flex-shrink: 0;
  transition: transform 0.2s ease;
  transform: rotate(-90deg);
}

.expand-icon--open {
  transform: rotate(0deg);
}

.no-results {
  padding: 14px 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.38);
  text-align: center;
}

/* ── Elements list ───────────────────────────────────── */
.sidebar-elements {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px;
}

/* Tile: 2-column grid, items centered in their cells */
.sidebar-elements--tile {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px 6px;
  justify-items: center;
  align-items: start;
}

/* List */
.sidebar-elements--list {
  gap: 2px;
  padding: 4px 6px;
}

/* ── Single element ──────────────────────────────────── */
.sidebar-element {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  padding: 6px 4px 5px;
  border-radius: 7px;
  cursor: grab;
  background: #ffffff;
  border: 1px solid rgba(var(--v-theme-outline), 0.13);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition:
    box-shadow 0.13s,
    border-color 0.13s,
    background 0.13s;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.sidebar-element:hover {
  background: rgba(var(--v-theme-primary), 0.03);
  box-shadow: 0 2px 7px rgba(0, 0, 0, 0.1);
  border-color: rgba(var(--v-theme-primary), 0.25);
}

.sidebar-element:active {
  cursor: grabbing;
}

/* List variant: horizontal row */
.sidebar-element--list {
  flex-direction: row;
  align-items: center;
  padding: 6px 8px;
  gap: 10px;
}

/* Tile: width is set via inline :style, auto here */
.sidebar-element--tile {
  width: auto;
  padding: 5px 4px 4px;
  gap: 3px;
}

/* Fixed-size preview container (centered + clipped) */
.preview-box {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

/* ── Labels ──────────────────────────────────────────── */
.element-label {
  font-size: 10px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.72);
  text-align: center;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: break-word;
  line-height: 1.25;
  width: 100%;
}

.sidebar-element--list .element-label {
  text-align: left;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: normal;
}

.sidebar-element--tile .element-label {
  font-size: 9px;
  text-align: center;
}

/* ── Collapse transition ─────────────────────────────── */
.collapse-enter-active,
.collapse-leave-active {
  overflow: hidden;
  transition: max-height 0.2s ease;
  max-height: 4000px;
}

.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
}
</style>
