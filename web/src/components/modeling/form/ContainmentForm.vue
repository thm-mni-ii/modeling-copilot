<template>
  <section>
    <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
      <v-icon color="primary" class="mr-2">mdi-tray-arrow-down</v-icon>
      <span>Container Contents</span>
    </div>

    <p class="text-body-2 text-medium-emphasis mb-3">Defines which Element types may be dropped into a container. A container without a selection accepts every type.</p>

    <v-alert v-if="containerTypes.length === 0" type="info" variant="tonal"> The language has no containers (Elements or Children with the Swimlane renderer). </v-alert>

    <v-select v-for="containerType in containerTypes" :key="containerType" :model-value="allowedTypes(containerType)" :items="elementOptions" :label="containerType" placeholder="Any type" multiple chips closable-chips density="compact" variant="outlined" class="mb-2" @update:model-value="(types: string[]) => store.setContainmentChildTypes(containerType, types)" />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChildElement, DiagramElement } from '@/model/Element'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'

const store = useDiagramLanguages()

const elementOptions = computed(() => (store.definition?.elements ?? []).map((element) => element.type))

// Alle Container der Sprache, auch Children wie die Attributliste eines SERM-E-Typs
const containerTypes = computed(() => {
  const types = new Set<string>()
  const collect = (element: DiagramElement | ChildElement) => {
    if (element.renderMode === 'swimlane') types.add(element.type)
    element.children?.forEach(collect)
  }
  store.definition?.elements.forEach(collect)
  return [...types]
})

const allowedTypes = (containerType: string): string[] => {
  const rule = store.definition?.syntax.find((entry) => entry.ruleType === 'containment')
  if (rule?.ruleType !== 'containment') return []
  return rule.config.relations.find((relation) => relation.containerType === containerType)?.childTypes ?? []
}
</script>
