<template>
  <div class="glossary-page">
    <header class="glossary-toolbar d-flex flex-wrap align-center ga-2 pa-2 border-b">
      <h1 class="text-h6 mr-2">Synonym glossary</h1>
      <v-select v-model="taskId" :items="tasks" item-title="name" item-value="id" label="Task" density="compact" hide-details class="header-select" />
      <v-select v-model="releaseId" :items="releaseItems" label="Release" density="compact" hide-details class="header-select-small" :disabled="!task" />
      <v-select v-model="solutionIndex" :items="solutionItems" label="Sample solution" density="compact" hide-details class="header-select-solution" :disabled="!solutions.length" />
      <v-select v-if="view && outcomeSources.length > 1 && excludeStaff" v-model="outcomeSource" :items="outcomeSources" label="Results" density="compact" hide-details class="header-select-solution" />
      <v-spacer />
      <template v-if="view">
        <span class="text-caption" role="status">{{ view.signals.evaluated }} submissions<span v-if="view.signals.missing"> · {{ view.signals.missing }} missing</span></span>
        <v-btn class="toolbar-action" size="small" variant="tonal" :disabled="!view.signals.missing || jobRunning" :loading="starting" @click="recalculate('missing')"><span>Calculate<br>missing</span></v-btn>
        <v-btn class="toolbar-action" size="small" variant="tonal" :disabled="!view.signals.evaluated" @click="replayOpen = true"><span>Compare full<br>evaluations</span></v-btn>
        <v-menu>
          <template #activator="{ props: menu }"><v-btn v-bind="menu" size="small" variant="text" icon="mdi-dots-vertical" aria-label="More glossary actions" /></template>
          <v-list density="compact">
            <v-list-item :disabled="jobRunning || !view.signals.evaluated" title="Recalculate all signals" @click="confirmAll = true" />
            <v-list-item :disabled="!importSources.length" title="Import from another release" @click="openImport" />
          </v-list>
        </v-menu>
      </template>
    </header>

    <v-alert v-if="!loading && !tasks.length" type="info" variant="tonal" class="ma-3">No evaluable tasks. A task needs a release with a sample solution.</v-alert>
    <template v-else>
      <div v-if="error || view?.signals.unavailable || job?.state === 'running' || job?.failed" class="px-3 pt-2 d-flex flex-column ga-2">
        <v-alert v-if="error" type="error" variant="tonal" density="compact" closable @click:close="error = ''">{{ error }}</v-alert>
        <v-alert v-if="view?.signals.unavailable" type="warning" variant="tonal" density="compact">The workflow service is unavailable. Saved glossary entries stay editable, suggestions may be out of date.</v-alert>
        <div v-if="job?.state === 'running'" role="status">
          <div class="text-caption">Calculating signals: {{ job.done + job.failed }} of {{ job.total }}. This continues while the view is open.</div>
          <v-progress-linear :model-value="100 * (job.done + job.failed) / Math.max(job.total, 1)" color="primary" />
        </div>
        <v-alert v-else-if="job?.failed" type="warning" variant="tonal" density="compact">{{ job.failed }} of {{ job.total }} submissions could not be calculated. They stay missing until you calculate them again.</v-alert>
      </div>
      <v-progress-linear v-if="loading" indeterminate />
      <div ref="splitContainer" class="glossary-layout pa-3" :style="{ '--model-width': `${modelWidth}%` }">
        <SubmissionReviewCanvas
          v-if="modelPackage" ref="canvas" class="glossary-canvas" :package="modelPackage" :marks="marks" :selected-cell-id="selectedId"
          show-feedback hide-feedback-toggle hide-view-controls aria-label="Read-only sample solution" @select="selectCell" @overlay="(_keys, cellId) => selectCell(cellId)"
        />
        <div v-if="modelPackage && view" class="split-handle" role="separator" tabindex="0" aria-label="Resize model and glossary" aria-orientation="vertical" :aria-valuenow="Math.round(modelWidth)" :aria-valuemin="15" :aria-valuemax="70" @pointerdown="startResize" @pointermove="resizePanels" @pointerup="stopResize" @pointercancel="stopResize" @lostpointercapture="resizing = false" @keydown="resizeWithKeyboard"><v-icon icon="mdi-drag-vertical" size="small" /></div>
        <aside v-if="view" class="glossary-panel" aria-label="Synonyms">
          <div class="d-flex align-center flex-wrap ga-2 px-3 py-2 border-b">
            <v-icon icon="mdi-source-branch" size="small" />
            <span class="text-body-2">{{ matchingSources.length }} additional sources</span>
            <span class="workload-indicator text-caption" :style="workloadStyle">{{ workloadLabel }}</span>
            <v-tooltip :text="workloadNote"><template #activator="{ props: tip }"><v-icon v-bind="tip" icon="mdi-information-outline" size="small" aria-label="How comparison effort is estimated" /></template></v-tooltip>
            <v-btn size="x-small" variant="text" @click="tab = 'sources'">Manage sources</v-btn>
          </div>
          <v-tabs v-model="tab" density="compact">
            <v-tab value="selected">Selected element</v-tab>
            <v-tab value="all">Review terms ({{ reviewTerms.length }})</v-tab>
            <v-tab value="results">Evaluation results ({{ activeOutcomes.length }})</v-tab>
            <v-tab value="sources">Matching sources ({{ matchingSources.length }})</v-tab>
          </v-tabs>
          <v-divider />
          <v-window v-model="tab" class="panel-body">
            <v-window-item value="selected" class="pa-3">
              <p v-if="!selectedId" class="text-body-2 text-medium-emphasis">Select an element or connection in the model.</p>
              <v-alert v-else-if="!selectedElement" type="info" variant="tonal" density="compact">This item is not compared, so it has no synonyms.</v-alert>
              <template v-else>
                <div class="text-subtitle-2">{{ selectedPath || selectedElement.label }}</div>
                <div class="text-caption text-medium-emphasis mb-3">{{ selectedElement.targetKind }} · {{ selectedElement.type }}</div>
                <v-form class="d-flex flex-wrap align-start ga-2 mb-3" @submit.prevent="addTerm('accepted')">
                  <v-text-field v-model="newTerm" label="Add synonym" density="compact" maxlength="256" hide-details="auto" :error-messages="newTermError" class="flex-grow-1 term-field" />
                  <v-btn color="primary" type="submit" :disabled="!newTerm.trim() || saving">Accept</v-btn>
                  <v-btn variant="tonal" :disabled="!newTerm.trim() || saving" @click="addTerm('rejected')">Reject</v-btn>
                </v-form>
                <v-data-table :headers="headers" :items="rows" item-value="key" :items-per-page="-1" hide-default-footer disable-sort density="compact">
                  <template #item="{ item }">
                    <tr v-if="item.header" class="section-row">
                      <td :colspan="headers.length">
                        <v-btn v-if="item.section === 'ignored'" variant="text" size="small" :prepend-icon="showIgnored ? 'mdi-chevron-down' : 'mdi-chevron-right'" :aria-expanded="showIgnored" @click="showIgnored = !showIgnored">Ignored ({{ item.count }})</v-btn>
                        <strong v-else class="text-body-2">{{ item.title }} ({{ item.count }})</strong>
                      </td>
                    </tr>
                    <tr v-else>
                      <td>
                        <div>{{ item.term }}</div>
                        <v-chip v-if="item.entry?.matchingSource" size="x-small" prepend-icon="mdi-source-branch" variant="tonal">Matching source</v-chip>
                        <div v-if="item.suggestion && item.suggestion.variants.length > 1" class="text-caption text-medium-emphasis">Variants: {{ item.suggestion.variants.map((variant) => `${variant.text} (${variant.count})`).join(', ') }}</div>
                        <div v-if="item.suggestion" class="text-caption text-medium-emphasis">{{ item.suggestion.submissions }} {{ item.suggestion.submissions === 1 ? 'case' : 'cases' }}</div>
                      </td>
                      <td class="reason-cell"><GlossaryConditionGroups :comparisons="item.suggestion?.comparisons ?? comparisonsOf(item.entry)" :outcome="outcomeOf(item.suggestion ?? item.entry)" /></td>
                      <td><GlossaryDecisionActions :status="item.entry?.status" :matching-source="item.entry?.matchingSource" :disabled="saving" @decide="item.suggestion ? decide(item.suggestion, $event) : change(item.entry!, $event)" @source="setMatchingSource(item.entry!, !item.entry!.matchingSource)" @remove="change(item.entry!, null)" /></td>
                    </tr>
                  </template>
                  <template #no-data>No synonyms yet.</template>
                </v-data-table>
              </template>
            </v-window-item>

            <v-window-item value="all" class="pa-3">
              <div class="d-flex flex-wrap ga-2 mb-3">
                <v-text-field v-model.number="minPersons" type="number" min="0" label="Min Case" density="compact" hide-details class="filter-field" />
                <v-checkbox v-model="excludeStaff" label="Exclude moderator/admin submissions" density="compact" hide-details />
                <v-select v-model="typeFilter" :items="typeItems" label="Element type" density="compact" hide-details clearable class="filter-field-wide" />
              </div>
              <v-data-table v-model:sort-by="termSort" :headers="allHeaders" :items="filteredSuggestions" :item-value="suggestionKey" :items-per-page="25" density="compact">
                <template #item="{ item }">
                  <tr :class="{ 'selected-row': item.referenceElementId === selectedId }">
                    <td><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId)">{{ elementsById.get(item.referenceElementId)?.label }}</v-btn></td>
                    <td>{{ item.term }}<v-chip v-if="item.evidence?.hintAccepted" size="x-small" color="info" variant="tonal" label class="ms-1" title="Learners accepted this term from a hint; it still needs your decision.">accepted from hint ×{{ item.evidence.hintAccepted }}</v-chip></td><td>{{ item.submissions }} {{ item.submissions === 1 ? 'case' : 'cases' }}</td>
                    <td class="reason-cell"><GlossaryConditionGroups :comparisons="item.comparisons" :outcome="outcomeOf(item)" /></td>
                    <td><GlossaryDecisionActions :status="findEntry(item)?.status" :matching-source="findEntry(item)?.matchingSource" :disabled="saving" @decide="decide(item, $event)" @source="toggleSource(item)" @remove="removeTerm(item)" /></td>
                  </tr>
                </template>
                <template #no-data>{{ view.signals.collected ? 'No open suggestions.' : 'No suggestions yet. Calculate missing signals to analyze earlier submissions.' }}</template>
              </v-data-table>
            </v-window-item>
            <v-window-item value="results" class="pa-3">
              <p class="text-caption text-medium-emphasis mb-3">All recorded terms, including counted matches. Decisions apply to future evaluations.</p>
              <v-data-table :headers="outcomeHeaders" :items="activeOutcomes" :item-value="suggestionKey" :items-per-page="25" density="compact">
                <template #[`item.element`]="{ item }"><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId)">{{ elementsById.get(item.referenceElementId)?.label ?? item.referenceElementId }}</v-btn></template>
                <template #[`item.similarity`]="{ item }"><GlossaryConditionGroups :comparisons="item.comparisons" :outcome="item" /></template>
                <template #[`item.actions`]="{ item }"><GlossaryDecisionActions :status="entryOf(item)?.status" :matching-source="entryOf(item)?.matchingSource" :disabled="saving" @decide="decideTerm(item, $event)" @source="toggleSource(item)" @remove="removeTerm(item)" /></template>
                <template #no-data>No verified final results for these terms yet.</template>
              </v-data-table>
            </v-window-item>
            <v-window-item value="sources" class="pa-3">
              <p class="text-caption text-medium-emphasis mb-3">Enabled terms are compared alongside the original element names in future evaluations.</p>
              <v-data-table :headers="sourceHeaders" :items="matchingSources" item-value="id" :items-per-page="10" density="compact">
                <template #[`item.element`]="{ item }"><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId); tab = 'selected'">{{ elementsById.get(item.referenceElementId)?.label ?? item.referenceElementId }}</v-btn></template>
                <template #[`item.actions`]="{ item }"><v-btn size="small" variant="text" :disabled="saving" @click="setMatchingSource(item, false)">Disable source</v-btn></template>
                <template #no-data>No extra matching sources enabled. Select an accepted synonym to enable one explicitly.</template>
              </v-data-table>
            </v-window-item>
          </v-window>
        </aside>
      </div>
    </template>

    <v-dialog v-model="replayOpen" max-width="1050" scrollable>
      <v-card title="Compare full evaluations">
        <v-card-text>
          <p class="text-body-2 mb-3">Runs parsing, synonym matching, graph matching, analysis and final learner feedback again for every evaluated submission version in this release, using current workflow services and the glossary frozen at comparison start. Original learner results stay unchanged.</p>
          <p class="text-caption mb-3">Comparisons expire after 7 days. At most 3 are kept per release; starting another removes the oldest completed comparison. Workspace files are removed after each run; workflow logs and artifacts expire after 7 days. New runs start while this view is open.</p>
          <v-alert v-if="replayError" type="error" variant="tonal" density="compact" class="mb-3">{{ replayError }}</v-alert>
          <div class="d-flex flex-wrap align-center ga-3 mb-3">
            <v-switch v-model="customThresholds" label="Custom similarity thresholds" density="compact" hide-details :disabled="replayRunning" />
            <v-btn color="primary" :loading="replayStarting" :disabled="replayRunning || !thresholdsValid" @click="startReplay">Start full comparison ({{ view?.signals.evaluated }})</v-btn>
          </div>
          <div v-if="customThresholds" class="d-flex flex-wrap ga-3 mb-3">
            <v-text-field v-model.number="thresholds.spelling" type="number" min="0" max="1" step="0.01" label="Spelling threshold (0–1)" density="compact" hide-details :disabled="replayRunning" />
            <v-text-field v-model.number="thresholds.meaning" type="number" min="0" max="1" step="0.01" label="Meaning threshold (0–1)" density="compact" hide-details :disabled="replayRunning" />
            <v-text-field v-model.number="thresholds.meaningFloor" type="number" min="0" max="1" step="0.01" label="Meaning floor (≤ meaning)" density="compact" hide-details :disabled="replayRunning" />
          </div>
          <v-select v-model="replayId" :items="replayOptions" label="Saved comparison" density="compact" hide-details class="mb-3" />
          <template v-if="selectedReplay">
            <div class="d-flex flex-wrap align-center ga-3 mb-3">
              <span class="text-caption">{{ selectedReplay.workflowName }} {{ selectedReplay.workflowVersion }} · Expires {{ formatDate(selectedReplay.expiresAt) }} · {{ selectedReplay.items.filter(item => item.status === 'done').length }} done, {{ selectedReplay.items.filter(item => item.status === 'failed').length }} failed of {{ selectedReplay.items.length }}</span>
              <v-btn size="small" variant="text" @click="outcomeSource = selectedReplay.id; tab = 'results'; replayOpen = false">Show term results</v-btn>
              <v-btn size="small" variant="text" color="error" :disabled="selectedReplay.state === 'running'" @click="deleteReplayId = selectedReplay.id">Delete comparison</v-btn>
            </div>
            <div class="text-caption mb-3">Thresholds: {{ selectedReplay.textEvidence ? `spelling ${selectedReplay.textEvidence.spelling}, meaning ${selectedReplay.textEvidence.meaning}, floor ${selectedReplay.textEvidence.meaningFloor}` : 'workflow defaults' }}. Percentages show the best recognition across all sample solutions.</div>
            <v-alert v-if="selectedReplay.unavailable" type="warning" variant="tonal" density="compact">The workflow service is unavailable. The comparison resumes when the service can be reached.</v-alert>
            <v-progress-linear v-if="selectedReplay.state === 'running'" :model-value="100 * selectedReplay.items.filter(item => ['done', 'failed'].includes(item.status)).length / Math.max(selectedReplay.items.length, 1)" class="mb-3" />
            <v-data-table :headers="replayHeaders" :items="selectedReplay.items" item-value="runId" :items-per-page="10" density="compact">
              <template #[`item.modelVersionId`]="{ item }"><span :title="item.modelVersionId">{{ item.modelVersionId.slice(0, 8) }}</span></template>
              <template #[`item.beforePercent`]="{ item }">{{ percentText(item.beforePercent) }}</template>
              <template #[`item.afterPercent`]="{ item }">{{ percentText(item.afterPercent) }}</template>
              <template #[`item.delta`]="{ item }">{{ item.beforePercent != null && item.afterPercent != null ? `${item.afterPercent - item.beforePercent > 0 ? '+' : ''}${(item.afterPercent - item.beforePercent).toFixed(1)} pp` : '—' }}</template>
            </v-data-table>
          </template>
          <p v-else class="text-body-2">No comparisons saved for this release yet.</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="replayOpen = false">Close</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog :model-value="!!deleteReplayId" max-width="460" @update:model-value="!$event && (deleteReplayId = null)">
      <v-card title="Delete comparison?">
        <v-card-text>The saved comparison and its term results will be removed. Original evaluations and glossary decisions stay unchanged.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="deleteReplayId = null">Cancel</v-btn><v-btn color="error" :loading="replayDeleting" @click="deleteReplay">Delete</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="confirmAll" max-width="480">
      <v-card title="Recalculate all signals?">
        <v-card-text>All {{ view?.signals.evaluated }} evaluated submissions are processed again from their frozen snapshots. Results and learner feedback do not change.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="confirmAll = false">Cancel</v-btn><v-btn color="primary" @click="confirmAll = false; recalculate('all')">Recalculate all</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog :model-value="!!applying" max-width="520" @update:model-value="!$event && !saving && (applying = null)">
      <v-card v-if="applying" :title="`Accept ${applying.term}`">
        <v-card-text>
          <p class="text-caption">Same name, multiple positions:</p>
          <v-checkbox v-for="element in acceptanceTargets" :key="element.id" v-model="acceptanceSelection" :value="element.id" :label="canvas?.pathOf(element.id) || element.label" :disabled="saving" density="compact" hide-details />
        </v-card-text>
        <v-card-actions><v-btn :disabled="saving" @click="applying = null">Cancel</v-btn><v-spacer /><v-btn :disabled="saving" @click="applySameNamed(true)">Accept all</v-btn><v-btn color="primary" :loading="saving" :disabled="!acceptanceSelection.length || saving" @click="applySameNamed(false)">Accept selected</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="importOpen" max-width="480">
      <v-card title="Import decisions">
        <v-card-text>
          <v-select v-model="importFrom" :items="importSources" label="From release" density="compact" />
          <p class="text-body-2">Only entries whose element and label are unchanged are imported. The rest is listed afterwards.</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="importOpen = false">Cancel</v-btn><v-btn color="primary" :disabled="!importFrom" @click="runImport">Import</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbar" :timeout="8000">
      {{ snackbarText }}
      <template #actions><v-btn v-if="undoChanges" variant="text" @click="undo">Undo</v-btn></template>
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SubmissionReviewCanvas, { type ReviewCanvasMark } from '@/components/submissions/SubmissionReviewCanvas.vue'
import GlossaryConditionGroups from '@/components/submissions/GlossaryConditionGroups.vue'
import GlossaryDecisionActions from '@/components/submissions/GlossaryDecisionActions.vue'
import languageService from '@/services/language/language.service'
import taskService from '@/services/task/task.service'
import { synonymGlossary, type EntryStatus, type EvaluableTask, type GlossaryChange, type GlossaryElement, type GlossaryEntry, type GlossaryView, type RecalculateScope, type SolutionRef, type Suggestion, type ReplayBatch, type TermOutcome, type TextEvidence } from '@/services/synonymGlossary'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { LanguageVersionReference } from '@/services/api/types/common'
import type { ModelPackage, PackagedLanguage } from '@/utils/modelPackage'

