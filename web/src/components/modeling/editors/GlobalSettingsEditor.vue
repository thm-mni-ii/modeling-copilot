<template>
  <v-container fluid class="pa-2">
    <v-alert type="warning" variant="tonal" class="mb-4">These are global settings for all modeling languages. They are saved separately and do not belong to the currently opened language or model.</v-alert>
    <div class="d-flex align-center ga-3 mb-3">
      <h2 class="text-h6">Global feedback settings</h2>
      <v-chip size="small">Global · v{{ settings.revision }}</v-chip>
      <v-spacer />
      <v-btn :disabled="busy" @click="useDefaultIcons">Use default MDI icons</v-btn>
      <v-btn :loading="busy" :disabled="!dirty || busy" color="primary" @click="save">Save global settings</v-btn>
      <v-btn :disabled="busy" @click="load">Reload</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert>
    <p class="text-body-2 mb-3">Correct: top left. Incorrect: top right. Hint: bottom right. Existing published feedback keeps its configuration version.</p>
    <p class="text-body-2 mb-3">On connections, Correct/Incorrect and Hint are spaced along the line on opposite sides of its midpoint, following bends. A single marking stays at the midpoint. Hint uses the bottom-aligned position. Configured offsets are applied additionally.</p>
    <FeedbackEditorForm :key="settings.revision" :config="settings.overlays" :state-definitions="states" @update="dirty = true" />
    <v-expansion-panels class="mt-4">
      <v-expansion-panel title="Archived · previous settings dummy"
        ><v-expansion-panel-text><LegacyGlobalSettingsDummy /></v-expansion-panel-text
      ></v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import FeedbackEditorForm from '@/components/modeling/form/FeedbackEditorForm.vue'
import LegacyGlobalSettingsDummy from './LegacyGlobalSettingsDummy.vue'
import { createDefaultTargetOverlays } from '@/utils/feedbackConfig'
import { submissions, submissionError } from '@/services/submissions'
import type { GlobalFeedbackSettings } from '@/services/api/types/submission'
import { getMdiGlyph } from '@/utils/feedbackOverlays'
const settings = ref<GlobalFeedbackSettings>({ revision: 0, overlays: createDefaultTargetOverlays() })
const dirty = ref(false)
const busy = ref(false)
const error = ref('')
const useDefaultIcons = () => {
  settings.value.overlays = createDefaultTargetOverlays()
  dirty.value = true
}
const states = [
  { key: 'correct' as const, label: 'Correct', shortLabel: 'Correct', color: 'success', icon: 'mdi-check-circle-outline' },
  { key: 'incorrect' as const, label: 'Incorrect', shortLabel: 'Incorrect', color: 'error', icon: 'mdi-close-circle-outline' },
  { key: 'hint' as const, label: 'Hint', shortLabel: 'Hint', color: 'warning', icon: 'mdi-alert-circle-outline' }
]
const load = async () => {
  busy.value = true
  error.value = ''
  try {
    settings.value = (await submissions.settings()).data
    dirty.value = false
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const save = async () => {
  if (Object.values(settings.value.overlays).some((overlay) => overlay.icon != null && (!getMdiGlyph(overlay.icon) || !/^#[0-9a-f]{6}$/i.test(overlay.color ?? '')))) {
    error.value = 'Choose an available MDI icon and a six-digit hex color for every icon overlay.'
    return
  }
  busy.value = true
  error.value = ''
  try {
    settings.value = (await submissions.saveSettings(settings.value)).data
    dirty.value = false
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
