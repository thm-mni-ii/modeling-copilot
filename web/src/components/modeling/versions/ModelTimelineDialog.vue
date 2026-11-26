<template>
  <v-dialog :model-value="modelValue" class="model-timeline-dialog" max-width="1600" :persistent="busy" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="timeline-card">
      <header class="timeline-header">
        <h2>Versions-Timeline</h2>
        <v-btn v-if="!panelOpen" size="small" variant="text" prepend-icon="mdi-dock-right" @click="panelOpen = true; mobilePane = 'feedback'">Sidebar einblenden</v-btn>
        <v-btn size="small" variant="text" icon="mdi-close" :disabled="busy" aria-label="Timeline schließen" @click="close" />
      </header>
      <v-progress-linear v-if="loading" class="timeline-loading" indeterminate />
      <section class="timeline-body">
        <v-btn-toggle v-if="panelOpen" v-model="mobilePane" mandatory class="timeline-mobile-tabs" density="compact"><v-btn value="model">Modell</v-btn><v-btn value="feedback">Details</v-btn></v-btn-toggle>
        <div ref="workspaceElement" class="timeline-workspace">
          <div class="timeline-model" :class="{ 'timeline-mobile-hidden': panelOpen && mobilePane !== 'model' }">
            <span v-if="previewError" class="timeline-preview-error">Dieser Modellstand ist nicht verfügbar.</span>
            <ModelSnapshotPreview ref="snapshotPreview" :data="timelineData" :height="null" fit />
          </div>
          <SidebarFrame v-if="panelOpen" v-model:width="sidebarWidth" side="right" :min-width="sidebarMinWidth" :max-width="sidebarMaxWidth" class="timeline-details" :class="{ 'timeline-mobile-hidden': mobilePane !== 'feedback' }" aria-label="Details zum Modellstand">
            <template #tabs>
              <SidebarTabs v-model="detailTab" :tabs="detailTabs" aria-label="Timeline-Sidebar" />
              <v-btn size="x-small" variant="text" icon="mdi-chevron-right" title="Sidebar schließen" aria-label="Sidebar schließen" @click="panelOpen = false" />
            </template>
            <TimelineFitContent :min-width="260">
              <template v-if="detailTab === 'task'">
                <v-btn v-if="task.active" size="small" variant="text" prepend-icon="mdi-text-box-clock-outline" :color="includeTaskEdits ? 'info' : undefined" :aria-pressed="includeTaskEdits" class="mb-2" @click="includeTaskEdits = !includeTaskEdits">Aufgabenhistorie {{ includeTaskEdits ? 'ausblenden' : 'einblenden' }}</v-btn>
                <TaskEditEditor v-if="timelineTaskEditSnapshot" :base-html="task.baseHtml" :base-document="task.baseDocument" :model-value="timelineTaskEditSnapshot.document" mode="read" class="timeline-task-edits" />
                <p v-else>Für diesen Stand ist keine Aufgabe verfügbar.</p>
              </template>
              <template v-else>
                <p v-if="evaluationError" class="text-warning">{{ evaluationError }} <v-btn size="small" @click="loadEvaluations">Erneut versuchen</v-btn></p>
                <HistoricalEvaluationView v-if="selectedEvaluationId && workspace.model" :key="selectedEvaluationId" :model-id="workspace.model.id" :evaluation-id="selectedEvaluationId" :perspective="evaluationPerspective" :graph="previewReady ? snapshotPreview?.graph : undefined" @evaluation-updated="updateRunStatus" />
                <p v-else class="text-body-2 pa-3">Für diesen Stand gibt es keine Auswertung.</p>
              </template>
            </TimelineFitContent>
          </SidebarFrame>
        </div>
      </section>
      <div class="timeline-navigation">
        <TimelineFitContent :min-width="640" :reflow="false">
          <div v-if="timelineSteps.length > 1" ref="sliderWrap" class="timeline-slider-wrap" :style="tickLayoutStyle">
            <v-slider v-model="timelineStep" :min="0" :max="timelineSteps.length - 1" :step="1" :ticks="timelineTicks" show-ticks="always" :tick-size="8" :color="timelineIsUnsaved ? 'warning' : 'primary'" :track-fill-color="timelineIsUnsaved ? 'warning' : 'primary'" :class="['timeline-slider', { 'timeline-slider--has-unsaved': hasUnsavedTimeline }]" :style="timelineSliderStyle" aria-label="Modellstand auswählen">
              <template #tick-label="{ tick }">
                <button v-if="tickHasFeedback(tick.value)" type="button" class="timeline-tick-text timeline-tick-text--feedback timeline-tick-text--lowered" :data-tick="tick.value" :data-position="tick.position" :data-align="tickAlign(tick.value)" :style="{ '--tick-lane': tickLanes[tick.value] ?? 1 }" :aria-label="`${tick.label}: Feedback anzeigen`" @mousedown.stop @touchstart.stop @click.stop="openFeedbackAt(tick.value)"><v-icon size="12">mdi-comment-text-outline</v-icon> {{ tick.label }}</button>
                <span v-else class="timeline-tick-text" :class="{ 'timeline-tick-text--lowered': (tickLanes[tick.value] ?? 0) > 0, 'timeline-tick-text--saved': tick.value === lastSavedIndex }" :data-tick="tick.value" :data-position="tick.position" :data-align="tickAlign(tick.value)" :style="{ '--tick-lane': tickLanes[tick.value] ?? 0 }" @mousedown="keepStep($event, tick.value)" @touchstart="keepStep($event, tick.value)">{{ tick.label }}</span>
              </template>
            </v-slider>
          </div>
          <div v-else-if="evaluationMarkers.length" class="timeline-single-marker"><button type="button" class="timeline-tick-text timeline-tick-text--feedback" @click="openFeedbackAt(0)"><v-icon size="14">mdi-comment-text-outline</v-icon> {{ timelineTicks[0] }}</button></div>
          <p class="timeline-position"><span v-if="timelineIsUnsaved" class="text-warning">Ungespeichert · </span>{{ timelineLabel }}</p>
          <p v-if="hasUnsavedTimeline" class="timeline-unsaved-note">Orange: lokale Änderungen nach dem letzten Speichern.</p>
          <p v-if="evaluationError && !panelOpen" class="text-warning">{{ evaluationError }} <v-btn size="x-small" @click="loadEvaluations">Erneut versuchen</v-btn></p>
        </TimelineFitContent>
      </div>
      <footer class="timeline-footer">
        <TimelineFitContent :min-width="600">
          <div class="timeline-actions">
            <v-btn v-if="!targetEvaluationId" size="small" :disabled="!previewReady || busy" :loading="restoring" prepend-icon="mdi-history" @click="restoreSelected">Restore as checkpoint</v-btn>
            <v-btn v-if="!targetEvaluationId && !files?.learningPath.value" size="small" :disabled="!previewReady || busy" :loading="branching" prepend-icon="mdi-source-branch" @click="openBranch">Branch from here</v-btn>
            <v-spacer />
            <v-btn size="small" :disabled="busy" @click="close">Zurück zum Editor</v-btn>
          </div>
        </TimelineFitContent>
      </footer>
    </v-card>
  </v-dialog>

  <v-dialog v-model="branchDialog" max-width="520" persistent>
    <v-card>
      <v-card-title>Branch from timeline position</v-card-title>
      <v-card-text>
        <v-text-field v-model="branchName" label="New model name" maxlength="256" counter autofocus @keyup.enter="createBranch" />
        <p class="text-caption text-medium-emphasis mb-0">The selected state becomes the initial release of a new model.</p>
        <v-checkbox v-if="timelineTaskEditSnapshot && task.active" v-model="branchEdits" label="Use task edits from the selected position" hide-details />
        <p v-if="sharedTaskContent?.notes" class="text-caption text-medium-emphasis mt-2 mb-0">Notes of the group stay in the room.</p>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="branching" @click="branchDialog = false">Cancel</v-btn><v-btn color="primary" :loading="branching" :disabled="!branchName.trim()" @click="createBranch">Create branch</v-btn></v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="restoreDialog" max-width="560" persistent>
    <v-card>
      <v-card-title>Restore model state?</v-card-title>
      <v-card-text>
        <p>The drawing and version-bound settings will be restored. Your current Task Edits remain unchanged by default.</p>
        <v-checkbox v-if="timelineTaskEditSnapshot" v-model="restoreEdits" label="Use Edits from this model state" hide-details />
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn :disabled="restoring" @click="restoreDialog = false">Cancel</v-btn><v-btn color="primary" :loading="restoring" @click="confirmRestore">Restore</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGraphContext } from '@/composables/useGraphContext'
import modelService from '@/services/model/model.service'
import type { JsonObject } from '@/services/api/types/common'
import type { ModelVersion, ModelVersionInfo, TaskEditDocument, TaskEditVersionInfo } from '@/services/api/types/model'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { applyModelPatches } from '@/utils/modelPatches'
import { importModelFromXml } from '@/utils/modelPersistence'
import { appendUnsavedTimelinePatches, buildModelTimeline, patchesForTimelineStep } from '@/utils/modelTimeline'
import ModelSnapshotPreview from './ModelSnapshotPreview.vue'
import HistoricalEvaluationView from './HistoricalEvaluationView.vue'
import TimelineFitContent from './TimelineFitContent.vue'
import SidebarFrame from '../sidebars/SidebarFrame.vue'
import SidebarTabs from '../sidebars/SidebarTabs.vue'
import evaluationService from '@/services/evaluation/evaluation.service'
import type { Evaluation, EvaluationOutcome } from '@/services/api/types/evaluation'
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import { buildTaskEditTimeline } from '@/utils/taskEditTimeline'
import { useTaskHistory } from '@/collab/worksheet/useTaskHistory'
import { roomBranchTask } from '@/collab/historyBuilder/fromRoom'
import { sharedTaskContent } from '@/collab/worksheet/sharedTask'
import { notifyError, notifyWarning } from '@/composables/useNotifications'
import { useModelFileContext } from '@/composables/useModelFileContext'

