<template>
  <section>
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon size="21">mdi-flag-outline</v-icon>
      <h3 class="text-subtitle-1 font-weight-bold">Challenge</h3>
    </div>
    <p class="text-body-2 text-medium-emphasis mb-4">Set a learning goal. Help and task completion always remain available.</p>
    <div class="challenge-options" role="group" aria-label="Challenge type">
      <button v-for="option in options" :key="option.type ?? 'none'" type="button" class="challenge-option" :class="{ 'challenge-option--selected': (modelValue?.type ?? null) === option.type }" :aria-pressed="(modelValue?.type ?? null) === option.type" @click="changeType(option.type)">
        <v-icon size="24">{{ option.icon }}</v-icon
        ><strong>{{ option.title }}</strong
        ><span>{{ option.description }}</span>
      </button>
    </div>
    <template v-if="modelValue">
      <div class="challenge-budget mt-5">
        <v-text-field
          v-if="modelValue.type === 'time'"
          :model-value="(modelValue.durationSeconds ?? 900) / 60"
          type="number"
          min="0.016667"
          max="1440"
          step="1"
          label="Time budget"
          suffix="minutes"
          variant="outlined"
          hide-details="auto"
          :rules="[(v) => (Math.round(Number(v) * 60) >= 1 && Number(v) <= 1440) || 'Choose a duration between one second and 24 hours.']"
          @update:model-value="update({ durationSeconds: Math.round(Number($event) * 60) })"
        />
        <v-text-field
          v-if="modelValue.type === 'help_budget'"
          :model-value="modelValue.helpBudget"
          type="number"
          min="0"
          max="1000"
          step="1"
          label="Target help budget"
          suffix="internal hints"
          variant="outlined"
          hide-details="auto"
          :rules="[(v) => (v !== '' && Number.isInteger(Number(v)) && Number(v) >= 0 && Number(v) <= 1000) || 'Choose a whole number between 0 and 1,000.']"
          @update:model-value="update({ helpBudget: Number($event) })"
        />
      </div>
      <div class="d-flex flex-wrap align-center ga-2 mt-4">
        <v-btn variant="tonal" size="small" prepend-icon="mdi-eye-outline" @click="preview = true">Preview introduction</v-btn><v-btn variant="text" size="small" :append-icon="customize ? 'mdi-chevron-up' : 'mdi-chevron-down'" :aria-expanded="customize" aria-controls="challenge-customization" @click="customize = !customize">Customize appearance and text</v-btn>
      </div>
      <div v-show="customize" id="challenge-customization" class="challenge-customization mt-4">
        <v-text-field :model-value="modelValue.title" label="Title" variant="outlined" maxlength="256" :rules="[required]" @update:model-value="update({ title: $event })" />
        <v-textarea :model-value="modelValue.description" label="Introduction" variant="outlined" rows="3" maxlength="3000" :rules="[required]" @update:model-value="update({ description: $event })" />
        <p class="text-caption font-weight-medium mb-2">Icon</p>
        <div class="appearance-options mb-4" role="group" aria-label="Challenge icon">
          <button v-for="icon in visibleIcons" :key="icon" type="button" :aria-label="iconLabels[icon] ?? 'Current icon'" :aria-pressed="modelValue.icon === icon" :class="{ chosen: modelValue.icon === icon }" @click="update({ icon })">
            <v-icon>{{ icon }}</v-icon>
          </button>
        </div>
        <p class="text-caption font-weight-medium mb-2">Accent color</p>
        <div class="appearance-options" role="group" aria-label="Challenge color">
          <button v-for="color in visibleColors" :key="color.value ?? 'default'" type="button" :aria-label="color.label" :aria-pressed="(modelValue.color ?? null) === color.value" :class="{ chosen: (modelValue.color ?? null) === color.value }" @click="update({ color: color.value })">
            <span v-if="color.value" class="color-swatch" :style="{ background: color.value }" /><v-icon v-else>mdi-palette-outline</v-icon>
          </button>
        </div>
      </div>
      <v-dialog v-model="preview" max-width="540"
        ><v-card
          ><v-card-title>Before you start</v-card-title
          ><v-card-text
            ><ChallengeDetails :config="modelValue" />
            <p v-if="modelValue.type === 'time'" class="text-body-2 mt-3">The countdown begins when you select “Start task”.</p></v-card-text
          ><v-card-actions><v-btn @click="preview = false">Close preview</v-btn><v-spacer /><v-btn disabled>Start task</v-btn></v-card-actions></v-card
        ></v-dialog
      >
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { createChallenge, type ChallengeConfig, type ChallengeType } from '@/services/challenges'
import ChallengeDetails from './ChallengeDetails.vue'
const props = defineProps<{ modelValue?: ChallengeConfig | null; showErrors?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: ChallengeConfig | null] }>()
const customize = ref(false),
  preview = ref(false)
