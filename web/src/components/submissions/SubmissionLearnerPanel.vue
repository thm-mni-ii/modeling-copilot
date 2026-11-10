<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <p>Deadline: {{ date(run.data.deadline) }}</p>
    <v-spacer />
    <v-btn v-if="run.canEnroll" color="primary" :loading="busy" @click="emit('enroll')">Join course to submit</v-btn>
    <v-btn v-else-if="run.canSubmit" color="primary" :disabled="busy" @click="emit('submit')">{{ rows.some((r) => r.current) ? 'Replace my submission' : 'Submit model' }}</v-btn>
  </div>
  <v-alert v-if="blockedMessage" type="info" variant="tonal" class="mb-4">{{ blockedMessage }}</v-alert>
  <h2 class="text-h6 mb-3">My submissions</h2>
  <v-list lines="two"><SubmissionLearnerEntry v-for="row in current" :key="row.id" :row="row" /></v-list>
  <v-expansion-panels v-if="previous.length" class="mt-3"
    ><v-expansion-panel :title="`Previous submissions (${previous.length})`"
      ><v-expansion-panel-text
        ><v-list lines="two"><SubmissionLearnerEntry v-for="row in previous" :key="row.id" :row="row" /></v-list></v-expansion-panel-text></v-expansion-panel
  ></v-expansion-panels>
  <p v-if="!rows.length && !busy" class="text-medium-emphasis my-5">You have not submitted a model for this semester yet.</p>
  <v-pagination v-if="total > 100" :model-value="page" :length="Math.ceil(total / 100)" @update:model-value="emit('page', $event)" />
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { SubmissionRow, SubmissionRun } from '@/services/api/types/submission'
import SubmissionLearnerEntry from './SubmissionLearnerEntry.vue'
const props = defineProps<{ run: SubmissionRun; rows: SubmissionRow[]; busy: boolean; total: number; page: number }>()
const emit = defineEmits<{ enroll: []; submit: []; page: [value: number] }>()
const date = (value: string) => new Date(value).toLocaleString()
const current = computed(() => props.rows.filter((row) => row.current))
const previous = computed(() => props.rows.filter((row) => !row.current))
const blockedMessage = computed(() => {
  if (props.run.canSubmit || props.run.canEnroll) return ''
  const reasons = {
    archived: 'This semester has ended. You can still view your submissions and published feedback.',
    closed: 'Submissions are closed. Your existing submission and feedback remain available.',
    deadline: 'The submission deadline has passed. You can still view your submitted model and feedback.',
    not_eligible: 'You are not eligible to submit in this semester. Contact the course staff if you need access.',
    not_enrolled: 'Join this course before submitting a model.',
    review_started: 'Reviewing has started. Your submitted model can no longer be replaced. Published feedback will appear here.'
  }
  return props.run.submissionBlockedReason ? reasons[props.run.submissionBlockedReason] : 'Submitting a model is not currently available.'
})
</script>
