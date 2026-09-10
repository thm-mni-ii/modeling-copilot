<template>
  <ConnectionEditorFormImpl v-model:preview-mode="previewMode" :selected-connection="selectedConnection" @update="emit('update')" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import type { ConnectionPreviewMode } from '@/utils/connectionPreview'
import ConnectionEditorFormImpl from '../form/ConnectionEditorForm.vue'

interface Props {
  selectedConnection: DiagramConnection
  previewMode: ConnectionPreviewMode
}

const props = defineProps<Props>()

const emit = defineEmits<{
  update: []
  'update:previewMode': [ConnectionPreviewMode]
}>()

const previewMode = computed<ConnectionPreviewMode>({
  get: () => props.previewMode,
  set: (value) => emit('update:previewMode', value)
})
</script>