const options: { type: ChallengeType | null; title: string; description: string; icon: string }[] = [
  { type: null, title: 'None', description: 'No extra goal', icon: 'mdi-minus-circle-outline' },
  { type: 'solo', title: 'Solo', description: 'Try independently', icon: 'mdi-account-outline' },
  { type: 'time', title: 'Time', description: 'Work with a timer', icon: 'mdi-timer-outline' },
  { type: 'help_budget', title: 'Help Budget', description: 'Use hints deliberately', icon: 'mdi-lightbulb-outline' }
]
const iconLabels: Record<string, string> = { 'mdi-account-outline': 'Person', 'mdi-timer-outline': 'Timer', 'mdi-lightbulb-outline': 'Light bulb', 'mdi-flag-outline': 'Flag', 'mdi-compass-outline': 'Compass', 'mdi-star-outline': 'Star' }
const visibleIcons = computed(() => [...new Set([...Object.keys(iconLabels), ...(props.modelValue?.icon ? [props.modelValue.icon] : [])])])
const colors = [
  { label: 'Default color', value: null },
  { label: 'Forest green', value: '#356458' },
  { label: 'Ocean blue', value: '#356b94' },
  { label: 'Gold', value: '#93691d' },
  { label: 'Purple', value: '#785a96' },
  { label: 'Coral', value: '#a34d45' }
] as { label: string; value: string | null }[]
const visibleColors = computed(() => (props.modelValue?.color && !colors.some((color) => color.value === props.modelValue?.color) ? [...colors, { label: 'Current custom color', value: props.modelValue.color }] : colors))
const required = (value: string) => Boolean(value?.trim()) || 'This field is required.'
const update = (changes: Partial<ChallengeConfig>) => {
  if (props.modelValue) emit('update:modelValue', { ...props.modelValue, ...changes })
}
const changeType = (type: ChallengeType | null) => {
  if (type === (props.modelValue?.type ?? null)) return
  emit('update:modelValue', type ? createChallenge(type) : null)
  customize.value = false
}
watch(
  () => [props.showErrors, props.modelValue?.title, props.modelValue?.description],
  () => {
    if (props.showErrors && props.modelValue && (!props.modelValue.title.trim() || !props.modelValue.description.trim())) customize.value = true
  },
  { immediate: true }
)
</script>
<style scoped>
.challenge-options {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.challenge-option {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 7px;
  padding: 15px 12px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.16);
  border-radius: 12px;
  text-align: left;
  background: rgb(var(--v-theme-surface));
  min-width: 0;
}
.challenge-option strong {
  font-size: 0.83rem;
}
.challenge-option span {
  font-size: 0.72rem;
  opacity: 0.7;
}
.challenge-option--selected {
  border-color: rgb(var(--v-theme-primary));
  background: rgb(var(--v-theme-primary), 0.08);
  box-shadow: inset 0 0 0 1px rgb(var(--v-theme-primary));
}
.challenge-option:focus-visible,
.appearance-options button:focus-visible {
  outline: 3px solid rgb(var(--v-theme-primary));
  outline-offset: 3px;
}
.challenge-budget {
  max-width: 360px;
}
.challenge-customization {
  padding: 18px;
  background: rgb(var(--v-theme-on-surface), 0.025);
  border-radius: 12px;
}
.appearance-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.appearance-options button {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.15);
  border-radius: 10px;
}
.appearance-options .chosen {
  border: 2px solid rgb(var(--v-theme-primary));
}
.color-swatch {
  display: block;
  width: 23px;
  height: 23px;
  border-radius: 50%;
}
@media (max-width: 700px) {
  .challenge-options {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
