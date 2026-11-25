<template>
  <v-dialog v-model="open" max-width="520" :persistent="busy" aria-label="Abgabeprüfung">
    <v-card>
      <v-card-title class="text-wrap">{{ title }}</v-card-title>
      <v-card-text>
        <template v-if="!result">
          <p v-if="error" class="mb-0">{{ error }}</p>
          <v-progress-linear v-else indeterminate color="primary" rounded height="6" aria-label="Prüfung läuft" />
        </template>
        <template v-else>
          <CompletionGateBars :result="result" animate @done="decided = true" />
          <HintNotice :count="hintCount ?? 0" @open="emit('hints')" />
          <template v-if="decided">
            <v-alert v-if="result.passed" type="success" variant="tonal" density="compact" class="mt-4">
              Du hast genug erreicht. Nach der Abgabe steht deine Punktzahl fest; dein Modell kannst du weiter bearbeiten.
            </v-alert>
            <v-checkbox v-if="result.passed" v-model="acknowledged" class="mt-2" density="compact" hide-details label="Ich möchte jetzt abgeben." />
            <v-alert v-else type="warning" variant="tonal" density="compact" class="mt-4">
              Die rot markierten Bereiche liegen noch unter der Grenze. Modelliere weiter und schließe dann erneut ab.
            </v-alert>
          </template>
        </template>
      </v-card-text>
      <v-card-actions class="flex-wrap">
        <v-btn v-if="result && decided && !result.passed && helpAvailable" variant="text" prepend-icon="mdi-lifebuoy" @click="emit('help')">Ich brauche Hilfe</v-btn>
        <v-spacer />
        <v-btn :variant="result?.passed ? 'text' : 'flat'" :color="result?.passed ? undefined : 'primary'" :disabled="busy" @click="open = false">Weiter modellieren</v-btn>
        <v-btn v-if="result?.passed && decided" color="#a33d32" variant="flat" prepend-icon="mdi-lock-outline" :loading="busy" :disabled="!acknowledged" @click="emit('submit')">Aufgabe abgeben</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CompletionGateBars from './CompletionGateBars.vue'
import HintNotice from '@/components/feedback/HintNotice.vue'
import type { GateResult } from '@/utils/completionGate'

const props = defineProps<{ result: GateResult | null; error?: string; busy?: boolean; helpAvailable?: boolean; hintCount?: number }>()
const emit = defineEmits<{ submit: []; help: []; hints: [] }>()
const open = defineModel<boolean>({ default: false })
const acknowledged = ref(false)
// The decision appears once the bars have finished filling.
const decided = ref(false)
watch(() => props.result, () => { decided.value = false; acknowledged.value = false })
const title = computed(() => {
  if (!props.result) return props.error ? 'Prüfung nicht möglich' : 'Dein Modell wird geprüft …'
  if (!decided.value) return 'Dein aktueller Stand'
  return props.result.passed ? 'Bereit zur Abgabe' : 'Noch nicht abgabebereit'
})
</script>
