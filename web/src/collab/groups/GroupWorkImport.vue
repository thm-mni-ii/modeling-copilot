<template>
  <div class="group-work-import">
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
            <td :class="problemOf(group) ? 'text-warning' : 'text-success'">{{ problemOf(group) ?? 'ready' }}</td>
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

      <div class="d-flex align-center justify-end ga-3 mt-4">
        <!-- Bis die Route im Backend steht, legt der Reiter noch nichts an. -->
        <span class="text-caption text-medium-emphasis">Creating the rooms follows with the backend.</span>
        <v-btn color="primary" variant="flat" disabled>Create {{ ready.length }} {{ ready.length === 1 ? 'room' : 'rooms' }}</v-btn>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue'
import { notifyError } from '@/composables/useNotifications'
import taskService from '@/services/task/task.service'
import type { Task, TaskVersionInfo } from '@/services/api/types/task'
import { decodeCsv, parseGroupWorkCsv, type CsvGroup, type GroupWorkCsv } from './groupWorkCsv'

/** Meldet, dass Räume angelegt wurden, damit <ck-management> neu lädt. */
defineEmits<{ created: [] }>()

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
const ready = computed(() => csv.value?.groups.filter((group) => !problemOf(group)) ?? [])

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
