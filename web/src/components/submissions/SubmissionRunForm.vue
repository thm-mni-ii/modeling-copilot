<template>
  <v-text-field v-model="data.name" label="Run name" placeholder="e.g. Winter semester 2026/27" hint="Enter the semester or another name so this run is easy to find later." persistent-hint maxlength="256" />
  <v-text-field v-model="deadline" type="datetime-local" :label="`Deadline (${timezone})`" class="mt-3" />
  <v-select
    v-model="data.state"
    label="State"
    :items="[
      { title: 'Open', value: 'open' },
      { title: 'Closed · reviews remain editable', value: 'closed' },
      { title: 'Archived · read only', value: 'archived' }
    ]"
  />
  <v-select
    v-model="data.participation"
    label="Who may submit?"
    :items="[
      { title: 'All signed-in users', value: 'all' },
      { title: 'Selected users', value: 'selected' }
    ]"
  />
  <SubmissionUserPicker v-if="data.participation === 'selected'" :model-value="data.participantIds ?? []" label="Participants" :run-id="directoryRunId" @update:model-value="data.participantIds = $event" />
  <h3 class="text-subtitle-1 mb-2">Additional permissions for this run</h3>
  <p class="text-body-2 mb-3">Administrators and FBS moderators can always manage runs. Additional permissions do not change a user's FBS role.</p>
  <SubmissionUserPicker :model-value="grantIds" label="Additional staff" :run-id="directoryRunId" @update:model-value="setGrants" />
  <div v-for="grant in data.grants" :key="grant.userId" class="d-flex flex-wrap align-center ga-3">
    <span>{{ grant.userId }}</span>
    <v-checkbox v-model="grant.manage" label="Manage" hide-details density="compact" />
    <v-checkbox v-model="grant.review" label="Review" hide-details density="compact" />
    <v-checkbox v-model="grant.publish" label="Release" hide-details density="compact" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SubmissionUserPicker from './SubmissionUserPicker.vue'
import type { RunData } from '@/services/api/types/submission'
const props = defineProps<{ data: RunData; directoryRunId?: string }>()
const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
const deadline = computed({
  get: () => {
    const d = new Date(props.data.deadline)
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  },
  set: (value: string) => {
    const d = new Date(value)
    if (Number.isFinite(d.getTime())) props.data.deadline = d.toISOString()
  }
})
const grantIds = computed(() => (props.data.grants ?? []).map((g) => g.userId))
const setGrants = (ids: string[]) => {
  props.data.grants = ids.map((id) => props.data.grants?.find((g) => g.userId === id) ?? { userId: id, manage: false, review: true, publish: false })
}
</script>
