<template>
  <div>
    <v-alert type="info" variant="tonal" density="compact" class="mb-4">
      <div class="text-caption">Enable collapsing and define the appearance, size, and style of the collapsed variant.</div>
    </v-alert>

    <!-- Collapsible Aktivieren -->
    <v-checkbox v-model="localElement.collapsible" label="Element Can Be Collapsed" density="compact" hint="Adds a +/- icon to the Element" persistent-hint @update:model-value="onCollapsibleChange" />

    <!-- Collapse-Einstellungen (nur wenn collapsible aktiviert) -->
    <template v-if="localElement.collapsible">
      <v-divider class="my-3" />

      <div class="text-subtitle-2 mb-3">Size & Text</div>

      <v-row dense>
        <v-col cols="6">
          <v-text-field v-model.number="collapsedConfig.width" label="Width (collapsed)" variant="outlined" density="compact" type="number" @input="emitUpdate" />
        </v-col>
        <v-col cols="6">
          <v-text-field v-model.number="collapsedConfig.height" label="Height (collapsed)" variant="outlined" density="compact" type="number" @input="emitUpdate" />
        </v-col>
      </v-row>

      <v-text-field v-model="collapsedConfig.label" label="Alternative Text" variant="outlined" density="compact" hint="Optional text shown in the collapsed state" persistent-hint clearable class="mt-2" @input="emitUpdate" />

      <v-divider class="my-4" />

      <div class="text-subtitle-2 mb-3">Shape & Style (collapsed)</div>

      <v-select v-model="collapsedStyle.shape" :items="shapeOptions" item-title="label" item-value="value" label="Shape" variant="outlined" density="compact" clearable @update:model-value="onShapeChange" />

      <v-row dense class="mt-1">
        <v-col cols="6">
          <ColorPickerField v-model="collapsedStyle.strokeColor" label="Border Color" @update:model-value="emitUpdate" />
        </v-col>
        <v-col cols="6">
          <ColorPickerField v-model="collapsedStyle.fillColor" label="Fill Color" @update:model-value="emitUpdate" />
        </v-col>
      </v-row>

      <v-slider v-model="collapsedStyle.strokeWidth" label="Border Width" min="1" max="10" step="1" thumb-label class="my-3" @update:model-value="emitUpdate" />

      <v-slider v-model="collapsedStyle.fontSize" label="Font Size" min="8" max="24" step="1" thumb-label class="mb-3" @update:model-value="emitUpdate" />

      <v-row dense>
        <v-col cols="6">
          <ColorPickerField v-model="collapsedStyle.fontColor" label="Font Color" @update:model-value="emitUpdate" />
        </v-col>
        <v-col cols="6">
          <v-text-field v-model="collapsedStyle.fontFamily" label="Font Family" variant="outlined" density="compact" @input="emitUpdate" />
        </v-col>
      </v-row>

      <v-row dense>
        <v-col cols="6">
          <v-select v-model="collapsedStyle.align" :items="horizontalAlignOptions" label="Horizontal Alignment" variant="outlined" density="compact" @update:model-value="emitUpdate" />
        </v-col>
        <v-col cols="6">
          <v-select v-model="collapsedStyle.verticalAlign" :items="verticalAlignOptions" label="Vertical Alignment" variant="outlined" density="compact" @update:model-value="emitUpdate" />
        </v-col>
      </v-row>
    </template>
  </div>
</template>

<script setup lang="ts">
/* eslint-disable vue/no-mutating-props */
import { computed, watch } from 'vue'
import type { DiagramElement, ElementStyle } from '@/model/Element'
import ColorPickerField from './ColorPickerField.vue'

interface Props {
  element: DiagramElement
}

const props = defineProps<Props>()
const emit = defineEmits<{
  update: []
}>()

const localElement = computed(() => props.element)

const shapeOptions = [
  { label: 'Rectangle', value: 'rectangle' },
  { label: 'Ellipse', value: 'ellipse' },
  { label: 'Diamond', value: 'rhombus' },
  { label: 'Triangle', value: 'triangle' }
]

const horizontalAlignOptions = ['left', 'center', 'right']
const verticalAlignOptions = ['top', 'middle', 'bottom']

function cloneStyle(style: ElementStyle): ElementStyle {
  return { ...style }
}

function ensureCollapsedConfig() {
  if (!localElement.value.collapsed) {
    const baseWidth = localElement.value.width ?? 120
    const baseHeight = localElement.value.height ?? 80

    localElement.value.collapsed = {
      width: Math.floor(baseWidth * 0.6),
      height: Math.floor(baseHeight * 0.6),
      label: '',
      style: cloneStyle(localElement.value.style)
    }
    emitUpdate()
  } else if (!localElement.value.collapsed.style) {
    localElement.value.collapsed.style = cloneStyle(localElement.value.style)
    emitUpdate()
  }
}

const collapsedConfig = computed(() => {
  ensureCollapsedConfig()
  return localElement.value.collapsed!
})

const collapsedStyle = computed(() => {
  ensureCollapsedConfig()
  return localElement.value.collapsed!.style!
})

function onShapeChange(value: string | null) {
  if (value) {
    collapsedStyle.value.shape = value
  } else {
    delete collapsedStyle.value.shape
  }
  emitUpdate()
}

function onCollapsibleChange() {
  // Wenn collapsible deaktiviert wird, entferne auch die Bounds
  if (!localElement.value.collapsible) {
    delete localElement.value.collapsed
    if (localElement.value.style) {
      delete localElement.value.style.foldable
    }
  } else {
    // Wenn aktiviert, stelle sicher dass Bounds existieren
    ensureCollapsedConfig()
    // Aktiviere foldable Style
    if (localElement.value.style) {
      localElement.value.style.foldable = true
    }
  }
  emitUpdate()
}

function emitUpdate() {
  emit('update')
}

watch(
  () => localElement.value.collapsed,
  () => emitUpdate(),
  { deep: true }
)
</script>
