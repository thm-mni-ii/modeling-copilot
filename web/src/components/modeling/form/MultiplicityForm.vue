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
                  <v-btn variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(relation.refinement.connectionTypes, '__all__')" size="small" :disabled="!hasLanguageVersion" @click="setAllConnectionTypes(relation)">
                    <v-icon size="16">mdi-select-all</v-icon>
                  </v-btn>
                </td>
                <td v-for="connectionType in connectionOptions" :key="`type-cell-${relationKey(relation.sourceType, relation.targetType)}-${connectionType}`" class="refinement-cell text-center">
                  <v-tooltip :text="`${relation.sourceType} → ${relation.targetType} (${connectionType})`" location="bottom">
                    <template #activator="{ props: typeProps }">
                      <v-btn v-bind="typeProps" variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(relation.refinement.connectionTypes, connectionType)" size="small" :disabled="!hasLanguageVersion" @click="toggleConnectionType(relation, connectionType)">
                        <v-icon size="16">{{ connectionTypeCellIcon(relation.refinement.connectionTypes, connectionType) }}</v-icon>
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
        <span>Incoming / Outgoing Edges</span>
      </div>

      <p class="text-body-2 text-medium-emphasis mb-1">Each rule counts the Connections at an Element in the chosen direction; <strong>Both</strong> ignores the direction. Empty fields match everything, <strong>All</strong> = all Connection types; min <strong>0</strong> and empty max = no restriction.</p>

      <v-sheet v-if="edgeRules.length" class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
        <v-table density="compact" class="refinement-matrix">
          <thead>
            <tr>
              <th class="refinement-corner">Element</th>
              <th class="refinement-kard-header">Direction</th>
              <th class="refinement-kard-header">Other End</th>
              <th class="refinement-kard-header">Min</th>
              <th class="refinement-kard-header">Max</th>
              <th class="refinement-sep text-center">All</th>
              <th v-for="connectionType in connectionOptions" :key="`edge-type-head-${connectionType}`" class="text-center">
                {{ connectionType }}
              </th>
              <th class="refinement-sep" />
            </tr>
          </thead>
          <tbody>
            <template v-for="(entry, index) in edgeRules" :key="`edge-rule-${index}`">
              <tr>
                <td class="refinement-header">
                  <v-select :model-value="entry.elementType || null" :items="elementOptions" placeholder="Any" clearable density="compact" variant="outlined" hide-details class="edge-select" :disabled="!hasLanguageVersion" @update:model-value="(type: string | null) => setEdgeRuleField(entry, 'elementType', type ?? '')" />
                </td>
                <td class="refinement-cell refinement-cell--cardinality">
                  <v-btn-toggle density="compact" mandatory rounded="lg" :model-value="entry.direction ?? 'incoming'" :disabled="!hasLanguageVersion" @update:model-value="(direction: EdgeDirection) => setEdgeRuleField(entry, 'direction', direction)">
                    <v-btn v-for="direction in edgeDirections" :key="direction.value" :value="direction.value" size="x-small" class="preset-btn">{{ direction.label }}</v-btn>
                  </v-btn-toggle>
                </td>
                <td class="refinement-cell">
                  <v-select :model-value="entry.neighborTypes ?? []" :items="elementOptions" placeholder="Any" multiple chips closable-chips density="compact" variant="outlined" hide-details class="edge-select" :disabled="!hasLanguageVersion" @update:model-value="(types: string[]) => setEdgeRuleField(entry, 'neighborTypes', types)" />
                </td>
                <td class="refinement-cell">
                  <v-text-field type="number" min="0" density="compact" variant="outlined" hide-details class="incoming-field" :model-value="entry.cardinality.min" :disabled="!hasLanguageVersion" @update:model-value="(value: string) => setEdgeRuleMin(entry, value)" />
                </td>
                <td class="refinement-cell">
                  <v-text-field type="number" min="0" density="compact" variant="outlined" hide-details placeholder="*" class="incoming-field" :model-value="entry.cardinality.max ?? ''" :error="isEdgeRuleMaxInvalid(entry)" :disabled="!hasLanguageVersion" @update:model-value="(value: string) => setEdgeRuleMax(entry, value)" />
                </td>
                <td class="refinement-cell refinement-sep text-center">
                  <v-btn variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(entry.connectionTypes ?? [], '__all__')" size="small" :disabled="!hasLanguageVersion" @click="setEdgeRuleField(entry, 'connectionTypes', [])">
                    <v-icon size="16">mdi-select-all</v-icon>
                  </v-btn>
                </td>
                <td v-for="connectionType in connectionOptions" :key="`edge-type-cell-${index}-${connectionType}`" class="refinement-cell text-center">
                  <v-btn variant="elevated" class="matrix-button rounded-lg" :class="connectionTypeCellClass(entry.connectionTypes ?? [], connectionType)" size="small" :disabled="!hasLanguageVersion" @click="setEdgeRuleField(entry, 'connectionTypes', toggledConnectionTypes(entry.connectionTypes ?? [], connectionType))">
                    <v-icon size="16">{{ connectionTypeCellIcon(entry.connectionTypes ?? [], connectionType) }}</v-icon>
                  </v-btn>
                </td>
                <td class="refinement-cell refinement-sep text-no-wrap">
                  <v-tooltip text="Error Message" location="bottom">
                    <template #activator="{ props: messageProps }">
                      <v-btn v-bind="messageProps" :icon="entry.messageTemplate ? 'mdi-message-text' : 'mdi-message-text-outline'" variant="text" size="small" :color="entry.messageTemplate ? 'primary' : undefined" @click="toggleEdgeRuleMessage(index)" />
                    </template>
                  </v-tooltip>
                  <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="!hasLanguageVersion" @click="removeEdgeRule(index)" />
                </td>
              </tr>
              <!-- Eigene Meldung aufgeklappt unter der Regel, damit die Zeile schmal bleibt -->
              <tr v-if="openEdgeRuleMessages.has(index)">
                <td class="refinement-cell text-left" :colspan="connectionOptions.length + 7">
                  <v-text-field :model-value="entry.messageTemplate ?? ''" label="Error Message for this rule" placeholder="Empty = Error Message Template below" density="compact" variant="outlined" hide-details class="edge-message" :disabled="!hasLanguageVersion" @update:model-value="(value: string) => setEdgeRuleField(entry, 'messageTemplate', value)" />
                </td>
              </tr>
            </template>
          </tbody>
        </v-table>
      </v-sheet>

      <div>
        <v-btn prepend-icon="mdi-plus" variant="tonal" color="primary" size="small" :disabled="!hasLanguageVersion || elementOptions.length === 0" @click="addEdgeRule">Add Rule</v-btn>
      </div>
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
import { computed, ref, watch } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { EdgeCardinality, EdgeDirection, MultiplicityConfig, MultiplicityRelation, MultiplicityRelationState } from '@/model/Syntax'

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

