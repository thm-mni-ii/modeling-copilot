<template>
  <v-dialog :model-value="modelValue" max-width="1000" persistent @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="d-flex align-center">
        Version timeline
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" :disabled="busy" aria-label="Close version timeline" @click="close" />
      </v-card-title>
      <v-progress-linear v-if="loading" indeterminate />
      <v-card-text>
        <v-checkbox v-if="workspace.taskVersion" v-model="includeTaskEdits" label="Include task edit history" hide-details />
        <v-expansion-panels v-if="timelineTaskEditSnapshot && workspace.taskVersion" class="mt-3" variant="accordion">
          <v-expansion-panel title="Edits in this model state">
            <v-expansion-panel-text><TaskEditEditor :base-html="workspace.taskVersion.data.contentHtml" :base-document="workspace.taskVersion.data.contentDocument" :model-value="timelineTaskEditSnapshot.document" mode="read" class="timeline-task-edits" /></v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <ModelSnapshotPreview :data="timelineData" :height="520" />
        <div v-if="timelineSteps.length > 1" class="timeline-slider-wrap">
          <v-slider v-model="timelineStep" :min="0" :max="timelineSteps.length - 1" :step="1" :ticks="timelineTicks" show-ticks="always" :tick-size="8" :color="timelineIsUnsaved ? 'warning' : 'primary'" :track-fill-color="timelineIsUnsaved ? 'warning' : 'primary'" :class="['timeline-slider', 'mt-7', { 'timeline-slider--has-unsaved': hasUnsavedTimeline }]" :style="timelineSliderStyle" />
        </div>
        <div class="d-flex align-center ga-2 mt-2">
          <v-chip v-if="timelineIsUnsaved" color="warning" size="x-small" variant="tonal">Unsaved</v-chip>
          <p class="text-caption text-medium-emphasis mb-0">{{ timelineLabel }}</p>
        </div>
        <p v-if="hasUnsavedTimeline" class="text-caption text-warning mt-2 mb-0">The orange area contains local changes after “Last save”.</p>
      </v-card-text>
      <v-card-actions>
        <v-btn :disabled="!previewReady || busy" :loading="restoring" prepend-icon="mdi-history" @click="restoreSelected">Restore as checkpoint</v-btn>
        <v-btn :disabled="!previewReady || busy" :loading="branching" prepend-icon="mdi-source-branch" @click="openBranch">Branch from here</v-btn>
        <v-spacer />
        <v-btn :disabled="busy" @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="branchDialog" max-width="520" persistent>
    <v-card>
      <v-card-title>Branch from timeline position</v-card-title>
      <v-card-text>
        <v-text-field v-model="branchName" label="New model name" maxlength="256" counter autofocus @keyup.enter="createBranch" />
        <p class="text-caption text-medium-emphasis mb-0">The selected state becomes the initial release of a new model.</p>
        <v-checkbox v-if="timelineTaskEditSnapshot" v-model="branchEdits" label="Use task edits from the selected position" hide-details />
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
import { computed, ref, watch } from 'vue'
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
import TaskEditEditor from '@/components/tasks/TaskEditEditor.vue'
import { buildTaskEditTimeline, loadTaskEditHistory } from '@/utils/taskEditTimeline'
import { notifyError } from '@/composables/useNotifications'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const workspace = useModelWorkspaceStore()
const { graph } = useGraphContext()
const router = useRouter()

