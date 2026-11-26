<template>
  <div>
    <v-sheet v-if="!surveys.surveys.length" border rounded="lg" class="pa-6">
      <p class="text-body-2 text-medium-emphasis mb-0">This learning path uses no surveys: no task questionnaires, survey steps, pulse pool or help questionnaire.</p>
    </v-sheet>
    <template v-else>
      <p class="text-body-2 text-medium-emphasis mb-3">
        Only answers of this path's participants are counted. A survey answered in several releases shows the newest release first.
      </p>
      <v-expansion-panels multiple>
        <path-survey-card v-for="survey in surveys.surveys" :key="survey.id" :survey="survey" />
      </v-expansion-panels>
    </template>
  </div>
</template>

<script setup lang="ts">
import PathSurveyCard from '@/components/analytics/PathSurveyCard.vue'
import type { PathSurveys } from '@/services/analytics'

defineProps<{ surveys: PathSurveys }>()
</script>
