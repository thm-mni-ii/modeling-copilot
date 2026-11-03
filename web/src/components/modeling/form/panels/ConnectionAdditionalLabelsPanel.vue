<template>
  <div>
    <div class="d-flex align-center justify-space-between mb-3">
      <div class="text-subtitle-2 font-weight-medium">Additional Labels</div>
      <v-btn color="primary" variant="tonal" size="small" class="text-none" @click="addLabel">
        <v-icon size="18" class="mr-1">mdi-plus</v-icon>
        Add Label
      </v-btn>
    </div>

    <v-alert v-if="labels.length === 0" type="info" variant="tonal" density="comfortable" class="mb-4"> No additional labels defined. Use “Add Label” to place more text labels along the Connection. </v-alert>

    <v-expansion-panels v-else multiple>
      <v-expansion-panel v-for="(label, index) in labels" :key="index" class="mb-3">
        <v-expansion-panel-title>
          <div class="d-flex align-center justify-space-between w-100">
            <div class="text-body-2 font-weight-medium">
              {{ label.id }}
              <span class="text-caption text-medium-emphasis ml-2">{{ previewText(label) }}</span>
            </div>
            <v-btn icon="mdi-delete" color="error" variant="text" size="small" @click.stop="removeLabel(index)" />
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="mb-4">
            <FieldWithIndicator>
              <v-text-field v-model="label.id" label="Label ID" variant="outlined" density="compact" hint="Unique identifier used as the cell ID on the canvas." persistent-hint />
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <v-text-field v-model="label.text" label="Label Text" variant="outlined" density="compact" hint="Displayed text of this additional label." persistent-hint />
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <v-switch v-model="label.geometry.relative" color="primary" density="compact" label="Relative Geometry" hint="When enabled, the position uses relative values along the Connection." persistent-hint />
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <div class="text-caption mb-2">Relative Position (along the Connection)</div>
              <v-row dense>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.x" type="number" step="0.05" label="Relative X" variant="outlined" density="compact" hint="0 = center, 0.5 = toward target, -0.5 = toward source." persistent-hint />
                </v-col>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.y" type="number" step="0.05" label="Relative Y" variant="outlined" density="compact" hint="Positive moves down and negative moves up relative to the Connection." persistent-hint />
                </v-col>
              </v-row>
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <div class="text-caption mb-2">Pixel-Offset</div>
              <v-row dense>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.offsetX" type="number" step="1" label="Offset X" variant="outlined" density="compact" hint="Horizontal offset in pixels." persistent-hint />
                </v-col>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.offsetY" type="number" step="1" label="Offset Y" variant="outlined" density="compact" hint="Vertical offset in pixels." persistent-hint />
                </v-col>
              </v-row>
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <div class="text-caption mb-2">Fixed Size (optional)</div>
              <v-row dense>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.width" type="number" step="1" label="Width" variant="outlined" density="compact" hint="0 = automatic width." persistent-hint />
                </v-col>
                <v-col cols="6">
                  <v-text-field v-model.number="label.geometry.height" type="number" step="1" label="Height" variant="outlined" density="compact" hint="0 = automatic height." persistent-hint />
                </v-col>
              </v-row>
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <ColorPickerField v-model="label.style.fontColor" label="Font Color" hint="Color of the label text." @update:model-value="triggerUpdate" />
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator>
              <v-slider v-model.number="label.style.fontSize" :min="6" :max="48" :step="1" label="Font Size" class="mb-2" hint="Font size in pixels (6–48)." persistent-hint thumb-label>
                <template #append>
                  <span class="text-caption">{{ label.style.fontSize ?? 12 }} px</span>
                </template>
              </v-slider>
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <div class="text-caption mb-2">Horizontal Alignment</div>
              <v-btn-toggle v-model="label.style.align" color="primary" mandatory variant="outlined" divided class="d-flex">
                <v-btn value="left" class="flex-grow-1">
                  <v-icon>mdi-format-align-left</v-icon>
                  Left
                </v-btn>
                <v-btn value="center" class="flex-grow-1">
                  <v-icon>mdi-format-align-center</v-icon>
                  Center
                </v-btn>
                <v-btn value="right" class="flex-grow-1">
                  <v-icon>mdi-format-align-right</v-icon>
                  Right
                </v-btn>
              </v-btn-toggle>
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <div class="text-caption mb-2">Vertical Alignment</div>
              <v-btn-toggle v-model="label.style.verticalAlign" color="primary" mandatory variant="outlined" divided class="d-flex">
                <v-btn value="top" class="flex-grow-1">
                  <v-icon>mdi-arrow-up</v-icon>
                  Top
                </v-btn>
                <v-btn value="middle" class="flex-grow-1">
                  <v-icon>mdi-minus</v-icon>
                  Middle
                </v-btn>
                <v-btn value="bottom" class="flex-grow-1">
                  <v-icon>mdi-arrow-down</v-icon>
                  Bottom
                </v-btn>
              </v-btn-toggle>
            </FieldWithIndicator>
          </div>

          <div class="mb-2">
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <ColorPickerField v-model="label.style.labelBackgroundColor" label="Background Color" hint="Optional background behind the additional label." @update:model-value="triggerUpdate" />
            </FieldWithIndicator>
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <v-text-field v-model.number="label.style.labelPadding" label="Label Padding" variant="outlined" density="compact" type="number" min="0" step="1" suffix="px" hint="Space between the label text and the edge of its background." persistent-hint class="mt-2" @update:model-value="triggerUpdate" />
            </FieldWithIndicator>
          </div>

          <div class="mb-4">
            <FieldWithIndicator :config="{ minComplexity: 'advanced' }">
              <ColorPickerField v-model="label.style.labelBorderColor" label="Border Color" hint="Optional border around the additional label." @update:model-value="triggerUpdate" />
            </FieldWithIndicator>
          </div>

          <div class="d-flex align-center" style="gap: 16px">
            <v-switch v-model="label.connectable" color="primary" density="compact" label="Connectable" />
            <v-switch v-model="label.allowLabelEdit" color="primary" density="compact" label="Label Editable" />
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import type { ConnectionLabelCell, DiagramConnection } from '@/model/Connection'
import type { VisibilityContext } from '../config/fieldVisibility'
import FieldWithIndicator from './FieldWithIndicator.vue'
import ColorPickerField from '../ColorPickerField.vue'

