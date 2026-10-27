<template>
  <v-container class="survey-editor py-5" max-width="1440">
    <v-form :disabled="!ready || busy" @submit.prevent="save">
      <header class="editor-header">
        <div class="header-title">
          <router-link to="/surveys" class="overview-link"><v-icon size="16">mdi-arrow-left</v-icon> Fragebögen</router-link>
          <h1 class="text-overline mt-2">Fragebogen</h1>
          <v-text-field v-model="title" class="survey-name" label="Titel des Fragebogens" placeholder="Gib deinem Fragebogen einen Namen" variant="plain" hide-details :error="attempted && titleRule(title) !== true" maxlength="256" />
        </div>
        <div class="header-actions">
          <v-chip size="small" variant="tonal">{{ version ? `${state?.latestKind === 'release' ? 'Release' : 'Checkpoint'} ${version}` : 'Neu' }}</v-chip>
          <v-chip size="small" :color="state?.activeReleaseId ? 'success' : undefined" variant="tonal">{{ state?.activeReleaseVersion ? `Aktiv: Release ${state.activeReleaseVersion}` : 'Nicht veröffentlicht' }}</v-chip>
          <span class="save-state" role="status">{{ dirty ? 'Ungespeicherte Änderungen' : unpublished ? 'Checkpoint gespeichert, noch nicht veröffentlicht' : id ? 'Alle Änderungen gespeichert' : 'Noch nicht gespeichert' }}</span>
          <v-btn variant="text" prepend-icon="mdi-history" :disabled="!ready || !id || busy" @click="historyDialog = true">Verlauf</v-btn>
          <v-btn variant="tonal" prepend-icon="mdi-eye-outline" :disabled="!ready || !questions.length || busy" @click="openPreview">{{ dirty || !id ? 'Speichern & Vorschau' : 'Vorschau' }}</v-btn>
          <v-btn type="submit" variant="tonal" :loading="saving" :disabled="!ready || releasing">Checkpoint speichern</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!ready || busy || !questions.length || (!dirty && state?.activeReleaseId === state?.latestVersionId)" @click="prepareRelease()">Release</v-btn>
        </div>
      </header>
      <v-progress-linear v-if="loading" indeterminate class="mb-4" />
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}<v-btn v-if="loadFailed" variant="text" size="small" @click="load">Erneut laden</v-btn></v-alert>
      <p class="version-note mb-4"><v-icon size="16" class="mr-1">mdi-information-outline</v-icon> Speichern legt einen vollständigen Checkpoint an. Erst „Release“ veröffentlicht ihn. Bestehende Antworten behalten ihre Version.</p>
      <div class="editor-grid" :class="{ 'editor-grid--detail': showDetail }">
        <aside class="survey-sidebar" aria-label="Fragen im Fragebogen">
          <div class="sidebar-header">
            <div>
              <h2 class="text-subtitle-1 font-weight-bold">Deine Fragen</h2>
              <span class="text-caption text-medium-emphasis">{{ questions.length }} {{ questions.length === 1 ? 'Frage' : 'Fragen' }} · zum Sortieren ziehen</span>
            </div>
            <v-btn icon="mdi-plus" size="small" variant="tonal" aria-label="Frage hinzufügen" :disabled="!canAdd" @click="add" />
          </div>
          <draggable v-model="questions" item-key="name" handle=".question-handle" class="question-list" ghost-class="question-row--ghost" :animation="150" :disabled="!ready || busy">
            <template #item="{ element, index }">
              <div class="question-row" :class="{ 'question-row--active': selectedId === element.name, 'question-row--error': issues[element.name]?.length }">
                <span class="question-handle" aria-hidden="true"><v-icon size="18">mdi-drag-vertical</v-icon></span>
                <button type="button" class="question-select" :disabled="!ready || busy" :aria-pressed="selectedId === element.name" @click="selectQuestion(element.name)">
                  <span class="question-number">{{ index + 1 }}</span>
                  <span class="question-copy"
                    ><strong>{{ element.title || 'Frage ohne Titel' }}</strong
                    ><span>{{ questionTypeLabel(element) }}{{ element.isRequired ? ' · Pflichtfrage' : '' }}</span></span
                  >
                  <v-icon v-if="issues[element.name]?.length" color="error" size="18" aria-label="Frage enthält Fehler">mdi-alert-circle-outline</v-icon>
                </button>
                <v-menu>
                  <template #activator="{ props }"><v-btn v-bind="props" icon="mdi-dots-vertical" size="x-small" variant="text" :disabled="!ready || busy" :aria-label="`Aktionen für Frage ${index + 1}`" /></template>
                  <v-list density="compact">
                    <v-list-item title="Nach oben" prepend-icon="mdi-arrow-up" :disabled="index === 0" @click="move(index, -1)" />
                    <v-list-item title="Nach unten" prepend-icon="mdi-arrow-down" :disabled="index === questions.length - 1" @click="move(index, 1)" />
                    <v-list-item title="Entfernen" prepend-icon="mdi-delete-outline" @click="removeId = element.name" />
                  </v-list>
                </v-menu>
              </div>
            </template>
          </draggable>
          <div v-if="!questions.length" class="sidebar-empty">
            <v-icon size="34" class="mb-3">mdi-form-select</v-icon>
            <p>Starte mit deiner ersten Frage.</p>
            <p class="text-caption mt-1">Weitere Fragen kannst du jederzeit hinzufügen.</p>
          </div>
          <v-btn block variant="text" prepend-icon="mdi-plus" class="sidebar-add" :disabled="!canAdd" @click="add">Frage hinzufügen</v-btn>
        </aside>
        <section class="question-details" aria-label="Einstellungen der ausgewählten Frage">
          <template v-if="selected">
            <v-btn class="mobile-back mb-3" variant="text" prepend-icon="mdi-arrow-left" @click="showDetail = false">Zurück zu den Fragen</v-btn>
            <div class="detail-heading">
              <div>
                <p class="text-overline text-medium-emphasis">FRAGE {{ selectedIndex + 1 }} VON {{ questions.length }}</p>
                <h2 ref="detailHeading" tabindex="-1" class="text-h5">Frage bearbeiten</h2>
              </div>
              <v-btn icon="mdi-delete-outline" variant="text" aria-label="Ausgewählte Frage entfernen" :disabled="busy" @click="removeId = selected.name" />
            </div>
            <v-alert v-if="issues[selected.name]?.length" type="error" variant="tonal" density="compact" class="mt-4"
              ><ul class="pl-4">
                <li v-for="issue in issues[selected.name]" :key="issue">{{ issue }}</li>
              </ul></v-alert
            >
            <SurveyQuestionEditor :key="selected.name" :model-value="selected" @update:model-value="questions[selectedIndex] = $event" />
          </template>
          <div v-else class="detail-empty">
            <v-icon size="52" color="primary">mdi-form-select</v-icon>
            <h2 class="text-h5 mt-5">Gestalte deinen Fragebogen</h2>
            <p class="text-medium-emphasis mt-3">Füge Fragen hinzu, ordne sie an und passe die Antworten an.</p>
            <v-btn color="primary" class="mt-5" prepend-icon="mdi-plus" :disabled="!canAdd" @click="add">Erste Frage hinzufügen</v-btn>
          </div>
        </section>
      </div>
    </v-form>
    <v-dialog :model-value="!!removeId" max-width="500" @update:model-value="!$event && (removeId = null)">
      <v-card title="Frage entfernen?">
        <v-card-text>„{{ questions.find((question) => question.name === removeId)?.title || 'Frage ohne Titel' }}“ wird aus diesem Entwurf entfernt. Bestehende Antworten bleiben erhalten.</v-card-text>
        <v-card-actions><v-btn @click="removeId = null">Abbrechen</v-btn><v-spacer /><v-btn color="error" @click="confirmRemove">Entfernen</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="previewDialog" max-width="960" scrollable>
      <v-card>
        <v-card-title class="d-flex align-center">Vorschau: {{ previewTitle }}<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Vorschau schließen" @click="previewDialog = false" /></v-card-title>
        <v-card-text><SurveyRenderer v-if="previewDialog" :survey-id="id" :version-id="previewVersionId" mode="preview" /></v-card-text>
      </v-card>
    </v-dialog>
    <SurveyVersionHistory v-if="state" v-model="historyDialog" :survey-id="id" :latest-version-id="state.latestVersionId" :active-release-id="state.activeReleaseId" :revision="state.revision" @preview="previewVersion" @release="prepareRelease" />
    <SurveyReleaseDialog v-model="releaseDialog" :target-label="releaseTarget ? `Version ${releaseTarget.version}` : 'Der aktuelle Bearbeitungsstand'" :active-version="state?.activeReleaseVersion ?? null" :save-first="!releaseTarget && (dirty || !id)" :busy="busy" :error="releaseError" @confirm="confirmRelease" />
    <SurveyLeaveDialog :model-value="leaveDialog" :dirty="dirty" :unpublished="unpublished" :active-version="state?.activeReleaseVersion ?? null" @resolve="resolveLeave" />
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import SurveyQuestionEditor from '@/components/surveys/SurveyQuestionEditor.vue'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import SurveyVersionHistory from '@/components/surveys/SurveyVersionHistory.vue'
import SurveyReleaseDialog from '@/components/surveys/SurveyReleaseDialog.vue'
import SurveyLeaveDialog from '@/components/surveys/SurveyLeaveDialog.vue'
import surveys, { surveyError, type SurveyQuestion, type Survey, type SurveyVersionInfo } from '@/services/surveys'
import { questionIssues, questionTypeLabel, titleRule } from '@/utils/surveyEditor'

