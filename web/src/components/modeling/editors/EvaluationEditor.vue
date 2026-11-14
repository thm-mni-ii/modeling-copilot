<template>
  <v-container fluid class="pa-2">
    <v-card variant="outlined">
      <v-card-title class="d-flex flex-wrap align-center ga-2 py-2">
        <v-icon color="primary" size="24">mdi-compare</v-icon>
        <h2 class="text-h6">Comparison groups</h2>
        <v-spacer />
        <v-btn color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="disabled || types.length < 2" @click="addGroup">New group</v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-3">
        <v-btn-toggle v-model="typeField" mandatory density="compact" color="primary" variant="outlined" divided class="mb-3" aria-label="Comparison type category">
          <v-btn value="elementTypes">Elements</v-btn>
          <v-btn value="connectionTypes">Connections</v-btn>
        </v-btn-toggle>
        <p class="text-body-2 text-medium-emphasis mb-3">Check the types that may match within each group. Identical types can always match.</p>
        <v-alert v-if="!store.definition" type="info" variant="tonal" density="compact">Load a language version to configure evaluation.</v-alert>
        <template v-else>
          <v-alert v-if="types.length < 2" type="info" variant="tonal" density="compact" class="mb-3">Add at least two {{ typeCategory }} types to create a comparison group.<span v-if="typeField === 'elementTypes'"> Declared child types are included.</span></v-alert>
          <v-alert v-if="errors.length" type="warning" variant="tonal" density="compact" class="mb-3" title="Resolve before saving">
            <div v-for="(message, index) in errors" :key="index">{{ message }}</div>
          </v-alert>
          <p v-if="!groups.length" class="text-body-2 text-medium-emphasis mb-0">No groups yet. Only identical types are candidates for matching.</p>
          <v-sheet v-else border rounded="lg" class="matrix-wrapper">
            <v-table density="compact" class="comparison-matrix">
              <thead>
                <tr>
                  <th scope="col" class="group-column">Comparison group</th>
                  <th v-for="type in types" :key="type" scope="col" class="type-column">
                    <ElementPreviewLabel v-if="typeField === 'elementTypes'" :element="previewElements.get(type)" :label="type" />
                    <template v-else>
                      <ConnectionPreviewItem :connection="previewConnections.get(type)" :width="140" :height="36" />
                      <span>{{ type }}</span>
                    </template>
                  </th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(group, index) in groups" :key="group.id">
                  <th scope="row" class="group-column">
                    <div class="d-flex align-center ga-2 py-2">
                      <v-text-field v-model="group.name" :aria-label="`Group ${index + 1} name`" placeholder="Group name" variant="outlined" density="compact" maxlength="256" :disabled="disabled" hide-details class="group-name" />
                      <v-chip size="x-small" variant="tonal" :color="groupTypes(group).length < 2 ? 'warning' : undefined" :aria-label="`${groupTypes(group).length} selected types`">{{ groupTypes(group).length }}</v-chip>
                    </div>
                    <div v-if="missingTypes(group).length" class="d-flex flex-wrap ga-1 pb-2">
                      <v-chip v-for="type in missingTypes(group)" :key="type" size="small" color="error" closable :disabled="disabled" :aria-label="`Remove missing type ${type} from ${group.name || `Group ${index + 1}`}`" @click:close="toggleType(group, type)">{{ type }} (missing)</v-chip>
                    </div>
                  </th>
                  <td v-for="type in types" :key="type" class="text-center">
                    <v-btn :color="groupTypes(group).includes(type) ? 'primary' : undefined" :variant="groupTypes(group).includes(type) ? 'flat' : 'tonal'" class="matrix-button rounded-lg" size="small" :disabled="disabled" :aria-label="`${type} in ${group.name || `Group ${index + 1}`}`" :aria-pressed="groupTypes(group).includes(type)" @click="toggleType(group, type)">
                      <v-icon size="18">{{ groupTypes(group).includes(type) ? 'mdi-check' : 'mdi-minus' }}</v-icon>
                    </v-btn>
                  </td>
                  <td class="text-center">
                    <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="disabled" :aria-label="`Delete ${group.name || `Group ${index + 1}`}`" @click="removeGroup(group.id)" />
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-sheet>
          <div v-if="groups.length" class="d-flex flex-wrap ga-4 text-caption text-medium-emphasis mt-2">
            <span><v-icon color="primary" size="16">mdi-check</v-icon> In group</span>
            <span><v-icon size="16">mdi-minus</v-icon> Not in group</span>
            <span>Select at least two types per group. Overlapping groups do not create indirect matches.</span>
          </div>
        </template>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { ComparisonGroup } from '@/model/DiagramLanguage'
