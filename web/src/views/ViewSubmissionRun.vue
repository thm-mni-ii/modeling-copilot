<template>
  <v-container
    ><v-progress-linear v-if="!error" indeterminate /><v-alert v-else type="error">{{ error }}</v-alert></v-container
  >
</template>
<script setup lang="ts">
// Compatibility route. The preserved run workspace is rendered directly inside its course.
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { submissions, submissionError } from '@/services/submissions'
const route = useRoute()
const router = useRouter()
const error = ref('')
watch(
  () => route.params.runId,
  async () => {
    try {
      const view = route.query.view === 'participant' ? 'participant' : route.query.view === 'management' ? 'management' : undefined
      const run = (await submissions.run(String(route.params.runId), view)).data
      await router.replace({ name: 'Submissions', params: { assignmentId: run.assignmentId }, query: { run: run.id, view: view ?? (run.canModerate ? 'management' : 'participant') } })
    } catch (cause) {
      error.value = submissionError(cause)
    }
  },
  { immediate: true }
)
</script>