const files = useModelFileContext()
const props = defineProps<{ modelValue: boolean; targetVersionId?: string; targetEvaluationId?: string; evaluationPerspective?: 'student' | 'service' }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const workspace = useModelWorkspaceStore()
const task = useTaskHistory()
const { graph } = useGraphContext()
const router = useRouter()

const history = ref<ModelVersionInfo[]>([])
const evaluations = ref<Evaluation[]>([])
const evaluationError = ref('')
const previewError = ref(false)
const mobilePane = ref('model')
const panelOpen = ref(true)
const detailTab = ref('feedback')
const detailTabs = computed(() => [
  { value: 'feedback', icon: 'mdi-comment-text-outline', label: 'Feedback' },
  ...(task.active ? [{ value: 'task', icon: 'mdi-text-box-outline', label: 'Aufgabe' }] : [])
])
const workspaceElement = ref<HTMLElement | null>(null)
const workspaceWidth = ref(1000)
const sidebarRatio = ref(0.4)
const sidebarMinWidth = computed(() => Math.min(260, workspaceWidth.value * 0.4))
const sidebarMaxWidth = computed(() => workspaceWidth.value * 0.75)
const sidebarWidth = computed({
  get: () => Math.max(sidebarMinWidth.value, Math.min(sidebarMaxWidth.value, workspaceWidth.value * sidebarRatio.value)),
  set: (width: number) => { sidebarRatio.value = width / Math.max(1, workspaceWidth.value) }
})
const workspaceObserver = new ResizeObserver(entries => { workspaceWidth.value = entries[0].contentRect.width })
watch(workspaceElement, (element, previous) => {
  if (previous) workspaceObserver.unobserve(previous)
  if (element) workspaceObserver.observe(element)
}, { flush: 'post' })
onBeforeUnmount(() => workspaceObserver.disconnect())
const openFeedbackAt = (index: number) => {
  timelineStep.value = index
  panelOpen.value = true
  detailTab.value = 'feedback'
  mobilePane.value = 'feedback'
}
const tickHasFeedback = (index: number) => Boolean(evaluationMarkers.value.some(marker => marker.index === index))
const snapshotPreview = shallowRef<InstanceType<typeof ModelSnapshotPreview> | null>(null)
const selectedPositionId = ref<string | null>(null)
const timelineData = ref<JsonObject | null>(null)
const materializedPositionId = ref<string | null>(null)
const loading = ref(false)
const restoring = ref(false)
const branching = ref(false)
const branchDialog = ref(false)
const branchName = ref('')
const restoreDialog = ref(false)
const restoreEdits = ref(false)
const timelineVersion = ref<ModelVersion | null>(null)
const selectedTaskSnapshot = ref<TaskEditDocument | null>(null)
const timelineTaskEditSnapshot = computed(() => selectedTaskSnapshot.value)
const includeTaskEdits = ref(false)
const taskHistory = ref<TaskEditVersionInfo[]>([])
const branchEdits = ref(false)
const releaseDataCache = new Map<string, JsonObject>()
const versionCache = new Map<string, ModelVersion>()
let timelineRequest = 0

