<template>
  <section class="feedback-catalog my-3" aria-label="Vorschau des Studierenden-Feedbacks">
    <p v-if="!catalogObjects" class="text-caption text-medium-emphasis">Für diese Auswertung und Musterlösung liegt kein Feedbackkatalog vor. Er entsteht bei neuen Auswertungen, die Administrierende oder Moderierende starten.</p>
    <template v-else>
      <p class="text-caption text-medium-emphasis mb-2">Vorschau: genau das Feedback, das Lernende erhalten, wenn sie nur dieses Objekt markieren und die gewählte Hilfe anfordern. Wie konkret eine Hilfeart werden darf, ist fest vorgegeben.</p>
      <v-text-field v-model="search" density="compact" variant="outlined" hide-details clearable prepend-inner-icon="mdi-magnify" label="Objekt oder Typ suchen" class="my-2" />
      <p v-if="!groups.length" class="text-caption text-medium-emphasis">Keine Objekte für diese Auswahl.</p>
      <section v-for="group in groups" :key="group.name" class="mt-3" :aria-label="group.name">
        <h3 class="feedback-catalog__group">{{ group.name }} <span class="text-medium-emphasis">{{ group.objects.length }}</span></h3>
        <v-expansion-panels :model-value="expanded.filter(id => group.objects.some(object => object.cellId === id))" variant="accordion" multiple @update:model-value="value => setExpanded(group.objects, value as string[])">
          <v-expansion-panel v-for="object in group.objects" :id="`catalog-${object.cellId}`" :key="object.cellId" :value="object.cellId" elevation="0">
            <v-expansion-panel-title class="feedback-catalog__title">
              <span class="feedback-catalog__name">{{ object.label || `${object.typeName} (unbeschriftet)` }}</span>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <!-- Shared choices: switching here switches every opened object, so no control sits out of reach. -->
              <v-chip-group v-model="helpType" mandatory column selected-class="text-primary" aria-label="Angeforderte Hilfe">
                <v-chip v-for="option in helpOptions" :key="option.type" :value="option.type" :title="option.request" size="x-small" variant="outlined">{{ option.title }}</v-chip>
              </v-chip-group>
              <FeedbackView compact :entries="entries(object, helpType)" />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import FeedbackView from '@/components/feedback/FeedbackView.vue'
import type { EvaluationDetail, HelpFeedbackCatalogObject, HelpFeedbackEntry, HelpFeedbackPattern } from '@/services/api/types/evaluation'

// focus: a diagram click in this tab; seq re-triggers the same object.
const props = defineProps<{ detail: EvaluationDetail; referenceKey: string; focus?: { id: string; seq: number } | null }>()

type HelpType = 'help.clarify' | 'help.next_step' | 'help.example' | 'help.check' | 'help.solution'
// Order and wording follow the learner's choice in the help questionnaire.
const helpOptions: { type: HelpType; title: string; request: string }[] = [
  { type: 'help.clarify', title: 'Erklärung', request: 'Eine Erklärung, damit ich es verstehe' },
  { type: 'help.next_step', title: 'Nächster Schritt', request: 'Ein Hinweis auf den nächsten Schritt' },
  { type: 'help.example', title: 'Beispiel', request: 'Ein Beispiel' },
  { type: 'help.check', title: 'Prüfung', request: 'Eine Prüfung/Bestätigung meiner bisherigen Lösung' },
  { type: 'help.solution', title: 'Lösung', request: 'Eine konkrete Lösung bzw. Antwort' }
]
const helpType = ref<HelpType>('help.clarify')
const search = ref<string | null>('')

const catalogEntry = computed(() => {
  const step = props.detail.steps.find(item => item.status === 'succeeded' && item.result?.schema === 'feedback-report/v4' &&
    (item.result.pair as { referenceKey?: string } | undefined)?.referenceKey === props.referenceKey)
  const entries = Array.isArray(step?.result?.feedback) ? step.result.feedback as unknown as (HelpFeedbackEntry & { catalog?: HelpFeedbackCatalogObject[]; patterns?: Record<string, HelpFeedbackPattern> })[] : []
  return entries.find(entry => entry.type === 'help.catalog') ?? null
})
const catalogObjects = computed(() => catalogEntry.value?.catalog ?? null)
const objects = computed(() => catalogObjects.value ?? [])
const groups = computed(() => {
  const query = (search.value ?? '').trim().toLocaleLowerCase('de')
  const visible = objects.value.filter(object => !query || `${object.label} ${object.typeName}`.toLocaleLowerCase('de').includes(query))
  const byType = new Map<string, HelpFeedbackCatalogObject[]>()
  for (const object of visible) byType.set(object.typeName, [...(byType.get(object.typeName) ?? []), object])
  return [...byType].map(([name, items]) => ({
    name, objects: items.sort((a, b) => a.label.localeCompare(b.label, 'de'))
  })).sort((a, b) => a.name.localeCompare(b.name, 'de'))
})
const expanded = ref<string[]>([])
// Only the current object stays open, across all type groups: opening one closes the others.
const setExpanded = (items: HelpFeedbackCatalogObject[], value: string[]) => {
  const opened = value.find(id => !expanded.value.includes(id))
  expanded.value = opened ? [opened] : expanded.value.filter(id => value.includes(id) || !items.some(object => object.cellId === id))
}
watch(() => props.focus, async (focus) => {
  const object = focus && objects.value.find(item => item.cellId === focus.id)
  if (!object) return
  if (!groups.value.some(group => group.objects.includes(object))) search.value = ''
  expanded.value = [object.cellId]
  await nextTick()
  document.getElementById(`catalog-${object.cellId}`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
})
// Exactly the learner entry of one help type, rendered with the learner components.
// help.example patterns are stored once per compared element and resolved here.
const entries = (object: HelpFeedbackCatalogObject, type: HelpType): HelpFeedbackEntry[] => {
  const help = object.help[type], patterns = catalogEntry.value!.patterns ?? {}
  const objects = help.objects?.map(item => item.pattern ? { ...item, pattern: patterns[item.pattern.cellId] ?? item.pattern } : item)
  return [{ overview: catalogEntry.value!.overview, ...help, objects, notices: help.notices ?? [], type }]
}
</script>

<style scoped>
.feedback-catalog__group { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
.feedback-catalog__title { min-height: 36px !important; padding: 6px 10px; font-size: 12px; }
.feedback-catalog__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feedback-catalog :deep(.v-expansion-panel-text__wrapper) { padding: 4px 10px 10px; }
</style>
