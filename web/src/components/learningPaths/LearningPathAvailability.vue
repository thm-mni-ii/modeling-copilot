<template>
  <section>
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon size="21">mdi-lock-open-outline</v-icon>
      <h3 class="text-subtitle-1 font-weight-bold">Availability</h3>
    </div>
    <p class="text-body-2 text-medium-emphasis mb-4">Choose when this task becomes available.</p>
    <v-select :model-value="preset" :items="presets" label="Unlock this task" variant="outlined" @update:model-value="choosePreset" />
    <v-text-field v-if="preset === 'date'" :model-value="localDate(modelValue.conditions[0]?.at)" type="datetime-local" :label="`Available from (${timezone})`" variant="outlined" @update:model-value="setDate(modelValue.conditions[0], $event)" />
    <template v-if="preset === 'custom'">
      <v-select
        :model-value="modelValue.mode"
        :items="[
          { title: 'All conditions (AND)', value: 'all' },
          { title: 'Any condition (OR)', value: 'any' }
        ]"
        label="How conditions work together"
        variant="outlined"
        @update:model-value="emit('update:modelValue', { ...modelValue, mode: $event })"
      />
      <v-sheet v-for="(condition, index) in modelValue.conditions" :key="index" border rounded class="pa-3 mb-3">
        <div class="d-flex align-center ga-2"><v-select v-model="condition.type" :items="conditionTypes" label="Condition" density="compact" variant="outlined" hide-details @update:model-value="resetCondition(condition)" /><v-btn icon="mdi-close" size="small" variant="text" aria-label="Remove condition" @click="removeCondition(index)" /></div>
        <v-select v-if="condition.type !== 'at'" v-model="condition.stepId" :items="sources(condition.type === 'after')" label="Prerequisite" class="mt-3" variant="outlined" density="compact" hide-details />
        <v-text-field v-if="condition.type === 'score'" v-model.number="condition.value" type="number" min="0" max="100" label="Minimum score (%)" class="mt-3" variant="outlined" density="compact" hide-details />
        <v-text-field v-if="condition.type === 'after'" :model-value="(condition.seconds ?? 0) / 3600" type="number" min="0" step="0.25" label="Delay in hours" class="mt-3" variant="outlined" density="compact" hide-details @update:model-value="condition.seconds = Math.round(Number($event) * 3600)" />
        <v-text-field v-if="condition.type === 'at'" :model-value="localDate(condition.at)" type="datetime-local" :label="`Available from (${timezone})`" class="mt-3" variant="outlined" density="compact" hide-details @update:model-value="setDate(condition, $event)" />
      </v-sheet>
      <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="modelValue.conditions.length >= 50" @click="emit('update:modelValue', { ...modelValue, conditions: [...modelValue.conditions, newCondition('completed')] })">Add condition</v-btn>
      <p v-if="modelValue.conditions.some((c) => c.type === 'score')" class="text-caption mt-3">Score conditions require the future scoring integration.</p>
    </template>
    <div class="availability-summary mt-4"><v-icon size="17" class="mr-2">mdi-information-outline</v-icon>{{ summary }}</div>
    <p v-if="modelValue.conditions.some((c) => c.stepId)" class="text-caption text-medium-emphasis mt-2">Prerequisites reference specific tasks. Reordering the path keeps these links unchanged.</p>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Condition, PathStep } from '@/services/learningPaths'
import { availabilitySummary } from '@/utils/learningPathEditor'
type Preset = 'immediate' | 'previous' | 'date' | 'custom'
const props = defineProps<{ modelValue: PathStep['unlock']; step: PathStep; steps: PathStep[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: PathStep['unlock']] }>()
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
const previous = computed(() => props.steps[props.steps.findIndex((step) => step.id === props.step.id) - 1])
const explicitCustom = ref(false)
const preset = computed<Preset>(() => {
  if (explicitCustom.value) return 'custom'
  const rules = props.modelValue.conditions
  if (!rules.length) return 'immediate'
  if (rules.length === 1 && rules[0].type === 'at') return 'date'
  if (rules.length === 1 && rules[0].type === 'completed' && rules[0].stepId === previous.value?.id) return 'previous'
  return 'custom'
})
const presets = computed(() => [{ title: 'Immediately available', value: 'immediate' }, ...(previous.value ? [{ title: `After the previous task: ${previous.value.title}`, value: 'previous' }] : []), { title: 'Available from a date', value: 'date' }, { title: 'Custom rules', value: 'custom' }])
const conditionTypes = [
  { title: 'Task completed', value: 'completed' },
  { title: 'Minimum score', value: 'score' },
  { title: 'Fixed date and time', value: 'at' },
  { title: 'Relative delay', value: 'after' }
]
const summary = computed(() => availabilitySummary({ ...props.step, unlock: props.modelValue }, props.steps))
const newCondition = (type: Condition['type']): Condition => ({ type, stepId: type === 'completed' ? previous.value?.id ?? null : null, value: type === 'score' ? 50 : null, at: null, seconds: type === 'after' ? 0 : null, timezone })
const choosePreset = (value: Preset) => {
  explicitCustom.value = value === 'custom'
  if (value === 'custom') return
  const conditions: Condition[] = value === 'immediate' ? [] : [newCondition(value === 'previous' ? 'completed' : 'at')]
  emit('update:modelValue', { mode: 'all', conditions })
}
const sources = (includeStart: boolean) => [...(includeStart ? [{ title: 'Start of the run', value: null }] : []), ...props.steps.filter((step) => step.id !== props.step.id).map((step) => ({ title: step.title, value: step.id }))]
const resetCondition = (condition: Condition) => Object.assign(condition, newCondition(condition.type))
const removeCondition = (index: number) => emit('update:modelValue', { ...props.modelValue, conditions: props.modelValue.conditions.filter((_, i) => i !== index) })
const localDate = (value?: string | null) => {
  if (!value || !Number.isFinite(Date.parse(value))) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const setDate = (condition: Condition, value: string) => {
  condition.at = value && Number.isFinite(new Date(value).getTime()) ? new Date(value).toISOString() : null
  condition.timezone = timezone
}
watch(
  () => props.step.id,
  () => {
    explicitCustom.value = false
  }
)
</script>
<style scoped>
.availability-summary {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgb(var(--v-theme-primary), 0.07);
  font-size: 0.85rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
</style>
