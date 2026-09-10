<template>
  <div class="floating-settings-menu" :class="{ 'hidden-during-pan': isPanning }">
    <v-menu v-model="menuOpen" :close-on-content-click="false" location="top">
      <template #activator="{ props: activatorProps }">
        <v-btn v-bind="activatorProps" icon="mdi-chevron-up" size="small" density="compact" variant="outlined" title="Settings" :class="{ 'settings-active': menuOpen }" />
      </template>
      <v-card class="settings-card" min-width="280">
        <v-card-title class="py-2 px-3">
          <v-icon class="mr-2">mdi-cog</v-icon>
          Settings
        </v-card-title>
        <v-card-text class="py-2 px-3">
          <v-row dense>
            <v-col cols="12">
              <v-text-field v-model="localGridSize" label="Grid (px)" type="number" density="compact" variant="outlined" min="5" max="100" hint="Recommended: 5–25" @input="handleGridSizeChange" />
            </v-col>
            <v-col cols="12">
              <v-text-field v-model="localTolerance" label="Tolerance (px)" type="number" density="compact" variant="outlined" min="1" max="50" hint="Mouse detection in px" @input="handleToleranceChange" />
            </v-col>
            <v-col cols="12">
              <v-select v-model="localSnapToGrid" label="Snap to Grid" :items="snapOptions" density="compact" variant="outlined" @update:model-value="handleSnapToGridChange" />
            </v-col>
            <v-col cols="12">
              <v-select v-model="localUseGridForPanning" label="Grid for Panning" :items="snapOptions" density="compact" variant="outlined" hint="Grid-based panning" @update:model-value="handleUseGridForPanningChange" />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-menu>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useGraphContext } from '@/composables/useGraphContext'

const { isPanning, gridSize, snapToGrid, tolerance, useGridForPanning } = useGraphContext()

// Lokale Kopien für v-model Bindings
const localGridSize = ref(gridSize.value)
const localTolerance = ref(tolerance.value)
const localSnapToGrid = ref(snapToGrid.value)
const localUseGridForPanning = ref(useGridForPanning.value)
const menuOpen = ref(false)

const snapOptions = ref([
  { title: 'On', value: true },
  { title: 'Off', value: false }
])

// Emits für Parent-Komponente
const emit = defineEmits(['update:gridSize', 'update:tolerance', 'update:snapToGrid', 'update:useGridForPanning'])

// Watchers um externe Änderungen zu übernehmen
watch(gridSize, (newVal) => {
  localGridSize.value = newVal
})

watch(tolerance, (newVal) => {
  localTolerance.value = newVal
})

watch(snapToGrid, (newVal) => {
  localSnapToGrid.value = newVal
})

watch(useGridForPanning, (newVal) => {
  localUseGridForPanning.value = newVal
})

// Event Handlers
const handleGridSizeChange = () => {
  emit('update:gridSize', Number(localGridSize.value))
}

const handleToleranceChange = () => {
  emit('update:tolerance', Number(localTolerance.value))
}

const handleSnapToGridChange = () => {
  emit('update:snapToGrid', localSnapToGrid.value)
}

const handleUseGridForPanningChange = () => {
  emit('update:useGridForPanning', localUseGridForPanning.value)
}
</script>

<style scoped>
.floating-settings-menu {
  position: absolute;
  bottom: 16px;
  right: 16px;
  z-index: 10;
}

.floating-settings-menu .v-btn {
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(0, 0, 0, 0.12);
  transition: all 0.2s ease;
  box-shadow:
    0 4px 12px rgba(0, 0, 0, 0.15),
    0 2px 6px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
}

.floating-settings-menu .v-btn:hover {
  background: rgba(255, 255, 255, 1);
  transform: translateY(-1px);
  box-shadow:
    0 6px 16px rgba(0, 0, 0, 0.2),
    0 3px 8px rgba(0, 0, 0, 0.15);
}

.floating-settings-menu .v-btn.settings-active {
  background: rgba(25, 118, 210, 0.1);
  border-color: #1976d2;
  color: #1976d2;
}

.settings-card {
  box-shadow:
    0 8px 24px rgba(0, 0, 0, 0.15),
    0 4px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(12px);
}

.settings-card .v-card-title {
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  font-size: 0.875rem;
  font-weight: 600;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.settings-card .v-text-field,
.settings-card .v-select {
  margin-bottom: 8px;
}

.settings-card .v-text-field :deep(.v-field__input),
.settings-card .v-select :deep(.v-field__input) {
  min-height: 32px !important;
  padding: 4px 8px !important;
  font-size: 0.875rem;
}

.hidden-during-pan {
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}
</style>
