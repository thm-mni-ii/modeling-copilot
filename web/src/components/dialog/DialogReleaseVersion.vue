<template>
  <v-dialog :model-value="modelValue" max-width="480" :persistent="busy" @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Release {{ subject }}</v-card-title>
      <v-form @submit.prevent="confirm">
        <v-card-text>
          <div class="text-overline text-medium-emphasis">Next version</div>
          <div class="text-h4 font-weight-bold text-primary mb-3">v{{ versionNumber }}</div>
          <p class="text-body-2 mb-5">The version number is assigned automatically. You can release right away, or add a name to help recognize this version.</p>
          <v-text-field v-model="displayName" label="Display name (optional)" variant="outlined" density="compact" maxlength="256" :disabled="busy" :hint="`Leave empty to use v${versionNumber}.`" persistent-hint />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="busy" @click="$emit('update:modelValue', false)">Cancel</v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="busy" :disabled="busy">Release v{{ versionNumber }}</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: boolean; subject: string; versionNumber: string; busy: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; confirm: [displayName: string] }>()
const displayName = ref('')

watch(() => props.modelValue, (open) => {
  if (open) displayName.value = ''
})

const confirm = () => {
  if (!props.busy) emit('confirm', displayName.value.trim())
}
</script>