const route = useRoute(),
  router = useRouter()
const id = ref(''),
  title = ref(''),
  version = ref<number | null>(null),
  questions = ref<SurveyQuestion[]>([])
const loading = ref(true),
  saving = ref(false),
  loadFailed = ref(false),
  error = ref(''),
  attempted = ref(false)
const state = ref<Survey | null>(null),
  releasing = ref(false)
const historyDialog = ref(false),
  releaseDialog = ref(false),
  releaseTarget = ref<SurveyVersionInfo | null>(null),
  releaseError = ref('')
const previewVersionId = ref<string | undefined>(),
  previewTitle = ref(''),
  leaveDialog = ref(false)
let leaveResolver: ((leave: boolean) => void) | null = null
const busy = computed(() => saving.value || releasing.value)
const unpublished = computed(() => ready.value && state.value?.latestKind === 'checkpoint')
const selectedId = ref<string | null>(null),
  showDetail = ref(false),
  detailHeading = ref<HTMLElement | null>(null)
const removeId = ref<string | null>(null),
  previewDialog = ref(false),
  baseline = ref('')
const ready = computed(() => !loading.value && !loadFailed.value)
const dirty = computed(() => ready.value && snapshot() !== baseline.value)
const canAdd = computed(() => ready.value && !busy.value && questions.value.length < 100)
const selectedIndex = computed(() => questions.value.findIndex((question) => question.name === selectedId.value))
const selected = computed(() => questions.value[selectedIndex.value] ?? null)
const issues = computed<Record<string, string[]>>(() => (attempted.value ? Object.fromEntries(questions.value.map((question) => [question.name, questionIssues(question)])) : {}))
let generation = 0
const snapshot = () => JSON.stringify([title.value, questions.value])
async function selectQuestion(name: string) {
  selectedId.value = name
  showDetail.value = true
  await nextTick()
  detailHeading.value?.focus({ preventScroll: true })
}
function add() {
  if (!canAdd.value) return
  const question: SurveyQuestion = { type: 'comment', name: `q_${crypto.randomUUID().replace(/-/g, '')}`, title: '', isRequired: false }
  questions.value.push(question)
  void selectQuestion(question.name)
}
function move(index: number, direction: number) {
  const target = index + direction
  if (target < 0 || target >= questions.value.length || busy.value) return
  const [question] = questions.value.splice(index, 1)
  questions.value.splice(target, 0, question)
}
function confirmRemove() {
  const index = questions.value.findIndex((question) => question.name === removeId.value)
  if (index < 0 || busy.value) return
  questions.value.splice(index, 1)
  if (selectedId.value === removeId.value) selectedId.value = questions.value[Math.min(index, questions.value.length - 1)]?.name ?? null
  if (!selectedId.value) showDetail.value = false
  removeId.value = null
}
async function load() {
  const current = ++generation
  id.value = String(route.params.id ?? '')
  loading.value = true
  loadFailed.value = false
  error.value = ''
  attempted.value = false
  showDetail.value = false
  try {
    const survey = id.value ? (await surveys.get(id.value)).data : null
    if (current !== generation) return
    state.value = survey
    title.value = survey?.title ?? ''
    version.value = survey?.version ?? null
    questions.value = survey?.definition.elements ?? []
    selectedId.value = questions.value[0]?.name ?? null
    baseline.value = snapshot()
  } catch (e) {
    if (current === generation) {
      loadFailed.value = true
      error.value = surveyError(e)
    }
  } finally {
    if (current === generation) loading.value = false
  }
}
async function save(): Promise<boolean> {
  if (busy.value || !ready.value) return false
  attempted.value = true
  error.value = ''
  const invalid = questions.value.find((question) => issues.value[question.name]?.length)
  if (titleRule(title.value) !== true || !questions.value.length || invalid) {
    error.value = titleRule(title.value) !== true ? String(titleRule(title.value)) : !questions.value.length ? 'Füge mindestens eine Frage hinzu.' : 'Bitte korrigiere die markierten Fragen.'
    if (invalid) await selectQuestion(invalid.name)
    return false
  }
  saving.value = true
  const savedSnapshot = snapshot()
  try {
    const survey = (await surveys.save(id.value, title.value, { elements: questions.value }, state.value?.latestVersionId ?? null, state.value?.revision ?? null)).data
    state.value = survey
    id.value = survey.id
    version.value = survey.version
    baseline.value = savedSnapshot
    await router.replace(`/surveys/${survey.id}/edit`)
    return true
  } catch (e) {
    error.value = surveyError(e)
    return false
  } finally {
    saving.value = false
  }
}
async function openPreview() {
  if ((dirty.value || !id.value) && !(await save())) return
  previewVersionId.value = state.value?.latestVersionId
  previewTitle.value = `${title.value} · Version ${version.value}`
  previewDialog.value = true
}
function previewVersion(version: SurveyVersionInfo) {
  historyDialog.value = false
  previewVersionId.value = version.id
  previewTitle.value = `${version.title} · Version ${version.version}`
  previewDialog.value = true
}
function prepareRelease(version: SurveyVersionInfo | null = null) {
  historyDialog.value = false
  releaseTarget.value = version
  releaseError.value = ''
  releaseDialog.value = true
}
async function confirmRelease() {
  if (busy.value) return
  if (!releaseTarget.value && (dirty.value || !id.value) && !(await save())) {
    releaseError.value = error.value
    return
  }
  if (!state.value) return
  releasing.value = true
  releaseError.value = ''
  try {
    state.value = (await surveys.activate(id.value, releaseTarget.value?.id ?? state.value.latestVersionId, state.value.revision)).data
    releaseDialog.value = false
  } catch (e) {
    releaseError.value = surveyError(e)
  } finally {
    releasing.value = false
  }
}
watch(
  () => route.params.id,
  () => {
    if (String(route.params.id ?? '') !== id.value || !baseline.value) void load()
  },
  { immediate: true }
)
function canLeave(): boolean | Promise<boolean> {
  if (busy.value || leaveResolver) return false
  if (!dirty.value && !unpublished.value) return true
  leaveDialog.value = true
  return new Promise((resolve) => {
    leaveResolver = resolve
  })
}
function resolveLeave(leave: boolean) {
  leaveDialog.value = false
  const resolve = leaveResolver
  leaveResolver = null
  resolve?.(leave)
}
function beforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value && !unpublished.value && !busy.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeRouteLeave(canLeave)
onBeforeRouteUpdate((to) => String(to.params.id ?? '') === id.value || canLeave())
onBeforeUnmount(() => {
  generation++
  window.removeEventListener('beforeunload', beforeUnload)
  resolveLeave(false)
})
</script>

