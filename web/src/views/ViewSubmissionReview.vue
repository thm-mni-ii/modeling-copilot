<template>
  <v-container v-if="submission" fluid>
    <div class="d-flex flex-wrap align-center ga-2 mb-3">
      <v-btn icon="mdi-arrow-left" variant="text" aria-label="Back to run" :to="{ name: 'Submissions', params: { assignmentId: submission.assignmentId }, query: { run: submission.runId, view: submission.managementView ? 'management' : 'participant' } }" />
      <div>
        <h1 class="text-h6">{{ learnerView ? (hasPublishedFeedback ? 'My feedback' : 'My submission') : `Review submission: ${personName(submission.ownerId)}` }}</h1>
        <p class="text-caption">
          Submitted {{ date(submission.createdAt) }}<span v-if="!learnerView"> · {{ position + 1 }} / {{ queue.length }} in this view</span>
        </p>
      </div>
      <v-spacer />
      <v-btn-toggle v-if="submission.canModerate && submission.isOwner" :model-value="submission.managementView ? 'management' : 'participant'" mandatory :disabled="busy" density="compact" @update:model-value="changePerspective"><v-btn value="participant">My participation</v-btn><v-btn value="management">Administration</v-btn></v-btn-toggle>
      <v-btn v-if="!learnerView" :disabled="busy || position <= 0" @click="navigate(-1)">Previous model</v-btn><v-btn v-if="!learnerView" :disabled="busy || position < 0 || position >= queue.length - 1" @click="navigate(1)">Next model</v-btn>
      <v-btn v-if="learnerView && submission.sourceModelId" :to="{ name: 'Modeling', params: { modelId: submission.sourceModelId } }" target="_blank" rel="noopener">Edit my working model</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-3">{{ error }} <v-btn v-if="dirty" variant="text" @click="save('save')">Retry saving</v-btn></v-alert>
    <v-alert v-if="(!learnerView && submission.runState === 'archived') || !submission.current" type="info" variant="tonal" class="mb-3">{{ !submission.current ? 'Previous submission.' : 'Archived run.' }} The submitted model and feedback remain available.</v-alert>
    <div class="d-flex flex-wrap align-center ga-3 mb-3">
      <v-select v-if="!learnerView" :model-value="mode" :items="reviewChoices" label="Review" density="compact" hide-details style="max-width: 370px" @update:model-value="switchMode" />
      <v-chip v-if="activeReview">{{ reviewStatusLabel(activeReview.status) }}</v-chip>
      <span v-if="editableMode" class="text-caption" role="status">{{ busy ? 'Saving…' : dirty ? 'Unsaved changes' : 'All changes saved' }}</span>
      <v-btn v-if="canEdit" :disabled="busy" color="primary" @click="save('complete')">Finish review</v-btn>
      <v-btn v-if="editableMode && activeReview && activeReview.status !== 'draft'" :disabled="busy || submission.runState === 'archived' || !submission.current" @click="save('reopen')">Continue reviewing</v-btn>
      <v-btn v-if="submission.permissions.publish && activeReview?.status === 'complete' && submission.runState !== 'archived'" color="primary" :disabled="busy" @click="releaseDialog = true">Publish feedback</v-btn>
      <v-spacer /><v-btn :disabled="busy" @click="reloadFromServer">{{ dirty ? 'Discard local changes and reload' : 'Reload' }}</v-btn>
    </div>
    <p v-if="learnerView" class="text-body-2 text-medium-emphasis mb-3">This is your submitted copy. Make changes in your working model, then record your progress here.</p>
    <p v-else-if="activeReview?.published && activeReview.status !== 'published'" class="text-body-2 text-medium-emphasis mb-3">Changes stay private until published. Students can still see the last published feedback.</p>
    <div class="review-layout">
      <SubmissionReviewCanvas ref="canvas" :package="submission.package" :marks="marks" :selected-cell-id="selectedCellId" v-model:show-feedback="showFeedback" @select="selectCell" @overlay="selectOverlay" />
      <aside class="feedback-panel" aria-label="Feedback comments">
        <section v-if="!learnerView && mode === 'staff'" class="overall-score pa-3 border-b" aria-labelledby="overall-score-heading">
          <h2 id="overall-score-heading" class="text-subtitle-1">Overall model score</h2>
          <p class="text-caption mb-3">Assess the entire model, separately from individual markings. Required to finish the review; published with your feedback.</p>
          <v-text-field
            v-if="canEdit"
            ref="scoreField"
            :model-value="scoreInput"
            label="Overall score (0–100)"
            suffix="%"
            type="number"
            min="0"
            max="100"
            step="any"
            :disabled="busy"
            :error-messages="scoreError"
            hint="0 = 0%, 100 = 100%"
            persistent-hint
            @update:model-value="updateScore"
          />
          <p v-else class="text-h5 mt-2">{{ activeReview?.score != null ? `${activeReview.score}%` : 'Not scored yet' }}</p>
        </section>
        <section v-else-if="publishedScore != null" class="overall-score pa-3 border-b" aria-label="Overall model score">
          <h2 class="text-subtitle-1">Overall model score</h2>
          <p class="text-h5 mt-2">{{ publishedScore }}%</p>
          <p class="text-caption">Published assessment of the entire model.</p>
        </section>
        <div v-if="canEdit" class="pa-3 border-b">
          <h2 class="text-subtitle-1">Mark selected object</h2>
          <p class="text-caption my-2">{{ selectedPath || 'Click the exact object, attribute or connection in the model.' }}</p>
          <div class="d-flex flex-wrap ga-1">
            <v-btn v-for="state in states" :key="state.key" size="small" :color="state.color" :variant="entries.some((e) => e.cellId === selectedCellId && e.state === state.key) ? 'flat' : 'tonal'" :aria-pressed="entries.some((e) => e.cellId === selectedCellId && e.state === state.key)" :disabled="!selectedCellId || busy" @click="toggleMark(state.key)">{{ state.label }}</v-btn>
          </div>
        </div>
        <div class="pa-3 border-b">
          <h2 class="text-subtitle-1">Comments</h2>
          <p class="text-caption">Open items: {{ openCount }}</p>
          <v-btn v-if="learnerView" size="small" :variant="showResolved ? 'tonal' : 'text'" :aria-pressed="showResolved" class="mt-2" @click="showResolved = !showResolved">Show done comments</v-btn>
          <p v-if="learnerView && hasPublishedFeedback" class="text-caption mt-2">Done tracks your own progress. It does not change your model or confirm that it is correct.</p>
        </div>
        <v-alert v-if="removedEntry && canEdit" type="info" variant="tonal" class="ma-2" role="status">Marking removed.<v-btn size="small" variant="text" :disabled="busy" @click="undoRemove">Undo</v-btn></v-alert>
        <v-alert v-if="!showFeedback && selectedCellId" type="info" density="compact" class="ma-2">Feedback is hidden.<v-btn size="small" variant="text" @click="showFeedback = true">Show model with feedback</v-btn></v-alert>
        <div class="feedback-entries">
          <div v-for="item in visibleEntries" :key="item.key" :ref="(el) => setEntryNode(item.key, el)" class="feedback-entry" :class="{ 'feedback-entry--selected': selectedKeys.includes(item.key), 'feedback-entry--resolved': resolved.has(item.key) }" tabindex="0" @click="selectEntry(item)" @keydown.enter.self="selectEntry(item)">
            <div class="d-flex align-center ga-2">
              <v-icon :color="stateOf(item.entry.state).color" :icon="stateOf(item.entry.state).icon" size="19" /><strong class="text-body-2">{{ stateOf(item.entry.state).label }}</strong
              ><v-spacer />
              <v-btn
                v-if="learnerView && item.entry.state !== 'correct'"
                size="small"
                :variant="resolved.has(item.key) ? 'flat' : 'outlined'"
                :color="resolved.has(item.key) ? 'success' : undefined"
                :prepend-icon="resolved.has(item.key) ? 'mdi-check' : undefined"
                :aria-pressed="resolved.has(item.key)"
                :title="resolved.has(item.key) ? 'Mark as not done' : 'Mark as done'"
                :disabled="busy"
                @click.stop="setResolved(item, !resolved.has(item.key))"
                >Done</v-btn
              >
              <v-btn v-if="canEdit" size="small" variant="text" color="error" :disabled="busy" @click.stop="removeMark(item.entry.id)">Remove marking</v-btn>
            </div>
            <p class="text-caption my-2">{{ cellPath(item.entry.cellId) }}</p>
            <v-textarea v-if="canEdit" :model-value="item.entry.comment" label="Comment" rows="2" auto-grow maxlength="10000" hide-details @update:model-value="updateComment(item.entry.id, $event)" @click.stop />
            <p v-else class="text-body-2" style="white-space: pre-wrap">{{ item.entry.comment || 'No comment.' }}</p>
            <p class="text-caption text-medium-emphasis mt-2">{{ item.entry.createdBy ? `By ${personName(item.entry.createdBy)}` : 'New feedback' }}{{ item.entry.updatedBy && item.entry.updatedBy !== item.entry.createdBy ? ` - Updated by ${personName(item.entry.updatedBy)}` : '' }}</p>
          </div>
          <p v-if="!visibleEntries.length" class="pa-4 text-body-2 text-medium-emphasis">{{ learnerView ? (hasPublishedFeedback ? 'No feedback matches this view.' : 'Your model has been submitted. Feedback will appear here once the reviewers publish it.') : 'Select an object in the model and choose Correct, Incorrect or Hint to add feedback.' }}</p>
        </div>
      </aside>
    </div>
    <v-dialog v-model="releaseDialog" max-width="550" :persistent="busy"
      ><v-card title="Publish feedback"
        ><v-card-text>This feedback, including the overall model score of {{ activeReview?.score }}%, will become visible to the student. Later changes stay private until published again.</v-card-text><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="releaseDialog = false">Cancel</v-btn><v-btn :loading="busy" color="primary" @click="release">Publish feedback</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
  <v-container v-else
    ><v-progress-linear v-if="busy" indeterminate /><v-alert v-if="error" type="error">{{ error }}</v-alert></v-container
  >
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import SubmissionReviewCanvas, { type ReviewCanvasMark } from '@/components/submissions/SubmissionReviewCanvas.vue'
import { submissions, submissionError } from '@/services/submissions'
import type { FeedbackState } from '@/model/Feedback'
import type { GlobalFeedbackSettings, ReviewEntry, SubmissionDetail, SubmissionRow } from '@/services/api/types/submission'
import { useUserStore } from '@/stores/userStore'
import { selectFeedbackMark, reviewStatusLabel } from '@/utils/submissionFeedback'
interface DisplayEntry {
  key: string
  entry: ReviewEntry
  reviewId: string
  publication: number
}
const route = useRoute()
const router = useRouter()
const user = useUserStore()
const submission = ref<SubmissionDetail | null>(null)
const learnerView = computed(() => Boolean(submission.value?.isOwner && !submission.value.managementView))
const perspective = computed(() => (route.query.view === 'participant' ? ('participant' as const) : route.query.view === 'management' ? ('management' as const) : undefined))
const changePerspective = (view: string) => router.replace({ query: { ...route.query, view } })
const queue = ref<SubmissionRow[]>([])
const mode = ref('staff')
const entries = ref<ReviewEntry[]>([])
const scoreInput = ref<string | number | null>(null)
const scoreField = ref<{ focus: () => void }>()
const scoreRequired = ref(false)
const score = computed(() => scoreInput.value == null || String(scoreInput.value).trim() === '' ? null : Number(scoreInput.value))
const scoreError = computed(() => {
  if (score.value === null) return scoreRequired.value ? 'Enter an overall score from 0 to 100 before finishing the review.' : ''
  return Number.isFinite(score.value) && score.value >= 0 && score.value <= 100 ? '' : 'Enter a number from 0 to 100.'
})
const removedEntry = ref<ReviewEntry | null>(null)
const hasPublishedFeedback = computed(() => Boolean(submission.value?.reviews.some((review) => review.published)))
const personName = (id: string) => submission.value?.people?.[id] ?? id
const dirty = ref(false)
const busy = ref(false)
const error = ref('')
const showFeedback = ref(true)
const showResolved = ref(true)
const selectedCellId = ref<string | null>(null)
const selectedPath = ref('')
const selectedKeys = ref<string[]>([])
const resolved = ref(new Set<string>())
const releaseDialog = ref(false)
const canvas = ref<InstanceType<typeof SubmissionReviewCanvas>>()
const entryNodes = new Map<string, Element>()
const configurations = ref<Record<number, GlobalFeedbackSettings>>({})
let editSequence = 0
let timer: ReturnType<typeof setTimeout> | undefined
let saving: Promise<boolean> | null = null
const states = [
  { key: 'correct' as const, label: 'Correct', color: 'success', icon: 'mdi-check-circle-outline' },
  { key: 'incorrect' as const, label: 'Incorrect', color: 'error', icon: 'mdi-close-circle-outline' },
  { key: 'hint' as const, label: 'Hint', color: 'warning', icon: 'mdi-alert-circle-outline' }
]
const stateOf = (key: FeedbackState) => states.find((s) => s.key === key)!
const date = (value: string) => new Date(value).toLocaleString()
const position = computed(() => queue.value.findIndex((item) => item.id === submission.value?.id))
const activeReview = computed(() => (mode.value === 'staff' ? submission.value?.reviews.find((review) => review.kind === 'staff') : undefined))
const publishedScore = computed(() => submission.value?.reviews.find((review) => review.kind === 'staff')?.published?.score)
const editableMode = computed(() => Boolean(submission.value && !learnerView.value && mode.value === 'staff' && submission.value.permissions.review))
const canEdit = computed(() => editableMode.value && submission.value?.current && submission.value.runState !== 'archived' && (!activeReview.value || activeReview.value.status === 'draft'))
const reviewChoices = computed(() => {
  const choices = [{ title: 'Published feedback', value: 'published' }]
  if (submission.value?.permissions.review || submission.value?.reviews.some((r) => r.kind === 'staff')) choices.unshift({ title: 'Staff review', value: 'staff' })
  return choices
})
const displayEntries = computed<DisplayEntry[]>(() => {
  if (!submission.value) return []
  if (mode.value !== 'published' && !learnerView.value) {
    return entries.value.map((entry) => ({ key: `draft:${mode.value}:${entry.id}`, entry, reviewId: activeReview.value?.id ?? '', publication: 0 }))
  }
  return submission.value.reviews.flatMap((review) => (review.published ? review.published.entries.map((entry) => ({ key: `${review.id}:${review.published!.number}:${entry.id}`, entry, reviewId: review.id, publication: review.published!.number })) : []))
})
const openCount = computed(() => displayEntries.value.filter((item) => item.entry.state !== 'correct' && !resolved.value.has(item.key)).length)
const visibleEntries = computed(() => displayEntries.value.filter((item) => showResolved.value || !resolved.value.has(item.key) || selectedKeys.value.includes(item.key)))
const marks = computed<ReviewCanvasMark[]>(() =>
  displayEntries.value
    .filter((item) => !resolved.value.has(item.key) || selectedKeys.value.includes(item.key))
    .flatMap((item) => {
      const revision = item.publication ? submission.value?.reviews.find((r) => r.id === item.reviewId)?.published?.configRevision : activeReview.value?.configRevision ?? configurations.value[-1]?.revision
      const config = configurations.value[revision ?? -1]?.overlays[item.entry.state]
      return config ? [{ key: item.key, cellId: item.entry.cellId, state: item.entry.state, config }] : []
    })
)
const loadConfigurations = async () => {
  const current = (await submissions.settings()).data
  configurations.value[-1] = current
  configurations.value[current.revision] = current
  const versions = new Set(submission.value?.reviews.flatMap((r) => [r.configRevision, ...(r.published ? [r.published.configRevision] : [])]) ?? [])
  await Promise.all(
    [...versions].map(async (revision) => {
      if (!configurations.value[revision]) configurations.value[revision] = (await submissions.settings(revision)).data
    })
  )
}
const adoptEntries = () => {
  entries.value = JSON.parse(JSON.stringify(activeReview.value?.entries ?? activeReview.value?.published?.entries ?? []))
  scoreInput.value = activeReview.value?.score ?? null
  scoreRequired.value = false
  dirty.value = false
  if (activeReview.value?.status !== 'draft') removedEntry.value = null
}
const load = async () => {
  removedEntry.value = null
  busy.value = true
  error.value = ''
  try {
    await user.ensureGlobalRole()
    submission.value = (await submissions.submission(String(route.params.submissionId), perspective.value)).data
    mode.value = !learnerView.value && submission.value.permissions.review ? 'staff' : 'published'
    adoptEntries()
    resolved.value = new Set(submission.value.resolved)
    selectedCellId.value = null
    selectedKeys.value = []
    selectedPath.value = ''
    await loadConfigurations()
    const all: SubmissionRow[] = []
    for (let skip = 0; ; skip += 100) {
      const result = (await submissions.listSubmissions(submission.value.runId, skip, false, perspective.value)).data
      all.push(...result.items)
      if (skip + 100 >= result.total) break
    }
    const filter = String(route.query.filter ?? 'all')
    queue.value = all.filter((row) => filter === 'all' || row.status === filter)
    if (!queue.value.some((row) => row.id === submission.value?.id)) queue.value.unshift({ ...submission.value, status: 'submitted' })
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const scheduleSave = () => {
  dirty.value = true
  editSequence++
  clearTimeout(timer)
  timer = setTimeout(() => {
    void save('save')
  }, 800)
}
const updateScore = (value: string | number | null) => {
  if (!canEdit.value) return
  scoreInput.value = value
  scheduleSave()
}
const reloadFromServer = () => {
  clearTimeout(timer)
  return load()
}
const save = async (action: 'save' | 'complete' | 'reopen'): Promise<boolean> => {
  clearTimeout(timer)
  if (saving) {
    if (!(await saving)) return false
    return save(action)
  }
  if (!submission.value || !editableMode.value || (action === 'save' && !dirty.value)) return true
  if (action === 'complete') scoreRequired.value = true
  if ((score.value !== null && scoreError.value) || (action === 'complete' && score.value === null)) {
    if (action === 'complete') {
      await nextTick()
      scoreField.value?.focus()
    }
    return false
  }
  const id = submission.value.id
  const sequence = editSequence
  const payload = { baseRevision: activeReview.value?.revision ?? 0, entries: JSON.parse(JSON.stringify(entries.value)) as ReviewEntry[], score: score.value, action }
  busy.value = true
  error.value = ''
  saving = (async () => {
    try {
      submission.value = (await submissions.saveReview(id, 'staff', payload, perspective.value)).data
      if (sequence === editSequence) adoptEntries()
      else {
        dirty.value = true
        timer = setTimeout(() => {
          void save('save')
        }, 800)
      }
      return true
    } catch (cause) {
      error.value = submissionError(cause)
      return false
    } finally {
      busy.value = false
      saving = null
    }
  })()
  return saving
}
const flush = async () => {
  if (saving && !(await saving)) return false
  return !dirty.value || (await save('save'))
}
const switchMode = async (value: string) => {
  if (!(await flush())) return
  mode.value = value
  removedEntry.value = null
  adoptEntries()
  selectedKeys.value = []
}
const toggleMark = (state: FeedbackState) => {
  if (!canEdit.value || !selectedCellId.value) return
  const selected = selectFeedbackMark(entries.value, selectedCellId.value, state, () => crypto.randomUUID())
  entries.value = selected.entries
  selectedKeys.value = displayEntries.value.filter((item) => item.entry.id === selected.selectedId).map((item) => item.key)
  if (selected.changed) {
    removedEntry.value = null
    scheduleSave()
  }
  void scrollToEntry()
}
const removeMark = (id: string) => {
  if (!canEdit.value || busy.value) return
  const entry = entries.value.find((item) => item.id === id)
  if (!entry) return
  removedEntry.value = { ...entry }
  entries.value = entries.value.filter((item) => item.id !== id)
  selectedKeys.value = []
  scheduleSave()
}
const undoRemove = () => {
  if (!canEdit.value || busy.value || !removedEntry.value) return
  entries.value = [...entries.value, removedEntry.value]
  selectedCellId.value = removedEntry.value.cellId
  selectedPath.value = cellPath(removedEntry.value.cellId)
  selectedKeys.value = displayEntries.value.filter((item) => item.entry.id === removedEntry.value?.id).map((item) => item.key)
  removedEntry.value = null
  scheduleSave()
  void scrollToEntry()
}
const updateComment = (id: string, comment: string) => {
  const entry = entries.value.find((e) => e.id === id)
  if (entry) {
    entry.comment = comment
    scheduleSave()
  }
}
const cellPath = (cellId: string) => canvas.value?.pathOf(cellId) ?? cellId
const scrollToEntry = async () => {
  await nextTick()
  const first = selectedKeys.value[0]
  if (first) entryNodes.get(first)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}
const selectCell = (cellId: string, path: string) => {
  selectedCellId.value = cellId
  selectedPath.value = path
  selectedKeys.value = displayEntries.value.filter((item) => item.entry.cellId === cellId).map((item) => item.key)
  void scrollToEntry()
}
const selectOverlay = (keys: string[], cellId: string) => {
  selectedCellId.value = cellId
  selectedPath.value = cellPath(cellId)
  selectedKeys.value = keys
  void scrollToEntry()
}
const selectEntry = (item: DisplayEntry) => {
  selectedCellId.value = item.entry.cellId
  selectedPath.value = cellPath(item.entry.cellId)
  selectedKeys.value = [item.key]
}
const setEntryNode = (key: string, node: unknown) => {
  if (node instanceof Element) entryNodes.set(key, node)
  else entryNodes.delete(key)
}
const setResolved = async (item: DisplayEntry, value: boolean) => {
  if (!submission.value) return
  busy.value = true
  error.value = ''
  try {
    await submissions.resolve(submission.value.id, { reviewId: item.reviewId, publication: item.publication, entryId: item.entry.id, resolved: value })
    const updated = new Set(resolved.value)
    if (value) {
      updated.add(item.key)
      selectedKeys.value = selectedKeys.value.filter((key) => key !== item.key)
    } else updated.delete(item.key)
    resolved.value = updated
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const release = async () => {
  if (!submission.value || !activeReview.value) return
  busy.value = true
  error.value = ''
  try {
    const result = (await submissions.publish(submission.value.runId, [{ submissionId: submission.value.id, reviewId: activeReview.value.id, revision: activeReview.value.revision }])).data.items[0]
    if (!result.published) throw new Error(result.message)
    releaseDialog.value = false
    submission.value = (await submissions.submission(submission.value.id, perspective.value)).data
    adoptEntries()
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const navigate = async (offset: number) => {
  if (!(await flush())) return
  const next = queue.value[position.value + offset]
  if (next) await router.push({ name: 'SubmissionReview', params: { submissionId: next.id }, query: route.query })
}
onBeforeRouteLeave(flush)
onBeforeRouteUpdate(flush)
const preventUnsavedUnload = (event: BeforeUnloadEvent) => {
  if (dirty.value || saving) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onMounted(() => window.addEventListener('beforeunload', preventUnsavedUnload))
onBeforeUnmount(() => {
  clearTimeout(timer)
  window.removeEventListener('beforeunload', preventUnsavedUnload)
})
watch([() => route.params.submissionId, () => route.query.view], load, { immediate: true })
</script>

<style scoped>
.review-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 350px;
  gap: 16px;
  height: calc(100vh - 250px);
  min-height: 600px;
}
.feedback-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: white;
}
.overall-score {
  flex-shrink: 0;
  background: rgb(var(--v-theme-surface));
}
.feedback-panel > :not(.feedback-entries) {
  flex-shrink: 0;
}
.feedback-entries {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.feedback-entry {
  padding: 14px;
  border-bottom: 1px solid #ddd;
  border-left: 4px solid transparent;
  cursor: pointer;
}
.feedback-entry--selected {
  border-left-color: #1565c0;
  background: #e3f2fd;
}
.feedback-entry--resolved {
  color: #757575;
  background: #f5f5f5;
}
.feedback-entry--resolved.feedback-entry--selected {
  background: #e3f2fd;
}
.feedback-entry:focus-visible {
  outline: 2px solid #1565c0;
  outline-offset: -2px;
}
@media (max-width: 850px) {
  .review-layout {
    grid-template-columns: 1fr;
    height: auto;
  }
  .feedback-panel {
    max-height: 600px;
  }
}
</style>
