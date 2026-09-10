<template>
  <v-menu location="bottom end" min-width="300">
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" density="compact" variant="tonal" :color="selectedMode.color" class="autonomy-trigger" :title="selectedMode.description">
        <v-icon start>{{ selectedMode.icon }}</v-icon>
        <span>{{ selectedMode.title }}</span>
        <v-icon end size="16">mdi-chevron-down</v-icon>
      </v-btn>
    </template>

    <v-list density="compact" class="autonomy-menu" aria-label="Feedback mode">
      <v-list-item v-for="option in AUTONOMY_MODES" :key="option.value" :active="option.value === mode" :base-color="option.color" @click="emit('update:mode', option.value)">
        <template #prepend><v-icon :color="option.color">{{ option.icon }}</v-icon></template>
        <v-list-item-title>{{ option.title }}</v-list-item-title>
        <v-list-item-subtitle>{{ option.description }}</v-list-item-subtitle>
        <template v-if="option.value === mode" #append><v-icon size="18" :color="option.color">mdi-check</v-icon></template>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AUTONOMY_MODES, type AutonomyMode } from '@/model/Autonomy'

const props = defineProps<{
  mode: AutonomyMode
}>()

const selectedMode = computed(() => AUTONOMY_MODES.find((option) => option.value === props.mode) ?? AUTONOMY_MODES[0])

const emit = defineEmits<{
  'update:mode': [mode: AutonomyMode]
}>()
</script>

<style scoped>
.autonomy-trigger {
  text-transform: none;
  letter-spacing: normal;
}

.autonomy-trigger :deep(.v-icon) {
  font-size: 18px;
}

.autonomy-menu {
  padding: 4px;
}

.autonomy-menu :deep(.v-list-item) {
  min-height: 52px;
  border-radius: 6px;
}
</style>