const savedTimelineSteps = computed(() => buildModelTimeline(history.value))
const modelSteps = computed(() => appendUnsavedTimelinePatches(savedTimelineSteps.value, workspace.baseReleaseId, workspace.pendingPatches, workspace.languages))
const timelineSteps = computed(() => {
  const positions = modelSteps.value.map((step, modelIndex) => ({
    id: `model-${modelIndex}`, modelIndex, taskStep: null as ReturnType<typeof buildTaskEditTimeline>[number] | null,
    createdAt: step.kind === 'release' ? step.createdAt : step.patch.createdAt,
    saved: step.kind === 'release' || step.saved,
    versionId: step.kind === 'release' ? step.releaseId : step.checkpointId && step.patchNumber === history.value.find(version => version.id === step.checkpointId)?.patches.length ? step.checkpointId : null,
    directVersionId: null as string | null,
    evaluationId: null as string | null
  }))
  for (const versionId of new Set([...evaluations.value.map(run => run.submission.versionId), ...(props.targetVersionId ? [props.targetVersionId] : [])])) {
    if (positions.some(position => position.versionId === versionId)) continue
    const version = history.value.find(entry => entry.id === versionId)
    const position = { id: `version-${versionId}`, modelIndex: -1, taskStep: null,
      versionId, directVersionId: versionId, saved: true, evaluationId: null,
      createdAt: version?.createdAt ?? evaluations.value.find(run => run.submission.versionId === versionId)?.startedAt ?? '' }
    const nextIndex = positions.findIndex(entry => entry.createdAt > position.createdAt)
    positions.splice(nextIndex < 0 ? positions.length : nextIndex, 0, position)
  }
  // Every run owns a distinct UI position, even when several runs evaluated
  // the same saved version. No duplicate model/version is persisted.
  const evaluatedPositions = positions.flatMap(position => {
    if (!position.versionId) return [position]
    const runs = evaluations.value.filter(run => run.submission.versionId === position.versionId)
      .sort((a, b) => a.startedAt.localeCompare(b.startedAt) || a.id.localeCompare(b.id))
    if (!runs.length) return [position]
    return runs.map(run => ({ ...position, id: `evaluation-${run.id}`, evaluationId: run.id,
      directVersionId: position.versionId }))
  })
  if (!includeTaskEdits.value) return evaluatedPositions
  if (includeTaskEdits.value) for (const taskStep of buildTaskEditTimeline(taskHistory.value, task.pending, task.start)) {
    let modelIndex = 0
    for (let index = 0; index < modelSteps.value.length; index++) {
      const step = modelSteps.value[index]
      const date = step.kind === 'release' ? step.createdAt : step.patch.createdAt
      if (date <= taskStep.createdAt) modelIndex = index
    }
    evaluatedPositions.push({ id: taskStep.id, modelIndex, taskStep, createdAt: taskStep.createdAt, saved: taskStep.saved, versionId: null, directVersionId: null, evaluationId: null })
  }
  // Preserve the patch order established by buildModelTimeline, including timestamp ties.
  return evaluatedPositions.sort((a, b) => a.createdAt.localeCompare(b.createdAt))
})
// Keep one source of truth: the selected position ID. Indices may shift when
// history is loaded or task positions are toggled; the selected run must not.
const timelineStep = computed({
  get: () => {
    const index = timelineSteps.value.findIndex(position => position.id === selectedPositionId.value)
    return index >= 0 ? index : Math.max(0, timelineSteps.value.length - 1)
  },
  set: (index: number) => { selectedPositionId.value = timelineSteps.value[index]?.id ?? null }
})
const selectedPosition = computed(() => timelineSteps.value[timelineStep.value] ?? null)
const selectedEvaluationId = computed(() => selectedPosition.value?.evaluationId ?? null)
const evaluationMarkers = computed(() => timelineSteps.value.flatMap((position, index) => {
  const run = evaluations.value.find(run => run.id === position.evaluationId)
  if (!run) return []
  const version = history.value.find(entry => entry.id === position.versionId)
  return [{ index, evaluationId: run.id, label: `${version ? `v${version.versionNumber}` : 'Modellstand'} · ${new Date(run.startedAt).toLocaleString()} · ${run.state}` }]
}))
const loadEvaluations = async () => {
  evaluationError.value = ''
  if (!workspace.model) return
  try { evaluations.value = await evaluationService.listAll(workspace.model.id) }
  catch { evaluationError.value = 'Auswertungen konnten nicht geladen werden.' }
}
const updateRunStatus = (outcome: EvaluationOutcome) => {
  const run = evaluations.value.find(entry => entry.id === outcome.id)
  if (run) run.state = outcome.state
}
const lastSavedIndex = computed(() => {
  for (let index = timelineSteps.value.length - 1; index >= 0; index--) if (timelineSteps.value[index].saved) return index
  return -1
})
const timelineTicks = computed(() => Object.fromEntries(timelineSteps.value.flatMap((position, index) => {
  const step = modelSteps.value[position.modelIndex]
  // Ein Release trägt immer eine volle Zahl; ohne ".0" bleibt das Label kurz. Ein Release-Name steht dahinter.
  const label = !position.taskStep && step?.kind === 'release' ? [`v${step.versionNumber.replace(/\.0$/, '')}`, step.releaseName].filter(Boolean).join(' · ') : ''
  const marker = evaluationMarkers.value.find(marker => marker.index === index)
  const evaluationLabel = marker ? `Ausw. ${evaluationMarkers.value.indexOf(marker) + 1}` : ''
  return label || marker || index === lastSavedIndex.value ? [[index, [label, evaluationLabel, index === lastSavedIndex.value ? 'Last save' : ''].filter(Boolean).join(' · ')]] : []
})))

