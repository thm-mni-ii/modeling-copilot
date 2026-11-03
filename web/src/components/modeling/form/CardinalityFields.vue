<template>
  <div>
    <div class="text-subtitle-2 mb-2">{{ label }}</div>
    <div class="d-flex ga-3">
      <v-text-field :model-value="modelValue.min" label="Minimum" type="number" min="0" step="1" variant="outlined" density="compact" :disabled="disabled" hide-details @update:model-value="setMin" />
      <v-text-field :model-value="modelValue.max ?? ''" label="Maximum" placeholder="Unlimited" type="number" min="0" step="1" variant="outlined" density="compact" :disabled="disabled" :error="invalid" :error-messages="invalid ? 'Maximum must be at least the minimum.' : []" @update:model-value="setMax" />
    </div>
    <div v-if="hint" class="text-caption text-medium-emphasis">{{ hint }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MultiplicityCardinality } from '@/model/Syntax'
const props = defineProps<{ modelValue: MultiplicityCardinality; label: string; hint?: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: MultiplicityCardinality] }>()
const invalid = computed(() => props.modelValue.max !== null && props.modelValue.max < props.modelValue.min)
const setMin = (value: string) => emit('update:modelValue', { ...props.modelValue, min: Math.max(0, Math.trunc(Number(value) || 0)) })
const setMax = (value: string) => emit('update:modelValue', { ...props.modelValue, max: value === '' || value == null ? null : Math.max(0, Math.trunc(Number(value) || 0)) })
</script>
