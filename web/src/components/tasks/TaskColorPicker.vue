<template>
  <v-menu :close-on-content-click="false" location="bottom">
    <template #activator="{ props: menuProps }">
      <v-btn v-bind="menuProps" :size="size" variant="outlined" :color="active ? 'primary' : undefined" :disabled="disabled" :title="title" @mousedown.prevent>
        <v-icon>{{ icon }}</v-icon>
        <span v-if="indicatorColor" class="task-color-picker__indicator" :style="{ backgroundColor: indicatorColor }" />
      </v-btn>
    </template>
    <v-card class="pa-2">
      <div class="task-color-picker__swatches">
        <button v-for="color in colors" :key="color.value" type="button" class="task-color-picker__swatch" :style="{ backgroundColor: color.value }" :title="color.label" @mousedown.prevent @click="emit('select', color.value)" />
        <button v-if="allowReset" type="button" class="task-color-picker__swatch task-color-picker__swatch--reset" :title="resetTitle" @mousedown.prevent @click="emit('reset')">
          <v-icon size="14">mdi-close</v-icon>
        </button>
      </div>
    </v-card>
  </v-menu>
</template>

<script setup lang="ts">
import type { TaskEditorColor } from './taskEditorExtensions'

withDefaults(
  defineProps<{
    title: string
    icon: string
    colors: readonly TaskEditorColor[]
    size?: 'x-small' | 'small' | 'default'
    disabled?: boolean
    active?: boolean
    indicatorColor?: string
    allowReset?: boolean
    resetTitle?: string
  }>(),
  {
    size: 'small',
    disabled: false,
    active: false,
    indicatorColor: undefined,
    allowReset: false,
    resetTitle: 'Reset color'
  }
)

const emit = defineEmits<{
  select: [color: string]
  reset: []
}>()
</script>

<style scoped>
.task-color-picker__indicator {
  width: 12px;
  height: 3px;
  margin-left: 3px;
  border-radius: 2px;
}

.task-color-picker__swatches {
  display: grid;
  grid-template-columns: repeat(5, 26px);
  gap: 6px;
}

.task-color-picker__swatch {
  width: 26px;
  height: 26px;
  border: 1px solid rgba(0, 0, 0, 0.25);
  border-radius: 4px;
  cursor: pointer;
}

.task-color-picker__swatch--reset {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}
</style>
