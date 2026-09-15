<template>
  <v-tabs :model-value="modelValue" density="compact" height="34" color="primary" :show-arrows="!iconsOnly" :grow="iconsOnly" :class="['sidebar-tabs', { 'sidebar-tabs--icons': iconsOnly }]" :aria-label="ariaLabel" @update:model-value="updateValue">
    <v-tab v-for="tab in tabs" :key="tab.value" :value="tab.value" :prepend-icon="iconsOnly ? undefined : tab.icon" :title="tab.label" :aria-label="tab.label">
      <v-icon v-if="iconsOnly" :icon="tab.icon" />
      <template v-else>{{ tab.label }}</template>
    </v-tab>
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
    iconsOnly?: boolean
  }>(),
  { ariaLabel: 'Sidebar sections', iconsOnly: false }
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

.sidebar-tabs--icons :deep(.v-tab) {
  flex: 1 1 0;
  max-width: none;
  padding: 0;
}
</style>
