<!-- Archived intermediate overview. Kept for reference; current routes use the direct course workspace. -->
<template>
  <v-container style="max-width: 1100px">
    <div class="d-flex align-center ga-3 mb-4">
      <v-btn v-if="assignment" icon="mdi-arrow-left" variant="text" :to="{ name: 'Submissions' }" aria-label="Back to assignments" />
      <h1 class="text-h5">{{ assignment?.name ?? 'Submissions and feedback' }}</h1>
      <v-spacer />
      <v-btn v-if="canCreate && !assignment" color="primary" @click="newAssignment">Create assignment</v-btn>
      <v-btn :loading="busy" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <template v-if="!assignment">
      <v-switch v-model="archived" label="Archived assignments" hide-details @update:model-value="reloadList" />
      <v-list lines="two">
        <v-list-item v-for="item in items" :key="item.id" :title="item.name" :subtitle="`Configuration v${item.revision}${item.archived ? ' · Archived' : ''}`" :to="{ name: 'Submissions', params: { assignmentId: item.id } }" append-icon="mdi-chevron-right" />
      </v-list>
      <p v-if="!items.length && !busy" class="text-medium-emphasis my-5">No assignments available.</p>
      <v-pagination v-if="total > 20" v-model="page" :length="Math.ceil(total / 20)" @update:model-value="load" />
    </template>
    <template v-else>
      <p class="mb-3" style="white-space: pre-wrap">{{ assignment.data.description }}</p>
      <div class="d-flex flex-wrap ga-2 mb-5">
        <v-chip>Configuration v{{ assignment.revision }}</v-chip>
        <v-chip v-if="assignment.archived">Archived</v-chip>
        <v-btn v-if="assignment.canManage" @click="editAssignment">Edit configuration</v-btn>
        <v-btn v-if="assignment.canManage && !assignment.archived" color="primary" @click="openRun">Start named run</v-btn>
      </div>
      <v-alert type="info" variant="tonal" class="mb-4">Each run keeps its own participants, submissions and feedback. Starting a new run never resets or moves previous data.</v-alert>
      <v-list lines="two">
        <v-list-item v-for="run in assignment.runs" :key="run.id" :title="run.data.name" :subtitle="`${run.data.state} · Deadline ${date(run.data.deadline)} · Configuration v${run.assignmentRevision}`" :to="{ name: 'SubmissionRun', params: { runId: run.id } }" append-icon="mdi-chevron-right" />
      </v-list>
      <p v-if="!assignment.runs?.length">No run started yet.</p>
      <v-expansion-panels v-if="assignment.canManage && assignment.history?.length" class="mt-5"
        ><v-expansion-panel title="Configuration history"
          ><v-expansion-panel-text
            ><div v-for="version in assignment.history" :key="version.revision" class="mb-3">
              <strong>v{{ version.revision }} · {{ version.data.name }}</strong>
              <p>{{ version.data.description }}</p>
            </div></v-expansion-panel-text
          ></v-expansion-panel
        ></v-expansion-panels
      >
    </template>
    <v-dialog v-model="editDialog" max-width="650" :persistent="busy"
      ><v-card title="Assignment configuration"
        ><v-card-text>
          <v-text-field v-model="form.name" label="Title" maxlength="256" />
          <v-textarea v-model="form.description" label="Description" maxlength="10000" />
          <v-select v-model="taskId" :items="tasks" item-title="name" item-value="id" label="Task (optional)" clearable @update:model-value="chooseTask" />
          <v-select v-if="taskId" v-model="taskVersionId" :items="taskVersions" item-value="id" :item-title="(version) => version.releaseName || version.versionNumber" label="Task release" />
          <v-checkbox v-model="form.archived" label="Archive assignment · existing runs stay accessible" />
          <v-alert v-if="dialogError" type="error">{{ dialogError }}</v-alert> </v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="editDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!form.name.trim() || Boolean(taskId && !taskVersionId)" @click="saveAssignment">Save configuration version</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="runDialog" max-width="760" :persistent="busy"
      ><v-card title="Start run"
        ><v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">Starting a new run archives earlier runs of this assignment. All their participants, submissions and feedback remain available.</v-alert>
          <SubmissionRunForm :data="runForm" :directory-run-id="assignment?.runs?.find((r) => r.permissions.manage)?.id" />
          <v-alert v-if="dialogError" type="error">{{ dialogError }}</v-alert> </v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="runDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!runForm.name.trim()" @click="startRun">Start run</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SubmissionRunForm from '@/components/submissions/SubmissionRunForm.vue'