<style scoped>
.editor-header {
  position: sticky;
  top: var(--v-layout-top, 64px);
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 16px 0 20px;
  margin-bottom: 16px;
  background: rgb(var(--v-theme-background));
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
}
.header-title {
  min-width: 180px;
  flex: 1;
}
.overview-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: rgb(var(--v-theme-on-surface), 0.65);
  text-decoration: none;
  font-size: 0.78rem;
}
.header-title h1 {
  line-height: 1.4;
}
.survey-name {
  max-width: 540px;
}
.survey-name :deep(input) {
  font-size: 1.4rem;
  font-weight: 650;
  padding-top: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}
.save-state {
  font-size: 0.72rem;
  opacity: 0.65;
}
.version-note {
  font-size: 0.8rem;
  color: rgb(var(--v-theme-on-surface), 0.65);
}
.editor-grid {
  display: grid;
  grid-template-columns: minmax(270px, 340px) minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}
.survey-sidebar {
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 16px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.08);
}
.question-list {
  min-height: 12px;
}
.question-row {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 12px 8px 12px 4px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.07);
  border-left: 3px solid transparent;
}
.question-row--active {
  background: rgb(var(--v-theme-primary), 0.08);
  border-left-color: rgb(var(--v-theme-primary));
}
.question-row--error {
  border-left-color: rgb(var(--v-theme-error));
}
.question-row--ghost {
  opacity: 0.4;
}
.question-handle {
  color: rgb(var(--v-theme-on-surface), 0.35);
  cursor: grab;
}
.question-select {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  flex: 1;
  text-align: left;
  border-radius: 6px;
  padding: 3px 1px;
}
.question-select:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 3px;
}
.question-number {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 25px;
  height: 25px;
  border-radius: 8px;
  background: rgb(var(--v-theme-on-surface), 0.06);
  font-size: 0.75rem;
  font-weight: 700;
}
.question-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.question-copy strong {
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}
.question-copy > span {
  font-size: 0.69rem;
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 225px;
}

.sidebar-add {
  margin: 8px 0;
}
.sidebar-empty {
  padding: 30px 18px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
}
.question-details {
  min-width: 0;
  padding: 24px 28px 32px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
}
.detail-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.detail-heading h2:focus {
  outline: none;
}

.detail-empty {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 30px;
}
.mobile-back {
  display: none;
}
@media (max-width: 1000px) {
  .editor-header {
    flex-wrap: wrap;
    position: static;
  }
  .header-actions {
    justify-content: flex-start;
  }
  .editor-grid {
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 16px;
  }
  .question-details {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .editor-grid {
    display: block;
  }
  .question-details {
    display: none;
  }
  .editor-grid--detail .survey-sidebar {
    display: none;
  }
  .editor-grid--detail .question-details {
    display: block;
  }
  .mobile-back {
    display: inline-flex;
  }
  .question-copy > span {
    max-width: 65vw;
  }
  .header-actions {
    gap: 4px;
  }
  .save-state {
    flex-basis: 100%;
  }
}
</style>
