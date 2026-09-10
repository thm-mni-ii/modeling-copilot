<template>
  <div class="sidebar-panel-header">
    <span class="sidebar-panel-header__title">{{ title }}</span>
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
}>()
</script>

<style scoped>
.sidebar-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
  padding: 9px 10px 9px 12px;
  background: #ffffff;
  border-left: 3px solid rgba(var(--v-theme-on-surface), 0.25);
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
  flex-shrink: 0;
}

.sidebar-panel-header__title {
  overflow: hidden;
  color: rgba(var(--v-theme-on-surface), 0.82);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
