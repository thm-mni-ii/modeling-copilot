<template>
  <v-dialog :model-value="modelValue" max-width="720" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="d-flex align-center">{{ purpose === 'pulse' ? 'Impuls-Fragen auswählen' : 'Add questionnaires' }}<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Close questionnaire picker" @click="emit('update:modelValue', false)" /></v-card-title>
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-4">{{ purpose === 'pulse' ? 'Die Impulse werden zufällig aus diesem Pool ausgewählt. Jeder Fragebogen verwendet seine aktuelle veröffentlichte Version.' : 'Select questionnaires to add as separate stations. Each uses its current published release.' }}</p>
        <v-text-field v-model="query" label="Search questionnaires" prepend-inner-icon="mdi-magnify" variant="outlined" density="compact" clearable hide-details autofocus />
        <v-progress-linear v-if="loading" indeterminate class="mt-3" />
        <div class="picker-results mt-3">
          <v-list aria-label="Available questionnaires">
            <v-list-item v-for="survey in filtered" :key="survey.id" :disabled="!survey.activeReleaseId" :title="survey.title" :subtitle="!survey.activeReleaseId ? 'Publish a release before adding this questionnaire' : usedCount(survey.id) ? `Already used ${usedCount(survey.id)} time(s) · can be added again` : 'Current published release'" @click="toggle(survey.id)">
              <template #prepend><v-checkbox-btn :model-value="selected.includes(survey.id)" :disabled="!survey.activeReleaseId" :aria-label="`Select ${survey.title}`" @click.stop="toggle(survey.id)" /></template>
              <template #append><v-icon v-if="usedCount(survey.id)" size="18" color="primary">mdi-repeat</v-icon></template>
            </v-list-item>
          </v-list>
          <p v-if="!filtered.length && !loading" class="text-center text-medium-emphasis pa-8">{{ surveys.length ? 'No questionnaires match your search.' : 'No questionnaires available. Create and publish a questionnaire first.' }}</p>
        </div>
      </v-card-text>
      <v-card-actions class="px-6 pb-5">
        <span class="text-body-2 text-medium-emphasis">{{ selected.length }} selected</span><v-spacer /><v-btn @click="emit('update:modelValue', false)">Cancel</v-btn><v-btn color="primary" variant="flat" :disabled="!selected.length || loading" @click="emit('add', [...selected])">{{ purpose === 'pulse' ? 'Übernehmen' : `Add ${selected.length || ''} ${selected.length === 1 ? 'questionnaire' : 'questionnaires'}` }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Survey } from '@/services/surveys'
import type { PathStep } from '@/services/learningPaths'

const props = defineProps<{ modelValue: boolean; surveys: Survey[]; steps: PathStep[]; loading: boolean; purpose?: 'stations' | 'pulse' }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; add: [ids: string[]] }>()
const selected = ref<string[]>([]),
  query = ref('')
const filtered = computed(() => props.surveys.filter((survey) => survey.title.toLocaleLowerCase('en').includes((query.value ?? '').trim().toLocaleLowerCase('en'))))
const usedCount = (id: string) => props.steps.filter((step) => step.type === 'survey' && step.surveyId === id).length
const toggle = (id: string) => {
  if (!props.surveys.find((survey) => survey.id === id)?.activeReleaseId) return
  selected.value = selected.value.includes(id) ? selected.value.filter((value) => value !== id) : [...selected.value, id]
}
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      selected.value = []
      query.value = ''
    }
  }
)
</script>

<style scoped>
.picker-results {
  max-height: 45vh;
  overflow-y: auto;
}
</style>
