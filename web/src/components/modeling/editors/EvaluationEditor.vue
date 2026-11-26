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
                <template v-for="(group, index) in groups" :key="group.id">
                <tr>
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
                  <td class="text-center text-no-wrap">
                    <v-btn v-if="typeField === 'elementTypes'" :icon="openSettings.has(group.id) ? 'mdi-cog' : 'mdi-cog-outline'" :color="group.passThrough || group.branching ? 'primary' : undefined" variant="text" size="small" :aria-label="`Settings of ${group.name || `Group ${index + 1}`}`" :aria-expanded="openSettings.has(group.id)" @click="toggleSettings(group.id)" />
                    <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="disabled" :aria-label="`Delete ${group.name || `Group ${index + 1}`}`" @click="removeGroup(group.id)" />
                  </td>
                </tr>
                <tr v-if="typeField === 'elementTypes' && openSettings.has(group.id)" class="settings-row">
                  <td :colspan="types.length + 2" class="py-2">
                    <div class="group-settings d-flex flex-column ga-2">
                      <div>
                        <div class="text-subtitle-2">Additional checks</div>
                        <div class="text-body-2 text-medium-emphasis">Run on top of the comparison. Matching within the group stays the same.</div>
                      </div>
                      <v-sheet border rounded="lg" class="pa-3 d-flex align-start ga-3">
                        <v-switch :model-value="group.passThrough ?? false" color="primary" inset density="compact" hide-details :disabled="disabled" aria-label="Connect through members" class="settings-switch" @update:model-value="setPassThrough(group, !!$event)" />
                        <div>
                          <div class="text-subtitle-2">Connect through members</div>
                          <div class="text-body-2 text-medium-emphasis">Connection rules skip members. <code>{{ passThroughExample(group).path }}</code> is allowed when <code>{{ passThroughExample(group).direct }}</code> is allowed.</div>
                        </div>
                      </v-sheet>
                      <v-sheet border rounded="lg" class="pa-3 d-flex flex-column ga-3">
                        <div class="d-flex align-start ga-3">
                          <v-switch :model-value="!!group.branching" color="primary" inset density="compact" hide-details :disabled="disabled" aria-label="Branching forms" class="settings-switch" @update:model-value="setBranching(group, !!$event)" />
                          <div>
                            <div class="text-subtitle-2">Branching forms</div>
                            <div class="text-body-2 text-medium-emphasis">Each member needs a fitting number of incoming and outgoing connections. It is valid when it matches at least one form.</div>
                          </div>
                        </div>
                        <div v-if="group.branching" class="settings-hint d-flex flex-column ga-2">
                          <v-sheet v-for="(form, formIndex) in group.branching.forms" :key="formIndex" border rounded="lg" class="pa-2 d-flex flex-column ga-2">
                            <div class="d-flex flex-wrap align-center ga-2">
                              <v-text-field v-model="form.name" placeholder="Form name" variant="plain" density="compact" hide-details :disabled="disabled" :aria-label="`Form ${formIndex + 1} name`" class="form-name font-weight-medium" />
                              <template v-for="key in boundKeys" :key="key">
                                <v-menu :close-on-content-click="false">
                                  <template #activator="{ props: menu }">
                                    <v-btn v-bind="menu" variant="outlined" class="bounds-box text-none" :disabled="disabled" :aria-label="`${key} of ${form.name}: ${boundsText(form[key])}`">
                                      <span class="d-flex flex-column align-start">
                                        <span class="text-caption text-medium-emphasis"><v-icon size="14">{{ key === 'incoming' ? 'mdi-arrow-bottom-right' : 'mdi-arrow-top-right' }}</v-icon> {{ key === 'incoming' ? 'Incoming' : 'Outgoing' }}</span>
                                        <span class="text-body-2 font-weight-medium">{{ boundsText(form[key]) }}</span>
                                      </span>
                                    </v-btn>
                                  </template>
                                  <v-card class="pa-3"><CardinalityFields v-model="form[key]" :label="key === 'incoming' ? 'Incoming' : 'Outgoing'" :disabled="disabled" /></v-card>
                                </v-menu>
                              </template>
                              <span class="text-body-2 text-medium-emphasis ml-2">Counts</span>
                              <v-select :model-value="form.connectionTypes ?? []" :items="connectionTypes" placeholder="all connections" persistent-placeholder multiple chips closable-chips variant="outlined" density="compact" hide-details :disabled="disabled" :aria-label="`Connection types counted for ${form.name}`" class="exception-select" @update:model-value="setFormConnectionTypes(form, $event ?? [])" />
                              <v-spacer />
                              <v-btn icon="mdi-delete-outline" variant="text" size="small" :disabled="disabled" :aria-label="`Delete form ${form.name}`" @click="group.branching.forms.splice(formIndex, 1)" />
                            </div>
                            <div v-if="form.notAfter && Object.keys(form.notAfter).length" class="text-caption text-medium-emphasis form-detail">Exceptions</div>
                            <div v-for="(row, rowIndex) in exceptionRows(form)" :key="rowIndex" class="d-flex flex-wrap align-center ga-2 form-detail">
                              <v-select :model-value="row.members" :items="[...row.members, ...freeMembers(group, form)]" multiple chips closable-chips variant="outlined" density="compact" hide-details :disabled="disabled" :aria-label="`Members of exception ${rowIndex + 1} in ${form.name}`" class="exception-select" @update:model-value="setRow(form, row, { members: $event ?? [], types: row.types })" />
                              <span class="text-body-2">can't be {{ form.name || 'this form' }} directly after</span>
                              <v-select :model-value="row.types" :items="elementTypes" placeholder="Element types" multiple chips closable-chips variant="outlined" density="compact" hide-details :disabled="disabled" :aria-label="`Preceding types of exception ${rowIndex + 1} in ${form.name}`" class="exception-select" @update:model-value="setRow(form, row, { members: row.members, types: $event ?? [] })" />
                              <v-btn icon="mdi-close" variant="text" size="small" :disabled="disabled" :aria-label="`Remove exception ${rowIndex + 1}`" @click="setRow(form, row, { members: [], types: [] })" />
                            </div>
                            <div v-if="freeMembers(group, form).length" class="form-detail"><v-btn size="small" variant="text" color="primary" prepend-icon="mdi-plus" :disabled="disabled" @click="form.notAfter = { ...form.notAfter, [freeMembers(group, form)[0]]: [] }">Add exception</v-btn></div>
                          </v-sheet>
                          <div><v-btn size="small" variant="text" color="primary" prepend-icon="mdi-plus" :disabled="disabled" @click="group.branching.forms.push({ name: '', incoming: { min: 0, max: null }, outgoing: { min: 0, max: null } })">Add form</v-btn></div>
                        </div>
                      </v-sheet>
                      <v-btn block size="small" variant="tonal" prepend-icon="mdi-chevron-up" class="text-none text-medium-emphasis" @click="toggleSettings(group.id)">Hide settings</v-btn>
                    </div>
                  </td>
                </tr>
                </template>
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
import type { BranchingForm, ComparisonGroup } from '@/model/DiagramLanguage'
import type { ChildElement, DiagramElement } from '@/model/Element'
import type { MultiplicityCardinality } from '@/model/Syntax'
import { evaluationConfigErrors, evaluationElementTypes } from '@/utils/languageEvaluation'
import ElementPreviewLabel from '@/components/modeling/form/ElementPreviewLabel.vue'
import CardinalityFields from '@/components/modeling/form/CardinalityFields.vue'
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
// Einstellungszeilen sind standardmäßig zu und werden über das Zahnrad geöffnet
const openSettings = ref(new Set<string>())
const toggleSettings = (id: string) => {
  const next = new Set(openSettings.value)
  if (!next.delete(id)) next.add(id)
  openSettings.value = next
}
const setPassThrough = (group: ComparisonGroup, value: boolean) => {
  if (value) group.passThrough = true
  else delete group.passThrough
}
// Beim Einschalten Split und Join vorbelegen; weitere Formen legt der Nutzer selbst an
const setBranching = (group: ComparisonGroup, value: boolean) => {
  if (value) group.branching = { forms: [{ name: 'Split', incoming: { min: 1, max: 1 }, outgoing: { min: 2, max: null } }, { name: 'Join', incoming: { min: 2, max: null }, outgoing: { min: 1, max: 1 } }] }
  else delete group.branching
}
// Beispiel aus den echten Typen der Sprache, z. B. „epk-event → epk-and → epk-function“
const passThroughExample = (group: ComparisonGroup) => {
  const member = group.elementTypes?.[0]
  const others = elementTypes.value.filter((type) => !group.elementTypes?.includes(type))
  const from = others[0]
  const to = others[1] ?? from
  return member && from ? { path: `${from} → ${member} → ${to}`, direct: `${from} → ${to}` } : { path: 'A → member → B', direct: 'A → B' }
}
const boundKeys = ['incoming', 'outgoing'] as const
// Bereich als kurzer Text für den Chip
const boundsText = ({ min, max }: MultiplicityCardinality) => max === null ? (min ? `${min} or more` : 'any') : min === max ? `exactly ${min}` : min ? `${min}–${max}` : `at most ${max}`
// Leerer Filter wird entfernt, dann zählen wieder alle Verbindungen
const setFormConnectionTypes = (form: BranchingForm, types: string[]) => {
  if (types.length) form.connectionTypes = types
  else delete form.connectionTypes
}
// Ausnahmen: Mitglieder mit gleicher Typliste bilden eine Zeile; gespeichert bleibt je Mitglied eine Liste, eine leere schränkt nichts ein
interface ExceptionRow { members: string[]; types: string[] }
const exceptionRows = (form: BranchingForm) => {
  const rows = new Map<string, ExceptionRow>()
  for (const [member, types] of Object.entries(form.notAfter ?? {})) {
    const key = [...types].sort().join('\n')
    const row = rows.get(key)
    if (row) row.members.push(member)
    else rows.set(key, { members: [member], types })
  }
  return [...rows.values()]
}
const freeMembers = (group: ComparisonGroup, form: BranchingForm) => groupTypes(group).filter((member) => !(member in (form.notAfter ?? {})))
// Zeile ersetzen, ihre Position bleibt erhalten
const setRow = (form: BranchingForm, row: ExceptionRow, next: ExceptionRow) => {
  const entries: [string, string[]][] = []
  for (const [member, types] of Object.entries(form.notAfter ?? {})) {
    if (!row.members.includes(member)) entries.push([member, types])
    else if (member === row.members[0]) entries.push(...next.members.map((entry): [string, string[]] => [entry, next.types]))
  }
  if (entries.length) form.notAfter = Object.fromEntries(entries)
  else delete form.notAfter
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
.group-settings { position: sticky; left: 12px; max-width: min(1100px, 90vw); }
.settings-switch { flex: 0 0 auto; }
.settings-hint { margin-left: 64px; }
.form-name { flex: 0 0 120px; }
.form-detail { margin-left: 128px; }
.exception-select { flex: 0 0 240px; }
.bounds-box { height: auto !important; min-width: 112px; padding: 4px 12px; letter-spacing: normal; }
</style>
