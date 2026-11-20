<template>
  <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
    {{ error }}
    <template #append><v-btn variant="text" @click="$emit('retry')">Try again</v-btn></template>
  </v-alert>
  <v-progress-linear v-else-if="loading" indeterminate class="mb-4" aria-label="Loading" />
</template>

<script setup lang="ts">
defineProps<{ loading: boolean; error: string }>()
defineEmits<{ retry: [] }>()
</script>
