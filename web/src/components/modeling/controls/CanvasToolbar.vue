<template>
  <div class="canvas-toolbar">
    <ModelingToolbarGroup title="Modeling">
      <LayerVisibilityControls :model-value="layerView" @update:model-value="emit('update:layer-view', $event)" />
      <ConnectionToolbar v-if="connections.length" ref="connectionToolbar" compact :connections="connections" :connection-groups="connectionGroups" :preferences="connectionPreferences" @select="emit('select-connection', $event)" @update:preferences="emit('update:connection-preferences', $event)" />
    </ModelingToolbarGroup>
    <v-divider vertical class="canvas-toolbar__divider" />

    <ModelingToolbarGroup title="Edit">
      <v-btn-group size="small" density="compact" variant="outlined"><v-btn icon="mdi-select-all" title="Select all (Ctrl+A)" @click="emit('select-all')" /><v-btn icon="mdi-selection-off" title="Clear selection (Esc)" @click="emit('clear-selection')" /></v-btn-group>
      <v-btn-group size="small" density="compact" variant="outlined"><v-btn icon="mdi-delete-outline" title="Delete (Del)" @click="emit('delete-selected')" /><v-btn icon="mdi-content-duplicate" title="Duplicate (Ctrl+D)" @click="emit('duplicate-selected')" /></v-btn-group>
    </ModelingToolbarGroup>
    <v-divider vertical class="canvas-toolbar__divider" />

    <ModelingToolbarGroup title="Layout">
      <v-btn-group size="small" density="compact" variant="outlined"><v-btn icon="mdi-format-horizontal-align-left" title="Align left" @click="emit('align-left')" /><v-btn icon="mdi-format-horizontal-align-center" title="Align horizontally" @click="emit('align-center-h')" /><v-btn icon="mdi-format-horizontal-align-right" title="Align right" @click="emit('align-right')" /></v-btn-group>
      <v-btn-group size="small" density="compact" variant="outlined"><v-btn icon="mdi-format-vertical-align-top" title="Align top" @click="emit('align-top')" /><v-btn icon="mdi-format-vertical-align-center" title="Align vertically" @click="emit('align-middle-v')" /><v-btn icon="mdi-format-vertical-align-bottom" title="Align bottom" @click="emit('align-bottom')" /></v-btn-group>
    </ModelingToolbarGroup>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ConnectionToolbar from './ConnectionToolbar.vue'
import LayerVisibilityControls, { type CanvasLayerView } from './LayerVisibilityControls.vue'
import ModelingToolbarGroup from './ModelingToolbarGroup.vue'
import type { JsonObject } from '@/services/api/types/common'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'

withDefaults(
  defineProps<{
    connections?: DiagramConnection[]
    connectionGroups?: DiagramConnectionGroup[]
    connectionPreferences?: JsonObject
    layerView: CanvasLayerView
  }>(),
  { connections: () => [], connectionGroups: () => [], connectionPreferences: undefined }
)

const emit = defineEmits<{
  'select-all': []
  'clear-selection': []
  'delete-selected': []
  'duplicate-selected': []
  'align-left': []
  'align-center-h': []
  'align-right': []
  'align-top': []
  'align-middle-v': []
  'align-bottom': []
  'select-connection': [connection: DiagramConnection]
  'update:connection-preferences': [preferences: JsonObject]
  'update:layer-view': [view: CanvasLayerView]
}>()

const connectionToolbar = ref<{ closePalette: () => void; selectConnectionByReference: (languageId: string, connectionType: string) => boolean } | null>(null)

defineExpose({
  closeConnectionPalette: () => connectionToolbar.value?.closePalette(),
  selectConnectionByReference: (languageId: string, connectionType: string) => connectionToolbar.value?.selectConnectionByReference(languageId, connectionType) ?? false
})
</script>

<style scoped>
.canvas-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex-wrap: wrap;
}

.canvas-toolbar__divider {
  align-self: stretch;
  margin: 2px 0;
}

</style>
