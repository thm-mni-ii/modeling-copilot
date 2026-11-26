<template>
  <section class="analysis-workspace" aria-label="Test run analysis">
    <div class="analysis-header d-flex flex-wrap align-center ga-3 px-3 py-2">
      <v-chip :color="stepColor(detail.state)" size="small" variant="tonal">{{ stepLabel(detail.state) }}</v-chip>
      <span class="text-caption text-medium-emphasis" role="status">{{ completedSteps }} / {{ detail.steps.length }} steps finished</span>
      <v-spacer />
      <v-select v-if="references.length > 1" v-model="referenceKey" :items="references" label="Sample solution" density="compact" hide-details class="reference-select" />
      <span v-else-if="references.length" class="text-caption text-medium-emphasis">{{ references[0]?.title }}</span>
    </div>
    <v-progress-linear v-if="!['succeeded', 'failed', 'cancelled'].includes(detail.state)" :model-value="100 * completedSteps / Math.max(detail.steps.length, 1)" aria-label="Workflow progress" />
    <v-alert v-if="modelError" type="warning" variant="tonal" density="compact" class="mx-3 mb-2">{{ modelError }}</v-alert>
    <div v-if="modelPackage" class="model-legend d-flex flex-wrap ga-3 px-3 pb-2" aria-label="Model marker legend">
      <span v-for="item in markerLegend" :key="item.label" class="text-caption"><v-icon :icon="item.icon" :color="item.color" size="16" class="mr-1" />{{ item.label }}</span>
    </div>
    <div ref="splitContainer" class="run-layout pa-3 pt-1" :class="{ 'run-layout--without-model': !modelPackage }" :style="{ '--model-width': `${modelWidth}%` }">
      <SubmissionReviewCanvas v-if="modelPackage" class="run-canvas" :package="modelPackage" :marks="emptyMarks" :selected-cell-id="selectedCellId" show-feedback hide-feedback-toggle aria-label="Evaluated submission. Select an element to inspect its findings." @select="selectCell" @graph-ready="reviewGraph = $event ?? undefined" />
      <div v-if="modelPackage" class="split-handle" role="separator" tabindex="0" aria-label="Resize model and analysis" aria-orientation="vertical" :aria-valuenow="Math.round(modelWidth)" :aria-valuemin="15" :aria-valuemax="70" @pointerdown="startResize" @pointermove="resizePanels" @pointerup="stopResize" @pointercancel="stopResize" @lostpointercapture="resizing = false" @keydown="resizeWithKeyboard"><v-icon icon="mdi-drag-vertical" size="small" /></div>
      <div class="run-details">
        <v-tabs v-model="tab" density="compact" class="analysis-tabs border-b" aria-label="Analysis section">
          <v-tab value="overview">Overview</v-tab>
          <v-tab value="findings">Findings</v-tab>
          <v-tab value="hints">Hinweise</v-tab>
          <v-tab value="feedback">Feedback</v-tab>
          <v-tab value="technical">Workflow</v-tab>
        </v-tabs>
        <div class="analysis-content px-3 pb-3">
          <AnalyticalFeedbackPanel ref="analysisPanel" v-model:reference-key="referenceKey" v-model:tab="tab" :detail="detail" overview-mode @feedback-object="selectCell" />
          <FeedbackCatalogPanel v-if="tab === 'feedback'" :detail="detail" :reference-key="referenceKey" :focus="catalogFocus" />
          <template v-if="tab === 'technical'">
            <p class="text-caption text-medium-emphasis my-3">Choose a step to inspect its result or error.</p>
            <v-expansion-panels v-model="expandedSteps" multiple variant="accordion">
              <v-expansion-panel v-for="(step, index) in detail.steps" :key="step.id" :value="step.id" elevation="0" class="workflow-step">
                <v-expansion-panel-title class="workflow-step-title">
                  <v-icon :color="stepColor(step.status)" :icon="step.status === 'failed' ? 'mdi-close-circle' : step.status === 'succeeded' ? 'mdi-check-circle' : step.status === 'running' ? 'mdi-progress-clock' : 'mdi-clock-outline'" size="18" class="mr-3" />
                  <div class="workflow-step-label">
                    <span class="text-body-2">{{ index + 1 }}. {{ step.label }}</span>
                    <span class="text-caption" :class="step.status === 'failed' ? 'text-error' : 'text-medium-emphasis'">{{ stepLabel(step.status) }}</span>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <p v-if="step.resultSummary && !step.result" class="text-caption step-summary mb-2">{{ step.resultSummary }}</p>
                  <JsonResultViewer v-if="step.result" :data="step.result">
                    <template #actions><SemanticComparisonViewer v-if="semanticComparisonResult(step.result)" :result="semanticComparisonResult(step.result)!" /></template>
                  </JsonResultViewer>
                  <p v-else-if="!step.resultSummary" class="text-caption text-medium-emphasis">{{ ['succeeded', 'failed', 'cancelled'].includes(step.status) ? 'No structured result was recorded for this step.' : 'The result will appear when this step finishes.' }}</p>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
            <p class="workflow-run-id text-caption text-medium-emphasis mt-3 mb-0">Run ID: {{ detail.dagRunId }}</p>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import type { Graph } from '@maxgraph/core'
