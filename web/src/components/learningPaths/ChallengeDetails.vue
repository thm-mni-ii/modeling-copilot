<template>
  <div class="challenge-details">
    <div class="d-flex align-center ga-2 mb-2">
      <v-icon :color="config.color ?? undefined">{{ config.icon }}</v-icon>
      <strong>{{ config.title }}</strong>
    </div>
    <p class="challenge-description mb-3">{{ config.description }}</p>
    <p class="text-body-2 font-weight-medium mb-3">{{ challengeGoal(config) }}</p>
    <p class="text-caption text-medium-emphasis">This challenge sets a learning goal. You can ask for help and continue working at any time.</p>
  </div>
</template>
<script setup lang="ts">
import { challengeGoal, type ChallengeConfig } from '@/services/challenges'
defineProps<{ config: ChallengeConfig }>()
</script>
<style scoped>
.challenge-description {
  white-space: pre-line;
  overflow-wrap: anywhere;
}
strong {
  overflow-wrap: anywhere;
}
</style>