const history = ref<ModelVersionInfo[]>([])
const timelineStep = ref(0)
const timelineData = ref<JsonObject | null>(null)
const materializedStepIndex = ref(-1)
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
    saved: step.kind === 'release' || step.saved
  }))
  if (!includeTaskEdits.value) return positions
  for (const taskStep of buildTaskEditTimeline(taskHistory.value, workspace.pendingTaskEditPatches, workspace.model?.taskEdit?.document ?? workspace.taskVersion?.data.contentDocument)) {
    let modelIndex = 0
    for (let index = 0; index < modelSteps.value.length; index++) {
      const step = modelSteps.value[index]
      const date = step.kind === 'release' ? step.createdAt : step.patch.createdAt
      if (date <= taskStep.createdAt) modelIndex = index
    }
    positions.push({ id: taskStep.id, modelIndex, taskStep, createdAt: taskStep.createdAt, saved: taskStep.saved })
  }
  return positions.sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id.localeCompare(b.id))
})
const lastSavedIndex = computed(() => {
  for (let index = timelineSteps.value.length - 1; index >= 0; index--) if (timelineSteps.value[index].saved) return index
  return -1
})
const timelineTicks = computed(() => Object.fromEntries(timelineSteps.value.flatMap((position, index) => {
  const step = modelSteps.value[position.modelIndex]
  const label = !position.taskStep && step?.kind === 'release' ? `Release v${step.versionNumber}` : ''
  return label || index === lastSavedIndex.value ? [[index, [label, index === lastSavedIndex.value ? 'Last save' : ''].filter(Boolean).join(' ? ')]] : []
})))
const selectedPosition = computed(() => timelineSteps.value[timelineStep.value] ?? null)
const selectedStep = computed(() => modelSteps.value[selectedPosition.value?.modelIndex ?? -1] ?? null)
const hasUnsavedTimeline = computed(() => timelineSteps.value.some((step) => !step.saved))
const timelineIsUnsaved = computed(() => selectedPosition.value ? !selectedPosition.value.saved : false)
const busy = computed(() => loading.value || restoring.value || branching.value)
const previewReady = computed(() => Boolean(timelineData.value) && materializedStepIndex.value === timelineStep.value)
const timelineSliderStyle = computed<Record<string, string>>(() => {
  const maximum = timelineSteps.value.length - 1
  const percentage = maximum > 0 ? (lastSavedIndex.value / maximum) * 100 : 100
  return { '--last-save-position': `${Math.max(0, percentage)}%` }
})
const timelineLabel = computed(() => {
  const taskStep = selectedPosition.value?.taskStep
  if (taskStep) return `${taskStep.saved ? 'Saved' : 'Local'} task edit - ${new Date(taskStep.createdAt).toLocaleString()} - ${taskStep.label}`
  const step = selectedStep.value
  if (!step) return 'No version history is available.'
  if (step.kind === 'release') {
    const name = step.releaseName ? `${step.releaseName} · ` : ''
    return `${name}Release v${step.versionNumber} · ${new Date(step.createdAt).toLocaleString('en-GB')}`
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
  materializedStepIndex.value = -1
  selectedTaskSnapshot.value = null
  const step = selectedStep.value
  if (!step) {
    timelineData.value = null
    return
  }
  try {
    const base = await getReleaseData(step.releaseId)
    if (request !== timelineRequest || typeof base.xml !== 'string') return
    timelineData.value = { ...base, xml: applyModelPatches(base.xml, patchesForTimelineStep(modelSteps.value, selectedPosition.value?.modelIndex ?? 0)) }
    const versionId = step.kind === 'release' ? step.releaseId : step.checkpointId
    if (versionId && workspace.model) {
      let version = versionCache.get(versionId)
      if (!version) {
        version = (await modelService.getVersion(workspace.model, versionId)).data
        versionCache.set(versionId, version)
      }
      if (request !== timelineRequest) return
      timelineVersion.value = version
    } else timelineVersion.value = null
    const taskStep = selectedPosition.value?.taskStep
    let taskSnapshot = taskStep?.patch ? { schemaVersion: 1 as const, revision: workspace.taskEdit?.revision ?? 0, updatedAt: taskStep.createdAt, document: taskStep.patch.document }
      : taskStep && workspace.model ? (await modelService.getTaskEditVersion(workspace.model.id, taskStep.id)).data
      : timelineIsUnsaved.value ? workspace.taskEdit : timelineVersion.value?.taskEditSnapshot ?? null
    if (request !== timelineRequest) return
    if (!taskSnapshot && workspace.taskVersion?.data.contentDocument) taskSnapshot = { schemaVersion: 1, revision: 0, updatedAt: workspace.taskVersion.createdAt, document: workspace.taskVersion.data.contentDocument }
    selectedTaskSnapshot.value = taskSnapshot
    materializedStepIndex.value = timelineStep.value
  } catch {
    if (request === timelineRequest) notifyError('Unable to load this timeline position.')
  }
}

const openTimeline = async () => {
  loading.value = true
  releaseDataCache.clear()
  history.value = []
  timelineData.value = null
  materializedStepIndex.value = -1
  try {
    await loadHistory()
    taskHistory.value = workspace.model && workspace.taskVersion ? await loadTaskEditHistory(workspace.model.id) : []
    timelineStep.value = Math.max(0, timelineSteps.value.length - 1)
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
  if (!step || !previewReady.value || !timelineData.value || !graph.value) return
  restoring.value = true
  try {
    await workspace.restoreSnapshot(timelineData.value, step.workspaceLanguages)
    if (restoreEdits.value && timelineTaskEditSnapshot.value) await workspace.adoptTaskEditSnapshot(timelineTaskEditSnapshot.value)
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
  if (!step || !previewReady.value || !timelineData.value || !branchName.value.trim()) return
  branching.value = true
  try {
    await workspace.branchSnapshot(timelineData.value, step.workspaceLanguages, branchName.value.trim(), timelineVersion.value?.taskVersion ?? workspace.taskReference, branchEdits.value ? timelineTaskEditSnapshot.value : workspace.taskEdit)
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
      branchDialog.value = false
      restoreDialog.value = false
    }
  }
)
watch(timelineStep, () => void updatePreview())
watch(includeTaskEdits, () => { timelineStep.value = Math.max(0, timelineSteps.value.length - 1); void updatePreview() })
</script>

<style scoped>
.timeline-slider-wrap {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  overflow: hidden;
  padding: 0 clamp(40px, 6vw, 64px) 24px;
}
.timeline-slider {
  width: 100%;
  min-width: 0;
}
.timeline-slider :deep(.v-slider-track__tick) {
  border: 2px solid rgb(var(--v-theme-primary));
  background: rgb(var(--v-theme-surface));
}
.timeline-slider :deep(.v-slider-track__tick-label) {
  color: rgb(var(--v-theme-primary));
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.timeline-slider--has-unsaved :deep(.v-slider-track__background) {
  opacity: 0.38;
  background: linear-gradient(to right, rgba(var(--v-theme-on-surface), 0.28) 0 var(--last-save-position), rgb(var(--v-theme-warning)) var(--last-save-position) 100%) !important;
}
</style>
