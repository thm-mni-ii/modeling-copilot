<template>
  <span class="info-tip" tabindex="0" :aria-label="text">
    <v-icon size="16">mdi-information-outline</v-icon>
    <v-tooltip activator="parent" location="top" max-width="340">{{ text }}</v-tooltip>
  </span>
</template>

<script setup lang="ts">
defineProps<{ text: string }>()
</script>

<style scoped>
.info-tip { display: inline-flex; margin-left: 6px; vertical-align: middle; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); cursor: help; }
</style>
