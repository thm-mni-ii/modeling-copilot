<template>
  <div class="d-flex flex-column ga-4">
    <div>
      <div class="text-subtitle-2 mb-1">Route: connection points</div>
      <p class="text-caption text-medium-emphasis mb-2">Where the connection may start ({{ sourceType }}) and end ({{ targetType }}). Empty = any point.</p>
      <div v-for="(pair, index) in visiblePairs" :key="index" class="mb-3">
        <div v-if="endpointPairs !== undefined && (endpointPairs.length || visiblePairs.length > 1)" class="d-flex align-center justify-space-between mb-2">
          <span class="text-subtitle-2">Point combination {{ index + 1 }}</span>
          <v-btn icon="mdi-delete" variant="text" size="small" :disabled="disabled" aria-label="Remove point combination" @click="removePair(index)" />
        </div>
        <div class="route-grid">
          <ConnectionPointSelector :model-value="pair.source" :element="sourceElement" :label="`${sourceType} start points`" :disabled="disabled" @update:model-value="setSelector(index, 'source', $event)" />
          <ConnectionPointSelector :model-value="pair.target" :element="targetElement" :label="`${targetType} end points`" :disabled="disabled" @update:model-value="setSelector(index, 'target', $event)" />
        </div>
      </div>
      <v-btn v-if="endpointPairs !== undefined" variant="tonal" prepend-icon="mdi-plus" size="small" :disabled="disabled" @click="emit('update:endpointPairs', [...visiblePairs, { source: {}, target: {} }])">Add point combination</v-btn>
      <p v-if="visiblePairs.length > 1" class="text-caption text-medium-emphasis mt-2 mb-0">A connection must match one complete source and target combination.</p>
    </div>
    <div class="route-grid">
      <ConnectionTypeSelect
        :model-value="rule.connectionTypes"
        :items="connectionOptions"
        label="Allowed connection types"
        placeholder="All connection types"
        persistent-placeholder
        multiple
        clearable
        :disabled="disabled"
        hint="Empty selection allows all connection types."
        @update:model-value="emit('patch', { connectionTypes: Array.isArray($event) ? $event : $event ? [$event] : [] })"
      />
      <CardinalityFields :model-value="rule.cardinality" :label="`Connections per ${sourceType}`" :hint="`How many connections one ${sourceType} may have to all matching ${targetType} elements together.`" :disabled="disabled" @update:model-value="emit('patch', { cardinality: $event })" />
    </div>
    <v-expansion-panels variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon size="18" class="mr-2">mdi-counter</v-icon>
          <div class="d-flex flex-column">
            <span>More limits</span>
            <span class="text-caption text-medium-emphasis">Per {{ targetType }}: {{ summary(rule.targetCardinality) }} · Per pair: {{ summary(rule.pairCardinality) }}</span>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <CardinalityFields :model-value="rule.targetCardinality ?? unlimited" :label="`Connections per ${targetType}`" :hint="`How many connections one ${targetType} may receive from all matching ${sourceType} elements together.`" :disabled="disabled" @update:model-value="emit('patch', { targetCardinality: $event })" />
          <CardinalityFields :model-value="rule.pairCardinality ?? unlimited" :label="`Connections per ${sourceType}–${targetType} pair`" hint="Between one specific source and one specific target. The minimum only applies to pairs that are already connected." :disabled="disabled" class="mt-4" @update:model-value="emit('patch', { pairCardinality: $event })" />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { EndpointSelector, MultiplicityCardinality } from '@/model/Syntax'
import CardinalityFields from './CardinalityFields.vue'
import ConnectionPointSelector from './ConnectionPointSelector.vue'
import ConnectionTypeSelect from './ConnectionTypeSelect.vue'

export interface RouteRuleValues {
  connectionTypes: string[]
  cardinality: MultiplicityCardinality
  targetCardinality?: MultiplicityCardinality
  pairCardinality?: MultiplicityCardinality
}

type EndpointPair = { source: EndpointSelector; target: EndpointSelector }
const props = defineProps<{ rule: RouteRuleValues; source: EndpointSelector; target: EndpointSelector; endpointPairs?: EndpointPair[]; sourceType: string; targetType: string; connectionOptions: string[]; disabled?: boolean }>()
const emit = defineEmits<{ patch: [values: Partial<RouteRuleValues>]; 'update:source': [value: EndpointSelector]; 'update:target': [value: EndpointSelector]; 'update:endpointPairs': [value: EndpointPair[]] }>()
const visiblePairs = computed(() => props.endpointPairs?.length ? props.endpointPairs : [{ source: props.source, target: props.target }])
const setSelector = (index: number, end: 'source' | 'target', value: EndpointSelector) => {
  if (props.endpointPairs !== undefined) {
    emit('update:endpointPairs', visiblePairs.value.map((pair, i) => i === index ? { ...pair, [end]: value } : pair))
  } else if (end === 'source') emit('update:source', value)
  else emit('update:target', value)
}
const removePair = (index: number) => emit('update:endpointPairs', visiblePairs.value.filter((_, i) => i !== index))
const store = useDiagramLanguages()
const elements = computed(() => store.definition?.elements ?? [])
const sourceElement = computed(() => elements.value.find((e) => e.type === props.sourceType))
const targetElement = computed(() => elements.value.find((e) => e.type === props.targetType))
const unlimited: MultiplicityCardinality = { min: 0, max: null }
const summary = (bounds?: MultiplicityCardinality) => `${bounds?.min ?? 0}…${bounds?.max ?? '∞'}`
</script>

<style scoped>
.route-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 16px;
}
@media (max-width: 1100px) {
  .route-grid {
    grid-template-columns: 1fr;
  }
}
</style>