import { provideGraphContext } from '@/composables/useGraphContext'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import type { LanguageVersionReference } from '@/services/api/types/common'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { ModelPackage, PackagedLanguage } from '@/utils/modelPackage'
import languageService from '@/services/language/language.service'
import SubmissionReviewCanvas, { type ReviewCanvasMark } from './SubmissionReviewCanvas.vue'
import AnalyticalFeedbackPanel from '@/components/modeling/sidebars/AnalyticalFeedbackPanel.vue'
import FeedbackCatalogPanel from '@/components/modeling/sidebars/FeedbackCatalogPanel.vue'
import JsonResultViewer from '@/components/modeling/sidebars/JsonResultViewer.vue'
import SemanticComparisonViewer from '@/components/modeling/sidebars/SemanticComparisonViewer.vue'
import { semanticComparisonResult } from '@/utils/semanticComparison'
import { analysisOverviewDisplay, recognizedWithLocalIssuesDisplay, studentQuestionDisplay, graphInfo } from '@/utils/analysisFeedback'

const props = defineProps<{ detail: EvaluationDetail }>()
const emptyMarks: ReviewCanvasMark[] = []
const markerLegend = [analysisOverviewDisplay.recognized, recognizedWithLocalIssuesDisplay, studentQuestionDisplay, { icon: 'mdi-information-outline', color: '#2196F3', label: 'Rückfrage ansehen' }, analysisOverviewDisplay.supported, analysisOverviewDisplay.unresolved, analysisOverviewDisplay.not_evaluated]
const reviewGraph = shallowRef<Graph>()
const analysisPanel = ref<InstanceType<typeof AnalyticalFeedbackPanel>>()
provideGraphContext({ graph: reviewGraph, isPanning: ref(false), gridSize: ref(10), snapToGrid: ref(false), tolerance: ref(0), useGridForPanning: ref(false) })
const modelWidth = defineModel<number>('modelWidth', { default: 35 })
const splitContainer = ref<HTMLDivElement>()
const resizing = ref(false)
const setModelWidth = (value: number) => { modelWidth.value = Math.min(70, Math.max(15, value)) }
const startResize = (event: PointerEvent) => {
  if (event.button !== 0) return
  event.preventDefault()
  resizing.value = true
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
const resizePanels = (event: PointerEvent) => {
  if (!resizing.value || !splitContainer.value) return
  const bounds = splitContainer.value.getBoundingClientRect()
  setModelWidth(100 * (event.clientX - bounds.left - 12) / (bounds.width - 24))
}
const stopResize = (event: PointerEvent) => {
  resizing.value = false
  const target = event.currentTarget as HTMLElement
  if (target.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId)
}
const resizeWithKeyboard = (event: KeyboardEvent) => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  setModelWidth(event.key === 'Home' ? 15 : event.key === 'End' ? 70 : modelWidth.value + (event.key === 'ArrowLeft' ? -2 : 2))
}
const tab = ref<'overview' | 'findings' | 'hints' | 'feedback' | 'technical'>(props.detail.state === 'succeeded' ? 'overview' : 'technical')
const referenceKey = ref('')
const selectedCellId = ref<string | null>(null)
const catalogFocus = ref<{ id: string; seq: number } | null>(null)
const modelPackage = ref<ModelPackage | null>(null)
const modelError = ref('')
const expandedSteps = ref<string[]>(props.detail.steps.filter(step => step.status === 'failed').map(step => step.id))
const stepLabel = (status: string) => ({ pending: 'Queued', queued: 'Queued', running: 'Running', succeeded: 'Completed', failed: 'Failed', cancelled: 'Cancelled', unknown: 'Status unknown' }[status] ?? status)
const stepColor = (status: string) => ({ running: 'info', succeeded: 'success', failed: 'error', cancelled: 'warning' }[status])
watch(() => props.detail.steps.filter(step => step.status === 'failed').map(step => step.id).join(','), (ids, previous) => {
  const known = new Set(previous?.split(',') ?? [])
  expandedSteps.value.push(...ids.split(',').filter(id => id && !known.has(id) && !expandedSteps.value.includes(id)))
})
const completedSteps = computed(() => props.detail.steps.filter(step => ['succeeded', 'failed', 'cancelled'].includes(step.status)).length)
const references = computed(() => props.detail.steps.filter(step => step.id.startsWith('generate_analytical_feedback_'))
  .map((step, index) => ({ title: `Solution ${index + 1}`, value: step.id.slice('generate_analytical_feedback_'.length) })))
