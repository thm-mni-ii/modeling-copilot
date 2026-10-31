<template>
  <div class="d-flex flex-column ga-8">
    <section>
      <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
        <v-icon color="primary" class="mr-2">mdi-grid</v-icon>
        <span>Connection Matrix</span>
      </div>

      <p class="text-body-2 text-medium-emphasis mb-3">Level 1 defines which Element types may be connected. Each cell cycles between <strong>undefined</strong>, <strong>allowed</strong>, and <strong>forbidden</strong>.</p>

      <v-alert v-if="elementOptions.length === 0" type="info" variant="tonal" class="mt-3"> Add Elements first to define Connection rules. </v-alert>

      <v-sheet v-else class="matrix-wrapper elevation-1 mt-3 rounded-lg bg-white" border>
        <v-table density="compact" class="relation-matrix">
          <thead>
            <tr>
              <th class="matrix-corner">
                <div class="d-flex align-center ga-1 text-caption text-uppercase text-medium-emphasis">
                  <span>From</span>
                  <span class="font-weight-bold">→</span>
                  <span>To</span>
                </div>
              </th>
              <th v-for="target in elementOptions" :key="`head-${target}`" class="matrix-header matrix-header--column">
                {{ target }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="source in elementOptions" :key="`row-${source}`">
              <th class="matrix-header matrix-header--row">{{ source }}</th>
              <td v-for="target in elementOptions" :key="`cell-${source}-${target}`" class="matrix-cell">
                <v-tooltip :text="`${source} → ${target}`" location="bottom">
                  <template #activator="{ props: relationProps }">
                    <div class="d-flex align-center justify-center" v-bind="relationProps">
                      <v-tooltip :text="stateLabel(getRelationState(source, target))">
                        <template #activator="{ props: tooltipProps }">
                          <v-btn v-bind="tooltipProps" :disabled="!hasLanguageVersion" variant="elevated" class="matrix-button rounded-lg" :class="stateClass(getRelationState(source, target))" size="small" @click="cycleRelationState(source, target)">
                            <v-icon size="18">{{ stateIcon(getRelationState(source, target)) }}</v-icon>
                          </v-btn>
                        </template>
                      </v-tooltip>
                    </div>
                  </template>
                </v-tooltip>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-sheet>

      <p v-if="elementOptions.length" class="text-body-2 text-medium-emphasis mt-2">Click a cell to cycle between <strong>undefined</strong>, <strong>allowed</strong>, and <strong>forbidden</strong>.</p>
    </section>

    <section class="d-flex flex-column ga-3 refinement-section">
      <div class="d-flex align-center font-weight-semibold text-h6 mb-0">
        <v-icon color="primary" class="mr-2">mdi-link-variant</v-icon>
        <span>Allowed Connection Refinement</span>
      </div>

      <v-alert v-if="allowedRelations.length === 0" type="info" variant="tonal" class="mt-3"> Mark at least one Connection as <strong>allowed</strong> in the matrix to configure Connection types and cardinalities. </v-alert>

      <template v-else>
        <p class="text-body-2 text-medium-emphasis mb-1"><strong>All</strong> = all Connection types; a targeted selection = selected types only. The preset sets min/max for the active range.</p>
        <v-sheet class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
          <v-table density="compact" class="refinement-matrix">
            <thead>
              <tr>
                <th class="refinement-corner">Connection</th>
                <th class="refinement-kard-header">Cardinality</th>
                <th class="refinement-sep text-center">All</th>
                <th v-for="connectionType in connectionOptions" :key="`type-head-${connectionType}`" class="text-center">
                  {{ connectionType }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="relation in allowedRelations" :key="`refinement-${relationKey(relation.sourceType, relation.targetType)}`">
                <th class="refinement-header">{{ relation.sourceType }} → {{ relation.targetType }}</th>
                <td class="refinement-cell refinement-cell--cardinality">
                  <v-btn-toggle density="compact" mandatory rounded="lg" :model-value="selectedCardinalityPresetId(relation)" :disabled="!hasLanguageVersion" @update:model-value="(id: string) => setCardinalityPresetById(relation, id)">
                    <v-btn v-for="preset in cardinalityPresets" :key="`preset-${relationKey(relation.sourceType, relation.targetType)}-${preset.id}`" :value="preset.id" size="x-small" class="preset-btn">
                      {{ preset.label }}
                    </v-btn>
                  </v-btn-toggle>
                </td>
                <td class="refinement-cell refinement-sep text-center">
                  <v-btn variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(relation, '__all__')" size="small" :disabled="!hasLanguageVersion" @click="setAllConnectionTypes(relation)">
                    <v-icon size="16">mdi-select-all</v-icon>
                  </v-btn>
                </td>
                <td v-for="connectionType in connectionOptions" :key="`type-cell-${relationKey(relation.sourceType, relation.targetType)}-${connectionType}`" class="refinement-cell text-center">
                  <v-tooltip :text="`${relation.sourceType} → ${relation.targetType} (${connectionType})`" location="bottom">
                    <template #activator="{ props: typeProps }">
                      <v-btn v-bind="typeProps" variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(relation, connectionType)" size="small" :disabled="!hasLanguageVersion" @click="toggleConnectionType(relation, connectionType)">
                        <v-icon size="16">{{ connectionTypeCellIcon(relation, connectionType) }}</v-icon>
                      </v-btn>
                    </template>
                  </v-tooltip>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-sheet>
      </template>
    </section>

    <section class="d-flex flex-column ga-3 refinement-section">
      <div class="d-flex align-center font-weight-semibold text-h6 mb-0">
        <v-icon color="primary" class="mr-2">mdi-arrow-collapse-right</v-icon>
        <span>Incoming Edges</span>
      </div>

      <v-alert v-if="incomingTargetTypes.length === 0" type="info" variant="tonal" class="mt-3"> Mark at least one Connection as <strong>allowed</strong> in the matrix to limit incoming Connections. </v-alert>

      <template v-else>
        <p class="text-body-2 text-medium-emphasis mb-1">Number of incoming Connections per target Element, counted across all source types. Min <strong>0</strong> and empty max = no restriction.</p>
        <v-sheet class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
          <v-table density="compact" class="incoming-matrix">
            <thead>
              <tr>
                <th class="refinement-corner">Element</th>
                <th class="refinement-kard-header">Min</th>
                <th class="refinement-kard-header">Max</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="elementType in incomingTargetTypes" :key="`incoming-${elementType}`">
                <th class="refinement-header">{{ elementType }}</th>
                <td class="refinement-cell">
                  <v-text-field type="number" min="0" density="compact" variant="outlined" hide-details class="incoming-field" :model-value="incomingCardinality(elementType).min" :disabled="!hasLanguageVersion" @update:model-value="(value: string) => setIncomingMin(elementType, value)" />
                </td>
                <td class="refinement-cell">
                  <v-text-field type="number" min="0" density="compact" variant="outlined" hide-details placeholder="*" class="incoming-field" :model-value="incomingCardinality(elementType).max ?? ''" :error="isIncomingMaxInvalid(elementType)" :disabled="!hasLanguageVersion" @update:model-value="(value: string) => setIncomingMax(elementType, value)" />
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-sheet>
      </template>
    </section>

    <section class="d-flex flex-column ga-3">
      <div class="d-flex align-center font-weight-semibold text-h6">
        <v-icon color="primary" class="mr-2">mdi-script-text-outline</v-icon>
        <span>Error Message Template</span>
      </div>
      <v-textarea v-model="messageTemplate" rows="3" density="compact" variant="outlined" label="Dynamic Error Message Template" auto-grow hint="Use placeholders such as {source}, {target}, {connection}, {min}, {max}" persistent-hint />
    </section>

    <section class="d-flex flex-column ga-2">
      <div class="d-flex align-center font-weight-semibold text-h6">
        <v-icon color="primary" class="mr-2">mdi-code-json</v-icon>
        <span>Syntax Data Structure</span>
      </div>
      <v-sheet border rounded="lg" class="structure-preview">
        <pre class="structure-preview__code">{{ uiStructureExampleJson }}</pre>
      </v-sheet>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { MultiplicityCardinality, MultiplicityConfig, MultiplicityRelation, MultiplicityRelationState } from '@/model/Syntax'

type RelationState = MultiplicityRelationState | 'unset'

interface Props {
  config: MultiplicityConfig
  elementOptions: string[]
  connectionOptions: string[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  update: []
}>()

const store = useDiagramLanguages()

const hasLanguageVersion = computed(() => store.currentVersion !== null)
const elementOptions = computed(() => props.elementOptions)
const connectionOptions = computed(() => props.connectionOptions)

const DEFAULT_MESSAGE_TEMPLATE = 'The Connection {source} -> {target} with Connection type {connection} violates the cardinality ({min}..{max}).'

const relationKey = (source: string, target: string): string => `${source}::${target}`

interface CardinalityPreset {
  id: string
  label: string
  min: number
  max: number | null
}

const cardinalityPresets: CardinalityPreset[] = [
  { id: '0..1', label: '0..1', min: 0, max: 1 },
  { id: '1..1', label: '1..1', min: 1, max: 1 },
  { id: '0..*', label: '0..*', min: 0, max: null },
  { id: '1..*', label: '1..*', min: 1, max: null }
]

const getRelationState = (source: string, target: string): RelationState => {
  const relation = props.config.relations.find((item) => item.sourceType === source && item.targetType === target)
  return relation ? relation.state : 'unset'
}

const stateIcon = (state: RelationState): string => {
  if (state === 'allowed') return 'mdi-check'
  if (state === 'forbidden') return 'mdi-close'
  return 'mdi-minus'
}

const stateClass = (state: RelationState): string => {
  if (state === 'allowed') return 'matrix-button--allowed'
  if (state === 'forbidden') return 'matrix-button--forbidden'
  return 'matrix-button--unset'
}

const stateLabel = (state: RelationState): string => {
  if (state === 'allowed') return 'Allowed Connection'
  if (state === 'forbidden') return 'Forbidden Connection'
  return 'Undefined'
}

const emitUpdate = () => {
  emit('update')
}

const cycleRelationState = (source: string, target: string) => {
  if (!hasLanguageVersion.value) return
  const current = getRelationState(source, target)
  const next: RelationState = current === 'unset' ? 'allowed' : current === 'allowed' ? 'forbidden' : 'unset'

  store.setMultiplicityRelationState(source, target, next === 'unset' ? 'unset' : next)

  emitUpdate()
}

const usesAllConnectionTypes = (relation: MultiplicityRelation): boolean => relation.refinement.connectionTypes.length === 0

const isConnectionTypeSelected = (relation: MultiplicityRelation, connectionType: string): boolean => relation.refinement.connectionTypes.includes(connectionType)

const setAllConnectionTypes = (relation: MultiplicityRelation) => {
  relation.refinement.connectionTypes = []
  emitUpdate()
}

const toggleConnectionType = (relation: MultiplicityRelation, connectionType: string) => {
  if (usesAllConnectionTypes(relation)) {
    relation.refinement.connectionTypes = [connectionType]
    emitUpdate()
    return
  }

  if (isConnectionTypeSelected(relation, connectionType)) {
    relation.refinement.connectionTypes = relation.refinement.connectionTypes.filter((entry) => entry !== connectionType)
  } else {
    relation.refinement.connectionTypes = [...relation.refinement.connectionTypes, connectionType]
  }

  relation.refinement.connectionTypes = [...new Set(relation.refinement.connectionTypes)]
  emitUpdate()
}

const connectionTypeCellClass = (relation: MultiplicityRelation, connectionType: string): string => {
  if (connectionType === '__all__') {
    return usesAllConnectionTypes(relation) ? 'matrix-button--allowed' : 'matrix-button--unset'
  }

  if (usesAllConnectionTypes(relation)) {
    return 'matrix-button--all'
  }

  return isConnectionTypeSelected(relation, connectionType) ? 'matrix-button--allowed' : 'matrix-button--unset'
}

const connectionTypeCellIcon = (relation: MultiplicityRelation, connectionType: string): string => {
  if (usesAllConnectionTypes(relation)) return 'mdi-check-all'
  return isConnectionTypeSelected(relation, connectionType) ? 'mdi-check' : 'mdi-minus'
}

const isCardinalityPresetSelected = (relation: MultiplicityRelation, preset: CardinalityPreset): boolean => relation.refinement.cardinality.min === preset.min && relation.refinement.cardinality.max === preset.max

const selectedCardinalityPresetId = (relation: MultiplicityRelation): string => {
  const preset = cardinalityPresets.find((entry) => isCardinalityPresetSelected(relation, entry))
  return preset?.id ?? '0..*'
}

const setCardinalityPreset = (relation: MultiplicityRelation, preset: CardinalityPreset) => {
  relation.refinement.cardinality.min = preset.min
  relation.refinement.cardinality.max = preset.max
  emitUpdate()
}

const setCardinalityPresetById = (relation: MultiplicityRelation, presetId: string) => {
  const preset = cardinalityPresets.find((entry) => entry.id === presetId)
  if (!preset) return
  setCardinalityPreset(relation, preset)
}

const sortedRelations = computed(() => {
  const relations = [...props.config.relations]

  relations.sort((a, b) => {
    if (a.state !== b.state) {
      return a.state === 'allowed' ? -1 : 1
    }
    if (a.sourceType !== b.sourceType) {
      return a.sourceType.localeCompare(b.sourceType)
    }
    return a.targetType.localeCompare(b.targetType)
  })
  return relations
})

const allowedRelations = computed(() => sortedRelations.value.filter((relation) => relation.state === 'allowed'))

// Eingehende Kanten: nur Elemente, in die laut Matrix eine Verbindung führen darf
const incomingTargetTypes = computed(() => elementOptions.value.filter((elementType) => allowedRelations.value.some((relation) => relation.targetType === elementType)))

const incomingCardinality = (elementType: string): MultiplicityCardinality => props.config.incoming?.find((entry) => entry.elementType === elementType)?.cardinality ?? { min: 0, max: null }

// 0..* entfernt den Eintrag, damit bleibt das bisherige Verhalten der Standard
const setIncomingCardinality = (elementType: string, cardinality: MultiplicityCardinality) => {
  const incoming = (props.config.incoming ?? []).filter((entry) => entry.elementType !== elementType)
  if (cardinality.min > 0 || cardinality.max !== null) incoming.push({ elementType, cardinality })
  Object.assign(props.config, { incoming })
  emitUpdate()
}

const setIncomingMin = (elementType: string, value: string) => {
  const min = Math.max(0, Number.parseInt(value, 10) || 0)
  setIncomingCardinality(elementType, { min, max: incomingCardinality(elementType).max })
}

// Leeres Feld = unbegrenzt (*); max < min wird am Feld markiert statt beim Tippen korrigiert
const setIncomingMax = (elementType: string, value: string) => {
  const parsed = Number.parseInt(value, 10)
  setIncomingCardinality(elementType, { min: incomingCardinality(elementType).min, max: Number.isNaN(parsed) ? null : Math.max(0, parsed) })
}

const isIncomingMaxInvalid = (elementType: string): boolean => {
  const { min, max } = incomingCardinality(elementType)
  return max !== null && max < min
}

watch(
  () => props.config.messageTemplate,
  (template) => {
    if ((template ?? '').trim().length > 0) {
      return
    }

    const newConfig = { ...props.config, messageTemplate: DEFAULT_MESSAGE_TEMPLATE }
    Object.assign(props.config, newConfig)
    emitUpdate()
  },
  { immediate: true }
)

const messageTemplate = computed({
  get: () => props.config.messageTemplate,
  set: (value: string) => {
    const newConfig = { ...props.config, messageTemplate: value ?? '' }
    Object.assign(props.config, newConfig)
    emitUpdate()
  }
})

const uiStructureExample = computed(() => ({
  ruleType: 'multiplicity',
  config: {
    messageTemplate: props.config.messageTemplate,
    relations: props.config.relations.map((relation) => ({
      sourceType: relation.sourceType,
      targetType: relation.targetType,
      state: relation.state,
      refinement: {
        connectionTypes: relation.refinement.connectionTypes,
        cardinality: {
          min: relation.refinement.cardinality.min,
          max: relation.refinement.cardinality.max
        }
      }
    })),
    incoming: props.config.incoming ?? []
  }
}))

const uiStructureExampleJson = computed(() => JSON.stringify(uiStructureExample.value, null, 2))
</script>

<style scoped>
/* Matrix-spezifische Styles - können nicht durch Vuetify ersetzt werden */
.matrix-wrapper {
  overflow: auto;
  max-width: 100%;
  max-height: 320px;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
}

.matrix-wrapper :deep(.v-table__wrapper) {
  overflow: visible;
  max-height: none;
}

.refinement-section {
  min-width: 0;
  overflow: hidden;
}

.relation-matrix {
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}

.relation-matrix thead th {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #f6f8fb;
  color: rgba(var(--v-theme-on-surface), 0.8);
  font-weight: 600;
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

.matrix-corner {
  position: sticky;
  left: 0;
  z-index: 4;
  background: #eef2f8;
  font-weight: 600;
}

.matrix-cell {
  padding: 6px;
  text-align: center;
  background: #ffffff;
}

.refinement-matrix {
  min-width: 980px;
  width: max-content;
  border-collapse: separate;
  border-spacing: 0;
}

.incoming-matrix {
  width: max-content;
  border-collapse: separate;
  border-spacing: 0;
}

.incoming-field {
  width: 90px;
}

.refinement-matrix thead th {
  background: #f6f8fb;
  color: rgba(var(--v-theme-on-surface), 0.8);
  font-weight: 600;
  white-space: nowrap;
  padding: 10px 12px;
}

.refinement-corner,
.refinement-header {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #eef2f8;
  font-weight: 600;
  white-space: nowrap;
  padding: 10px 12px;
}

.refinement-corner {
  z-index: 3;
}

.refinement-cell {
  padding: 5px 8px;
  background: #ffffff;
  vertical-align: middle;
  text-align: center;
}

.refinement-cell--cardinality {
  min-width: 0;
  white-space: nowrap;
  text-align: center;
}

.refinement-cell--cardinality :deep(.v-btn-toggle) {
  justify-content: center;
}

.refinement-kard-header {
  padding: 8px 10px;
  background: #f6f8fb;
  font-weight: 600;
  white-space: nowrap;
}

.refinement-sep {
  border-left: 1px solid rgba(var(--v-theme-outline), 0.18);
}

.preset-btn {
  font-size: 10px !important;
  letter-spacing: 0 !important;
  min-width: 34px !important;
  padding: 0 4px !important;
  height: 22px !important;
}

.structure-preview {
  background: #0f172a;
  color: #e2e8f0;
  overflow: auto;
  max-height: 280px;
}

.structure-preview__code {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.45;
  font-family: 'Cascadia Code', 'Consolas', monospace;
}

.matrix-button--all {
  background: rgba(var(--v-theme-primary), 0.18);
  color: rgb(var(--v-theme-primary));
}

/* Button-spezifische Styles für Matrix */
.matrix-button {
  width: 38px;
  height: 30px;
  min-width: 38px;
}

.matrix-button--allowed {
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}

.matrix-button--forbidden {
  background: rgb(var(--v-theme-error));
  color: rgb(var(--v-theme-on-error));
}

.matrix-button--unset {
  background: rgba(var(--v-theme-outline), 0.18);
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* Scrollbar-Styling */
.matrix-wrapper::-webkit-scrollbar {
  height: 8px;
  width: 8px;
}

.matrix-wrapper::-webkit-scrollbar-thumb {
  background-color: rgba(var(--v-theme-outline), 0.3);
  border-radius: 4px;
}
</style>
