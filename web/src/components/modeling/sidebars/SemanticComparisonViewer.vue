<template>
  <v-btn size="x-small" variant="text" prepend-icon="mdi-table-search" title="Vergleichsergebnisse als Übersicht anzeigen" @click="dialog = true">Übersicht</v-btn>
  <v-dialog v-model="dialog" max-width="1400" aria-label="Semantische Vergleichsergebnisse">
    <v-card v-if="dialog" class="semantic-viewer">
      <v-card-title class="d-flex align-center ga-2">
        <span class="text-body-1">Vergleichsergebnisse</span>
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" aria-label="Übersicht schließen" @click="dialog = false" />
      </v-card-title>
      <v-card-text class="semantic-toolbar pt-0 pb-2">
        <div class="d-flex flex-wrap ga-3 text-caption text-medium-emphasis mb-2">
          <span v-for="counter in counters" :key="counter.key">{{ counter.label }}: {{ counter.value }}</span>
        </div>
        <v-tabs v-model="matrix" density="compact" color="primary" aria-label="Vergleichsart">
          <v-tab value="elements">Elemente</v-tab>
          <v-tab value="connections">Verbindungsbeschriftungen</v-tab>
        </v-tabs>
        <p class="text-caption text-medium-emphasis mt-2 mb-0">Sortierung zeigt Ähnlichkeiten, keine bestätigte Zuordnung. Alle Kandidaten bleiben erhalten.</p>
      </v-card-text>
      <v-divider />
      <div class="semantic-layout">
        <aside class="semantic-references" aria-label="Referenzelemente">
          <v-text-field v-model="search" label="Referenz suchen" aria-label="Referenz suchen (ID oder Beschriftung)" placeholder="ID oder Beschriftung" prepend-inner-icon="mdi-magnify" variant="outlined" density="compact" hide-details clearable class="semantic-search ma-2" />
          <div class="text-caption text-medium-emphasis px-3 pb-1">{{ filteredReferences.length }} / {{ references.length }} Referenzen</div>
          <v-list density="compact" class="semantic-reference-list" aria-label="Referenz auswählen">
            <v-list-item v-for="reference in filteredReferences" :key="reference.id" :active="selected?.id === reference.id" color="primary" @click="selectedIds[matrix] = reference.id">
              <v-list-item-title>{{ reference.label || '(ohne Beschriftung)' }}</v-list-item-title>
              <v-list-item-subtitle>{{ reference.id }} · {{ reference.candidates.length }} Kandidaten</v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <p v-if="!filteredReferences.length" class="text-caption text-medium-emphasis pa-3">{{ references.length ? 'Keine Referenz zur Suche gefunden.' : matrix === 'connections' ? 'Keine Verbindungstextpaare vorhanden.' : 'Keine Elementpaare vorhanden.' }}</p>
        </aside>
        <section class="semantic-candidates" aria-label="Kandidaten der ausgewählten Referenz">
          <template v-if="selected">
            <div class="pa-3">
              <div class="text-body-2 font-weight-medium selected-reference">Referenz: {{ selected.label || '(ohne Beschriftung)' }} ({{ selected.id }})</div>
              <div class="text-caption text-medium-emphasis mt-1">{{ selected.candidates.length }} Kandidaten</div>
            </div>
            <div class="semantic-table-scroll" tabindex="0" aria-label="Kandidatentabelle, horizontal scrollbar">
              <v-data-table v-model:sort-by="sortBy" :headers="headers" :items="selected.candidates" :items-per-page="-1" must-sort density="compact" class="semantic-table" no-data-text="Keine Kandidaten für diese Referenz vorhanden.">
                <template #[`item.scoreStatus`]="{ item }">{{ statusLabel(item) }}</template>
                <template v-for="key in ['referenceOwnerId', 'submissionOwnerId', 'kind', 'connectionLabelId', 'comparisonBasis']" :key="key" #[`item.${key}`]="{ value }">{{ value || '—' }}</template>
                <template #[`item.label`]="{ item }">{{ item.label || '(ohne Beschriftung)' }}</template>
                <template v-for="method in prepared.methods" :key="method.name" #[`header.score:${method.name}`]="{ column, getSortIcon }">
                  <div class="v-data-table-header__content">
                    <div>
                      <div>{{ method.label }}</div>
                      <div v-if="method.scoreRange" class="text-caption text-medium-emphasis">{{ method.scoreRange[0] }} … {{ method.scoreRange[1] }}</div>
                      <div v-if="method.missingMetadata" class="text-caption text-medium-emphasis">Ohne Metadaten</div>
                    </div>
                    <v-icon class="v-data-table-header__sort-icon" :icon="getSortIcon(column)" />
                  </div>
                </template>
                <template v-for="method in prepared.methods" :key="method.name" #[`item.score:${method.name}`]="{ item }">
                  <span :title="semanticScore(item, method.name) === undefined ? 'Score nicht verfügbar' : undefined">{{ semanticScore(item, method.name)?.toFixed(3) ?? '—' }}</span>
                </template>
                <template #bottom />
              </v-data-table>
            </div>
            <p class="text-caption text-medium-emphasis px-3 py-2 mb-0">— Score nicht verfügbar. Werte werden mit drei Dezimalstellen angezeigt.</p>
          </template>
          <p v-else class="text-body-2 text-medium-emphasis pa-4">{{ references.length ? 'Wähle eine Referenz aus.' : matrix === 'connections' ? 'Keine Verbindungstextpaare vorhanden.' : 'Keine Elementpaare vorhanden.' }}</p>
        </section>
      </div>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import { prepareSemanticComparison, semanticScore, type SemanticCandidate } from '@/utils/semanticComparison'

