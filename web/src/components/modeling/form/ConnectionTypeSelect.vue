<template>
  <v-select :model-value="modelValue" :items="items" :label="label" :multiple="multiple" :chips="multiple" :closable-chips="multiple" :hint="hint" :persistent-hint="!!hint" :disabled="disabled" :class="className" density="compact" variant="outlined" prepend-inner-icon="mdi-connection" @update:model-value="$emit('update:modelValue', $event)">
    <template #item="{ props: itemProps, item }">
      <v-list-item v-bind="itemProps">
        <template #title>
          <div class="preview-item">
            <ConnectionPreviewItem :connection="getConnectionByType(item.raw as string)" :width="200" :height="30" />
            <span class="preview-item__label">{{ formatConnectionLabel(item.raw as string) }}</span>
          </div>
        </template>
      </v-list-item>
    </template>
    <template #selection="{ item }">
      <div :class="multiple ? 'preview-item' : 'entry-selection'">
        <ConnectionPreviewItem :connection="getConnectionByType(item.raw as string)" :width="200" :height="multiple ? 30 : 40" />
        <span :class="multiple ? 'preview-item__label' : 'ml-2'">{{ formatConnectionLabel(item.raw as string) }}</span>
      </div>
    </template>
  </v-select>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'

interface Props {
  modelValue: string | string[]
  items: string[]
  label?: string
  multiple?: boolean
  hint?: string
  disabled?: boolean
  className?: string
}

defineProps<Props>()
defineEmits<{
  'update:modelValue': [value: string | string[]]
}>()

const store = useDiagramLanguages()

const connections = computed(() => store.definition?.connections ?? [])

const getConnectionByType = (type?: string) => {
  if (!type) return undefined
  return connections.value.find((connection) => connection.type === type) ?? connections.value.find((connection) => connection.connectionType === type)
}

const formatConnectionLabel = (type?: string) => {
  if (!type) return 'Connection'
  const connection = connections.value.find((item) => item.type === type)
  return connection?.label || type
}
</script>

<style scoped>
.preview-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.preview-item__label {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.entry-selection {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