// Überlappen sich Labels, rutscht das spätere in eine tiefere Zeile. Breiten, Spur und Zeilenhöhe kommen aus dem DOM, nichts ist fest.
const sliderWrap = ref<HTMLElement | null>(null)
const tickLanes = ref<Record<number, number>>({})
const tickRowHeight = ref(0)
// Die Pille von Last save ist nur Anzeige: ein Klick darauf springt nicht zu der Stelle unter dem Mauszeiger.
const keepStep = (event: Event, value: number) => {
  if (value === lastSavedIndex.value) event.stopPropagation()
}
const tickLayoutStyle = computed(() => ({ '--tick-row-height': `${tickRowHeight.value}px`, '--tick-lanes-height': `${Math.max(0, ...Object.values(tickLanes.value)) * tickRowHeight.value}px` }))
// Das erste Label beginnt am Tick, das letzte endet dort, die anderen sind zentriert (wie bei Vuetify).
const tickAlign = (value: number) => (value === 0 ? 'start' : value === timelineSteps.value.length - 1 ? 'end' : 'center')
const layoutTickLabels = () => {
  const track = sliderWrap.value?.querySelector<HTMLElement>('.v-slider-track')
  const labels = Array.from(sliderWrap.value?.querySelectorAll<HTMLElement>('.timeline-tick-text') ?? [])
  if (!track || labels.length === 0) return
  const gap = parseFloat(getComputedStyle(labels[0]).fontSize)
  const ends: number[] = []
  const lanes: Record<number, number> = {}
  for (const label of labels) {
    const width = label.offsetWidth
    const at = (Number(label.dataset.position) / 100) * track.offsetWidth
    const start = label.dataset.align === 'start' ? at : label.dataset.align === 'end' ? at - width : at - width / 2
    const minimumLane = label.classList.contains('timeline-tick-text--feedback') ? 1 : 0
    let lane = minimumLane
    while (ends[lane] != null && start < ends[lane] + gap) lane++
    ends[lane] = start + width
    lanes[Number(label.dataset.tick)] = lane
  }
  tickRowHeight.value = labels[0].offsetHeight
  if (JSON.stringify(lanes) !== JSON.stringify(tickLanes.value)) tickLanes.value = lanes
}
const tickObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(layoutTickLabels)
watch(sliderWrap, (element, before) => {
  if (before) tickObserver?.unobserve(before)
  if (element) tickObserver?.observe(element)
}, { flush: 'post' })
watch(timelineTicks, () => void nextTick(layoutTickLabels), { flush: 'post' })
onBeforeUnmount(() => tickObserver?.disconnect())
const selectedStep = computed(() => modelSteps.value[selectedPosition.value?.modelIndex ?? -1] ?? null)
const hasUnsavedTimeline = computed(() => timelineSteps.value.some((step) => !step.saved))
const timelineIsUnsaved = computed(() => selectedPosition.value ? !selectedPosition.value.saved : false)
const busy = computed(() => loading.value || restoring.value || branching.value)
const previewReady = computed(() => Boolean(timelineData.value) && materializedPositionId.value === selectedPosition.value?.id)
const timelineSliderStyle = computed<Record<string, string>>(() => {
  const maximum = timelineSteps.value.length - 1
  const percentage = maximum > 0 ? (lastSavedIndex.value / maximum) * 100 : 100
  return { '--last-save-position': `${Math.max(0, percentage)}%` }
})
const timelineLabel = computed(() => {
  if (selectedEvaluationId.value) {
    const run = evaluations.value.find(run => run.id === selectedEvaluationId.value)
    const version = history.value.find(version => version.id === selectedPosition.value?.versionId)
    return run ? `${version ? `v${version.versionNumber} · ` : ''}${new Date(run.startedAt).toLocaleString()} · ${run.state}` : ''
  }
  if (selectedPosition.value?.directVersionId) {
    const version = history.value.find(entry => entry.id === selectedPosition.value?.directVersionId)
    return version ? `Checkpoint v${version.versionNumber} · ${new Date(version.createdAt).toLocaleString()}` : 'Gespeicherter Modellstand nicht verfügbar'
  }
  const taskStep = selectedPosition.value?.taskStep
  if (taskStep) return `${taskStep.saved ? 'Saved' : 'Local'} task edit - ${new Date(taskStep.createdAt).toLocaleString()} - ${taskStep.label}`
  const step = selectedStep.value
  if (!step) return 'No version history is available.'
  if (step.kind === 'release') {
    const name = step.releaseName ? `${step.releaseName} · ` : ''
    const same = step.sameAsCheckpoint ? ` = Checkpoint v${step.sameAsCheckpoint}` : ''
    return `${name}Release v${step.versionNumber}${same} · ${new Date(step.createdAt).toLocaleString('en-GB')}`
  }
  if (!step.saved) return `Local patch ${step.patchNumber} · ${new Date(step.patch.createdAt).toLocaleString('en-GB')}`
  return `Checkpoint v${step.checkpointVersionNumber}, patch ${step.patchNumber} · ${new Date(step.patch.createdAt).toLocaleString('en-GB')}`
})

