<template>
  <div class="group-work-import">
    <!-- Derselbe Kurs und derselbe Gruppenname sind derselbe Raum; ein anderer Kurs, etwa ein anderes Semester, gibt neue Räume. -->
    <v-text-field v-model="course" label="Course" placeholder="Datenbanken WS 26/27" prepend-icon="mdi-school-outline" density="compact" hint="Same course and group name is the same room; another course, such as another semester, gets rooms of its own." persistent-hint class="mb-2" />
    <!-- Die Kurse früherer Importe zum Anklicken statt Tippen, damit derselbe Kurs gleich geschrieben wird. -->
    <div v-if="courses.length" class="d-flex align-center flex-wrap ga-2 mb-4 ml-10">
      <span class="text-caption text-medium-emphasis">Already used:</span>
      <v-chip v-for="known in courses" :key="known" size="small" :color="known === course?.trim() ? 'primary' : undefined" :variant="known === course?.trim() ? 'flat' : 'tonal'" @click="course = known">{{ known }}</v-chip>
    </div>
    <v-file-input label="Participant list from Moodle (CSV)" accept=".csv,.txt,text/csv" prepend-icon="mdi-file-delimited-outline" density="compact" show-size :loading="reading" @update:model-value="load" />
    <v-alert v-if="failure" type="error" variant="tonal" density="compact" class="mb-4">{{ failure }}</v-alert>

    <template v-if="csv">
      <p class="text-medium-emphasis mb-4">{{ csv.people }} people · {{ csv.groups.length }} groups · {{ csv.caseStudies.length }} case studies</p>

      <h3 class="text-subtitle-1 font-weight-medium mb-2">Case study → task</h3>
      <p v-if="!csv.caseStudies.length" class="text-medium-emphasis">The column "Fallstudie" is empty.</p>
      <div v-for="caseStudy in csv.caseStudies" :key="caseStudy" class="d-flex align-center ga-3 mb-2">
        <span class="case-study">F{{ caseStudy }}</span>
        <v-select :model-value="choices[caseStudy].taskId" :items="tasks" item-title="name" item-value="id" label="Task" density="compact" hide-details :loading="loadingTasks" @update:model-value="chooseTask(caseStudy, $event)" />
        <v-select v-model="choices[caseStudy].versionId" :items="versions[choices[caseStudy].taskId ?? ''] ?? []" :item-title="releaseLabel" item-value="id" label="Release" density="compact" hide-details :disabled="!choices[caseStudy].taskId" class="release" />
      </div>

      <h3 class="text-subtitle-1 font-weight-medium mt-6 mb-2">Groups</h3>
      <v-table density="compact">
        <thead>
          <tr>
            <th>Room</th>
            <th>Tasks</th>
            <th>Members</th>
            <th>Check</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="group in csv.groups" :key="group.name">
            <td>{{ group.name }}</td>
            <td>{{ group.caseStudies.map(taskLabel).join(', ') || '—' }}</td>
            <td>
              <v-chip v-for="member in group.members" :key="member.username" size="small" class="mr-1 my-1" :title="member.username">{{ member.name }}</v-chip>
            </td>
            <td :class="statusOf(group).tone">{{ statusOf(group).text }}</td>
          </tr>
        </tbody>
      </v-table>

      <v-alert v-if="csv.skipped.length" type="warning" variant="tonal" density="compact" class="mt-4" :title="`${csv.skipped.length} ${csv.skipped.length === 1 ? 'row was' : 'rows were'} skipped and get no room`" text="Fix them in the CSV and load it again.">
        <v-table density="compact" class="skipped mt-2">
          <thead>
            <tr>
              <th>Row</th>
              <th>Person</th>
              <th>Login name</th>
              <th>Group</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in csv.skipped" :key="entry.row">
              <td>{{ entry.row }}</td>
              <td>{{ entry.name || '—' }}</td>
              <td class="login">{{ entry.username || '—' }}</td>
              <td>{{ entry.group || '—' }}</td>
              <td>{{ entry.reason }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-alert>

      <v-alert v-if="planFailure" type="error" variant="tonal" density="compact" class="mt-4">The check against the existing rooms failed: {{ planFailure }}</v-alert>
      <v-alert v-if="appliedRooms.length" type="success" variant="tonal" density="compact" class="mt-4" :title="appliedTitle">
        <template v-if="missingPeople.length">
          Not in the Feedbacksystem, so not in their room:
          <ul class="ml-4">
            <li v-for="room in missingPeople" :key="room.roomId">{{ room.name }}: {{ room.missing.join(', ') }}</li>
          </ul>
        </template>
      </v-alert>
      <v-alert v-if="createFailure" type="error" variant="tonal" density="compact" class="mt-4">{{ createFailure }} What was applied before stays; applying again sends only what is still missing.</v-alert>

      <div class="d-flex align-center justify-end ga-3 mt-4">
        <span v-if="creating" class="text-caption text-medium-emphasis">{{ progress }} of {{ progressTotal }} groups done</span>
        <span v-else-if="!course?.trim()" class="text-caption text-medium-emphasis">Enter the course first.</span>
        <v-btn color="primary" variant="flat" :disabled="!changes.length || planning || !course?.trim()" :loading="creating" @click="create">{{ changes.length ? `Apply ${changes.length} ${changes.length === 1 ? 'change' : 'changes'}` : 'Nothing to apply' }}</v-btn>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import type { AxiosError } from 'axios'
import { notifyError } from '@/composables/useNotifications'
import httpClient from '@/services/api/httpClient'
import taskService from '@/services/task/task.service'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
import { decodeCsv, parseGroupWorkCsv, type CsvGroup, type GroupWorkCsv } from './groupWorkCsv'

/** `courses`: die Kurse früherer Importe, zum Auswählen, damit derselbe Kurs gleich geschrieben wird. */
withDefaults(defineProps<{ courses?: string[] }>(), { courses: () => [] })

/** Meldet, dass Räume angelegt oder ergänzt wurden, damit <ck-management> und die Übersicht neu laden. */
const emit = defineEmits<{ created: [] }>()

/** Wie viele Gruppen eine Anfrage höchstens anlegt; dieselbe Grenze wie MAX_GROUPS in api/…/schemas/group_work.py. */
const BATCH = 10

/** Ein Raum, wie das Backend ihn angelegt oder ergänzt hat. */
interface AppliedRoom {
  name: string
  roomId: string
  created: boolean
  addedMembers: string[]
  workpieceIds: string[]
  missing: string[]
}

interface Choice {
  taskId: string | null
  versionId: string | null
}

const csv = shallowRef<GroupWorkCsv | null>(null)
const failure = ref('')
const reading = ref(false)
const tasks = shallowRef<Task[]>([])
const loadingTasks = ref(false)
// Je Fallstudie die Aufgabe und ihr Release; die Releases je Aufgabe werden einmal geladen.
const choices = reactive<Record<string, Choice>>({})
const versions = reactive<Record<string, TaskVersionInfo[]>>({})

const releaseLabel = (version: TaskVersionInfo) => (version.releaseName ? `${version.releaseName} · v${version.versionNumber}` : `v${version.versionNumber}`)

const load = async (files: File | File[] | null | undefined) => {
  const file = Array.isArray(files) ? files[0] : files
  csv.value = null
  failure.value = ''
  appliedRooms.value = []
  createFailure.value = ''
  if (!file) return
  reading.value = true
  try {
    const parsed = parseGroupWorkCsv(decodeCsv(await file.arrayBuffer()))
    // Eine Wahl bleibt, wenn dieselbe Fallstudie in der nächsten Datei wieder vorkommt.
    for (const caseStudy of parsed.caseStudies) choices[caseStudy] ??= { taskId: null, versionId: null }
    csv.value = parsed
    assignByNumber()
  } catch (error) {
    failure.value = (error as Error).message
  } finally {
    reading.value = false
  }
}

const chooseTask = async (caseStudy: string, taskId: string | null) => {
  const choice = choices[caseStudy]
  choice.taskId = taskId
  choice.versionId = null
  if (!taskId) return
  try {
    versions[taskId] ??= (await taskService.listVersions(taskId, 0, 100)).data.items.filter((version) => version.kind === 'release')
  } catch {
    notifyError('The releases of this task could not be loaded.')
    return
  }
  // Wie bei „From task“: das neueste Release, solange niemand inzwischen eine andere Aufgabe gewählt hat.
  if (choice.taskId === taskId) choice.versionId = tasks.value.find((task) => task.id === taskId)?.latestReleaseId ?? versions[taskId][0]?.id ?? null
}

/** Die Nummer im Namen einer Aufgabe: „F1 – Einzelhandel“ ist Fallstudie 1. */
const numberOf = (task: Task) => {
  const number = task.name.match(/^\s*F\s*(\d+)/i)?.[1]
  return number ? String(Number(number)) : null
}

/** Ordnet jeder Fallstudie ohne Wahl die Aufgabe mit ihrer Nummer zu; eine Wahl von Hand bleibt. */
const assignByNumber = () => {
  for (const caseStudy of csv.value?.caseStudies ?? []) {
    const task = tasks.value.find((item) => numberOf(item) === caseStudy)
    if (task && !choices[caseStudy].taskId) void chooseTask(caseStudy, task.id)
  }
}

const taskLabel = (caseStudy: string) => tasks.value.find((task) => task.id === choices[caseStudy]?.taskId)?.name ?? `F${caseStudy}`

/** Was eine Gruppe noch vom Anlegen abhält; null, wenn sie bereit ist. Wie viele Fallstudien sie hat, ist frei. */
const problemOf = (group: CsvGroup) => {
  if (!group.caseStudies.length) return 'no case study'
  const missing = group.caseStudies.filter((caseStudy) => !choices[caseStudy]?.versionId)
  return missing.length ? `no task for ${missing.map((caseStudy) => `F${caseStudy}`).join(', ')}` : null
}
/** Was das Backend für eine Gruppe vorhat: neuer Raum, oder was dem vorhandenen Raum dieses Kurses fehlt. */
interface PlannedRoom {
  name: string
  roomId: string | null
  newMembers: string[]
  newTasks: { taskId: string; versionId: string }[]
  missing: string[]
}

const course = ref<string | null>('')
const plans = ref<Record<string, PlannedRoom>>({})
const planning = ref(false)
const planFailure = ref('')
const appliedRooms = ref<AppliedRoom[]>([])
const missingPeople = computed(() => appliedRooms.value.filter((room) => room.missing.length))
const appliedTitle = computed(() => {
  const created = appliedRooms.value.filter((room) => room.created).length
  const completed = appliedRooms.value.length - created
  return [created && `${created} ${created === 1 ? 'room' : 'rooms'} created`, completed && `${completed} ${completed === 1 ? 'room' : 'rooms'} completed`].filter(Boolean).join(', ')
})
const creating = ref(false)
const createFailure = ref('')
const progress = ref(0)
const progressTotal = ref(0)

/** Die Gruppen ohne Problem in der Datei; nur sie prüft und schickt der Reiter. */
const valid = computed(() => csv.value?.groups.filter((group) => !problemOf(group)) ?? [])
const additionsOf = (plan: PlannedRoom) => plan.newMembers.length + plan.newTasks.length
/** Was „Apply“ schickt: neue Räume und vorhandene, denen etwas fehlt. */
const changes = computed(() => valid.value.filter((group) => plans.value[group.name] && (!plans.value[group.name].roomId || additionsOf(plans.value[group.name]))))

const count = (n: number, one: string, many: string) => `+${n} ${n === 1 ? one : many}`
/** Die Prüfspalte: erst Fehler der Datei, dann was der Import mit der Gruppe täte. */
const statusOf = (group: CsvGroup) => {
  const problem = problemOf(group)
  if (problem) return { text: problem, tone: 'text-error' }
  if (!course.value?.trim()) return { text: 'enter the course', tone: 'text-medium-emphasis' }
  const plan = plans.value[group.name]
  if (!plan) return { text: planning.value ? 'checking…' : '—', tone: 'text-medium-emphasis' }
  if (!plan.roomId) return { text: 'new room', tone: 'text-success' }
  if (!additionsOf(plan)) return { text: 'exists · up to date', tone: 'text-medium-emphasis' }
  const parts = [plan.newMembers.length && count(plan.newMembers.length, 'person', 'people'), plan.newTasks.length && count(plan.newTasks.length, 'model', 'models')].filter(Boolean)
  return { text: `exists · ${parts.join(' · ')}`, tone: 'text-warning' }
}

/** Die Gruppe, wie das Backend sie annimmt: Anmeldenamen und je Fallstudie die gewählte Aufgabe. */
const requestOf = (group: CsvGroup) => ({
  name: group.name,
  usernames: group.members.map((member) => member.username),
  tasks: group.caseStudies.map((caseStudy) => ({ taskId: choices[caseStudy].taskId, versionId: choices[caseStudy].versionId }))
})
const messageOf = (error: unknown) => (error as AxiosError<{ message?: string }>).response?.data?.message ?? (error as Error).message

// Nur die Antwort auf die letzte Prüfung zählt; eine ältere kann später ankommen.
let planRun = 0
/** Fragt das Backend, was mit den Gruppen geschähe, in denselben Paketen wie beim Anwenden; geschrieben wird nichts. */
const preview = async () => {
  const run = ++planRun
  const groups = valid.value
  const name = course.value?.trim()
  planFailure.value = ''
  if (!name || !groups.length) {
    plans.value = {}
    return
  }
  planning.value = true
  try {
    const next: Record<string, PlannedRoom> = {}
    for (let start = 0; start < groups.length; start += BATCH) {
      const { data } = await httpClient.post<{ rooms: PlannedRoom[] }>('/v1/group-work/preview', { course: name, groups: groups.slice(start, start + BATCH).map(requestOf) })
      for (const room of data.rooms) next[room.name] = room
    }
    if (run === planRun) plans.value = next
  } catch (error) {
    if (run === planRun) planFailure.value = messageOf(error)
  } finally {
    if (run === planRun) planning.value = false
  }
}

// Kurs, Datei und Aufgaben ändern sich oft kurz nacheinander; geprüft wird erst, wenn es eine Weile ruhig ist.
let planTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => JSON.stringify([course.value?.trim(), valid.value.map(requestOf)]),
  () => {
    clearTimeout(planTimer)
    plans.value = {}
    planTimer = setTimeout(() => void preview(), 400)
  }
)

