<template>
  <div class="help-preview">
    <p class="text-caption mb-3">Vorschau · Es werden keine Antworten oder Modellstände gespeichert.</p>
    <section v-if="stage === 'marking'" class="help-preview-step">
      <h3 class="text-subtitle-2">Problemstellen markieren</h3>
      <p class="text-body-2 my-3">Hier markieren Lernende höchstens ein Modellelement und beliebig viele Textstellen in der Aufgabe. Für automatisches Feedback zu dieser Problemstelle ist ein Modellelement erforderlich. In dieser Vorschau wird der Schritt simuliert.</p>
      <v-btn size="small" color="primary" @click="stage = 'action'">Weiter</v-btn>
    </section>
    <template v-else-if="stage === 'completed'">
      <p class="text-body-2">Die gewählte Hilfequelle wird angezeigt. Die automatische Überprüfung des Modells öffnet die Auswertung in der Studierendenansicht.</p>
      <v-btn class="mt-3" variant="text" @click="stage = 'topic'">Vorschau neu starten</v-btn>
    </template>
    <SurveyRenderer v-else :key="stage" survey-id="help-preview" mode="preview" compact :local-definition="content" :new-choice="automaticModelCheckChoice" :question-per-page="stage === 'reflection'" :complete-text="stage === 'action' ? 'Hilfe auswählen' : 'Weiter'" @completed="advance" />
    <v-btn v-if="stage === 'action' && canMark" class="mt-2" size="small" variant="text" prepend-icon="mdi-arrow-left" @click="stage = 'marking'">Zurück zur Markierung</v-btn>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { HelpBlueprint, HelpRequestConfig } from '@/services/learningPaths'
import type { SurveyResponse } from '@/services/surveys'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import { automaticModelCheckChoice, helpPhaseDefinition } from '@/utils/helpQuestionnaire'

const props = defineProps<{ blueprint: HelpBlueprint; config: HelpRequestConfig }>()
const stage = ref<'topic' | 'marking' | 'reflection' | 'action' | 'completed'>('topic')
const problemArea = ref('')
const objectFeedback = ref(false)
const canMark = computed(() => props.config.markingEnabled && problemArea.value === 'Aufgabenstellung/Modell' && objectFeedback.value)
const content = computed(() => helpPhaseDefinition(props.blueprint, props.config, stage.value === 'reflection' ? 'reflection' : stage.value === 'action' ? 'action' : 'topic', !objectFeedback.value || canMark.value))
const advance = (response?: SurveyResponse) => {
  if (stage.value === 'topic') {
    problemArea.value = String(response?.answers.problem_area ?? '')
    objectFeedback.value = false
    stage.value = 'reflection'
  } else if (stage.value === 'reflection') {
    objectFeedback.value = ['support_need_1', 'support_need_2', 'support_need_3', 'support_need_5'].includes(String(response?.answers.support_need))
    stage.value = canMark.value ? 'marking' : 'action'
  } else stage.value = 'completed'
}
</script>

<style scoped>
.help-preview { max-width: 320px; margin: auto; padding: 12px; border: 1px solid #ddbf88; border-radius: 10px; background: #fffdf8; }
</style>
