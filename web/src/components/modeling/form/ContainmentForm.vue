<template>
  <section>
    <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
      <v-icon color="primary" class="mr-2">mdi-tray-arrow-down</v-icon>
      <span>Container Contents</span>
    </div>

    <p class="text-body-2 text-medium-emphasis mb-3">Defines which Element types may be dropped into a container. <strong>All</strong> = the container accepts every type; otherwise only the checked types.</p>

    <v-alert v-if="containerTypes.length === 0" type="info" variant="tonal"> The language has no containers (Elements or Children with the Swimlane renderer). </v-alert>

    <!-- Gleiche Darstellung wie die Allowed Connection Refinement: All oder ausgewählte Typen -->
    <v-sheet v-else class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
      <v-table density="compact" class="containment-matrix">
        <thead>
          <tr>
            <th class="matrix-header matrix-header--row">Container</th>
            <th class="text-center">All</th>
            <th v-for="elementType in elementOptions" :key="`head-${elementType}`" class="text-center">{{ elementType }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="containerType in containerTypes" :key="containerType">
            <th class="matrix-header matrix-header--row">{{ containerType }}</th>
            <td class="text-center">
              <v-btn variant="elevated" class="matrix-button rounded-lg" :color="allowedTypes(containerType).length === 0 ? 'primary' : undefined" size="small" :disabled="!store.definition" @click="store.setContainmentChildTypes(containerType, [])">
                <v-icon size="16">mdi-select-all</v-icon>
              </v-btn>
            </td>
            <td v-for="elementType in elementOptions" :key="`${containerType}-${elementType}`" class="text-center">
              <v-tooltip :text="`${elementType} in ${containerType}`" location="bottom">
                <template #activator="{ props: cellProps }">
                  <v-btn v-bind="{ ...cellProps, ...cellStyle(containerType, elementType) }" class="matrix-button rounded-lg" size="small" :disabled="!store.definition" @click="toggleChildType(containerType, elementType)">
                    <v-icon size="16">{{ cellIcon(containerType, elementType) }}</v-icon>
                  </v-btn>
                </template>
              </v-tooltip>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-sheet>
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

// Reihenfolge der Elemente der Sprache, damit Aus- und wieder Einschalten den gespeicherten Stand ergibt
const toggleChildType = (containerType: string, elementType: string) => {
  const types = allowedTypes(containerType)
  const next = types.includes(elementType) ? types.filter((entry) => entry !== elementType) : [...types, elementType]
  store.setContainmentChildTypes(containerType, [...elementOptions.value.filter((entry) => next.includes(entry)), ...next.filter((entry) => !elementOptions.value.includes(entry))])
}

// Ohne Auswahl nimmt der Container alles auf (getönt), sonst nur die gewählten Typen
const cellStyle = (containerType: string, elementType: string) => {
  const types = allowedTypes(containerType)
  if (types.length === 0) return { color: 'primary', variant: 'tonal' as const }
  return types.includes(elementType) ? { color: 'primary', variant: 'elevated' as const } : { variant: 'elevated' as const }
}

const cellIcon = (containerType: string, elementType: string): string => {
  const types = allowedTypes(containerType)
  if (types.length === 0) return 'mdi-check-all'
  return types.includes(elementType) ? 'mdi-check' : 'mdi-minus'
}
</script>

<style scoped>
.matrix-wrapper {
  overflow: auto;
  max-width: 100%;
}

.containment-matrix {
  width: max-content;
  min-width: 100%;
}

.containment-matrix thead th {
  background: #f6f8fb;
  white-space: nowrap;
}

.matrix-header {
  padding: 8px 12px;
  white-space: nowrap;
}

.matrix-header--row {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #f6f8fb;
  font-weight: 600;
}

.matrix-button {
  width: 38px;
  height: 30px;
  min-width: 38px;
}
</style>