watch(references, items => {
  if (!items.some(item => item.value === referenceKey.value)) referenceKey.value = items[0]?.value ?? ''
}, { immediate: true })
const selectCell = (id: string) => {
  if (graphInfo(props.detail, 'submission')?.nodes.get(id)?.kind === 'structuralElement') return
  selectedCellId.value = id
  if (tab.value === 'feedback') catalogFocus.value = { id, seq: (catalogFocus.value?.seq ?? 0) + 1 }
  else analysisPanel.value?.openSubmission(id)
}
watch(() => props.detail.submission.versionId, async (_, __, onCleanup) => {
  let active = true
  onCleanup(() => { active = false })
  modelPackage.value = null
  modelError.value = ''
  selectedCellId.value = null
  const snapshot = props.detail.submissionSnapshot
  const xml = (snapshot.data as { xml?: string } | undefined)?.xml
  if (!xml) { modelError.value = 'The saved submission has no model preview.'; return }
  const workspaceLanguages = snapshot.workspaceLanguages as unknown as LanguageVersionReference[] ?? []
  try {
    const languages = new Map<string, PackagedLanguage>()
    const pending = [...workspaceLanguages]
    while (pending.length) {
      const reference = pending.pop()!
      const key = `${reference.languageId}:${reference.versionId}`
      if (languages.has(key)) continue
      const { data: version } = await languageService.getVersion<DiagramLanguage>(reference.languageId, reference.versionId)
      if (!active) return
      const included = version.includedLanguageVersions ?? []
      languages.set(key, { ...reference, name: '', data: version.data, includedLanguageVersions: included })
      pending.push(...included)
    }
    if (active) modelPackage.value = { format: 'modeling-copilot-model', version: 1, model: { xml }, workspaceLanguages, languages: [...languages.values()] }
  } catch {
    if (active) modelError.value = 'The model preview could not be loaded. Run analysis remains available.'
  }
}, { immediate: true })
</script>

<style scoped>
.analysis-workspace { display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden; }
.analysis-header { flex-shrink: 0; }
.model-legend { flex-shrink: 0; }
.run-layout { display: grid; grid-template-columns: minmax(0, var(--model-width)) 12px minmax(0, 1fr); gap: 0; flex: 1; min-height: 0; }
.run-layout--without-model { grid-template-columns: minmax(0, 1fr); }
.split-handle { cursor: col-resize; touch-action: none; user-select: none; align-self: stretch; display: flex; align-items: center; justify-content: center; color: rgb(var(--v-theme-on-surface)); background: rgba(var(--v-theme-on-surface), 0.06); border-radius: 4px; }
.split-handle:hover, .split-handle:focus-visible { background: rgba(var(--v-theme-primary), 0.2); outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
.run-canvas { min-height: 0; height: 100%; }
.run-canvas :deep(.review-graph) { min-height: 0; }
.run-details { display: flex; flex-direction: column; min-width: 0; min-height: 0; overflow: hidden; border: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; }
.analysis-tabs { flex-shrink: 0; }
.analysis-content { flex: 1; min-height: 0; overflow: auto; }
.reference-select { flex: 0 1 190px; min-width: 150px; }
.workflow-step { border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.workflow-step-title { padding: 12px 8px; }
.workflow-step-label { display: flex; flex-direction: column; gap: 3px; min-width: 0; overflow-wrap: anywhere; }
.workflow-run-id { overflow-wrap: anywhere; }
.step-summary { white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 1200px) {
  .run-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(140px, 35%) minmax(0, 1fr); gap: 12px; }
  .run-layout--without-model { grid-template-rows: minmax(0, 1fr); }
  .split-handle { display: none; }
}
@media (max-width: 700px) {
  .analysis-workspace { overflow: auto; }
  .run-layout { display: flex; flex-direction: column; flex: 0 0 auto; }
  .run-canvas { flex: 0 0 260px; height: 260px; }
  .run-details { flex: 0 0 auto; min-height: 360px; overflow: visible; }
  .analysis-content { flex: 0 0 auto; overflow: visible; }
}
</style>