/** Wendet den Plan in Paketen an; bricht eines ab, bleibt das Vorige, und ein neuer Versuch schickt nur, was noch fehlt. */
const create = async () => {
  const groups = changes.value
  const name = course.value?.trim()
  if (!name) return
  creating.value = true
  createFailure.value = ''
  appliedRooms.value = []
  progress.value = 0
  progressTotal.value = groups.length
  try {
    for (let start = 0; start < groups.length; start += BATCH) {
      const { data } = await httpClient.post<{ rooms: AppliedRoom[] }>('/v1/group-work', { course: name, groups: groups.slice(start, start + BATCH).map(requestOf) })
      appliedRooms.value = [...appliedRooms.value, ...data.rooms]
      progress.value += data.rooms.length
    }
  } catch (error) {
    createFailure.value = messageOf(error)
  } finally {
    creating.value = false
    if (progress.value) emit('created')
    // Danach zeigt die Prüfung den neuen Stand, also „up to date“ für alles Angewendete.
    void preview()
  }
}

onMounted(async () => {
  loadingTasks.value = true
  try {
    tasks.value = (await taskService.list(0, 100, { visibility: 'published' })).data.items
    // Die CSV kann schon geladen sein, bevor die Aufgaben da sind.
    assignByNumber()
  } catch {
    notifyError('Tasks could not be loaded.')
  } finally {
    loadingTasks.value = false
  }
})
</script>

<style scoped>
.group-work-import {
  padding: 4px 0;
}

.case-study {
  min-width: 96px;
  font-weight: 600;
}

.release {
  max-width: 220px;
}

/* Die Tabelle liegt im getönten Hinweis und übernimmt dessen Farbe. */
.skipped {
  background: transparent;
  color: inherit;
}

.login {
  font-family: monospace;
}
</style>