const loadHistory = async () => {
  if (!workspace.model) return
  const currentModel = workspace.model
  const entries: ModelVersionInfo[] = []
  let total = 0
  do {
    const page = (await modelService.listVersions(currentModel, entries.length, 100)).data
    if (page.items.length === 0) break
    entries.push(...page.items)
    total = page.total
  } while (entries.length < total)
  history.value = entries
}

const getReleaseData = async (releaseId: string) => {
  const cached = releaseDataCache.get(releaseId)
  if (cached) return cached
  if (!workspace.model) throw new Error('No model is loaded.')
  const data = (await modelService.getVersion(workspace.model, releaseId)).data.data
  releaseDataCache.set(releaseId, data)
  return data
}

const updatePreview = async () => {
  const request = ++timelineRequest
  materializedPositionId.value = null
  timelineVersion.value = null
  selectedTaskSnapshot.value = null
  previewError.value = false
  const position = selectedPosition.value
  const step = selectedStep.value
  if (!position || (!step && !position.directVersionId)) return
  try {
    const versionId = position.directVersionId ?? (step?.kind === 'release' ? step.releaseId : step?.checkpointId)
    if (versionId && workspace.model) {
      let version = versionCache.get(versionId)
      if (!version) {
        version = (await modelService.getVersion(workspace.model, versionId)).data
        versionCache.set(versionId, version)
      }
      if (request !== timelineRequest) return
      timelineVersion.value = version
    } else timelineVersion.value = null
    if (position.versionId && timelineVersion.value) {
      timelineData.value = timelineVersion.value.data
    } else if (step) {
      const base = await getReleaseData(step.releaseId)
      if (request !== timelineRequest || typeof base.xml !== 'string') return
      timelineData.value = { ...base, xml: applyModelPatches(base.xml, patchesForTimelineStep(modelSteps.value, position.modelIndex)) }
    }
    const taskStep = selectedPosition.value?.taskStep
    let taskSnapshot = taskStep?.patch ? { schemaVersion: 1 as const, revision: workspace.taskEdit?.revision ?? 0, updatedAt: taskStep.createdAt, document: taskStep.patch.document }
      : taskStep ? await task.stateOf(taskStep.id)
      : timelineIsUnsaved.value ? workspace.taskEdit : timelineVersion.value?.taskEditSnapshot ?? null
    if (request !== timelineRequest) return
    if (!taskSnapshot && task.baseDocument) taskSnapshot = { schemaVersion: 1, revision: 0, updatedAt: workspace.taskVersion?.createdAt ?? new Date().toISOString(), document: task.baseDocument }
    selectedTaskSnapshot.value = taskSnapshot
    materializedPositionId.value = position.id
  } catch {
    if (request === timelineRequest) { timelineData.value = null; previewError.value = true }
  }
}

