<template>
  <v-menu location="bottom start" min-width="220">
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" density="compact" variant="tonal" color="primary" class="layer-trigger" :title="selectedLayer.description">
        <v-icon start>{{ selectedLayer.icon }}</v-icon>
        <span>{{ selectedLayer.title }}</span>
        <v-icon end size="16">mdi-chevron-down</v-icon>
      </v-btn>
    </template>

    <v-list density="compact" class="layer-menu" aria-label="Visible layers">
      <v-list-item v-for="option in LAYER_OPTIONS" :key="option.value" :active="option.value === modelValue" color="primary" @click="emit('update:modelValue', option.value)">
        <template #prepend><v-icon>{{ option.icon }}</v-icon></template>
        <v-list-item-title>{{ option.title }}</v-list-item-title>
        <v-list-item-subtitle>{{ option.description }}</v-list-item-subtitle>
        <template v-if="option.value === modelValue" #append><v-icon size="18" color="primary">mdi-check</v-icon></template>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export type CanvasLayerView = 'both' | 'model' | 'feedback'

const LAYER_OPTIONS: { value: CanvasLayerView; title: string; description: string; icon: string }[] = [
  { value: 'both', title: 'Both layers', description: 'Show model and feedback.', icon: 'mdi-layers-outline' },
  { value: 'model', title: 'Model', description: 'Show model elements only.', icon: 'mdi-shape-outline' },
  { value: 'feedback', title: 'Feedback', description: 'Show feedback elements only.', icon: 'mdi-comment-check-outline' }
]

const props = defineProps<{
  modelValue: CanvasLayerView
}>()

const emit = defineEmits<{
  'update:modelValue': [value: CanvasLayerView]
}>()

const selectedLayer = computed(() => LAYER_OPTIONS.find((option) => option.value === props.modelValue) ?? LAYER_OPTIONS[0])
</script>

<style scoped>
.layer-trigger {
  text-transform: none;
  letter-spacing: normal;
}

.layer-menu {
  padding: 4px;
}

.layer-menu :deep(.v-list-item) {
  min-height: 48px;
  border-radius: 6px;
}
</style>