// Auswahl der Verbindungstypen für Refinement und Kantenregeln; leere Liste = alle Typen
const toggledConnectionTypes = (types: string[], connectionType: string): string[] => {
  if (types.length === 0) return [connectionType]
  const next = types.includes(connectionType) ? types.filter((entry) => entry !== connectionType) : [...types, connectionType]
  // Reihenfolge der Sprache, damit Aus- und wieder Einschalten den gespeicherten Stand ergibt; unbekannte Typen bleiben hinten
  return [...connectionOptions.value.filter((entry) => next.includes(entry)), ...next.filter((entry) => !connectionOptions.value.includes(entry))]
}

const setAllConnectionTypes = (relation: MultiplicityRelation) => {
  relation.refinement.connectionTypes = []
  emitUpdate()
}

const toggleConnectionType = (relation: MultiplicityRelation, connectionType: string) => {
  relation.refinement.connectionTypes = toggledConnectionTypes(relation.refinement.connectionTypes, connectionType)
  emitUpdate()
}

const connectionTypeCellClass = (types: string[], connectionType: string): string => {
  if (connectionType === '__all__') {
    return types.length === 0 ? 'matrix-button--allowed' : 'matrix-button--unset'
  }

  if (types.length === 0) {
    return 'matrix-button--all'
  }

  return types.includes(connectionType) ? 'matrix-button--allowed' : 'matrix-button--unset'
}

const connectionTypeCellIcon = (types: string[], connectionType: string): string => {
  if (types.length === 0) return 'mdi-check-all'
  return types.includes(connectionType) ? 'mdi-check' : 'mdi-minus'
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

// Kantenregeln liegen weiter unter config.incoming, damit gespeicherte Sprachen gültig bleiben
const edgeRules = computed(() => props.config.incoming ?? [])

const edgeDirections: { value: EdgeDirection; label: string }[] = [
  { value: 'incoming', label: 'In' },
  { value: 'outgoing', label: 'Out' },
  { value: 'both', label: 'Both' }
]

const addEdgeRule = () => {
  Object.assign(props.config, { incoming: [...edgeRules.value, { elementType: '', cardinality: { min: 0, max: null } }] })
  emitUpdate()
}

// Zeilen mit aufgeklappter eigener Meldung
const openEdgeRuleMessages = ref(new Set<number>())

const toggleEdgeRuleMessage = (index: number) => {
  const open = new Set(openEdgeRuleMessages.value)
  if (!open.delete(index)) open.add(index)
  openEdgeRuleMessages.value = open
}

const removeEdgeRule = (index: number) => {
  Object.assign(props.config, { incoming: edgeRules.value.filter((_, entryIndex) => entryIndex !== index) })
  openEdgeRuleMessages.value = new Set()
  emitUpdate()
}

// Standardwerte entfernen das Feld, damit Umstellen und Zurückstellen den gespeicherten Stand ergibt
const setEdgeRuleField = <K extends keyof EdgeCardinality>(entry: EdgeCardinality, field: K, value: EdgeCardinality[K]) => {
  const isDefault = (field === 'direction' && value === 'incoming') || (field === 'messageTemplate' && value === '') || (Array.isArray(value) && value.length === 0)
  if (isDefault) Reflect.deleteProperty(entry, field)
  else entry[field] = value
  emitUpdate()
}

const setEdgeRuleMin = (entry: EdgeCardinality, value: string) => {
  setEdgeRuleField(entry, 'cardinality', { min: Math.max(0, Number.parseInt(value, 10) || 0), max: entry.cardinality.max })
}

// Leeres Feld = unbegrenzt (*); max < min wird am Feld markiert statt beim Tippen korrigiert
const setEdgeRuleMax = (entry: EdgeCardinality, value: string) => {
  const parsed = Number.parseInt(value, 10)
  setEdgeRuleField(entry, 'cardinality', { min: entry.cardinality.min, max: Number.isNaN(parsed) ? null : Math.max(0, parsed) })
}

const isEdgeRuleMaxInvalid = (entry: EdgeCardinality): boolean => entry.cardinality.max !== null && entry.cardinality.max < entry.cardinality.min

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

.incoming-field {
  width: 90px;
}

.edge-select {
  min-width: 240px;
}

/* Bleibt beim horizontalen Scrollen links sichtbar, über der festen Element-Spalte */
.edge-message {
  position: sticky;
  left: 12px;
  z-index: 3;
  max-width: 560px;
  background: #ffffff;
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