const openTimeline = async () => {
  loading.value = true
  panelOpen.value = true
  detailTab.value = 'feedback'
  mobilePane.value = 'model'
  selectedPositionId.value = null
  evaluations.value = []
  releaseDataCache.clear()
  versionCache.clear()
  history.value = []
  timelineData.value = null
  materializedPositionId.value = null
  try {
    await Promise.all([loadHistory(), loadEvaluations()])
    taskHistory.value = task.active ? await task.list() : []
    const targetIndex = props.targetEvaluationId
      ? timelineSteps.value.findIndex(position => position.evaluationId === props.targetEvaluationId)
      : timelineSteps.value.findIndex(position => position.versionId === props.targetVersionId)
    timelineStep.value = targetIndex >= 0 ? targetIndex : Math.max(0, timelineSteps.value.length - 1)
    await updatePreview()
  } catch {
    notifyError('Unable to load the version timeline.')
  } finally {
    loading.value = false
  }
}

const restoreSelected = () => {
  restoreEdits.value = false
  restoreDialog.value = true
}

const confirmRestore = async () => {
  const step = selectedStep.value
  const languages = timelineVersion.value?.workspaceLanguages ?? step?.workspaceLanguages
  if (!languages || !previewReady.value || !timelineData.value || !graph.value) return
  restoring.value = true
  try {
    await workspace.restoreSnapshot(timelineData.value, languages)
    if (restoreEdits.value && timelineTaskEditSnapshot.value) await task.restore(timelineTaskEditSnapshot.value)
    importModelFromXml(graph.value, workspace.data.xml)
    await workspace.save()
    restoreDialog.value = false
    emit('update:modelValue', false)
  } catch {
    notifyError('Unable to restore this timeline position.')
  } finally {
    restoring.value = false
  }
}

