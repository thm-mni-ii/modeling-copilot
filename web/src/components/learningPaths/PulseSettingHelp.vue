<template>
  <v-tooltip location="top" max-width="340" open-on-click open-on-focus>
    <template #activator="{ props }">
      <v-btn v-bind="props" icon="mdi-help-circle-outline" size="x-small" variant="text" :aria-label="`Hilfe: ${label}`" @click.stop />
    </template>
    <p class="setting-help">{{ text }}</p>
  </v-tooltip>
</template>

<script setup lang="ts">
defineProps<{ label: string; text: string }>()
</script>

<style scoped>
.setting-help { white-space: normal; line-height: 1.5; margin: 0; }
</style>
