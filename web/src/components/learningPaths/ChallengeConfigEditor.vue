<template>
  <v-sheet border rounded class="pa-4 mt-5">
    <h2 class="text-subtitle-1 mb-3">Challenge</h2>
    <v-select :model-value="modelValue?.type ?? null" :items="[{ title: 'No challenge', value: null }, ...challengeTypes]" label="Challenge type" @update:model-value="changeType" />
    <template v-if="modelValue">
      <v-text-field :model-value="modelValue.title" label="Title" maxlength="256" :rules="[required]" @update:model-value="update({ title: $event })" />
      <v-textarea :model-value="modelValue.description" label="Description and introduction" rows="3" maxlength="3000" :rules="[required]" @update:model-value="update({ description: $event })" />
      <div class="challenge-appearance">
        <v-text-field :model-value="modelValue.icon" label="Icon (mdi-…)" :prepend-inner-icon="validIcon ? modelValue.icon : 'mdi-help-circle-outline'" :rules="[(v) => /^mdi-[a-z0-9-]{1,80}$/.test(v) || 'Enter a valid mdi icon.']" @update:model-value="update({ icon: $event })" />
        <v-text-field :model-value="modelValue.color ?? ''" label="Color (optional, #RRGGBB)" placeholder="#32736d" clearable :rules="[(v) => !v || /^#[0-9a-fA-F]{6}$/.test(v) || 'Enter a six-digit hex color.']" @update:model-value="update({ color: $event || null })" />
      </div>
      <v-text-field v-if="modelValue.type === 'time'" :model-value="(modelValue.durationSeconds ?? 900) / 60" type="number" min="0.016667" max="1440" step="1" label="Time budget in minutes" :rules="[(v) => (Number(v) > 0 && Number(v) <= 1440) || 'Enter a duration between one second and 24 hours.']" @update:model-value="update({ durationSeconds: Math.round(Number($event) * 60) })" />
      <v-text-field v-if="modelValue.type === 'help_budget'" :model-value="modelValue.helpBudget" type="number" min="0" max="1000" step="1" label="Target budget of internal hints" :rules="[(v) => (v !== '' && Number.isInteger(Number(v)) && Number(v) >= 0 && Number(v) <= 1000) || 'Enter a whole number between 0 and 1000.']" @update:model-value="update({ helpBudget: Number($event) })" />
      <p class="text-caption mb-4">No restrictions or automatic termination. Changes apply to tasks that have not been started yet.</p>
      <v-divider class="mb-4" />
      <p class="text-overline mb-2">Introduction preview</p>
      <ChallengeDetails :config="modelValue" />
    </template>
  </v-sheet>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { challengeTypes, createChallenge, type ChallengeConfig, type ChallengeType } from '@/services/challenges'
import ChallengeDetails from './ChallengeDetails.vue'
const props = defineProps<{ modelValue?: ChallengeConfig | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: ChallengeConfig | null] }>()
const validIcon = computed(() => /^mdi-[a-z0-9-]{1,80}$/.test(props.modelValue?.icon ?? ''))
const required = (value: string) => Boolean(value?.trim()) || 'This field is required.'
const update = (changes: Partial<ChallengeConfig>) => {
  if (props.modelValue) emit('update:modelValue', { ...props.modelValue, ...changes })
}
const changeType = (type: ChallengeType | null) => {
  if (type === props.modelValue?.type) return
  emit('update:modelValue', type ? createChallenge(type) : null)
}
</script>
<style scoped>
.challenge-appearance {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}
</style>