const openBranch = () => {
  branchName.value = `${workspace.model?.name ?? workspace.data.name} – ${timelineLabel.value}`.slice(0, 256)
  branchEdits.value = false
  branchDialog.value = true
}

const createBranch = async () => {
  const step = selectedStep.value
  const languages = timelineVersion.value?.workspaceLanguages ?? step?.workspaceLanguages
  if (files?.learningPath.value || !languages || !previewReady.value || !timelineData.value || !branchName.value.trim()) return
  branching.value = true
  try {
    const edits = branchEdits.value ? timelineTaskEditSnapshot.value : null
    // Modell eines Raums: die Task des Raums, sofern sie mitkommen kann.
    const room = await roomBranchTask(languages, edits)
    if (room?.notice) notifyWarning(room.notice)
    await workspace.branchSnapshot(timelineData.value, room?.languages ?? languages, branchName.value.trim(), room ? room.reference : timelineVersion.value?.taskVersion ?? workspace.taskReference, room ? room.taskEdit : edits ?? workspace.taskEdit)
    await workspace.save()
    branchDialog.value = false
    emit('update:modelValue', false)
    await router.push(`/modeling/${workspace.model!.id}`)
  } catch {
    notifyError('Unable to create a branch from this timeline position.')
  } finally {
    branching.value = false
  }
}

const close = () => emit('update:modelValue', false)

watch(
  () => props.modelValue,
  (open) => {
    if (open) void openTimeline()
    else {
      ++timelineRequest
      branchDialog.value = false
      restoreDialog.value = false
    }
  },
  { immediate: true }
)
watch(() => selectedPosition.value?.id, () => { if (props.modelValue && !loading.value) void updatePreview() })
</script>

