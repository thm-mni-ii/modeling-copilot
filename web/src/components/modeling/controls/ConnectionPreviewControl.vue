<template>
  <v-tooltip :text="description" location="bottom">
    <template #activator="{ props: activatorProps }">
      <span v-bind="activatorProps" class="connection-preview-control">
        <v-btn-group size="small" density="compact" variant="outlined" class="connection-preview-group">
          <v-btn :color="allowed && modelValue ? 'success' : 'medium-gray'" :disabled="!allowed" :aria-pressed="allowed && modelValue" aria-label="Connection Preview" icon="mdi-vector-polyline" @click="emit('update:modelValue', !modelValue)" />
        </v-btn-group>
      </span>
    </template>
  </v-tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ modelValue: boolean; allowed?: boolean }>(), { allowed: true })
const emit = defineEmits<{ 'update:modelValue': [enabled: boolean] }>()
const description = computed(() => (!props.allowed ? 'Connection Preview: not allowed by this task' : props.modelValue ? 'Connection Preview: On' : 'Connection Preview: Off'))
</script>

<style scoped>
.connection-preview-control {
  display: inline-flex;
}

.connection-preview-group {
  height: 32px;
  border-radius: 4px;
}

.connection-preview-group .v-btn {
  min-width: 28px;
  width: 28px;
  height: 28px;
}

.connection-preview-group :deep(.v-icon) {
  font-size: 20px;
}
</style>