const props = defineProps<{ result: JsonObject }>()
const dialog = ref(false)
const matrix = ref<'elements' | 'connections'>('elements')
const search = ref('')
const selectedIds = ref<{ elements: string | null; connections: string | null }>({ elements: null, connections: null })
const sortBy = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'id', order: 'asc' }])
const prepared = computed(() => dialog.value ? prepareSemanticComparison(props.result) : { methods: [], elements: [], connections: [] })
const references = computed(() => prepared.value[matrix.value])
const filteredReferences = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('de')
  return references.value.filter((reference) => `${reference.id} ${reference.label}`.toLocaleLowerCase('de').includes(query))
})
const selected = computed(() => references.value.find((reference) => reference.id === selectedIds.value[matrix.value]) ?? references.value[0])
const headerProps = (key: string, className?: string) => ({
  class: className,
  tabindex: 0,
  'aria-sort': sortBy.value[0]?.key === key ? (sortBy.value[0].order === 'desc' ? 'descending' : 'ascending') : 'none',
  onKeydown: (event: KeyboardEvent) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    ;(event.currentTarget as HTMLElement).click()
  }
})
const headers = computed(() => [
  { key: 'id', title: 'Abgabe-ID', headerProps: headerProps('id', 'candidate-id'), cellProps: { class: 'candidate-id' }, sort: (a: string, b: string) => a.localeCompare(b, 'de', { numeric: true }) },
  { key: 'label', title: 'Abgabebeschriftung', headerProps: headerProps('label', 'candidate-label'), cellProps: { class: 'candidate-label' } },
  ...(matrix.value === 'connections' ? [
    { key: 'referenceOwnerId', title: 'Referenzverbindung-ID' },
    { key: 'submissionOwnerId', title: 'Abgabeverbindung-ID' },
    { key: 'kind', title: 'Beschriftungsart' },
    { key: 'connectionLabelId', title: 'Beschriftungs-ID' }
  ] : [{ key: 'comparisonBasis', title: 'Vergleichsbasis' }]).map((header) => ({ ...header, headerProps: headerProps(header.key) })),
  { key: 'scoreStatus', title: 'Status', headerProps: headerProps('scoreStatus') },
  ...prepared.value.methods.map((method) => ({
    key: `score:${method.name}`,
    title: method.label,
    align: 'end' as const,
    headerProps: { ...headerProps(`score:${method.name}`, 'score-column'), title: method.name },
    cellProps: { class: 'score-column' },
    sortRaw: (left: SemanticCandidate, right: SemanticCandidate) => {
      const a = semanticScore(left, method.name)
      const b = semanticScore(right, method.name)
      // Vuetify swaps operands for descending sort; keep unavailable scores last.
      const descending = sortBy.value[0]?.order === 'desc'
      if (a === undefined) return b === undefined ? 0 : descending ? -1 : 1
      if (b === undefined) return descending ? 1 : -1
      return a - b
    }
  }))
])
const counters = computed(() => [
  { key: 'candidatePairCount', label: 'Elementpaare' },
  { key: 'scoredPairCount', label: 'Mit Scores' },
  { key: 'unavailablePairCount', label: 'Ohne Scores' }
].filter(({ key }) => typeof props.result[key] === 'number').map((counter) => ({ ...counter, value: props.result[counter.key] })))
const statusLabel = (candidate: SemanticCandidate) => {
  if (candidate.scoreStatus === 'unavailable') {
    const reason = ({ missing_text: 'Text fehlt', unsupported_text: 'Text nicht unterstützt' } as Record<string, string>)[candidate.unavailableReason] ?? candidate.unavailableReason
    return `Nicht verfügbar${reason ? `: ${reason}` : ''}`
  }
  return candidate.scoreStatus === 'scored' ? 'Bewertet' : candidate.scoreStatus || '—'
}
</script>

<style scoped>
.semantic-viewer { display: flex; flex-direction: column; height: min(850px, 90dvh); }
.semantic-toolbar { flex: 0 0 auto; }
.semantic-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); flex: 1; min-height: 0; }
.semantic-references { display: flex; flex-direction: column; min-height: 0; border-right: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.semantic-search { flex: 0 0 auto; }
.semantic-reference-list { flex: 1; overflow: auto; }
.semantic-reference-list :deep(.v-list-item-title), .semantic-reference-list :deep(.v-list-item-subtitle) { white-space: normal; overflow-wrap: anywhere; }
.semantic-candidates { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.selected-reference { overflow-wrap: anywhere; }
.semantic-table-scroll { overflow: auto; flex: 1; min-height: 0; }
.semantic-table { width: max-content; min-width: 100%; }
.semantic-table :deep(.v-table__wrapper) { overflow: visible; }
.semantic-table :deep(th), .semantic-table :deep(td) { padding: 6px 12px; }
.semantic-table :deep(thead th) { position: sticky; top: 0; z-index: 2; background: rgb(var(--v-theme-surface)); white-space: nowrap; }
.semantic-table :deep(.candidate-id), .semantic-table :deep(.candidate-label) { position: sticky; z-index: 1; background: rgb(var(--v-theme-surface)); overflow-wrap: anywhere; }
.semantic-table :deep(.candidate-id) { left: 0; min-width: 140px; max-width: 140px; width: 140px; }
.semantic-table :deep(.candidate-label) { left: 140px; min-width: 200px; max-width: 200px; width: 200px; }
.semantic-table :deep(thead .candidate-id), .semantic-table :deep(thead .candidate-label) { z-index: 3; }
.semantic-table :deep(.score-column) { text-align: right; font-variant-numeric: tabular-nums; }
@media (max-width: 700px) {
  .semantic-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(140px, 30%) minmax(0, 1fr); }
  .semantic-references { border-right: 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
  .semantic-table :deep(.candidate-label) { position: static; }
}
</style>
