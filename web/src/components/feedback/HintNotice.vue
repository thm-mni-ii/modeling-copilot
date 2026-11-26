<template>
  <v-alert v-if="hints.length" type="info" variant="tonal" class="my-3" aria-live="polite">
    <template v-if="questions">
      <strong>{{ questions === 1 ? 'Bei der Auswertung blieb eine Zuordnung offen.' : `Bei der Auswertung blieben ${questions} Zuordnungen offen.` }}</strong>
      <p class="text-body-2 mt-1 mb-2">Hilfst du uns kurz, die gemeinten Begriffe zu klären?<template v-if="observations"> {{ observationText }}</template></p>
    </template>
    <template v-else>
      <strong>{{ observations === 1 ? 'Die Auswertung hat eine Beobachtung zu deinem Modell.' : `Die Auswertung hat ${observations} Beobachtungen zu deinem Modell.` }}</strong>
      <p class="mb-2" />
    </template>
    <v-btn color="info" variant="flat" size="small" @click="emit('open')">Hinweise ansehen</v-btn>
  </v-alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { LabelHint } from '@/services/api/types/evaluation'

const props = defineProps<{ hints: Pick<LabelHint, 'note'>[] }>()
const emit = defineEmits<{ open: [] }>()
// Observations (e.g. a surplus copy) only report a finding; only label questions ask for clarification.
const observations = computed(() => props.hints.filter(hint => hint.note).length)
const questions = computed(() => props.hints.length - observations.value)
const observationText = computed(() => observations.value === 1 ? 'Dazu gibt es eine Beobachtung zu deinem Modell.' : `Dazu gibt es ${observations.value} Beobachtungen zu deinem Modell.`)
</script>