type Section = 'suggested' | 'accepted' | 'rejected' | 'ignored'
interface Row { key: string; header?: boolean; section: Section; title?: string; count?: number; term?: string; status?: string; origin?: string; suggestion?: Suggestion; entry?: GlossaryEntry }

const statuses: EntryStatus[] = ['accepted', 'rejected', 'ignored']
const headers = [{ title: 'Term', key: 'term' }, { title: 'Evidence', key: 'evidence', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const allHeaders = [{ title: 'Element', key: 'element', value: (item: { referenceElementId?: string }) => elementsById.value.get(item.referenceElementId ?? '')?.label ?? '' }, { title: 'Term', key: 'term' }, { title: 'Cases', key: 'submissions' }, { title: 'Evidence', key: 'evidence', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const outcomeHeaders = [{ title: 'Element', key: 'element', value: (item: { referenceElementId?: string }) => elementsById.value.get(item.referenceElementId ?? '')?.label ?? '' }, { title: 'Term', key: 'term' }, { title: 'Evidence', key: 'similarity', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const sourceHeaders = [{ title: 'Reference element', key: 'element', sortable: false }, { title: 'Additional source', key: 'term' }, { title: 'Actions', key: 'actions', sortable: false }]
const replayHeaders = [{ title: 'Submission version', key: 'modelVersionId' }, { title: 'Status', key: 'status' }, { title: 'Original', key: 'beforePercent' }, { title: 'Comparison', key: 'afterPercent' }, { title: 'Change', key: 'delta', sortable: false }, { title: 'Details', key: 'error', sortable: false }]
const markImage = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#f9a825" stroke="white" stroke-width="1.5"/></svg>')}`

const route = useRoute()
const router = useRouter()
const canvas = ref<InstanceType<typeof SubmissionReviewCanvas>>()
const splitContainer = ref<HTMLDivElement>()
const modelWidth = ref(35)
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
const tasks = ref<EvaluableTask[]>([])
const taskId = ref<string | null>(null)
const releaseId = ref<string | null>(null)
const solutionIndex = ref(0)
const view = ref<GlossaryView | null>(null)
const modelPackage = ref<ModelPackage | null>(null)
const selectedId = ref<string | null>(null)
const selectedPath = ref('')
const tab = ref('all')
const newTerm = ref('')
const newTermError = ref('')
const showIgnored = ref(false)
const minPersons = ref(0)
const termSort = ref<{ key: string; order?: boolean | 'asc' | 'desc' }[]>([{ key: 'submissions', order: 'desc' }])
const excludeStaff = ref(true)
const typeFilter = ref<string | null>(null)
const loading = ref(false)
const saving = ref(false)
const starting = ref(false)
const error = ref('')
const snackbar = ref(false)
const snackbarText = ref('')
const undoChanges = ref<GlossaryChange[] | null>(null)
const confirmAll = ref(false)
const applying = ref<Suggestion | null>(null)
const acceptanceSelection = ref<string[]>([])
const acceptanceTargets = computed(() => applying.value ? [elementsById.value.get(applying.value.referenceElementId)!, ...sameNamed(applying.value)].filter(Boolean) : [])
const importOpen = ref(false)
const importFrom = ref<string | null>(null)
const replays = ref<ReplayBatch[]>([])
const replayId = ref<string | null>(null)
const replayOpen = ref(false)
const replayStarting = ref(false)
const replayDeleting = ref(false)
const replayError = ref('')
const deleteReplayId = ref<string | null>(null)
const outcomeSource = ref('original')
const customThresholds = ref(false)
const thresholds = ref<TextEvidence>({ spelling: 0.85, meaning: 0.85, meaningFloor: 0.7 })
let pollTimer: ReturnType<typeof setTimeout> | undefined
let loadToken = 0

const task = computed(() => tasks.value.find((item) => item.id === taskId.value) ?? null)
const release = computed(() => task.value?.releases.find((item) => item.id === releaseId.value) ?? null)
const releaseItems = computed(() => task.value?.releases.map((item) => ({ title: `Release ${item.versionNumber}`, value: item.id })) ?? [])
const solutions = computed(() => release.value?.sampleSolutions ?? [])
const solutionItems = computed(() => solutions.value.map((_solution, index) => ({ title: `Solution ${index + 1}`, value: index })))
const solutionRef = computed<SolutionRef | null>(() => {
  const solution = solutions.value[solutionIndex.value]
  return solution && taskId.value && releaseId.value ? { taskId: taskId.value, versionId: releaseId.value, modelId: solution.modelId, modelVersionId: solution.versionId } : null
})
const job = computed(() => view.value?.signals.job ?? null)
const jobRunning = computed(() => job.value?.state === 'running')
const replayRunning = computed(() => replays.value.some(item => item.state === 'running'))
const selectedReplay = computed(() => replays.value.find(item => item.id === replayId.value) ?? null)
const formatDate = (date: string) => new Date(date).toLocaleString()
const replayOptions = computed(() => replays.value.map(item => ({ title: `${formatDate(item.createdAt)} · ${item.workflowVersion ?? ''} · ${item.state}`, value: item.id })))
const outcomeSources = computed(() => [{ title: 'Original learner results', value: 'original' }, ...replayOptions.value.map(item => ({ ...item, title: `Comparison ${item.title}` }))])
const activeOutcomes = computed(() => outcomeSource.value === 'original' ? view.value?.outcomes ?? [] : replays.value.find(item => item.id === outcomeSource.value)?.outcomes ?? [])
const outcomeOf = (item?: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => item ? activeOutcomes.value.find(outcome => outcome.referenceElementId === item.referenceElementId && outcome.termKey === item.termKey) : undefined
const thresholdsValid = computed(() => !customThresholds.value || (Object.values(thresholds.value).every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1) && thresholds.value.meaningFloor <= thresholds.value.meaning))
const percentText = (value: number | null) => value == null ? 'Unknown' : `${value.toFixed(1)}%`
const elementsById = computed(() => new Map((view.value?.elements ?? []).map((element) => [element.id, element])))
const selectedElement = computed(() => (selectedId.value ? elementsById.value.get(selectedId.value) ?? null : null))
const matchingSources = computed(() => (view.value?.entries ?? []).filter(item => item.status === 'accepted' && item.matchingSource))
const workloadLabel = computed(() => {
  const work = view.value?.matchingWorkload
  if (!work) return 'Effort estimate unavailable'
  const unit = work.basis === 'text_pairs' ? 'comparisons' : 'reference texts'
  const percent = work.percent == null ? '' : ` (+${work.percent.toLocaleString(undefined, { maximumFractionDigits: 1 })}%)`
  return `${work.baseline.toLocaleString()} + ${work.additional.toLocaleString()} = ${work.total.toLocaleString()} ${unit}${percent}`
})
const workloadNote = computed(() => {
  const work = view.value?.matchingWorkload
  return work?.basis === 'text_pairs'
    ? `Baseline + ${work.additional.toLocaleString()} extra text comparisons, based on ${work.covered} of ${work.evaluated} evaluated submissions. Comparison counts, not a runtime forecast.`
    : 'No saved comparison inventory available. This estimate counts original element names plus additional source texts; actual effort depends on submission size.'
})
const workloadStyle = computed(() => {
  const percent = Math.max(0, view.value?.matchingWorkload.percent ?? 0)
  const ratio = percent / (percent + 100)
  return { backgroundColor: `hsl(${120 * (1 - ratio)} 65% ${94 - ratio * 62}%)`, color: ratio > 0.82 ? '#fff' : '#202820' }
})
const marks = computed<ReviewCanvasMark[]>(() => {
  const counts = new Map<string, number>()
  for (const item of view.value?.suggestions ?? []) if (!findEntry(item)) counts.set(item.referenceElementId, (counts.get(item.referenceElementId) ?? 0) + 1)
  return [...counts].map(([cellId, count]) => ({
    key: cellId, cellId, state: 'hint' as const,
    config: { image: { src: markImage, width: 16, height: 16 }, tooltip: `${count} open suggestion${count === 1 ? '' : 's'}`, align: 'right' as const, verticalAlign: 'top' as const, cursor: 'pointer' }
  }))
})
const rows = computed<Row[]>(() => {
  if (!selectedId.value || !view.value) return []
  const suggestions = view.value.suggestions.filter((item) => item.referenceElementId === selectedId.value && !findEntry(item))
  const entries = view.value.entries.filter((item) => item.referenceElementId === selectedId.value)
  const result: Row[] = []
  const section = (name: Section, title: string, items: Row[], open = true) => {
    if (!items.length) return
    result.push({ key: `header:${name}`, header: true, section: name, title, count: items.length })
    if (open) result.push(...items)
  }
  section('suggested', 'Suggested', suggestions.map((item) => ({ key: `s:${item.termKey}`, section: 'suggested', term: item.term, status: 'suggested', suggestion: item })))
  for (const status of statuses) {
    const title = { accepted: 'Accepted', rejected: 'Rejected', ignored: 'Ignored' }[status]
    section(status, title, entries.filter((item) => item.status === status).map((item) => ({ key: `e:${item.id}`, section: status, term: item.term, status, origin: item.origin, entry: item })), status !== 'ignored' || showIgnored.value)
  }
  return result
})
const typeItems = computed(() => [...new Set((view.value?.suggestions ?? []).map((item) => elementsById.value.get(item.referenceElementId)?.type).filter((type): type is string => !!type))].sort())
const reviewTerms = computed<Suggestion[]>(() => {
  const terms = new Map((view.value?.suggestions ?? []).map(item => [suggestionKey(item), item]))
  for (const entry of view.value?.entries ?? []) {
    if (terms.has(suggestionKey(entry))) continue
    const outcome = outcomeOf(entry)
    terms.set(suggestionKey(entry), { ...entry, variants: [], persons: 0,
      submissions: new Set(outcome?.occurrences.map(item => item.modelVersionId) ?? []).size,
      evidence: { contextUnique: 0, contextBest: 0, textOnly: 0, recognized: outcome?.counts.counted ?? 0 },
      alsoSuggestedFor: [], comparisons: outcome?.comparisons ?? [] })
  }
  return [...terms.values()]
})
const filteredSuggestions = computed(() => reviewTerms.value.filter((item) =>
  item.submissions >= (minPersons.value || 0)
  && (!typeFilter.value || elementsById.value.get(item.referenceElementId)?.type === typeFilter.value)))
const importSources = computed(() => {
  const current = solutions.value[solutionIndex.value]
  if (!current || !task.value) return []
  const seen = new Set<string>([current.versionId])
  return task.value.releases.flatMap((item) => item.sampleSolutions.filter((solution) => solution.modelId === current.modelId && !seen.has(solution.versionId) && seen.add(solution.versionId))
    .map((solution) => ({ title: `Release ${item.versionNumber}`, value: solution.versionId })))
})

const suggestionKey = (item: Pick<Suggestion, 'referenceElementId' | 'termKey'>) => `${item.referenceElementId}:${item.termKey}`
const comparisonsOf = (item?: Pick<Suggestion, 'referenceElementId' | 'termKey'>) => item ? reviewTerms.value.find(term => suggestionKey(term) === suggestionKey(item))?.comparisons : undefined
const entryOf = (item: TermOutcome) => view.value?.entries.find(entry => entry.referenceElementId === item.referenceElementId && entry.termKey === item.termKey)
const decideTerm = (item: TermOutcome, status: EntryStatus) => {
  const term = reviewTerms.value.find(term => suggestionKey(term) === suggestionKey(item))
  if (term) return decide(term, status)
  const entry = entryOf(item)
  return entry ? change(entry, status) : save([{ referenceElementId: item.referenceElementId, term: item.term, status }], `“${item.term}” ${status}.`, [{ referenceElementId: item.referenceElementId, term: item.term, status: null }])
}
const sameNamed = (item: Suggestion): GlossaryElement[] => {
  const own = elementsById.value.get(item.referenceElementId)
  if (!own || !view.value) return []
  const decided = new Set(view.value.entries.map((entry) => `${entry.referenceElementId}:${entry.termKey}`))
  return view.value.elements.filter((element) => element.id !== own.id && element.label === own.label && element.targetKind === own.targetKind && !decided.has(`${element.id}:${item.termKey}`))
}
const message = (cause: unknown, fallback: string) => (cause as { response?: { data?: { message?: string } } }).response?.data?.message ?? fallback
const notify = (text: string, undoable: GlossaryChange[] | null = null) => {
  snackbarText.value = text
  undoChanges.value = undoable
  snackbar.value = true
}

const loadPackage = async (ref: SolutionRef): Promise<ModelPackage> => {
  const { data: solution } = await taskService.getSampleSolution(ref.taskId, ref.versionId, ref.modelId, ref.modelVersionId)
  const languages = new Map<string, PackagedLanguage>()
  const pending: LanguageVersionReference[] = [...solution.workspaceLanguages]
  while (pending.length) {
    const reference = pending.pop()!
    const key = `${reference.languageId}:${reference.versionId}`
    if (languages.has(key)) continue
    const { data: version } = await languageService.getVersion<DiagramLanguage>(reference.languageId, reference.versionId)
    const included = version.includedLanguageVersions ?? []
    languages.set(key, { languageId: reference.languageId, versionId: reference.versionId, name: '', data: version.data, includedLanguageVersions: included })
    pending.push(...included)
  }
  return { format: 'modeling-copilot-model', version: 1, model: { xml: String(solution.data.xml) }, workspaceLanguages: solution.workspaceLanguages, languages: [...languages.values()] }
}
const schedulePoll = () => {
  clearTimeout(pollTimer)
  if (jobRunning.value || replayRunning.value) pollTimer = setTimeout(poll, 3000)
}
const poll = async () => {
  const current = solutionRef.value
  if (!current || !view.value) return
  try {
    if (jobRunning.value) {
      const { data } = await synonymGlossary.status(current.taskId, current.versionId)
      if (solutionRef.value !== current || !view.value) return
      const finished = data.job?.state !== 'running'
      const grew = data.collected !== view.value.signals.collected
      view.value = { ...view.value, signals: data }
      if (finished || grew) {
        const refreshed = await synonymGlossary.solution(current, false, excludeStaff.value)
        if (solutionRef.value !== current) return
        view.value = refreshed.data
      }
    }
    const running = replays.value.find(item => item.state === 'running')
    if (running) {
      const { data } = await synonymGlossary.replay(current, running.id)
      if (solutionRef.value !== current) return
      replays.value = replays.value.map(item => item.id === data.id ? data : item)
    }
  } catch {
    // The next poll retries; saved glossary data stays usable.
  }
  schedulePoll()
}
const load = async () => {
  const current = solutionRef.value
  const token = ++loadToken
  clearTimeout(pollTimer)
  selectedId.value = null
  selectedPath.value = ''
  view.value = null
  modelPackage.value = null
  replays.value = []
  replayId.value = null
  outcomeSource.value = 'original'
  replayError.value = ''
  if (!current) return
  loading.value = true
  error.value = ''
  try {
    const [glossary, model] = await Promise.all([synonymGlossary.solution(current, false, excludeStaff.value), loadPackage(current)])
    if (token !== loadToken) return
    view.value = glossary.data
    modelPackage.value = model
    try {
      const { data } = await synonymGlossary.replays(current)
      if (token !== loadToken) return
      replays.value = data
      replayId.value = data[0]?.id ?? null
    } catch (cause) {
      if (token === loadToken) replayError.value = message(cause, 'Saved comparisons could not be loaded.')
    }
    schedulePoll()
  } catch (cause) {
    if (token === loadToken) error.value = message(cause, 'The glossary could not be loaded.')
  } finally {
    if (token === loadToken) loading.value = false
  }
}
const reload = async () => {
  if (solutionRef.value) view.value = (await synonymGlossary.solution(solutionRef.value, false, excludeStaff.value)).data
}
const save = async (changes: GlossaryChange[], text: string, undoable: GlossaryChange[] | null) => {
  if (!solutionRef.value || !view.value) return false
  saving.value = true
  try {
    view.value = (await synonymGlossary.save(solutionRef.value, view.value.revision, changes)).data
    await reload()
    notify(text, undoable)
    return true
  } catch (cause) {
    const status = (cause as { response?: { status?: number } }).response?.status
    if (status === 409) {
      await reload().catch(() => undefined)
      error.value = 'Another administrator changed this glossary. The latest state is shown, please check and repeat your decision.'
    } else if (status === 422 && tab.value === 'selected' && newTerm.value) {
      newTermError.value = message(cause, 'This term cannot be saved.')
    } else {
      error.value = message(cause, 'The decision could not be saved.')
    }
    return false
  } finally {
    saving.value = false
  }
}
const setMatchingSource = async (entry: GlossaryEntry, enabled: boolean) => {
  const current = solutionRef.value
  if (!current || !view.value || saving.value) return
  saving.value = true
  try {
    const { data } = await synonymGlossary.setMatchingSource(current, entry.id, view.value.revision, enabled)
    if (solutionRef.value !== current) return
    view.value = data
    await reload()
    notify(enabled ? 'Matching source enabled.' : 'Matching source disabled.')
  } catch (cause) {
    if (solutionRef.value !== current) return
    if ((cause as { response?: { status?: number } }).response?.status === 409) {
      await reload().catch(() => undefined)
      error.value = 'The glossary changed. The latest state is shown; please repeat your change.'
    } else error.value = message(cause, 'The matching source could not be changed.')
  } finally {
    saving.value = false
  }
}
const findEntry = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => view.value?.entries.find(entry => entry.referenceElementId === item.referenceElementId && entry.termKey === item.termKey)
const toggleSource = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => {
  const entry = findEntry(item)
  if (entry) return setMatchingSource(entry, !entry.matchingSource)
}
const removeTerm = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => {
  const entry = findEntry(item)
  if (entry) return change(entry, null)
}
const decide = (item: Suggestion, status: EntryStatus) => {
  if (status === 'accepted' && sameNamed(item).length) {
    acceptanceSelection.value = [item.referenceElementId]
    applying.value = item
    return
  }
  const entry = findEntry(item)
  return entry ? change(entry, status) : save([{ referenceElementId: item.referenceElementId, term: item.term, status }], `Term ${status}.`, [{ referenceElementId: item.referenceElementId, term: item.term, status: null }])
}
const change = (entry: GlossaryEntry, status: EntryStatus | null) =>
  save([{ referenceElementId: entry.referenceElementId, term: entry.term, status }], status ? `“${entry.term}” ${status}.` : `“${entry.term}” removed.`, [{ referenceElementId: entry.referenceElementId, term: entry.term, status: entry.status }])
const addTerm = async (status: EntryStatus) => {
  const term = newTerm.value.trim()
  if (!term || !selectedId.value) return
  newTermError.value = ''
  const change = { referenceElementId: selectedId.value, term }
  if (await save([{ ...change, status }], `“${term}” ${status}.`, [{ ...change, status: null }])) newTerm.value = ''
}
const applySameNamed = async (all: boolean) => {
  const item = applying.value
  if (!item || saving.value) return
  const targets = all ? acceptanceTargets.value.map(element => element.id) : [...acceptanceSelection.value]
  if (!targets.length) return
  const saved = await save(targets.map((referenceElementId) => ({ referenceElementId, term: item.term, status: 'accepted' })), `“${item.term}” accepted for ${targets.length} elements.`,
    targets.map((referenceElementId) => ({ referenceElementId, term: item.term, status: null })))
  if (saved) applying.value = null
}
const undo = async () => {
  const changes = undoChanges.value
  snackbar.value = false
  if (changes) await save(changes, 'Decision undone.', null)
}
const selectCell = (cellId: string, path?: string) => {
  selectedId.value = cellId
  tab.value = 'selected'
  selectedPath.value = path ?? canvas.value?.pathOf(cellId) ?? ''
  newTermError.value = ''
}
const recalculate = async (scope: RecalculateScope) => {
  if (!taskId.value || !releaseId.value || !view.value) return
  starting.value = true
  try {
    view.value = { ...view.value, signals: (await synonymGlossary.recalculate(taskId.value, releaseId.value, scope)).data }
    schedulePoll()
  } catch (cause) {
    error.value = message(cause, 'The calculation could not be started.')
  } finally {
    starting.value = false
  }
}
const startReplay = async () => {
  const current = solutionRef.value
  if (!current || !thresholdsValid.value) return
  replayStarting.value = true
  replayError.value = ''
  try {
    const { data } = await synonymGlossary.startReplay(current, customThresholds.value ? { ...thresholds.value } : null)
    if (solutionRef.value !== current) return
    replays.value = [data, ...replays.value.filter(item => item.id !== data.id)].slice(0, 3)
    replayId.value = data.id
    schedulePoll()
    const saved = await synonymGlossary.replays(current)
    if (solutionRef.value !== current) return
    replays.value = saved.data
    schedulePoll()
  } catch (cause) {
    if (solutionRef.value === current) replayError.value = message(cause, 'The comparison could not be started.')
  } finally {
    replayStarting.value = false
  }
}
const deleteReplay = async () => {
  const current = solutionRef.value
  const id = deleteReplayId.value
  if (!current || !id) return
  replayDeleting.value = true
  try {
    await synonymGlossary.deleteReplay(current, id)
    if (solutionRef.value !== current) return
    replays.value = replays.value.filter(item => item.id !== id)
    if (outcomeSource.value === id) outcomeSource.value = 'original'
    if (replayId.value === id) replayId.value = replays.value[0]?.id ?? null
    deleteReplayId.value = null
  } catch (cause) {
    replayError.value = message(cause, 'The comparison could not be deleted.')
    deleteReplayId.value = null
  } finally {
    replayDeleting.value = false
  }
}
const openImport = () => {
  importFrom.value = importSources.value[0]?.value ?? null
  importOpen.value = true
}
const runImport = async () => {
  if (!solutionRef.value || !view.value || !importFrom.value) return
  importOpen.value = false
  try {
    const { data } = await synonymGlossary.importEntries(solutionRef.value, importFrom.value, view.value.revision)
    view.value = data.glossary
    await reload()
    notify(`${data.imported} entries imported.${data.skipped.length ? ` Not imported: ${data.skipped.join(', ')}` : ''}`)
  } catch (cause) {
    error.value = message(cause, 'The entries could not be imported.')
    await reload().catch(() => undefined)
  }
}

watch(taskId, (id) => {
  releaseId.value = task.value?.releases[0]?.id ?? null
  if (id && route.params.taskId !== id) router.replace({ name: 'SynonymGlossary', params: { taskId: id } })
})
watch(releaseId, () => { solutionIndex.value = 0 })
watch(solutionRef, load)
watch(excludeStaff, load)
onMounted(async () => {
  loading.value = true
  try {
    tasks.value = (await synonymGlossary.tasks()).data
    const wanted = String(route.params.taskId ?? '')
    taskId.value = tasks.value.some((item) => item.id === wanted) ? wanted : tasks.value[0]?.id ?? null
  } catch (cause) {
    error.value = message(cause, 'The tasks could not be loaded.')
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  loadToken++
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.glossary-page { display: flex; flex-direction: column; height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px)); min-height: 0; overflow: hidden; }
.glossary-toolbar { flex-shrink: 0; }
.header-select { flex: 0 1 240px; min-width: 180px; }
.header-select-small { flex: 0 1 120px; min-width: 110px; }
.header-select-solution { flex: 0 1 165px; min-width: 145px; }
.toolbar-action { height: auto !important; min-height: 34px; padding: 4px 10px; line-height: 1.2; }
.toolbar-action :deep(.v-btn__content) { white-space: normal; }
.glossary-layout { display: grid; grid-template-columns: minmax(0, var(--model-width)) 12px minmax(0, 1fr); gap: 0; flex: 1; min-height: 0; align-items: stretch; overflow: hidden; }
.glossary-canvas { min-height: 0; height: 100%; }
.glossary-canvas :deep(.review-graph) { min-height: 0; }
.glossary-panel { display: flex; flex-direction: column; border: 1px solid #ddd; border-radius: 8px; min-width: 0; min-height: 0; overflow: hidden; }
.glossary-panel > :not(.panel-body) { flex-shrink: 0; }
.panel-body { flex: 1; min-height: 0; overflow-x: scroll; overflow-y: auto; scrollbar-gutter: stable; }
.panel-body :deep(.v-window__container) { height: auto; }
.panel-body :deep(.v-table__wrapper) { overflow: visible; }
.panel-body::-webkit-scrollbar { width: 12px; height: 12px; }
.panel-body::-webkit-scrollbar-track { background: rgba(var(--v-theme-on-surface), 0.05); }
.panel-body::-webkit-scrollbar-thumb { background: rgba(var(--v-theme-on-surface), 0.35); border: 2px solid rgb(var(--v-theme-surface)); border-radius: 6px; }
.reason-cell { min-width: 200px; max-width: 340px; padding-block: 8px !important; }
.row-actions { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 85px; padding-block: 6px; }
.row-actions :deep(.v-btn__content) { white-space: normal; overflow: visible; text-overflow: clip; }
.row-actions > .v-btn { height: auto; min-height: 24px; max-width: 140px; }
.split-handle { cursor: col-resize; touch-action: none; user-select: none; align-self: stretch; display: flex; align-items: center; justify-content: center; color: rgb(var(--v-theme-on-surface)); background: rgba(var(--v-theme-on-surface), 0.06); border-radius: 4px; }
.split-handle:hover, .split-handle:focus-visible { background: rgba(var(--v-theme-primary), 0.2); outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
.workload-indicator { border-radius: 4px; padding: 3px 8px; font-variant-numeric: tabular-nums; }
.term-field { min-width: 200px; }
.filter-field { flex: 0 1 120px; }
.filter-field-wide { flex: 1 1 170px; }
.section-row td { background: rgba(var(--v-theme-on-surface), 0.04); }
.selected-row td { background: rgba(var(--v-theme-primary), 0.08); }
@media (max-width: 1000px) {
  .glossary-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(100px, 30%) minmax(0, 1fr); gap: 12px; }
  .split-handle { display: none; }
}
</style>
