<template>
  <section>
    <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
      <v-icon color="primary" class="mr-2">mdi-sync-off</v-icon>
      <span>Cycles</span>
    </div>

    <p class="text-body-2 text-medium-emphasis mb-3">
      <strong>Forbid</strong> blocks Connections that close a cycle. <strong>Every Element</strong> marks the selected Elements that are not part of a cycle, <strong>At least one</strong> reports a diagram without any cycle; both only report, since a cycle is built step by step. Loops on the same Element are set per Connection with <strong>Allow Loops</strong>.
    </p>

    <v-btn-toggle :model-value="rule ? rule.config.mode ?? 'forbid' : 'off'" mandatory density="compact" rounded="lg" color="primary" variant="outlined" :disabled="!store.definition" @update:model-value="setMode">
      <v-btn v-for="option in modeOptions" :key="option.value" :value="option.value" size="small">{{ option.label }}</v-btn>
    </v-btn-toggle>

    <template v-if="rule">
      <v-switch :model-value="rule.config.ignoreDirection ?? false" color="primary" density="compact" hide-details label="Ignore direction" class="mt-2" @update:model-value="(value: boolean | null) => setConfigField('ignoreDirection', value || undefined)" />
      <p class="text-caption text-medium-emphasis">A cycle counts regardless of the Connection direction, e.g. wires in a circuit.</p>

      <template v-for="section in typeSections" :key="section.field">
        <p class="text-body-2 text-medium-emphasis mt-3 mb-2">{{ section.text }} <strong>All</strong> = {{ section.all }}; otherwise only the checked types.</p>

        <!-- Gleiche Darstellung wie die Allowed Connection Refinement: All oder ausgewählte Typen -->
        <v-sheet class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
          <v-table density="compact" class="cycle-matrix">
            <thead>
              <tr>
                <th class="text-center">All</th>
                <th v-for="type in section.options" :key="`head-${type}`" class="text-center">{{ type }}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="text-center">
                  <v-btn variant="elevated" class="matrix-button rounded-lg" :color="selectedTypes(section.field).length === 0 ? 'primary' : undefined" size="small" @click="setTypes(section.field, [])">
                    <v-icon size="16">mdi-select-all</v-icon>
                  </v-btn>
                </td>
                <td v-for="type in section.options" :key="`cell-${type}`" class="text-center">
                  <v-btn v-bind="cellStyle(section.field, type)" class="matrix-button rounded-lg" size="small" @click="toggleType(section, type)">
                    <v-icon size="16">{{ cellIcon(section.field, type) }}</v-icon>
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-sheet>
      </template>

      <v-textarea
        :model-value="rule.config.messageTemplate"
        rows="2"
        density="compact"
        variant="outlined"
        label="Error Message Template"
        auto-grow
        :hint="(rule.config.mode ?? 'forbid') === 'forbid' ? 'Use placeholders such as {source}, {target}' : 'Use the placeholder {element}'"
        persistent-hint
        class="mt-3"
        @update:model-value="(value: string) => setConfigField('messageTemplate', value ?? '')"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AcyclicRule, CycleMode } from '@/model/Syntax'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import { DEFAULT_CYCLE_MESSAGE_TEMPLATES } from '@/utils/acyclic'

const store = useDiagramLanguages()

const rule = computed(() => store.definition?.syntax.find((entry): entry is AcyclicRule => entry.ruleType === 'acyclic'))

const modeOptions: { value: CycleMode | 'off'; label: string }[] = [
  { value: 'off', label: 'Off' },
  { value: 'forbid', label: 'Forbid' },
  { value: 'every', label: 'Every Element' },
  { value: 'any', label: 'At least one' }
]

type CycleConfig = AcyclicRule['config']

// Standardwerte entfernen das Feld, damit Umstellen und Zurückstellen den gespeicherten Stand ergibt
const setConfigField = <K extends keyof CycleConfig>(field: K, value: CycleConfig[K] | undefined) => {
  if (!rule.value) return
  const config = { ...rule.value.config }
  if (value === undefined) Reflect.deleteProperty(config, field)
  else config[field] = value
  store.setAcyclicRule(config)
}

// Eine unveränderte Standardmeldung wechselt mit dem Modus, eine eigene bleibt
const setMode = (selected: string) => {
  const value = selected as CycleMode | 'off'
  if (value === 'off') return store.setAcyclicRule(null)
  const previous = rule.value?.config
  const template = previous?.messageTemplate ?? ''
  const isDefault = !template.trim() || Object.values(DEFAULT_CYCLE_MESSAGE_TEMPLATES).includes(template)
  const config: CycleConfig = { ...previous, messageTemplate: isDefault ? DEFAULT_CYCLE_MESSAGE_TEMPLATES[value] : template }
  if (value === 'forbid') delete config.mode
  else config.mode = value
  store.setAcyclicRule(config)
}

// Wie in SyntaxEditorForm: semantischer Typ der Verbindung, sonst ihr Typ
const connectionOptions = computed(() => [...new Set((store.definition?.connections ?? []).map((connection) => connection.connectionType || connection.type))])

// Nur verbindbare Elemente können auf einem Zyklus liegen
const elementOptions = computed(() => (store.definition?.elements ?? []).filter((element) => element.connectable).map((element) => element.type))

type TypeField = 'connectionTypes' | 'elementTypes'

// Verbindungstypen gelten für alle Modi, die Elementauswahl nur für every
const typeSections = computed(() => {
  const sections: { field: TypeField; text: string; all: string; options: string[] }[] = [{ field: 'connectionTypes', text: 'Connections that count for a cycle.', all: 'every Connection', options: connectionOptions.value }]
  if (rule.value?.config.mode === 'every') sections.push({ field: 'elementTypes', text: 'Elements that must be part of a cycle.', all: 'every Element', options: elementOptions.value })
  return sections
})

const selectedTypes = (field: TypeField): string[] => rule.value?.config[field] ?? []

const setTypes = (field: TypeField, types: string[]) => setConfigField(field, types.length > 0 ? types : undefined)

// Reihenfolge der Sprache, damit Aus- und wieder Einschalten den gespeicherten Stand ergibt
const toggleType = (section: { field: TypeField; options: string[] }, type: string) => {
  const types = selectedTypes(section.field)
  const next = types.includes(type) ? types.filter((entry) => entry !== type) : [...types, type]
  setTypes(section.field, [...section.options.filter((entry) => next.includes(entry)), ...next.filter((entry) => !section.options.includes(entry))])
}

// Ohne Auswahl zählen alle Typen (getönt), sonst nur die gewählten
const cellStyle = (field: TypeField, type: string) => {
  const types = selectedTypes(field)
  if (types.length === 0) return { color: 'primary', variant: 'tonal' as const }
  return types.includes(type) ? { color: 'primary', variant: 'elevated' as const } : { variant: 'elevated' as const }
}

const cellIcon = (field: TypeField, type: string): string => {
  const types = selectedTypes(field)
  if (types.length === 0) return 'mdi-check-all'
  return types.includes(type) ? 'mdi-check' : 'mdi-minus'
}
</script>

<style scoped>
.matrix-wrapper {
  overflow: auto;
  max-width: 100%;
}

.cycle-matrix {
  width: max-content;
}

.cycle-matrix thead th {
  background: #f6f8fb;
  white-space: nowrap;
}

.matrix-button {
  width: 38px;
  height: 30px;
  min-width: 38px;
}
</style>