interface Props {
  connection: DiagramConnection
  visibilityContext: VisibilityContext
}

const props = defineProps<Props>()
const emit = defineEmits<{ update: [] }>()

const connection = computed(() => props.connection)

type NormalizedGeometry = {
  x: number
  y: number
  offsetX: number
  offsetY: number
  width: number
  height: number
  relative: boolean
}

type NormalizedStyle = Record<string, any> & {
  shape: string
  align: string
  verticalAlign: string
  fontColor: string
  fontSize: number
}

type NormalizedLabel = ConnectionLabelCell & {
  geometry: NormalizedGeometry
  style: NormalizedStyle
}

const ensureLabelDefaults = (label: ConnectionLabelCell): NormalizedLabel => {
  if (!label.type || label.type.trim().length === 0) {
    label.type = 'connection-label'
  }

  const trimmedId = typeof label.id === 'string' ? label.id.trim() : ''
  if (!trimmedId) {
    const index = connection.value.additionalLabels?.indexOf(label) ?? -1
    const fallbackIndex = index >= 0 ? index + 1 : (connection.value.additionalLabels?.length ?? 0) + 1
    // eslint-disable-next-line vue/no-mutating-props
    label.id = `Label ${fallbackIndex}`
  } else if (trimmedId !== label.id) {
    // eslint-disable-next-line vue/no-mutating-props
    label.id = trimmedId
  }
  if (!label.geometry) {
    // eslint-disable-next-line vue/no-mutating-props
    label.geometry = {
      x: 0,
      y: 0,
      offsetX: 0,
      offsetY: 0,
      width: 0,
      height: 0,
      relative: true
    }
  } else {
    if (label.geometry.x === undefined) label.geometry.x = 0
    if (label.geometry.y === undefined) label.geometry.y = 0
    if (label.geometry.offsetX === undefined) label.geometry.offsetX = 0
    if (label.geometry.offsetY === undefined) label.geometry.offsetY = 0
    if (label.geometry.width === undefined) label.geometry.width = 0
    if (label.geometry.height === undefined) label.geometry.height = 0
    if (label.geometry.relative === undefined) label.geometry.relative = true
  }

  if (!label.style) {
    // eslint-disable-next-line vue/no-mutating-props
    label.style = {
      shape: 'label',
      align: 'center',
      verticalAlign: 'middle',
      fontColor: connection.value.style.fontColor ?? '#000000',
      fontSize: connection.value.style.fontSize ?? 12
    }
  } else {
    if (label.style.shape === undefined) label.style.shape = 'label'
    if (label.style.align === undefined) label.style.align = 'center'
    if (label.style.verticalAlign === undefined) label.style.verticalAlign = 'middle'
    if (label.style.fontColor === undefined) label.style.fontColor = connection.value.style.fontColor ?? '#000000'
    if (label.style.fontSize === undefined) label.style.fontSize = connection.value.style.fontSize ?? 12
  }

  if (label.connectable === undefined) label.connectable = false
  if (label.allowLabelEdit === undefined) label.allowLabelEdit = true

  return label as NormalizedLabel
}

const ensureAllLabels = () => {
  if (!connection.value.additionalLabels) {
    // eslint-disable-next-line vue/no-mutating-props
    connection.value.additionalLabels = []
  }
  connection.value.additionalLabels.forEach((label, index) => {
    connection.value.additionalLabels![index] = ensureLabelDefaults(label)
  })
}

const labels = computed<NormalizedLabel[]>(() => (connection.value.additionalLabels ?? []) as NormalizedLabel[])

const addLabel = () => {
  const index = labels.value.length + 1
  if (!connection.value.additionalLabels) {
    // eslint-disable-next-line vue/no-mutating-props
    connection.value.additionalLabels = []
  }
  const newLabelId = `Label ${index}`
  const newLabel: NormalizedLabel = {
    id: newLabelId,
    type: 'connection-label',
    text: newLabelId,
    geometry: {
      x: 0,
      y: 0,
      offsetX: 0,
      offsetY: 0,
      width: 0,
      height: 0,
      relative: true
    },
    style: {
      shape: 'label',
      align: 'center',
      verticalAlign: 'middle',
      fontColor: connection.value.style.fontColor ?? '#000000',
      fontSize: connection.value.style.fontSize ?? 12
    },
    connectable: false,
    allowLabelEdit: true
  }

  connection.value.additionalLabels!.push(newLabel)
  emit('update')
}

const removeLabel = (index: number) => {
  labels.value.splice(index, 1)
  emit('update')
}

const triggerUpdate = () => {
  emit('update')
}

const previewText = (label: NormalizedLabel): string => {
  if (!label.text || label.text.trim().length === 0) {
    return '(no text)'
  }
  if (label.text.length > 24) {
    return `${label.text.slice(0, 24)}…`
  }
  return label.text
}

watch(
  labels,
  () => {
    emit('update')
  },
  { deep: true }
)

watch(
  () => connection.value.additionalLabels,
  () => {
    ensureAllLabels()
  },
  { immediate: true, deep: true }
)
</script>
