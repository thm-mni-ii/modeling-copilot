<template>
  <div>
    <div class="text-subtitle-2 mb-2">{{ label }}</div>
    <ConnectionPointMap
      v-if="!groupsOnly && element?.anchorPoints.length"
      :element="element"
      :markers="pointMarkers"
      :disabled="disabled"
      :aria-label="`${element.type} connection points (schematic)`"
      class="point-map"
      @select="toggle"
    />
    <v-select v-if="!groupsOnly" :model-value="modelValue.pointIds ?? []" :items="pointOptions" label="Points" placeholder="Any point / outline" multiple chips closable-chips clearable :disabled="disabled" variant="outlined" density="compact" hide-details class="mb-2" @update:model-value="setPoints" />
    <v-select :model-value="modelValue.groups ?? []" :items="groups" label="Point groups" placeholder="Any group" multiple chips closable-chips clearable :disabled="disabled" variant="outlined" density="compact" hide-details @update:model-value="setGroups" />
    <div class="text-caption text-medium-emphasis mt-1">{{ groupsOnly ? 'Select groups. Each group has its own limit across all member points.' : modelValue.pointIds?.length || modelValue.groups?.length ? 'Selected points OR members of the selected groups.' : 'All points and free docking where enabled on the element.' }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DiagramElement } from '@/model/Element'
import type { EndpointSelector } from '@/model/Syntax'
import { matchesEndpoint, pointId, pointLabel } from '@/utils/connectionPoints'
import ConnectionPointMap from '@/components/modeling/ConnectionPointMap.vue'
const props = defineProps<{ modelValue: EndpointSelector; label: string; element?: DiagramElement; elements?: DiagramElement[]; disabled?: boolean; groupsOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: EndpointSelector] }>()
const allElements = computed(() => props.element ? [props.element] : props.elements ?? [])
const pointOptions = computed(() => allElements.value.flatMap((e) => e.anchorPoints.map((p) => ({ title: `${allElements.value.length > 1 ? e.type + ': ' : ''}${pointLabel(p)}`, value: pointId(p) }))))
const pointMarkers = computed(() => {
  const element = props.element
  if (!element) return []
  return element.anchorPoints.map((point) => ({
    id: pointId(point),
    label: `${pointLabel(point)}${point.groups?.length ? ` · ${point.groups.join(', ')}` : ''}`,
    point,
    selected: matchesEndpoint(props.modelValue, pointId(point), element.anchorPoints)
  }))
})
const groups = computed(() => [...new Set(allElements.value.flatMap((e) => e.anchorPoints.flatMap((p) => p.groups ?? [])))])
const setPoints = (ids: string[] | null) => emit('update:modelValue', { ...props.modelValue, pointIds: ids ?? [] })
const setGroups = (names: string[] | null) => emit('update:modelValue', { ...props.modelValue, groups: names ?? [] })
const toggle = (id: string) => {
  if (props.disabled) return
  const selected = props.modelValue.pointIds ?? []
  setPoints(selected.includes(id) ? selected.filter((p) => p !== id) : [...selected, id])
}
</script>

<style scoped>
.point-map { margin-bottom: 12px; }
</style>
