<template>
  <section>
    <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
      <v-icon color="primary" class="mr-2">mdi-sync-off</v-icon>
      <span>No Cycles</span>
    </div>

    <p class="text-body-2 text-medium-emphasis mb-3">Forbids Connections that close a cycle along the Connection direction. Without this rule, cycles are allowed. Loops on the same Element are set per Connection with <strong>Allow Loops</strong>.</p>

    <v-switch :model-value="rule !== undefined" color="primary" density="compact" hide-details label="Forbid cycles" :disabled="!store.definition" @update:model-value="(enabled: boolean | null) => store.setAcyclicRule(enabled ? { messageTemplate: DEFAULT_ACYCLIC_MESSAGE_TEMPLATE } : null)" />

    <template v-if="rule">
      <p class="text-body-2 text-medium-emphasis mt-3 mb-2">Connections that count for a cycle. <strong>All</strong> = every Connection; otherwise only the checked types.</p>

      <!-- Gleiche Darstellung wie die Allowed Connection Refinement: All oder ausgewählte Typen -->
      <v-sheet class="matrix-wrapper elevation-1 rounded-lg bg-white" border>
        <v-table density="compact" class="cycle-matrix">
          <thead>
            <tr>
              <th class="text-center">All</th>
              <th v-for="connectionType in connectionOptions" :key="`head-${connectionType}`" class="text-center">{{ connectionType }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="text-center">
                <v-btn variant="elevated" class="matrix-button rounded-lg" :color="selectedTypes.length === 0 ? 'primary' : undefined" size="small" @click="setConnectionTypes([])">
                  <v-icon size="16">mdi-select-all</v-icon>
                </v-btn>
              </td>
              <td v-for="connectionType in connectionOptions" :key="`cell-${connectionType}`" class="text-center">
                <v-btn v-bind="cellStyle(connectionType)" class="matrix-button rounded-lg" size="small" @click="toggleConnectionType(connectionType)">
                  <v-icon size="16">{{ cellIcon(connectionType) }}</v-icon>
                </v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-sheet>

      <v-textarea :model-value="rule.config.messageTemplate" rows="2" density="compact" variant="outlined" label="Error Message Template" auto-grow hint="Use placeholders such as {source}, {target}" persistent-hint class="mt-3" @update:model-value="(value: string) => store.setAcyclicRule({ ...rule!.config, messageTemplate: value ?? '' })" />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AcyclicRule } from '@/model/Syntax'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import { DEFAULT_ACYCLIC_MESSAGE_TEMPLATE } from '@/utils/acyclic'

const store = useDiagramLanguages()

const rule = computed(() => store.definition?.syntax.find((entry): entry is AcyclicRule => entry.ruleType === 'acyclic'))

// Wie in SyntaxEditorForm: semantischer Typ der Verbindung, sonst ihr Typ
const connectionOptions = computed(() => [...new Set((store.definition?.connections ?? []).map((connection) => connection.connectionType || connection.type))])

const selectedTypes = computed(() => rule.value?.config.connectionTypes ?? [])

// Leere Auswahl entfernt das Feld, damit Umstellen und Zurückstellen den gespeicherten Stand ergibt
const setConnectionTypes = (types: string[]) => {
  if (!rule.value) return
  const config = { ...rule.value.config }
  if (types.length > 0) config.connectionTypes = types
  else delete config.connectionTypes
  store.setAcyclicRule(config)
}

// Reihenfolge der Verbindungen der Sprache, damit Aus- und wieder Einschalten den gespeicherten Stand ergibt
const toggleConnectionType = (connectionType: string) => {
  const types = selectedTypes.value
  const next = types.includes(connectionType) ? types.filter((entry) => entry !== connectionType) : [...types, connectionType]
  setConnectionTypes([...connectionOptions.value.filter((entry) => next.includes(entry)), ...next.filter((entry) => !connectionOptions.value.includes(entry))])
}

// Ohne Auswahl zählen alle Verbindungen (getönt), sonst nur die gewählten Typen
const cellStyle = (connectionType: string) => {
  if (selectedTypes.value.length === 0) return { color: 'primary', variant: 'tonal' as const }
  return selectedTypes.value.includes(connectionType) ? { color: 'primary', variant: 'elevated' as const } : { variant: 'elevated' as const }
}

const cellIcon = (connectionType: string): string => {
  if (selectedTypes.value.length === 0) return 'mdi-check-all'
  return selectedTypes.value.includes(connectionType) ? 'mdi-check' : 'mdi-minus'
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
