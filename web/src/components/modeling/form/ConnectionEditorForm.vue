<template>
  <div>
    <!-- Grundeinstellungen -->
    <v-text-field v-model="connection.label" label="Name" variant="outlined" density="compact" class="mb-3" hint="Connection identifier in the language definition." persistent-hint @input="triggerUpdate" />
    <v-text-field v-model="connection.type" label="Connection Type" variant="outlined" density="compact" class="mb-4" hint="Technical type used for imports and rules." persistent-hint @input="triggerUpdate" />
    <v-switch v-model="connection.undirected" label="Undirected connection" hint="Swapping the ends preserves the meaning. Input/output roles do not restrict this connection." persistent-hint color="primary" density="compact" class="mb-4" @update:model-value="triggerUpdate" />

    <!-- Einstellungsumfang -->
    <section class="mb-4">
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="section-label">Settings Level</span>
        <v-chip :color="currentLevelMeta.color" variant="tonal" size="small" class="text-uppercase font-weight-medium">
          <v-icon size="16" class="mr-1">{{ currentLevelMeta.icon }}</v-icon>
          {{ currentLevelMeta.label }}
        </v-chip>
      </div>
      <v-btn-toggle v-model="complexity" mandatory class="w-100 mb-2" rounded="lg">
        <v-btn v-for="option in complexityLevels" :key="option.value" :value="option.value" :color="complexity === option.value ? option.color : undefined" variant="tonal" class="flex-grow-1 text-none">
          {{ option.label }}
        </v-btn>
      </v-btn-toggle>
      <div class="text-caption">{{ currentLevelMeta.description }}</div>
    </section>

    <!-- Vorschau -->
    <section class="mb-6">
      <div class="d-flex align-center justify-space-between mb-2">
        <span class="section-label">Preview</span>
      </div>
      <v-btn-toggle v-model="previewModeModel" mandatory class="w-100 mb-2" rounded="lg">
        <v-btn v-for="option in previewOptions" :key="option.value" :value="option.value" :color="previewModeModel === option.value ? option.color : undefined" variant="tonal" class="preview-mode-btn text-none">
          <v-icon size="18" class="mr-2">{{ option.icon }}</v-icon>
          {{ option.label }}
        </v-btn>
      </v-btn-toggle>
      <div class="text-caption">{{ previewDescription }}</div>
    </section>

    <!-- Panels -->
    <v-expansion-panels variant="accordion">
      <!-- Line & Marker Panel -->
      <v-expansion-panel value="line-marker">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-arrow-right-bold</v-icon>
          Line & Markers
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionLineMarkerPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Routing Panel -->
      <v-expansion-panel value="routing">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-map-marker-path</v-icon>
          Path & Routing
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionRoutingPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Label Panel -->
      <v-expansion-panel value="label">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-format-text</v-icon>
          Label
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionLabelPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Additional Labels Panel -->
      <v-expansion-panel value="additional-labels">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-label-multiple</v-icon>
          Additional Labels
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionAdditionalLabelsPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Interaction Panel -->
      <v-expansion-panel v-if="visibility.isVisible({ minComplexity: 'advanced' })" value="interaction">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-gesture-tap</v-icon>
          Interaction & Visibility
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionInteractionPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Ports Panel -->
      <v-expansion-panel v-if="visibility.isVisible({ minComplexity: 'advanced' })" value="ports">
        <v-expansion-panel-title>
          <v-icon class="mr-2">mdi-dock-window</v-icon>
          Ports & Attachments
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ConnectionPortsPanel :connection="connection" :visibility-context="visibilityContext" @update="triggerUpdate" />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed, provide, reactive, ref, watch } from 'vue'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import type { ConnectionPreviewMode } from '@/utils/connectionPreview'
import type { ComplexityLevel, VisibilityContext } from './config/fieldVisibility'
import { complexityLevels, createVisibilityChecker } from './config/fieldVisibility'
import ConnectionRoutingPanel from './panels/ConnectionRoutingPanel.vue'
import ConnectionPortsPanel from './panels/ConnectionPortsPanel.vue'
import ConnectionLineMarkerPanel from './panels/ConnectionLineMarkerPanel.vue'
import ConnectionLabelPanel from './panels/ConnectionLabelPanel.vue'
import ConnectionInteractionPanel from './panels/ConnectionInteractionPanel.vue'
import ConnectionAdditionalLabelsPanel from './panels/ConnectionAdditionalLabelsPanel.vue'

type PreviewMode = ConnectionPreviewMode

interface Props {
  selectedConnection: DiagramConnection
  previewMode: PreviewMode
}

const props = defineProps<Props>()

const emit = defineEmits<{
  update: []
  'update:previewMode': [PreviewMode]
}>()

const connection = computed(() => props.selectedConnection)

const triggerUpdate = () => {
  emit('update')
}

// Complexity Management
const complexity = ref<ComplexityLevel>('basic')
const currentLevelMeta = computed(() => complexityLevels.find((l) => l.value === complexity.value) ?? complexityLevels[0])

// Visibility Context - als reactive object für provide/inject
const visibilityContext: VisibilityContext = reactive({
  complexity: complexity.value
})

// Synchronisiere die Complexity-Änderungen mit dem Context
watch(complexity, (newComplexity) => {
  visibilityContext.complexity = newComplexity
})

// Stelle visibilityContext für alle Child-Komponenten bereit
provide('visibilityContext', visibilityContext)

const visibility = computed(() => createVisibilityChecker(visibilityContext))

// Preview Mode
const previewModeModel = computed<PreviewMode>({
  get: () => props.previewMode,
  set: (value) => emit('update:previewMode', value)
})

const previewOptions = [
  { label: 'Simple Arrow', value: 'simple' as PreviewMode, icon: 'mdi-vector-line', color: 'primary' },
  { label: 'Scenario', value: 'scenario' as PreviewMode, icon: 'mdi-animation-outline', color: 'secondary' },
  { label: 'Routing Demo', value: 'routing' as PreviewMode, icon: 'mdi-graph-outline', color: 'accent' }
]

const previewDescriptions: Record<PreviewMode, string> = {
  simple: 'Shows a single arrow with the current settings.',
  scenario: 'Visualizes a sample scenario with multiple actors and flows.',
  routing: 'Demonstrates different routing algorithms and Connection paths.'
}

const previewDescription = computed(() => previewDescriptions[previewModeModel.value])
</script>

<style scoped>
.section-label {
  font-size: 0.75rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--v-theme-on-surface-variant);
}

.preview-mode-btn {
  min-width: 140px;
}
</style>
