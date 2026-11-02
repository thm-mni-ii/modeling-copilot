<template>
  <div>
    <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
      <div class="d-flex gap-4 mb-3">
        <v-text-field v-model="sourcePerimeterSpacingValue" label="Source Perimeter Spacing (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Additional spacing from the source node perimeter." persistent-hint />
        <v-text-field v-model="targetPerimeterSpacingValue" label="Target Perimeter Spacing (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Additional spacing from the target node perimeter." persistent-hint />
      </div>
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <div class="d-flex gap-4 mb-3">
        <v-text-field v-model="entryXValue" label="Entry X (relative)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Relative X position of the entry point (0..1 within the element)." persistent-hint />
        <v-text-field v-model="entryYValue" label="Entry Y (relative)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Relative Y position of the entry point (0..1 within the element)." persistent-hint />
      </div>
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <div class="d-flex gap-4 mb-3">
        <v-text-field v-model="entryDxValue" label="Entry Offset X (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Absolute entry point offset in pixels." persistent-hint />
        <v-text-field v-model="entryDyValue" label="Entry Offset Y (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Absolute entry point offset in pixels." persistent-hint />
      </div>
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="localStyle.entryPerimeter" color="primary" density="compact" class="mb-3" label="Align Entry to Perimeter" hint="Calculates the entry point from the object perimeter." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <div class="d-flex gap-4 mb-3">
        <v-text-field v-model="exitXValue" label="Exit X (relative)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Relative X position of the exit point (0..1 within the element)." persistent-hint />
        <v-text-field v-model="exitYValue" label="Exit Y (relative)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Relative Y position of the exit point (0..1 within the element)." persistent-hint />
      </div>
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <div class="d-flex gap-4 mb-3">
        <v-text-field v-model="exitDxValue" label="Exit Offset X (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Absolute exit position offset in pixels." persistent-hint />
        <v-text-field v-model="exitDyValue" label="Exit Offset Y (px)" variant="outlined" density="compact" type="number" step="0.1" class="flex-grow-1" hint="Absolute exit position offset in pixels." persistent-hint />
      </div>
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="localStyle.exitPerimeter" color="primary" density="compact" class="mb-3" label="Align Exit to Perimeter" hint="Calculates the exit point from the object perimeter." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import type { VisibilityContext } from '../config/fieldVisibility'
import { useStyleHelpers } from '../composables/useStyleHelpers'
import FieldWithIndicator from './FieldWithIndicator.vue'

interface Props {
  connection: DiagramConnection
  visibilityContext: VisibilityContext
}

const props = defineProps<Props>()
const emit = defineEmits<{ update: [] }>()

const localStyle = computed(() => props.connection.style as Record<string, any>)

const { setStyleNumber } = useStyleHelpers(localStyle, emit)

// Two-way computed values
const entryXValue = computed({
  get: () => localStyle.value.entryX ?? '',
  set: (value) => setStyleNumber('entryX', value, { allowNegative: true })
})

const entryYValue = computed({
  get: () => localStyle.value.entryY ?? '',
  set: (value) => setStyleNumber('entryY', value, { allowNegative: true })
})

const entryDxValue = computed({
  get: () => localStyle.value.entryDx ?? '',
  set: (value) => setStyleNumber('entryDx', value, { allowNegative: true })
})

const entryDyValue = computed({
  get: () => localStyle.value.entryDy ?? '',
  set: (value) => setStyleNumber('entryDy', value, { allowNegative: true })
})

const exitXValue = computed({
  get: () => localStyle.value.exitX ?? '',
  set: (value) => setStyleNumber('exitX', value, { allowNegative: true })
})

const exitYValue = computed({
  get: () => localStyle.value.exitY ?? '',
  set: (value) => setStyleNumber('exitY', value, { allowNegative: true })
})

const exitDxValue = computed({
  get: () => localStyle.value.exitDx ?? '',
  set: (value) => setStyleNumber('exitDx', value, { allowNegative: true })
})

const exitDyValue = computed({
  get: () => localStyle.value.exitDy ?? '',
  set: (value) => setStyleNumber('exitDy', value, { allowNegative: true })
})

const sourcePerimeterSpacingValue = computed({
  get: () => localStyle.value.sourcePerimeterSpacing ?? '',
  set: (value) => setStyleNumber('sourcePerimeterSpacing', value, { min: 0, allowNegative: false })
})

const targetPerimeterSpacingValue = computed({
  get: () => localStyle.value.targetPerimeterSpacing ?? '',
  set: (value) => setStyleNumber('targetPerimeterSpacing', value, { min: 0, allowNegative: false })
})
</script>
