<template>
  <v-sheet class="template-field">
    <div class="d-flex align-center justify-space-between flex-wrap ga-2">
      <h3 class="text-h6">{{ title }}</h3>
      <v-chip size="small" variant="tonal">{{ value?.trim() && value !== fallback ? 'Configured' : 'Uses default' }}</v-chip>
    </div>
    <p class="text-body-2 text-medium-emphasis mt-1 mb-5">{{ description }}</p>
    <div class="template-workspace">
      <div class="template-input">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <h4 class="text-subtitle-2">Message template</h4>
          <v-btn size="small" variant="text" prepend-icon="mdi-restore" :aria-label="`Use default for ${title}`" :disabled="disabled || !value?.trim()" @click="emit('update:value', '')">Use default</v-btn>
        </div>
        <v-textarea
          :model-value="effectiveValue"
          :placeholder="fallback"
          :label="`${title} template`"
          rows="3"
          auto-grow
          density="compact"
          variant="outlined"
          :disabled="disabled"
          hint="Empty uses the default. Templates are saved with the language version."
          persistent-hint
          @update:model-value="emit('update:value', $event ?? '')"
        />
        <p v-if="unknownPlaceholders.length" class="text-body-2 text-warning mt-2" role="status">
          Unrecognized placeholders: {{ unknownPlaceholders.join(', ') }}. They will appear unchanged in the message.
        </p>
        <div v-if="placeholders.length" class="mt-5">
          <h4 class="text-subtitle-2 mb-1">Add placeholder</h4>
          <p class="text-caption text-medium-emphasis mb-2">Click to append to the message.</p>
          <div class="d-flex flex-wrap ga-2">
            <v-btn v-for="name in placeholders" :key="name" size="small" variant="tonal" class="placeholder-button" :aria-label="`Add ${name} placeholder to ${title}`" :disabled="disabled" @click="emit('update:value', `${effectiveValue}{${name}}`)">
              {{ '{' + name + '}' }}
            </v-btn>
          </div>
        </div>
        <p v-else class="text-caption text-medium-emphasis mt-4">No placeholders available for this template.</p>
        <div class="mt-5 pt-4 border-t">
          <h4 class="text-subtitle-2 mb-2">Default</h4>
          <p class="text-body-2 text-medium-emphasis template-message mb-0">{{ fallback }}</p>
        </div>
      </div>
      <v-sheet border rounded="lg" class="pa-4 template-example">
        <div class="d-flex align-center ga-2 mb-3">
          <v-icon icon="mdi-message-text-outline" size="small" />
          <h4 class="text-subtitle-2">Example</h4>
        </div>
        <p class="text-body-2 template-message mb-3" aria-live="polite">{{ preview }}</p>
        <p class="text-caption text-medium-emphasis mb-0">Example values illustrate one possible validation result.</p>
      </v-sheet>
    </div>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Cell } from '@maxgraph/core'
import { renderAcyclicMessage, renderCycleRequiredMessage } from '@/utils/acyclic'
import { renderTemplate, renderValidationIssue } from '@/utils/syntaxMessages'

const props = defineProps<{
  title: string
  description: string
  value?: string
  fallback: string
  placeholders: readonly string[]
  kind?: 'connection' | 'quantity' | 'cycle'
  connectionCode?: 'connection.forbidden' | 'connection.type' | 'connection.endpoint'
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:value': [value: string] }>()
const effectiveValue = computed(() => props.value?.trim() ? props.value : props.fallback)
const examples: Record<string, string> = { source: 'Source type', target: 'Target type', sourceLabel: 'Source', targetLabel: 'Target', sourcePoint: 'Point A', targetPoint: 'Point B', allowedPoints: 'source point A and target point B', allowedConnections: 'Connection', connection: 'Connection', element: 'Element', elementLabel: 'Element', container: 'Container', other: '-', direction: 'outgoing', point: '*', scope: 'source', route: '-', count: '0', min: '1', max: '2' }
const source = Object.assign(new Cell('Source'), { diagramElementType: 'Source type' })
const target = Object.assign(new Cell('Target'), { diagramElementType: 'Target type' })
const preview = computed(() => {
  const template = effectiveValue.value
  if (props.kind === 'quantity') return renderValidationIssue({
    kind: 'quantity', code: 'quantity.minimum', cell: source, template, values: { ...examples },
    quantity: { count: 0, bounds: { min: 1, max: 2 }, scope: 'source', direction: 'outgoing', connections: ['Connection'], neighbors: ['Target type'] }
  })
  if (props.kind === 'connection') return renderValidationIssue({ kind: 'connection', code: props.connectionCode ?? 'connection.forbidden', source, target, template, values: examples })
  if (props.kind === 'cycle') return props.placeholders.includes('source') ? renderAcyclicMessage(template, source, target).trim() : renderCycleRequiredMessage(template, props.placeholders.includes('element') ? source : undefined).trim()
  return renderTemplate(template, examples)
})
const unknownPlaceholders = computed(() => {
  const placeholders = [...effectiveValue.value.matchAll(/\{([^{}]+)\}/g)].map((match) => match[0])
  return [...new Set(placeholders.filter((placeholder) => !props.placeholders.includes(placeholder.slice(1, -1))))]
})
</script>

<style scoped>
.template-workspace {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(220px, 2fr);
  align-items: start;
  gap: 24px;
}

.template-input {
  min-width: 0;
}

.placeholder-button {
  text-transform: none;
  letter-spacing: normal;
}

.template-example {
  background: rgba(var(--v-theme-on-surface), 0.03);
}

.template-message {
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

@media (max-width: 1200px) {
  .template-workspace {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
