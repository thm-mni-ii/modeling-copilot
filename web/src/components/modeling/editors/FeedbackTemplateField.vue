<template>
  <v-sheet border rounded="lg" class="pa-4">
    <div class="d-flex align-center justify-space-between flex-wrap ga-2">
      <h3 class="text-subtitle-1 font-weight-bold">{{ title }}</h3>
      <v-chip size="small" variant="tonal">{{ value?.trim() ? 'Configured' : 'Uses default' }}</v-chip>
    </div>
    <p class="text-body-2 text-medium-emphasis mt-1">{{ description }}</p>
    <v-textarea
      :model-value="value ?? ''"
      :placeholder="fallback"
      :label="`${title} template`"
      rows="2"
      auto-grow
      density="compact"
      variant="outlined"
      :disabled="disabled"
      :hint="`Available placeholders: ${placeholders.length ? placeholders.map((name) => `{${name}}`).join(', ') : 'none'}. Empty uses the default.`"
      persistent-hint
      @update:model-value="emit('update:value', $event ?? '')"
    />
    <p class="text-caption text-medium-emphasis mt-2 mb-0"><strong>Default:</strong> {{ fallback }}</p>
    <p v-if="unknownPlaceholders.length" class="text-body-2 text-warning mt-2" role="status">
      Unrecognized placeholders: {{ unknownPlaceholders.join(', ') }}. They will appear unchanged in the message.
    </p>
    <div class="d-flex flex-wrap align-center ga-2 mt-3">
      <span v-if="placeholders.length" class="text-caption">Add placeholder at end:</span>
      <v-btn v-for="name in placeholders" :key="name" size="small" variant="tonal" :aria-label="`Add ${name} placeholder to ${title}`" :disabled="disabled" @click="emit('update:value', `${effectiveValue}{${name}}`)">
        {{ name }}
      </v-btn>
      <v-spacer />
      <v-btn size="small" variant="text" :aria-label="`Use default for ${title}`" :disabled="disabled || !value?.trim()" @click="emit('update:value', '')">Use default</v-btn>
    </div>
    <div class="mt-3 text-body-2">
      <strong>Example:</strong> {{ preview }}
    </div>
    <p class="text-caption text-medium-emphasis mb-0">Example values illustrate the template only; the validator may add context to the final message.</p>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  title: string
  description: string
  value?: string
  fallback: string
  placeholders: string[]
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:value': [value: string] }>()
const effectiveValue = computed(() => props.value?.trim() ? props.value : props.fallback)
const examples: Record<string, string> = { source: 'Source', target: 'Target', connection: 'Connection', element: 'Element', min: '1', max: '2' }
const preview = computed(() => effectiveValue.value.replace(/\{([^{}]+)\}/g, (match, name: string) => props.placeholders.includes(name) ? examples[name] ?? match : match))
const unknownPlaceholders = computed(() => {
  const placeholders = [...effectiveValue.value.matchAll(/\{([^{}]+)\}/g)].map((match) => match[0])
  return [...new Set(placeholders.filter((placeholder) => !props.placeholders.includes(placeholder.slice(1, -1))))]
})
</script>
