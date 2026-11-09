<template>
  <v-list-item :title="row.modelName || 'Model submission'" :subtitle="`Submitted on ${new Date(row.createdAt).toLocaleString()}`">
    <template #append>
      <div class="d-flex flex-wrap align-center ga-2">
        <v-chip size="small" :color="hasFeedback ? 'success' : 'info'">{{ submissionStatus(row.status) }}</v-chip>
        <v-btn :to="{ name: 'SubmissionReview', params: { submissionId: row.id }, query: { view: 'participant' } }" :variant="hasFeedback ? 'tonal' : 'text'" :color="hasFeedback ? 'primary' : undefined">{{ hasFeedback ? 'Read feedback' : 'View submission' }}</v-btn>
      </div>
    </template>
  </v-list-item>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { submissionStatus, type SubmissionRow } from '@/services/api/types/submission'
const props = defineProps<{ row: SubmissionRow }>()
const hasFeedback = computed(() => props.row.status === 'feedback_available')
</script>
