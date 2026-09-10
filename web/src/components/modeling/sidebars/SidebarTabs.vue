<template>
  <v-tabs :model-value="modelValue" density="compact" height="34" color="primary" show-arrows class="sidebar-tabs" :aria-label="ariaLabel" @update:model-value="updateValue">
    <v-tab v-for="tab in tabs" :key="tab.value" :value="tab.value" :prepend-icon="tab.icon" :title="tab.label">{{ tab.label }}</v-tab>
  </v-tabs>
</template>

<script setup lang="ts">
export interface SidebarTabItem {
  value: string
  icon: string
  label: string
}

withDefaults(
  defineProps<{
    modelValue: string
    tabs: SidebarTabItem[]
    ariaLabel?: string
  }>(),
  { ariaLabel: 'Sidebar sections' }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const updateValue = (value: unknown) => {
  if (typeof value === 'string') emit('update:modelValue', value)
}
</script>

<style scoped>
.sidebar-tabs {
  width: 100%;
  min-width: 0;
}

.sidebar-tabs :deep(.v-tab) {
  min-width: 0;
  padding: 0 9px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: normal;
  text-transform: none;
}
</style>
