<template>
  <v-container style="max-width: 1250px">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <v-btn v-if="course" icon="mdi-arrow-left" variant="text" :to="{ name: 'Submissions', query: { view: perspective } }" aria-label="Back to courses" />
      <h1 class="text-h5">{{ course?.name ?? 'Submissions' }}</h1>
      <v-spacer />
      <v-btn-toggle v-if="canSwitch" :model-value="perspective" mandatory density="compact" @update:model-value="changeView"> <v-btn value="participant">My participation</v-btn><v-btn value="management">Administration</v-btn> </v-btn-toggle>
      <v-btn v-if="perspective === 'management' && canCreate && !course" color="primary" @click="newAssignment">Create course</v-btn>
      <v-btn :loading="busy" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <v-alert v-if="notice" type="success" variant="tonal" class="mb-4" role="status">{{ notice }}</v-alert>
    <p v-if="canSwitch && perspective === 'participant'" class="text-body-2 text-medium-emphasis mb-4">This is your own participation, using your account. Other students' submissions are shown in Administration.</p>
    <template v-if="!route.params.assignmentId">
      <SubmissionCourseList v-if="perspective === 'participant'" :courses="courses" :busy="busy" @enroll="enrollCourse" />
      <SubmissionManagementCatalog v-else :items="items" :total="total" :page="page" :archived="archived" :busy="busy" @archive="changeArchive" @page="changePage" />
    </template>
    <template v-else-if="course">
      <p class="mb-4" style="white-space: pre-wrap">{{ course.description }}</p>
      <div class="d-flex flex-wrap align-center ga-3 mb-5">
        <v-select v-if="course.runs.length" :model-value="selectedRun?.id" :items="course.runs" item-title="name" item-value="id" :label="perspective === 'management' ? 'Run' : 'Semester'" hide-details style="max-width: 420px" @update:model-value="selectRun" />
        <template v-if="perspective === 'management' && assignment">
          <v-menu v-if="assignment.canManage"
            ><template #activator="{ props: menuProps }"><v-btn v-bind="menuProps" variant="text" prepend-icon="mdi-cog-outline">Course settings</v-btn></template
            ><v-list><v-list-item title="Edit course settings" @click="editAssignment" /><v-list-item v-if="!assignment.archived" title="Start a new course run" @click="openRun" /></v-list
          ></v-menu>
        </template>
      </div>
      <SubmissionRunWorkspace v-if="selectedRun" :key="`${selectedRun.id}:${perspective}`" :run-id="selectedRun.id" :view="perspective" @enrolled="enrollmentComplete" />
      <v-sheet v-else-if="perspective === 'management' && assignment?.canManage && !assignment.archived && !course.runs.length" border rounded="lg" class="pa-6">
        <h2 class="text-h6 mb-2">Start your first run</h2>
        <p class="text-body-2 mb-4">This course has no runs yet. Start a run, for example for the current semester, so students can join and submit their models.</p>
        <v-btn color="success" variant="flat" prepend-icon="mdi-play" :disabled="busy" @click="openRun">Start first run</v-btn>
      </v-sheet>
      <p v-else class="text-medium-emphasis">No semester available yet.</p>
      <v-expansion-panels v-if="perspective === 'management' && assignment?.canManage && assignment.history?.length" class="mt-5"
        ><v-expansion-panel title="Configuration history"
          ><v-expansion-panel-text
            ><div v-for="version in assignment.history" :key="version.revision" class="mb-3">
              <strong>v{{ version.revision }} - {{ version.data.name }}</strong>
              <p>{{ version.data.description }}</p>
            </div></v-expansion-panel-text
          ></v-expansion-panel
        ></v-expansion-panels
      >
    </template>
    <v-dialog v-model="editDialog" max-width="650" :persistent="busy"
      ><v-card title="Course settings"
        ><v-card-text>
          <v-text-field v-model="form.name" label="Title" maxlength="256" />
          <v-textarea v-model="form.description" label="Description" maxlength="10000" />
          <v-select v-model="taskId" :items="tasks" item-title="name" item-value="id" label="Task (optional)" clearable @update:model-value="chooseTask" />
          <v-select v-if="taskId" v-model="taskVersionId" :items="taskVersions" item-value="id" :item-title="(version) => version.releaseName || version.versionNumber" label="Task release" />
          <v-checkbox v-model="form.archived" label="Archive course · existing runs stay accessible" />
          <v-alert v-if="dialogError" type="error">{{ dialogError }}</v-alert> </v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="editDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!form.name.trim() || Boolean(taskId && !taskVersionId)" @click="saveAssignment">Save course settings</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="runDialog" max-width="760" :persistent="busy"
      ><v-card title="Start course run"
        ><v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">Starting a new run archives earlier runs of this assignment. All their participants, submissions and feedback remain available.</v-alert>
          <SubmissionRunForm :data="runForm" :directory-run-id="assignment?.runs?.find((r) => r.permissions.manage)?.id" />
          <v-alert v-if="dialogError" type="error">{{ dialogError }}</v-alert> </v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="runDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!runForm.name.trim()" @click="startRun">Start course run</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SubmissionRunForm from '@/components/submissions/SubmissionRunForm.vue'
