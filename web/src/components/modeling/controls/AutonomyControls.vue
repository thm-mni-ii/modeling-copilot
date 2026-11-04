<template>
  <v-menu location="bottom end" min-width="300" :disabled="props.disabled">
    <template #activator="{ props: activatorProps }">
      <v-btn v-bind="activatorProps" density="compact" variant="tonal" :color="selectedMode.color" class="autonomy-trigger" :title="props.disabled ? 'The feedback mode is fixed by the task.' : selectedMode.description" :disabled="props.disabled">
        <v-icon start>{{ selectedMode.icon }}</v-icon>
        <span>{{ selectedMode.title }}</span>
        <v-icon end size="16">mdi-chevron-down</v-icon>
      </v-btn>
    </template>

    <v-list density="compact" class="autonomy-menu" aria-label="Feedback mode">
      <v-list-item v-for="option in AUTONOMY_MODES" :key="option.value" :active="option.value === mode" :base-color="option.color" :disabled="props.disabled" @click="emit('update:mode', option.value)">
        <template #prepend
          ><v-icon :color="option.color">{{ option.icon }}</v-icon></template
        >
        <v-list-item-title>{{ option.title }}</v-list-item-title>
        <v-list-item-subtitle>{{ option.description }}</v-list-item-subtitle>
        <template v-if="option.value === mode" #append><v-icon size="18" :color="option.color">mdi-check</v-icon></template>
      </v-list-item>
      <template v-if="props.connectionPreviewAllowed !== undefined">
        <v-divider class="my-1" />
        <v-list-subheader>Task permissions</v-list-subheader>
        <v-list-item role="menuitemcheckbox" :aria-checked="props.connectionPreviewAllowed" aria-label="Allow Connection Preview" :active="props.connectionPreviewAllowed" @click="emit('update:connectionPreviewAllowed', !props.connectionPreviewAllowed)">
          <template #prepend><v-icon>mdi-plus-network</v-icon></template>
          <v-list-item-title>Allow Connection Preview</v-list-item-title>
          <v-list-item-subtitle>Participants may enable visual connection suggestions for this task.</v-list-item-subtitle>
          <template #append
            ><v-icon :color="props.connectionPreviewAllowed ? 'primary' : undefined">{{ props.connectionPreviewAllowed ? 'mdi-toggle-switch' : 'mdi-toggle-switch-off-outline' }}</v-icon></template
          >
        </v-list-item>
      </template>
    </v-list>
  </v-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AUTONOMY_MODES, type AutonomyMode } from '@/model/Autonomy'

const props = withDefaults(
  defineProps<{
    mode: AutonomyMode
    disabled?: boolean
    connectionPreviewAllowed?: boolean
  }>(),
  { connectionPreviewAllowed: undefined }
)

const selectedMode = computed(() => AUTONOMY_MODES.find((option) => option.value === props.mode) ?? AUTONOMY_MODES[0])

const emit = defineEmits<{
  'update:mode': [mode: AutonomyMode]
  'update:connectionPreviewAllowed': [allowed: boolean]
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
