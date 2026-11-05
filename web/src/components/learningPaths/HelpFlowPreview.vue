<template>
  <div class="help-preview">
    <p class="text-caption mb-3">Vorschau · Es werden keine Antworten oder Modellstände gespeichert.</p>
    <section v-if="stage === 'marking'" class="help-preview-step">
      <h3 class="text-subtitle-2">Problemstellen markieren</h3>
      <p class="text-body-2 my-3">Hier markieren Lernende Elemente im Modell oder Textstellen in der Aufgabe. In dieser Vorschau wird der Schritt simuliert.</p>
      <v-btn size="small" color="primary" @click="stage = 'reflection'">Weiter</v-btn>
    </section>
    <template v-else-if="stage === 'completed'">
      <p class="text-body-2">Die gewählte Hilfequelle wird angezeigt. Anschließend geht es zurück zum Modell.</p>
      <v-btn class="mt-3" variant="text" @click="stage = 'topic'">Vorschau neu starten</v-btn>
    </template>
    <SurveyRenderer v-else :key="stage" survey-id="help-preview" mode="preview" compact :local-definition="content" :question-per-page="stage === 'reflection'" :complete-text="stage === 'action' ? 'Hilfe auswählen' : 'Weiter'" @completed="advance" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { HelpBlueprint, HelpRequestConfig } from '@/services/learningPaths'
import type { SurveyResponse } from '@/services/surveys'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import { helpPhaseDefinition } from '@/utils/helpQuestionnaire'

const props = defineProps<{ blueprint: HelpBlueprint; config: HelpRequestConfig }>()
const stage = ref<'topic' | 'marking' | 'reflection' | 'action' | 'completed'>('topic')
const content = computed(() => helpPhaseDefinition(props.blueprint, props.config, stage.value === 'reflection' ? 'reflection' : stage.value === 'action' ? 'action' : 'topic'))
const advance = (response?: SurveyResponse) => {
  if (stage.value === 'topic') stage.value = props.config.markingEnabled && response?.answers.problem_area === 'Aufgabenstellung/Modell' ? 'marking' : 'reflection'
  else stage.value = stage.value === 'reflection' ? 'action' : 'completed'
}
</script>

<style scoped>
.help-preview { max-width: 320px; margin: auto; padding: 12px; border: 1px solid #ddbf88; border-radius: 10px; background: #fffdf8; }
</style>