import type { ChildElement, DiagramElement } from '@/model/Element'
import { evaluationConfigErrors, evaluationElementTypes } from '@/utils/languageEvaluation'
import ElementPreviewLabel from '@/components/modeling/form/ElementPreviewLabel.vue'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'

const store = useDiagramLanguages()
const typeField = ref<'elementTypes' | 'connectionTypes'>('elementTypes')
const typeCategory = computed(() => typeField.value === 'elementTypes' ? 'element' : 'connection')
const allGroups = computed(() => store.definition?.evaluation?.comparisonGroups ?? [])
const groups = computed(() => allGroups.value.filter((group) => group[typeField.value] !== undefined))
const elementTypes = computed(() => evaluationElementTypes(store.definition?.elements ?? []))
const connectionTypes = computed(() => [...new Set(store.definition?.connections.map((connection) => connection.type) ?? [])])
const types = computed(() => typeField.value === 'elementTypes' ? elementTypes.value : connectionTypes.value)
const previewConnections = computed(() => new Map(store.definition?.connections.map((connection) => [connection.type, connection])))
const errors = computed(() => evaluationConfigErrors(store.definition?.evaluation, elementTypes.value, connectionTypes.value))
const disabled = computed(() => !store.definition || store.loading || store.saving)
const previewElements = computed(() => {
  const result = new Map<string, DiagramElement>()
  const collect = (element: DiagramElement | ChildElement) => {
    if (!result.has(element.type)) {
      result.set(element.type, 'position' in element
        ? { ...element, x: 0, y: 0, width: element.position.width, height: element.position.height, anchorPoints: [], movable: false, resizable: false, connectable: element.connectable ?? false }
        : element)
    }
    ;(element.children ?? []).forEach(collect)
  }
  store.definition?.elements.forEach(collect)
  return result
})
const groupTypes = (group: ComparisonGroup) => group[typeField.value] ?? []
const missingTypes = (group: ComparisonGroup) => groupTypes(group).filter((type) => !types.value.includes(type))
const toggleType = (group: ComparisonGroup, type: string) => {
  const members = groupTypes(group)
  group[typeField.value] = members.includes(type) ? members.filter((entry) => entry !== type) : [...members, type]
}
const addGroup = () => {
  if (!store.definition || types.value.length < 2) return
  store.definition.evaluation ??= { comparisonGroups: [] }
  store.definition.evaluation.comparisonGroups.push({ id: crypto.randomUUID(), name: `Group ${allGroups.value.length + 1}`, [typeField.value]: [] })
}
const removeGroup = (id: string) => {
  if (!store.definition?.evaluation) return
  store.definition.evaluation.comparisonGroups = allGroups.value.filter((group) => group.id !== id)
}
</script>

<style scoped>
.matrix-wrapper { overflow: auto; max-width: 100%; max-height: calc(100vh - 340px); }
.comparison-matrix { width: max-content; min-width: 100%; }
.comparison-matrix :deep(thead th) { position: sticky; top: 0; z-index: 2; background: rgb(var(--v-theme-surface)); padding: 8px; }
.comparison-matrix :deep(.group-column) { position: sticky; left: 0; z-index: 1; background: rgb(var(--v-theme-surface)); min-width: 220px; width: 220px; padding: 0 12px; }
.comparison-matrix :deep(thead .group-column) { z-index: 3; }
.comparison-matrix :deep(.type-column) { text-align: center; }
.group-name { min-width: 160px; }
.matrix-button { width: 38px; min-width: 38px; height: 30px; }
</style>
