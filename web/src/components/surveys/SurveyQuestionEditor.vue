<template>
  <div class="mt-5">
    <v-text-field :model-value="modelValue.title" variant="outlined" label="Fragetitel" :rules="[titleRule]" maxlength="256" @update:model-value="patch({ title: $event })" />
    <v-textarea :model-value="modelValue.description" variant="outlined" label="Hinweis zur Frage (optional)" maxlength="2000" rows="2" @update:model-value="patch({ description: $event })" />
    <v-select v-if="pages?.length" :model-value="modelValue.page" :items="pages.map(page => ({ title: page.title, value: page.name }))" label="Seite" variant="outlined" @update:model-value="patch({ page: $event })" />
    <v-select :model-value="modelValue.type" variant="outlined" label="Fragetyp" :items="questionTypes" @update:model-value="changeType" />
    <v-switch :model-value="modelValue.isRequired" label="Pflichtfrage" color="primary" @update:model-value="patch({ isRequired: !!$event, ...(modelValue.type === 'matrix' ? { isAllRowRequired: !!$event } : {}) })" />
    <v-select :model-value="modelValue.visibleWhen" :items="[{ title: 'Hilfe-Button tatsächlich genutzt', value: 'help_requested' }, { title: 'Mindestens eine Piraten-Zwischenfrage beantwortet', value: 'pulse_answered' }]" label="Nur bei protokollierter Nutzung anzeigen (optional)" hint="Die Nutzung wird im Aufgabenabschluss serverseitig geprüft. Admin-Vorschauen zeigen alle Fragen." persistent-hint clearable variant="outlined" class="mb-4" @update:model-value="patch({ visibleWhen: $event || undefined })" />
    <v-select :model-value="condition?.source" :items="conditionSources.map(question => ({ title: question.title, value: question.name }))" clearable label="Nur nach bestimmter Antwort anzeigen (optional)" variant="outlined" @update:model-value="setConditionSource" />
    <v-select v-if="condition" :model-value="condition.choice" :items="conditionSources.find(question => question.name === condition?.source)?.choices ?? []" label="Bei dieser Antwort anzeigen" variant="outlined" @update:model-value="setConditionChoice" />
    <v-select v-if="condition && conditionSources.find(question => question.name === condition?.source)?.type === 'radiogroup'" :model-value="condition.operator" :items="[{ title: 'Bei der gewählten Antwort', value: '=' }, { title: 'Bei jeder anderen beantworteten Auswahl', value: '!=' }]" label="Bedingung" variant="outlined" @update:model-value="setConditionOperator" />
    <v-divider class="mb-5" />
    <p v-if="modelValue.type === 'comment'" class="text-body-2 text-medium-emphasis">Teilnehmende antworten in einem mehrzeiligen Textfeld.</p>
    <v-textarea v-if="['radiogroup', 'checkbox'].includes(modelValue.type)" :model-value="modelValue.choices?.join('\n')" variant="outlined" label="Antwortoptionen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="changeChoices" />
    <v-select v-if="modelValue.type === 'checkbox'" :model-value="modelValue.exclusiveChoices ?? []" :items="modelValue.choices ?? []" multiple chips variant="outlined" label="Exklusive Antworten (optional)" hint="Eine exklusive Antwort kann nicht zusammen mit anderen Optionen gewählt werden." persistent-hint class="mb-4" @update:model-value="patch({ exclusiveChoices: $event })" />
    <template v-if="modelValue.type === 'matrix'">
      <v-textarea :model-value="modelValue.rows?.join('\n')" variant="outlined" label="Aussagen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="patch({ rows: lines($event) })" />
      <v-textarea :model-value="modelValue.columns?.join('\n')" variant="outlined" label="Skalenoptionen (eine pro Zeile)" :rules="[optionsRule]" @update:model-value="patch({ columns: lines($event) })" />
    </template>
    <div v-if="modelValue.type === 'rating'" class="d-flex ga-4">
      <v-text-field :model-value="modelValue.rateMin" variant="outlined" label="Minimum" type="number" :rules="[() => ratingRule(modelValue)]" @update:model-value="patch({ rateMin: Number($event) })" />
      <v-text-field :model-value="modelValue.rateMax" variant="outlined" label="Maximum" type="number" :rules="[() => ratingRule(modelValue)]" @update:model-value="patch({ rateMax: Number($event) })" />
    </div>
    <template v-if="modelValue.type === 'rating'">
      <v-text-field :model-value="modelValue.minRateDescription" label="Beschriftung Minimum (optional)" maxlength="256" variant="outlined" @update:model-value="patch({ minRateDescription: $event || undefined })" />
      <v-text-field :model-value="modelValue.maxRateDescription" label="Beschriftung Maximum (optional)" maxlength="256" variant="outlined" @update:model-value="patch({ maxRateDescription: $event || undefined })" />
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { SurveyQuestion, SurveyPage } from '@/services/surveys'
import { questionTypes, titleRule, optionsRule, ratingRule } from '@/utils/surveyEditor'
const props = defineProps<{ modelValue: SurveyQuestion; pages?: SurveyPage[]; earlierQuestions?: SurveyQuestion[] }>()
const emit = defineEmits<{ 'update:modelValue': [question: SurveyQuestion] }>()
const lines = (v: string) => v.split('\n')
const conditionSources = computed(() => (props.earlierQuestions ?? []).filter(question => ['radiogroup', 'checkbox'].includes(question.type)))
const condition = computed(() => {
  const match = props.modelValue.visibleIf?.match(/^\{([a-zA-Z][a-zA-Z0-9_-]{0,79})\} (=|!=|contains) '([^']+)'$/)
  return match ? { source: match[1], operator: match[2], choice: match[3] } : null
})
function setCondition(source: string, choice: string, operator = '=') {
  const question = conditionSources.value.find(question => question.name === source)
  patch({ visibleIf: question && choice ? `{${source}} ${question.type === 'checkbox' ? 'contains' : operator} '${choice}'` : undefined })
}
function setConditionSource(source: string | null) {
  if (!source) return patch({ visibleIf: undefined })
  const question = conditionSources.value.find(question => question.name === source)
  setCondition(source, question?.choices?.[0] ?? '')
}
function setConditionChoice(choice: string) {
  if (condition.value) setCondition(condition.value.source, choice, condition.value.operator)
}
function setConditionOperator(operator: string) {
  if (condition.value) setCondition(condition.value.source, condition.value.choice, operator)
}
function patch(value: Partial<SurveyQuestion>) {
  emit('update:modelValue', { ...props.modelValue, ...value })
}
function changeChoices(value: string) {
  const choices = lines(value)
  patch({ choices, ...(props.modelValue.exclusiveChoices ? { exclusiveChoices: props.modelValue.exclusiveChoices.filter(choice => choices.includes(choice)) } : {}) })
}
function changeType(type: SurveyQuestion['type']) {
  const { name, title, isRequired, page, description, visibleIf, visibleWhen } = props.modelValue
  emit('update:modelValue', {
    name,
    title,
    isRequired,
    page,
    description,
    visibleIf,
    visibleWhen,
    type,
    ...(type === 'radiogroup' || type === 'checkbox' ? { choices: ['Option 1', 'Option 2'] } : {}),
    ...(type === 'rating' ? { rateMin: 1, rateMax: 5 } : {}),
    ...(type === 'matrix' ? { rows: ['Aussage 1'], columns: ['Stimme nicht zu', 'Neutral', 'Stimme zu'], isAllRowRequired: isRequired } : {})
  })
}
</script>