<style scoped>
.model-timeline-dialog :deep(.v-overlay__content) {
  width: calc(100vw - 32px);
  height: min(900px, calc(100dvh - 32px));
  max-height: calc(100dvh - 32px);
  margin: 16px;
  overflow: visible;
}
.model-timeline-dialog :deep(.v-overlay__content > .timeline-card) {
  height: 100%;
  max-height: none;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) clamp(80px, 19dvh, 144px) 44px;
  overflow: visible;
}
.timeline-header { display: flex; align-items: center; gap: 4px; padding: 8px 12px; }
.timeline-header h2 { flex: 1; min-width: 0; font-size: clamp(12px, 2vw, 18px); font-weight: 600; }
.timeline-loading { position: absolute; top: 0; }
.timeline-body { display: flex; flex-direction: column; min-height: 0; padding: 0 16px; gap: 6px; }
.timeline-workspace { flex: 1; min-height: 0; display: flex; gap: 12px; }
.timeline-model { position: relative; flex: 1; min-width: 0; min-height: 0; }
.timeline-preview-error { position: absolute; inset: 8px 8px auto; z-index: 1; font-size: 12px; }
.timeline-details { min-height: 0; overflow: visible; }
.timeline-details :deep(.sidebar-frame__body) { padding: 8px; overflow: visible; }
.timeline-details :deep(.sidebar-frame__tabs) { padding: 4px; }
.timeline-task-edits { height: auto; }
.timeline-task-edits :deep(.task-edit-body) { height: auto; overflow: visible; }
.timeline-navigation { min-height: 0; min-width: 0; padding: 4px 24px 0; }
.timeline-footer { min-height: 0; padding: 2px 12px 6px; }
.timeline-actions { display: flex; gap: 8px; align-items: center; }
.timeline-position, .timeline-unsaved-note { font-size: 11px; line-height: 1.4; margin: 0; overflow-wrap: anywhere; }
.timeline-unsaved-note { color: rgb(var(--v-theme-warning)); }
.timeline-mobile-tabs { display: none; flex: none; }
.timeline-single-marker { padding: 8px 0; }
@media (max-width: 800px) {
  .timeline-details { width: 100% !important; min-width: 0 !important; }
  .timeline-details :deep(.sidebar-frame__resize) { display: none; }
  .timeline-mobile-tabs { display: inline-flex; align-self: start; }
  .timeline-mobile-hidden { display: none; }
  .timeline-header { padding: 4px 6px; gap: 0; }
  .timeline-body { padding-inline: 8px; }
}
@media (max-height: 480px) {
  .model-timeline-dialog :deep(.v-overlay__content > .timeline-card) { grid-template-rows: auto minmax(0, 1fr) minmax(40px, 22dvh) 32px; }
  .timeline-header { padding-block: 2px; }
  .timeline-header :deep(.v-btn) { width: 28px; height: 28px; }
  .timeline-mobile-tabs { height: 24px; }
  .timeline-mobile-tabs :deep(.v-btn) { height: 24px; font-size: 10px; }
}
.timeline-slider-wrap {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  overflow: visible;
  padding: 0 24px calc(24px + var(--tick-lanes-height, 0px));
}
.timeline-slider { width: 100%; min-width: 0; margin-top: 0; }
.timeline-slider :deep(.v-slider-track__tick) { border: 2px solid rgb(var(--v-theme-primary)); background: rgb(var(--v-theme-surface)); }
.timeline-slider :deep(.v-slider-track__tick-label) { color: rgb(var(--v-theme-primary)); font-size: 11px; font-weight: 600; white-space: nowrap; }
.timeline-tick-text { display: inline-block; position: relative; transform: translateY(calc(var(--tick-lane, 0) * var(--tick-row-height, 0px))); }
.timeline-tick-text--saved { padding: 0 8px; border-radius: 999px; background: rgb(var(--v-theme-primary)); color: rgb(var(--v-theme-on-primary)); cursor: default; }
.timeline-tick-text--feedback { padding: 1px 6px; border: 1px solid rgba(var(--v-theme-info), 0.3); border-radius: 6px; background: rgba(var(--v-theme-info), 0.1); color: rgb(var(--v-theme-info)); cursor: pointer; font: inherit; }
.timeline-tick-text--feedback:hover { background: rgba(var(--v-theme-info), 0.2); }
.timeline-tick-text--feedback:focus-visible { outline: 2px solid rgb(var(--v-theme-info)); outline-offset: 2px; }
.timeline-tick-text--lowered::before { content: ''; position: absolute; bottom: 100%; height: calc(var(--tick-lane, 0) * var(--tick-row-height, 0px)); border-left: 1px solid currentColor; opacity: 0.35; }
.timeline-tick-text--lowered[data-align='center']::before { left: 50%; }
.timeline-tick-text--lowered[data-align='start']::before { left: 0; }
.timeline-tick-text--lowered[data-align='end']::before { right: 0; }
.timeline-slider--has-unsaved :deep(.v-slider-track__background) { opacity: 0.38; background: linear-gradient(to right, rgba(var(--v-theme-on-surface), 0.28) 0 var(--last-save-position), rgb(var(--v-theme-warning)) var(--last-save-position) 100%) !important; }
</style>
