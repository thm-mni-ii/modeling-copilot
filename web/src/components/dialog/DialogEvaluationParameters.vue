<template>
  <v-dialog :model-value="modelValue" max-width="480" :persistent="busy" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Auswertung starten</v-card-title>
      <v-form v-model="valid" @submit.prevent="confirm">
        <v-card-text>
          <p class="text-body-2 mb-4">Die Parameter gelten für diese Auswertung. Angepasste Werte bleiben bis zum Neuladen der Seite erhalten.</p>
          <v-switch v-model="draft.textSimilarity" label="Textähnlichkeit (Levenshtein) einbeziehen" color="primary" density="compact" hide-details class="mb-3" :disabled="busy" />
          <v-text-field
            v-model.number="draft.levenshteinThreshold"
            type="number"
            label="Levenshtein-Mindestähnlichkeit"
            min="0"
            max="1"
            step="0.05"
            variant="outlined"
            density="compact"
            :rules="[thresholdRule]"
            :disabled="busy || !draft.textSimilarity"
            hint="0 bis 1. Höhere Werte verlangen ähnlichere Beschriftungen für eine Zuordnung."
            persistent-hint
          />
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :disabled="busy" @click="Object.assign(draft, defaults)">Standardwerte</v-btn>
          <v-spacer />
          <v-btn variant="text" :disabled="busy" @click="emit('update:modelValue', false)">Abbrechen</v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="busy" :disabled="busy || valid === false">Auswertung starten</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
const defaults = { textSimilarity: true, levenshteinThreshold: 0.8 }
// Module scope: survives reopening the dialog, resets on page reload.
let saved = { ...defaults }
</script>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import type { EvaluationParameters } from '@/services/api/types/evaluation'

const props = defineProps<{ modelValue: boolean; busy: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; confirm: [parameters: EvaluationParameters] }>()
const draft = reactive({ ...saved })
const valid = ref<boolean | null>(null)

watch(() => props.modelValue, (open) => {
  if (open) Object.assign(draft, saved)
})

const thresholdRule = (value: unknown) =>
  !draft.textSimilarity || (typeof value === 'number' && value >= 0 && value <= 1) || 'Wert zwischen 0 und 1 angeben.'

const confirm = () => {
  if (props.busy || thresholdRule(draft.levenshteinThreshold) !== true) return
  saved = { ...draft }
  emit('confirm', { levenshteinThreshold: draft.textSimilarity ? draft.levenshteinThreshold : null })
}
</script>
