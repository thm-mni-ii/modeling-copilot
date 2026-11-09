<template>
  <div class="feedback-form">
    <v-alert type="info" variant="tonal" density="comfortable" class="mb-4"> Configure the overlay for each state (icon, position, tooltip, and cursor). </v-alert>

    <v-expansion-panels variant="accordion" multiple>
      <v-expansion-panel v-for="state in stateDefinitions" :key="state.key">
        <v-expansion-panel-title>
          <v-icon :color="state.color" class="mr-2">{{ state.icon }}</v-icon>
          {{ state.label }}
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="state-section">
            <v-select
              :model-value="config[state.key].icon != null ? 'icon' : 'image'"
              :items="[
                { title: 'Material Design Icon', value: 'icon' },
                { title: 'Image (legacy)', value: 'image' }
              ]"
              label="Overlay type"
              variant="outlined"
              density="comfortable"
              hide-details
              @update:model-value="setOverlayType(state.key, $event)"
            />
            <v-row v-if="config[state.key].icon != null" dense>
              <v-col cols="12" sm="8">
                <v-text-field v-model="config[state.key].icon" label="MDI icon name" placeholder="mdi-check-circle-outline" hint="Enter an icon name from the installed Material Design Icons palette." persistent-hint :error-messages="iconError(state.key)" variant="outlined" density="comfortable" @update:model-value="emitUpdate" />
              </v-col>
              <v-col cols="12" sm="4">
                <v-text-field v-model="config[state.key].color" label="Color (hex)" placeholder="#4CAF50" :rules="[(value) => /^#[0-9a-f]{6}$/i.test(value ?? '') || 'Use a six-digit hex color.']" variant="outlined" density="comfortable" @update:model-value="emitUpdate">
                  <template #prepend-inner><input v-model="config[state.key].color" type="color" class="overlay-color-input" aria-label="Overlay color" @input="emitUpdate" /></template>
                </v-text-field>
              </v-col>
            </v-row>
            <v-row dense>
              <v-col v-if="config[state.key].icon == null" cols="12" sm="6">
                <v-combobox v-model="config[state.key].image.src" :items="overlayImageOptions" item-title="title" item-value="value" label="Overlay Image" density="comfortable" variant="outlined" clearable :return-object="false" @update:model-value="emitUpdate" />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="config[state.key].image.width" label="Width (px)" type="number" min="8" max="96" density="comfortable" variant="outlined" @input="emitUpdate" />
              </v-col>
              <v-col cols="6" sm="3">
                <v-text-field v-model.number="config[state.key].image.height" label="Height (px)" type="number" min="8" max="96" density="comfortable" variant="outlined" @input="emitUpdate" />
              </v-col>
            </v-row>

            <div class="d-flex align-center ga-3">
              <span class="text-caption">Preview</span>
              <div class="overlay-preview">
                <svg v-if="config[state.key].icon != null && !iconError(state.key)" :width="config[state.key].image.width" :height="config[state.key].image.height" :viewBox="`0 0 ${config[state.key].image.width} ${config[state.key].image.height}`" role="img" :aria-label="`${state.label} overlay preview`">
                  <circle cx="50%" cy="50%" :r="Math.min(config[state.key].image.width, config[state.key].image.height) / 2" fill="#FFFFFF" />
                  <text x="50%" y="50%" dominant-baseline="central" text-anchor="middle" font-family="Material Design Icons" :font-size="Math.min(config[state.key].image.width, config[state.key].image.height)" :fill="config[state.key].color ?? '#000000'">{{ getMdiGlyph(config[state.key].icon!) }}</text>
                </svg>
                <img v-else-if="config[state.key].icon == null && config[state.key].image.src" :src="config[state.key].image.src" :width="config[state.key].image.width" :height="config[state.key].image.height" :alt="`${state.label} overlay preview`" />
                <span v-else class="text-caption">No preview</span>
              </div>
            </div>

            <section class="mb-2">
              <div class="d-flex align-center justify-space-between mb-2">
                <span class="section-label">Positioning</span>
                <v-chip :color="positionModeMeta[overlayDisplayMode[state.key]].color" variant="tonal" size="small" class="text-uppercase font-weight-medium">
                  <v-icon size="16" class="mr-1">{{ positionModeMeta[overlayDisplayMode[state.key]].icon }}</v-icon>
                  {{ positionModeMeta[overlayDisplayMode[state.key]].label }}
                </v-chip>
              </div>
              <v-btn-toggle v-model="overlayDisplayMode[state.key]" mandatory class="w-100 mb-2" rounded="lg">
                <v-btn v-for="mode in positionModeOptions" :key="mode.value" :value="mode.value" :color="overlayDisplayMode[state.key] === mode.value ? mode.color : undefined" variant="tonal" class="flex-grow-1 text-none">
                  <v-icon size="16" class="mr-1">{{ mode.icon }}</v-icon>
                  {{ mode.label }}
                </v-btn>
              </v-btn-toggle>
              <div class="text-caption">{{ positionModeMeta[overlayDisplayMode[state.key]].description }}</div>
            </section>

            <div v-if="overlayDisplayMode[state.key] === 'alignment'" class="alignment-fields">
              <v-select v-model="config[state.key].align" :items="alignOptions" label="Horizontal Alignment" density="comfortable" variant="outlined" @update:model-value="emitUpdate" />
              <v-select v-model="config[state.key].verticalAlign" :items="verticalAlignOptions" label="Vertical Alignment" density="comfortable" variant="outlined" @update:model-value="emitUpdate" />
            </div>

            <div v-else-if="config[state.key].offset" class="offset-fields">
              <v-text-field v-model.number="config[state.key].offset!.x" label="Offset X" type="number" density="comfortable" variant="outlined" @input="emitUpdate" />
              <v-text-field v-model.number="config[state.key].offset!.y" label="Offset Y" type="number" density="comfortable" variant="outlined" @input="emitUpdate" />
            </div>

            <v-row dense>
              <v-col cols="6">
                <v-text-field v-model="config[state.key].tooltip" label="Tooltip" density="comfortable" variant="outlined" @input="emitUpdate" />
              </v-col>
              <v-col cols="6">
                <v-combobox v-model="config[state.key].cursor" :items="cursorOptions" item-title="title" item-value="value" label="Cursor" density="comfortable" variant="outlined" clearable :return-object="false" @update:model-value="emitUpdate" />
              </v-col>
            </v-row>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { reactive, toRef } from 'vue'
