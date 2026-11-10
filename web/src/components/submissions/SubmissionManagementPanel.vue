<template>
  <div class="d-flex flex-wrap align-center ga-3 mb-4">
    <v-chip>{{ { open: 'Open for submissions', closed: 'Submissions closed', archived: 'Archived' }[run.data.state] }}</v-chip>
    <span class="text-body-2">Deadline {{ date(run.data.deadline) }}</span
    ><v-spacer />
    <v-menu
      ><template #activator="{ props: menuProps }"><v-btn v-bind="menuProps" variant="text" prepend-icon="mdi-cog-outline">Run details</v-btn></template
      ><v-list
        ><v-list-subheader>Run v{{ run.revision }} / Configuration v{{ run.assignmentRevision }}</v-list-subheader
        ><v-list-item v-if="run.permissions.manage && run.data.state !== 'archived'" title="Edit run settings" @click="emit('configure')" /></v-list
    ></v-menu>
  </div>
  <v-alert v-if="run.data.state === 'archived'" type="info" variant="tonal" class="mb-4">Archived run. Submissions and feedback remain available in read-only form.</v-alert>
  <div class="d-flex flex-wrap align-center ga-3 mb-3">
    <v-select :model-value="filter" :items="filters" label="Filter submissions" hide-details density="compact" style="max-width: 280px" @update:model-value="emit('filter', $event)" />
    <v-checkbox :model-value="history" label="Include replaced submissions" hide-details density="compact" @update:model-value="emit('history', Boolean($event))" />
    <v-spacer />
    <template v-if="run.permissions.publish && run.data.state !== 'archived'"
      ><v-btn :disabled="busy || !selected.length" variant="tonal" @click="emit('release', false)">Publish selected ({{ selected.length }})</v-btn><v-btn :disabled="busy" variant="text" @click="emit('release', true)">Publish all ready</v-btn></template
    >
  </div>
  <v-btn v-if="run.permissions.review && run.data.state !== 'archived' && nextSubmission" :to="reviewLink(nextSubmission.id)" color="primary" :disabled="busy" class="mb-4">Review next submission in this list</v-btn>
  <div class="d-flex flex-wrap align-center ga-3 mb-3">
    <h2 class="text-h6">All submissions</h2>
    <v-spacer />
    <v-btn variant="tonal" prepend-icon="mdi-download" :loading="exporting" :disabled="busy || exporting" title="Export student IDs, names and available email addresses for all submissions in this run, including replaced submissions, regardless of filters." @click="exportCsv">Download all as CSV</v-btn>
  </div>
  <v-alert v-if="exportError" type="error" variant="tonal" class="mb-3">{{ exportError }}</v-alert>
  <v-table
    ><thead>
      <tr>
        <th v-if="run.permissions.publish">Select</th>
        <th>Student</th>
        <th>Submitted</th>
        <th>Status</th>
        <th>Feedback</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="row in rows" :key="row.id">
        <td v-if="run.permissions.publish"><v-checkbox :model-value="selected" :value="row.id" :disabled="!row.current || !row.reviews.some((r) => r.status === 'complete')" hide-details density="compact" :aria-label="`Select submission by ${row.ownerId}`" @update:model-value="selectRows" /></td>
        <td :title="`Account: ${row.ownerId}`">{{ row.ownerName || row.ownerId }} <v-chip v-if="!row.current" size="x-small">Previous submission</v-chip></td>
        <td>{{ date(row.createdAt) }}</td>
        <td>{{ submissionStatus(row.status) }}</td>
        <td><v-btn variant="text" :to="{ name: 'SubmissionReview', params: { submissionId: row.id }, query: { view: 'management', filter } }">Open review</v-btn></td>
      </tr>
    </tbody></v-table
  >
  <p v-if="!rows.length && !busy" class="my-5 text-medium-emphasis">No submissions in this view.</p>
  <v-pagination v-if="total > 100" :model-value="page" :length="Math.ceil(total / 100)" @update:model-value="emit('page', $event)" />
  <v-expansion-panels v-if="run.history?.length" class="mt-4"
    ><v-expansion-panel title="Run configuration history"
      ><v-expansion-panel-text
        ><div v-for="version in run.history" :key="version.revision" class="mb-2">v{{ version.revision }} · {{ version.data.name }} · {{ version.data.state }} · Deadline {{ date(version.data.deadline) }}</div></v-expansion-panel-text
      ></v-expansion-panel
    ></v-expansion-panels
  >
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useUserStore } from '@/stores/userStore'
import { submissionStatus, type SubmissionRun, type SubmissionRow } from '@/services/api/types/submission'
import { submissions, submissionError } from '@/services/submissions'
const props = defineProps<{ run: SubmissionRun; rows: SubmissionRow[]; busy: boolean; filter: string; history: boolean; selected: string[]; total: number; page: number }>()
const user = useUserStore()
const exporting = ref(false)
const exportError = ref('')
const exportCsv = async () => {
  exporting.value = true
  exportError.value = ''
  try {
    const { data } = await submissions.exportCsv(props.run.id)
    const url = URL.createObjectURL(data)
    try {
      const link = document.createElement('a')
      link.href = url
      link.download = `submissions-${props.run.id}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    }
  } catch (cause) {
    exportError.value = submissionError(cause)
  } finally {
    exporting.value = false
  }
}
const nextSubmission = computed(() => props.rows.find((row) => row.current && (row.ownerId !== user.userId || user.globalRole === 'ADMIN') && (!row.reviews.some((review) => review.kind === 'staff') || row.reviews.some((review) => review.kind === 'staff' && review.status === 'draft'))))
const reviewLink = (id: string) => ({ name: 'SubmissionReview', params: { submissionId: id }, query: { view: 'management', filter: props.filter } })
const emit = defineEmits<{ configure: []; filter: [value: string]; history: [value: boolean]; select: [value: string[]]; release: [all: boolean]; page: [value: number] }>()
const selectRows = (value: unknown) => emit('select', Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string') : [])
const filters = [{ title: 'All', value: 'all' }, ...['submitted', 'in_review', 'reviewed', 'feedback_available'].map((value) => ({ title: submissionStatus(value), value }))]
const date = (value: string) => new Date(value).toLocaleString()
</script>
