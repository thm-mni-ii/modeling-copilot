<template>
  <div class="mt-5">
    <v-text-field :model-value="modelValue.title" variant="outlined" label="Fragetitel" :rules="[titleRule]" maxlength="256" @update:model-value="patch({ title: $event })" />
    <v-select :model-value="modelValue.type" variant="outlined" label="Fragetyp" :items="questionTypes" @update:model-value="changeType" />
    <v-switch :model-value="modelValue.isRequired" label="Pflichtfrage" color="primary" @update:model-value="patch({ isRequired: !!$event, ...(modelValue.type === 'matrix' ? { isAllRowRequired: !!$event } : {}) })" />
    <v-divider class="mb-5" />
    <p v-if="modelValue.type === 'comment'" class="text-body-2 text-medium-emphasis">Teilnehmende antworten in einem mehrzeiligen Textfeld.</p>
    <v-textarea v-if="['radiogroup', 'checkbox'].includes(modelValue.type)" :model-value="modelValue.choices?.join('\n')" variant="outlined" label="Antwortoptionen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="patch({ choices: lines($event) })" />
    <template v-if="modelValue.type === 'matrix'">
      <v-textarea :model-value="modelValue.rows?.join('\n')" variant="outlined" label="Aussagen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="patch({ rows: lines($event) })" />
      <v-textarea :model-value="modelValue.columns?.join('\n')" variant="outlined" label="Skalenoptionen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="patch({ columns: lines($event) })" />
    </template>
    <div v-if="modelValue.type === 'rating'" class="d-flex ga-4">
      <v-text-field :model-value="modelValue.rateMin" variant="outlined" label="Minimum" type="number" :rules="[() => ratingRule(modelValue)]" @update:model-value="patch({ rateMin: Number($event) })" />
      <v-text-field :model-value="modelValue.rateMax" variant="outlined" label="Maximum" type="number" :rules="[() => ratingRule(modelValue)]" @update:model-value="patch({ rateMax: Number($event) })" />
    </div>
  </div>
</template>
<script setup lang="ts">
import type { SurveyQuestion } from '@/services/surveys'
import { questionTypes, titleRule, optionsRule, ratingRule } from '@/utils/surveyEditor'
const props = defineProps<{ modelValue: SurveyQuestion }>()
const emit = defineEmits<{ 'update:modelValue': [question: SurveyQuestion] }>()
const lines = (v: string) => v.split('\n')
function patch(value: Partial<SurveyQuestion>) {
  emit('update:modelValue', { ...props.modelValue, ...value })
}
function changeType(type: SurveyQuestion['type']) {
  const { name, title, isRequired } = props.modelValue
  emit('update:modelValue', {
    name,
    title,
    isRequired,
    type,
    ...(type === 'radiogroup' || type === 'checkbox' ? { choices: ['Option 1', 'Option 2'] } : {}),
    ...(type === 'rating' ? { rateMin: 1, rateMax: 5 } : {}),
    ...(type === 'matrix' ? { rows: ['Aussage 1'], columns: ['Stimme nicht zu', 'Neutral', 'Stimme zu'], isAllRowRequired: isRequired } : {})
  })
}
</script>