import type { FeedbackState, FeedbackTargetOverlays } from '@/model/Feedback'
import { createDefaultFeedbackOverlay } from '@/utils/feedbackConfig'
import { getMdiGlyph } from '@/utils/feedbackOverlays'

interface StateDefinition {
  key: FeedbackState
  label: string
  shortLabel: string
  color: string
  icon: string
}

interface Props {
  config: FeedbackTargetOverlays
  stateDefinitions: StateDefinition[]
}

type OverlayPositionMode = 'alignment' | 'offset'

interface PositionModeOption {
  value: OverlayPositionMode
  label: string
  description: string
  icon: string
  color: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  update: []
}>()

const config = toRef(props, 'config')

const iconError = (state: FeedbackState) => (config.value[state].icon != null && !getMdiGlyph(config.value[state].icon!) ? 'Enter an available MDI icon, for example mdi-check-circle-outline.' : '')

const setOverlayType = (state: FeedbackState, type: string) => {
  const overlay = config.value[state]
  if (type === 'icon') {
    const defaults = createDefaultFeedbackOverlay(state)
    overlay.icon = defaults.icon
    overlay.color = defaults.color
  } else {
    overlay.icon = null
    overlay.color = null
    overlay.image.src ||= { correct: '/images/checkmark.gif', incorrect: '/images/error.gif', hint: '/images/warning.gif' }[state]
  }
  emitUpdate()
}

const alignOptions = [
  { title: 'Left', value: 'left' },
  { title: 'Center', value: 'center' },
  { title: 'Right', value: 'right' }
]

const verticalAlignOptions = [
  { title: 'Top', value: 'top' },
  { title: 'Middle', value: 'middle' },
  { title: 'Bottom', value: 'bottom' }
]

const overlayImageOptions = [
  { title: 'Green Checkmark (checkmark)', value: '/images/checkmark.gif' },
  { title: 'Red Cross (cross)', value: '/images/cross.gif' },
  { title: 'Error (error)', value: '/images/error.gif' },
  { title: 'Small Error (small_error)', value: '/images/small_error.gif' },
  { title: 'Warning (warning)', value: '/images/warning.gif' },
  { title: 'Help (help)', value: '/images/help.gif' },
  { title: 'Green Dot (green-dot)', value: '/images/green-dot.gif' },
  { title: 'Info/Link (small_link)', value: '/images/small_link.gif' }
]

const cursorOptions = [
  { title: 'Default (default)', value: 'default' },
  { title: 'Pointer (pointer)', value: 'pointer' },
  { title: 'Help (help)', value: 'help' },
  { title: 'Move (move)', value: 'move' },
  { title: 'Text (text)', value: 'text' },
  { title: 'Wait (wait)', value: 'wait' },
  { title: 'Crosshair (crosshair)', value: 'crosshair' },
  { title: 'Not Allowed (not-allowed)', value: 'not-allowed' },
  { title: 'Grab (grab)', value: 'grab' },
  { title: 'Grabbing (grabbing)', value: 'grabbing' }
]

const positionModeOptions: PositionModeOption[] = [
  {
    value: 'alignment',
    label: 'Alignment',
    description: 'Set the position using horizontal and vertical alignment.',
    icon: 'mdi-select-compare',
    color: 'primary'
  },
  {
    value: 'offset',
    label: 'Offset',
    description: 'Fine-tune the position with X and Y values.',
    icon: 'mdi-cursor-move',
    color: 'teal-darken-2'
  }
]

const positionModeMeta = positionModeOptions.reduce(
  (acc, option) => {
    acc[option.value] = option
    return acc
  },
  {} as Record<OverlayPositionMode, PositionModeOption>
)

const overlayDisplayMode = reactive<Record<FeedbackState, OverlayPositionMode>>({
  correct: 'alignment',
  incorrect: 'alignment',
  hint: 'alignment'
})

const emitUpdate = () => {
  emit('update')
}
</script>

<style scoped>
.feedback-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overlay-color-input {
  width: 28px;
  height: 28px;
  border: 0;
  cursor: pointer;
}

.overlay-preview {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 112px;
  min-height: 112px;
  padding: 8px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
}

.state-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.alignment-fields,
.offset-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
</style>
