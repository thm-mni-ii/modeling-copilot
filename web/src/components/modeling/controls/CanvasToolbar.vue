<template>
  <div class="canvas-toolbar">
    <ModelingToolbarGroup title="Modeling">
      <div hidden>
        <LayerVisibilityControls :model-value="layerView" @update:model-value="emit('update:layer-view', $event)" />
      </div>
      <SelectedTypeControl ref="typeControl" :languages="typeSwitchLanguages" :enabled="canChangeType" :connections="connections" :connection-groups="connectionGroups" :connection-preferences="connectionPreferences" @select-connection="emit('select-connection', $event)" @update:connection-preferences="emit('update:connection-preferences', $event)" />
    </ModelingToolbarGroup>
    <v-divider vertical class="canvas-toolbar__divider" />

    <ModelingToolbarGroup title="Edit">
      <v-btn-group size="small" density="compact" variant="outlined" color="dark-gray"><v-btn icon="mdi-select-all" title="Select all (Ctrl+A)" @click="emit('select-all')" /><v-btn icon="mdi-selection-off" title="Clear selection (Esc)" @click="emit('clear-selection')" /></v-btn-group>
      <v-btn-group size="small" density="compact" variant="outlined" color="dark-gray"><v-btn icon="mdi-delete-outline" title="Delete (Del)" @click="emit('delete-selected')" /><v-btn icon="mdi-content-duplicate" title="Duplicate (Ctrl+D)" @click="emit('duplicate-selected')" /></v-btn-group>
    </ModelingToolbarGroup>
    <v-divider vertical class="canvas-toolbar__divider" />

    <ModelingToolbarGroup title="Layout">
      <v-btn-group size="small" density="compact" variant="outlined" color="dark-gray"><v-btn icon="mdi-format-horizontal-align-left" title="Align left" @click="emit('align-left')" /><v-btn icon="mdi-format-horizontal-align-center" title="Align horizontally" @click="emit('align-center-h')" /><v-btn icon="mdi-format-horizontal-align-right" title="Align right" @click="emit('align-right')" /></v-btn-group>
      <v-btn-group size="small" density="compact" variant="outlined" color="dark-gray"><v-btn icon="mdi-format-vertical-align-top" title="Align top" @click="emit('align-top')" /><v-btn icon="mdi-format-vertical-align-center" title="Align vertically" @click="emit('align-middle-v')" /><v-btn icon="mdi-format-vertical-align-bottom" title="Align bottom" @click="emit('align-bottom')" /></v-btn-group>
    </ModelingToolbarGroup>
    <v-divider vertical class="canvas-toolbar__divider" />

    <!-- mousedown.prevent: der offene Label-Editor behält Fokus und Markierung -->
    <ModelingToolbarGroup title="Text">
      <v-btn-group size="small" density="compact" variant="outlined" color="dark-gray"><v-btn icon="mdi-format-bold" title="Bold (Ctrl+B)" @mousedown.prevent @click="emit('format-text', 'bold')" /><v-btn icon="mdi-format-italic" title="Italic (Ctrl+I)" @mousedown.prevent @click="emit('format-text', 'italic')" /><v-btn icon="mdi-format-underline" title="Underline (Ctrl+U)" @mousedown.prevent @click="emit('format-text', 'underline')" /></v-btn-group>
    </ModelingToolbarGroup>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SelectedTypeControl from './SelectedTypeControl.vue'
import type { SwitchLanguage } from '@/utils/typeSwitch'
import LayerVisibilityControls, { type CanvasLayerView } from './LayerVisibilityControls.vue'
import ModelingToolbarGroup from './ModelingToolbarGroup.vue'
import type { JsonObject } from '@/services/api/types/common'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'
import type { TextFormat } from '@/utils/htmlLabels'

withDefaults(
  defineProps<{
    connections?: DiagramConnection[]
    connectionGroups?: DiagramConnectionGroup[]
    connectionPreferences?: JsonObject
    typeSwitchLanguages?: SwitchLanguage[]
    canChangeType?: boolean
    layerView: CanvasLayerView
  }>(),
  { typeSwitchLanguages: () => [], canChangeType: false, connections: () => [], connectionGroups: () => [], connectionPreferences: undefined }
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
  'format-text': [format: TextFormat]
  'select-connection': [connection: DiagramConnection]
  'update:connection-preferences': [preferences: JsonObject]
  'update:layer-view': [view: CanvasLayerView]
}>()

const typeControl = ref<InstanceType<typeof SelectedTypeControl> | null>(null)

defineExpose({
  closeConnectionPalette: () => typeControl.value?.closePalette(),
  selectConnectionByReference: (languageId: string, connectionType: string) => typeControl.value?.selectConnectionByReference(languageId, connectionType) ?? false
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