import { submissions, submissionError } from '@/services/submissions'
import taskService from '@/services/task/task.service'
import type { Assignment, RunData } from '@/services/api/types/submission'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
const route = useRoute()
const router = useRouter()
const assignment = ref<Assignment | null>(null)
const items = ref<Assignment[]>([])
const total = ref(0)
const page = ref(1)
const archived = ref(false)
const canCreate = ref(false)
const busy = ref(false)
const error = ref('')
const dialogError = ref('')
const editDialog = ref(false)
const runDialog = ref(false)
const form = ref({ name: '', description: '', archived: false })
const tasks = ref<Task[]>([])
const taskVersions = ref<TaskVersionInfo[]>([])
const taskId = ref<string | null>(null)
const taskVersionId = ref<string | null>(null)
const newRun = (): RunData => ({ name: '', deadline: new Date(Date.now() + 14 * 86400000).toISOString(), state: 'open', participation: 'all', participantIds: [], grants: [] })
const runForm = ref<RunData>(newRun())
const date = (value: string) => new Date(value).toLocaleString()
const load = async () => {
  busy.value = true
  error.value = ''
  try {
    if (route.params.assignmentId) assignment.value = (await submissions.assignment(String(route.params.assignmentId))).data
    else {
      assignment.value = null
      const result = (await submissions.list((page.value - 1) * 20, archived.value)).data
      items.value = result.items
      total.value = result.total
      canCreate.value = result.canCreate
    }
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const reloadList = () => {
  page.value = 1
  return load()
}
const chooseTask = async () => {
  taskVersionId.value = null
  try {
    taskVersions.value = taskId.value ? (await taskService.listVersions(taskId.value, 0, 100)).data.items.filter((v) => v.kind === 'release') : []
  } catch (cause) {
    dialogError.value = submissionError(cause)
  }
}
const prepareEditor = async () => {
  dialogError.value = ''
  editDialog.value = true
  try {
    tasks.value = (await taskService.list(0, 100)).data.items
  } catch (cause) {
    dialogError.value = submissionError(cause)
  }
}
const newAssignment = () => {
  form.value = { name: '', description: '', archived: false }
  taskId.value = null
  taskVersionId.value = null
  void prepareEditor()
}
const editAssignment = async () => {
  if (!assignment.value) return
  form.value = { name: assignment.value.data.name, description: assignment.value.data.description, archived: assignment.value.archived }
  taskId.value = assignment.value.data.taskVersion?.taskId ?? null
  await chooseTask()
  taskVersionId.value = assignment.value.data.taskVersion?.versionId ?? null
  await prepareEditor()
}
const saveAssignment = async () => {
  busy.value = true
  dialogError.value = ''
  try {
    const saved = (await submissions.saveAssignment(assignment.value?.id ?? null, { ...form.value, baseRevision: assignment.value?.revision ?? 0, taskVersion: taskId.value && taskVersionId.value ? { taskId: taskId.value, versionId: taskVersionId.value } : null })).data
    editDialog.value = false
    await router.push({ name: 'Submissions', params: { assignmentId: saved.id } })
    await load()
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const openRun = () => {
  runForm.value = newRun()
  dialogError.value = ''
  runDialog.value = true
}
const startRun = async () => {
  if (!assignment.value) return
  busy.value = true
  dialogError.value = ''
  try {
    const run = (await submissions.startRun(assignment.value.id, { ...runForm.value, assignmentRevision: assignment.value.revision })).data
    runDialog.value = false
    await router.push({ name: 'SubmissionRun', params: { runId: run.id } })
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
watch(() => route.params.assignmentId, load, { immediate: true })
</script>