import { submissions, submissionError } from '@/services/submissions'
import taskService from '@/services/task/task.service'
import type { Assignment, RunData, SubmissionCourse, SubmissionCourseDetail, SubmissionView } from '@/services/api/types/submission'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
import SubmissionCourseList from '@/components/submissions/SubmissionCourseList.vue'
import SubmissionManagementCatalog from '@/components/submissions/SubmissionManagementCatalog.vue'
import SubmissionRunWorkspace from '@/components/submissions/SubmissionRunWorkspace.vue'
const route = useRoute()
const router = useRouter()
const assignment = ref<Assignment | null>(null)
const course = ref<SubmissionCourseDetail | null>(null)
const courses = ref<SubmissionCourse[]>([])
const canManage = ref(false)
const perspective = computed<SubmissionView>(() => (canManage.value && route.query.view !== 'participant' ? 'management' : 'participant'))
const canSwitch = computed(() => canManage.value && (!course.value || course.value.canModerate))
const selectedRun = computed(() => course.value?.runs.find((r) => r.id === route.query.run) ?? course.value?.runs.find((r) => r.id === course.value?.activeRunId) ?? course.value?.runs[0])
const items = ref<Assignment[]>([])
const total = ref(0)
const page = ref(1)
const archived = ref(false)
const canCreate = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
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
const load = async () => {
  notice.value = ''
  busy.value = true
  error.value = ''
  try {
    const access = (await submissions.access()).data
    canManage.value = access.canManage
    canCreate.value = access.canCreate
    const id = route.params.assignmentId ? String(route.params.assignmentId) : null
    if (id) {
      if (perspective.value === 'management') {
        assignment.value = (await submissions.assignment(id)).data
        const runs = (assignment.value.runs ?? []).filter((r) => Object.values(r.permissions).some(Boolean))
        if (!runs.length && !assignment.value.canManage) {
          await router.replace({ query: { view: 'participant' } })
          return
        }
        course.value = { id, name: assignment.value.name, description: assignment.value.data.description, activeRunId: assignment.value.activeRunId ?? null, canModerate: true, runs: runs.map((r) => ({ id: r.id, name: r.data.name, enrolled: r.enrolled })) }
      } else {
        assignment.value = null
        course.value = (await submissions.course(id)).data
        if (route.query.run && !course.value.runs.some((run) => run.id === route.query.run) && selectedRun.value) {
          await router.replace({ query: { ...route.query, run: selectedRun.value.id } })
          notice.value = 'You have no submissions in the previously selected semester. Showing an available semester for your account.'
        }
      }
    } else {
      assignment.value = null
      course.value = null
      if (perspective.value === 'management') {
        const result = (await submissions.list((page.value - 1) * 20, archived.value)).data
        items.value = result.items
        total.value = result.total
      } else {
        const result = (await submissions.courses()).data
        courses.value = result.items
      }
    }
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const changeView = (view: SubmissionView) => router.replace({ query: { ...route.query, view } })
const selectRun = (run: string) => router.replace({ query: { ...route.query, run, view: perspective.value } })
const changeArchive = (value: boolean) => {
  archived.value = value
  page.value = 1
  return load()
}
const changePage = (value: number) => {
  page.value = value
  return load()
}
const enrollCourse = async (item: SubmissionCourse) => {
  if (!item.activeRunId) return
  busy.value = true
  error.value = ''
  try {
    await submissions.enroll(item.activeRunId)
    await router.push({ name: 'Submissions', params: { assignmentId: item.id }, query: { view: 'participant' } })
    notice.value = 'You have joined this course. You can submit your model below.'
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const enrollmentComplete = async () => {
  await load()
  notice.value = 'You have joined this course. You can submit your model below.'
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
    await router.push({ name: 'Submissions', params: { assignmentId: saved.id }, query: { view: 'management' } })
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
    await router.push({ name: 'Submissions', params: { assignmentId: assignment.value.id }, query: { run: run.id, view: 'management' } })
    await load()
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
watch([() => route.params.assignmentId, () => route.query.view], load, { immediate: true })
</script>
