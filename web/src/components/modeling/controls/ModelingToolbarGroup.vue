<template>
  <div class="modeling-toolbar-group">
    <span class="modeling-toolbar-group__label">{{ title }}</span>
    <div class="modeling-toolbar-group__content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<style scoped>
.modeling-toolbar-group {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  min-width: 0;
}

.modeling-toolbar-group__label {
  padding-left: 2px;
  color: rgba(var(--v-theme-on-surface), 0.52);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.07em;
  line-height: 1;
  text-transform: uppercase;
}

.modeling-toolbar-group__content {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.modeling-toolbar-group :deep(.v-btn-group) {
  height: 32px;
  border-radius: 4px;
}

.modeling-toolbar-group :deep(.v-btn-group .v-btn) {
  min-width: 28px;
  width: 28px;
  height: 28px;
}

.modeling-toolbar-group :deep(.v-btn .v-icon) {
  font-size: 20px;
}
</style>
