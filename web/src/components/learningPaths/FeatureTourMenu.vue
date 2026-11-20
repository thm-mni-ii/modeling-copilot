<template>
  <v-btn class="feature-tour-trigger" variant="text" size="small" :aria-label="done ? 'Hilfe-Tour erneut öffnen' : 'Neue Hilfe-Funktionen entdecken'" :aria-expanded="open" @click="toggleChecklist">
    <v-badge v-if="loaded && !done" content="Neu" color="#a33d32" floating>
      <v-icon>mdi-help-circle-outline</v-icon>
    </v-badge>
    <v-icon v-else>mdi-help-circle-outline</v-icon>
  </v-btn>
  <Teleport to="body">
    <aside v-if="open" class="feature-checklist" aria-label="Neue Funktionen entdecken">
      <header class="feature-checklist-header">
        <div>
          <strong>Neue Funktionen entdecken</strong>
          <p>Erkunde die automatische Hilfe auf deiner Schatzreise.</p>
        </div>
        <button type="button" class="feature-checklist-close" aria-label="Checkliste zuklappen" @click="open = false">×</button>
        <div class="feature-checklist-progress">
          <progress :value="done ? 1 : 0" max="1" aria-label="Fortschritt der Checkliste" />
          <span>{{ done ? 1 : 0 }}/1</span>
        </div>
      </header>
      <div class="feature-checklist-body">
        <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-2">{{ error }} <v-btn size="x-small" variant="text" @click="loadProgress">Erneut laden</v-btn></v-alert>
        <div class="feature-checklist-item">
          <v-icon :color="done ? 'success' : undefined">{{ done ? 'mdi-check-circle' : 'mdi-circle-outline' }}</v-icon>
          <div>
            <strong>Automatisches Feedback entdecken</strong>
            <p>{{ done ? (skipped ? 'Übersprungen' : 'Angesehen') : 'Eine geführte Hilfeanfrage mit Modellprüfung.' }}</p>
          </div>
        </div>
        <p v-if="helpRequest" class="feature-checklist-note">Beende zuerst deine laufende Hilfeanfrage, bevor du die Tour startest.</p>
        <p v-else-if="!feedbackLegendAvailable" class="feature-checklist-note">Die Hilfeanzeigen sind noch nicht verfügbar. Lade die Seite erneut, um die Tour zu starten.</p>
        <p v-else-if="!checkAvailable" class="feature-checklist-note">Für die geführte Modellprüfung ist in dieser Aufgabe keine Nutzung mehr verfügbar.</p>
        <div class="feature-checklist-actions">
          <v-btn size="small" variant="flat" color="#765035" :disabled="starting || Boolean(helpRequest) || !feedbackLegendAvailable || !checkAvailable" @click="startTour">{{ done ? 'Erneut starten' : 'Tour starten' }}</v-btn>
          <v-btn v-if="!done" size="small" variant="text" :disabled="starting" @click="skipTour">Überspringen</v-btn>
        </div>
      </div>
    </aside>
    <div v-if="visible" class="feature-checklist-toggle">
      <button type="button" :aria-expanded="open" @click="toggleChecklist">
        Neue Funktionen <span>{{ done ? 1 : 0 }}/1</span> <v-icon size="16">{{ open ? 'mdi-chevron-down' : 'mdi-chevron-up' }}</v-icon>
      </button>
      <button type="button" class="feature-checklist-hide" aria-label="Neue Funktionen ausblenden" @click="hideChecklist">×</button>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { driver, type Driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import paths, { type HelpRequest, type HelpTourAnswer, type TourEventName, type TourProgress } from '@/services/learningPaths'
import { notifyError } from '@/composables/useNotifications'

const props = defineProps<{ feedbackLegendAvailable: boolean; checkAvailable: boolean; helpRequest?: HelpRequest | null; helpQuestion?: string | null; helpAnswer?: HelpTourAnswer | null }>()
const tourId = 'help-feedback'
const open = ref(false)
const visible = ref(false)
const starting = ref(false)
const loaded = ref(false)
const error = ref('')
const progress = ref<TourProgress>({ completed: false, skipped: false })
const done = computed(() => progress.value.completed || progress.value.skipped)
const skipped = computed(() => progress.value.skipped && !progress.value.completed)
let activeTour: Driver | null = null
let finishing = false
let disposed = false
let loadPromise: Promise<void> | null = null
let followVersion = 0

const updateProgress = (value: TourProgress) => {
  progress.value = { completed: progress.value.completed || value.completed, skipped: progress.value.skipped || value.skipped }
}
const loadProgress = () => {
  if (loadPromise) return loadPromise
  loadPromise = (async () => {
    try {
      const result = await paths.tourProgress(tourId)
      if (!disposed) {
        updateProgress(result.data)
        loaded.value = true
        error.value = ''
      }
    } catch {
      if (!disposed) error.value = 'Der Tour-Fortschritt konnte nicht geladen werden.'
    } finally {
      loadPromise = null
    }
  })()
  return loadPromise
}
const record = async (event: TourEventName, stepId?: string) => {
  try {
    const result = await paths.recordTourEvent(tourId, event, stepId)
    if (!disposed) {
      updateProgress(result.data)
      loaded.value = true
      error.value = ''
    }
  } catch {
    if (!disposed) {
      error.value = 'Der Tour-Fortschritt konnte nicht gespeichert werden. Bitte versuche es erneut.'
      notifyError(error.value)
    }
  }
}
const toggleChecklist = async () => {
  visible.value = true
  open.value = !open.value
  if (!open.value) return
  if (!loaded.value) await loadProgress()
  if (open.value) await record('opened')
}
const hideChecklist = () => {
  open.value = false
  visible.value = false
}
const skipTour = async () => {
  await record('skipped')
}

const helpStep = 6
// Same order as the steps below and the tour registry in the API (services/tours.py).
const stepIds = ['intro', 'check', 'clarify', 'next-step', 'example', 'solution', 'request-help', 'describe-problem', 'load-questionnaire', 'estimate-duration', 'choose-support', 'confirm-support', 'mark-problem', 'choose-action', 'start-check', 'choose-source']
const activeStepId = (current: Driver | null) => stepIds[current?.getActiveIndex() ?? -1]
// Step events are analytics only; a failed request must not disturb the learner.
const recordStep = (stepId: string | undefined) => {
  if (stepId) void paths.recordTourEvent(tourId, 'step', stepId).catch(() => undefined)
}
const steps: DriveStep[] = [
  {
    element: '[data-help-feedback-legend]',
    popover: { title: 'Neue Hilfe für deine Aufgabe', description: 'Entdecke die fünf neuen Hilfefunktionen und Wie du sie nutzen kannst.', side: 'left', showButtons: ['next', 'close'] }
  },
  {
    element: '[data-help-feedback-type="help.check"]',
    popover: { title: 'Prüfung', description: 'Prüfe deinen bisherigen Modellstand. Die Anzeige zeigt deine Nutzungen und das für diese Aufgabe erlaubte Kontingent. ∞ bedeutet unbegrenzt.', side: 'left', showButtons: ['previous', 'next', 'close'] }
  },
  {
    element: '[data-help-feedback-type="help.clarify"]',
    popover: { title: 'Erklärung', description: 'Lass dir eine ausgewählte Problemstelle erklären. Wie oft diese Hilfe verfügbar ist, zeigt das Kontingent darunter.', side: 'left', showButtons: ['previous', 'next', 'close'] }
  },
  {
    element: '[data-help-feedback-type="help.next_step"]',
    popover: { title: 'Nächster Schritt', description: 'Erhalte einen Hinweis, wie du an deiner Problemstelle weiterarbeiten kannst. Wie oft diese Hilfe verfügbar ist, zeigt das Kontingent darunter.', side: 'left', showButtons: ['previous', 'next', 'close'] }
  },
  {
    element: '[data-help-feedback-type="help.example"]',
    popover: { title: 'Beispiel', description: 'Ein Beispiel kann dir bei deiner Problemstelle helfen. Die Anzeige zeigt links deine Nutzungen und rechts das verfügbare Kontingent.', side: 'left', showButtons: ['previous', 'next', 'close'] }
  },
  {
    element: '[data-help-feedback-type="help.solution"]',
    popover: { title: 'Lösung', description: 'Zeigt eine konkrete Lösung zur Problemstelle. Ist das eingestellte Kontingent aufgebraucht, wird die Anzeige ausgegraut und die Hilfe steht nicht mehr zur Auswahl.', side: 'left', showButtons: ['previous', 'next', 'close'] }
  },
  {
    element: '[data-help-sign]',
    popover: { title: 'Hilfe anfordern', description: 'Um Hilfe zu erhalten, klicke zunächst auf "Ich brauche Hilfe".', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card',
    popover: { title: 'Dein Problem beschreiben', description: 'Wähle "Aufgabenstellung/Modell" und klicke dort auf "Weiter".', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card',
    popover: { title: 'Fragebogen laden', description: 'Der nächste Fragebogen wird geladen.', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card',
    popover: { title: 'Dauer einschätzen', description: 'Gib an, wie lange du bei deinem Problem feststeckst, und klicke im Fragebogen auf "Weiter".', side: 'left', showButtons: ['close'] }
  },
  {
    element: '[data-help-tour-choice="support_need"]',
    allowedElements: ['.help-flow-card'],
    popover: { title: 'Unterstützung auswählen', description: 'Wähle für diese Tour die Prüfung deiner bisherigen Lösung. Eine erfolgreiche Auswertung zählt als Nutzung der Feedbackart „Prüfung“.', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card .sd-navigation__complete-btn',
    allowedElements: ['.help-flow-card'],
    popover: { title: 'Auswahl bestätigen', description: 'Klicke auf "Weiter", um deine Unterstützungsauswahl zu bestätigen.', side: 'left', showButtons: ['close'] }
  },
  {
    element: '[data-help-marking-panel]',
    popover: { title: 'Problemstelle markieren', description: 'Für die gewählte Unterstützung kannst du hier ein passendes Modellelement markieren und danach auf "Weiter" klicken.', side: 'left', showButtons: ['close'] }
  },
  {
    element: '[data-help-tour-choice="next_action"]',
    allowedElements: ['.help-flow-card'],
    popover: { title: 'Modell automatisch prüfen', description: 'Wähle "Automatische Überprüfung des Modells".', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card .sd-navigation__complete-btn',
    allowedElements: ['.help-flow-card'],
    popover: { title: 'Überprüfung starten', description: 'Klicke auf "Hilfe auswählen". Damit startest du eine echte Auswertung.', side: 'left', showButtons: ['close'] }
  },
  {
    element: '.help-flow-card',
    popover: { title: 'Hilfequelle auswählen', description: 'Wähle eine verfügbare Hilfequelle und bestätige deine Auswahl im Fragebogen.', side: 'left', showButtons: ['close'] }
  }
]

const finish = (event: 'completed' | 'skipped') => {
  if (!activeTour || finishing) return
  finishing = true
  const stepId = activeStepId(activeTour)
  activeTour.destroy()
  activeTour = null
  void record(event, event === 'skipped' ? stepId : undefined)
}
const followRequest = async () => {
  const version = ++followVersion
  if (!activeTour || finishing) return
  const request = props.helpRequest
  if (!request || request.stage === 'cancelled') {
    if (request?.stage === 'cancelled' || (activeTour.getActiveIndex() ?? 0) > helpStep) finish('skipped')
    return
  }
  if (request.stage === 'completed') {
    finish(request.supportKind === 'help.check' && request.nextActionId === 'automatic_feedback' ? 'completed' : 'skipped')
    return
  }
  const index =
    helpStep +
    (request.stage === 'reflection'
      ? props.helpQuestion === 'stuck_duration'
        ? 3
        : props.helpQuestion === 'support_need'
        ? props.helpAnswer?.question === 'support_need' && props.helpAnswer.selected
          ? 5
          : 4
        : 2
      : request.stage === 'action'
      ? request.supportKind !== 'help.check'
        ? 9
        : props.helpAnswer?.question === 'next_action' && props.helpAnswer.selected
        ? 8
        : 7
      : { topic: 1, marking: 6 }[request.stage])
  await nextTick()
  if (version === followVersion && activeTour && !finishing && activeTour.getActiveIndex() !== index) activeTour.moveTo(index)
}
const startTour = async () => {
  if (starting.value || activeTour || props.helpRequest || !props.feedbackLegendAvailable || !props.checkAvailable) return
  starting.value = true
  await record('started')
  if (disposed) return
  open.value = false
  finishing = false
  activeTour = driver({
    steps,
    showProgress: false,
    allowPageInteraction: true,
    disableActiveInteraction: false,
    allowKeyboardControl: false,
    overlayClickBehavior: 'none',
    waitForElement: 10000,
    closeBtnLabel: 'Tour schließen',
    nextBtnText: 'Weiter',
    prevBtnText: 'Zurück',
    onHighlighted: (_element, _step, { driver: current }) => recordStep(activeStepId(current)),
    onElementMissing: (_element, _step, { driver: current }) => {
      if (finishing) return false
      finishing = true
      const stepId = activeStepId(current)
      current.destroy()
      activeTour = null
      error.value = 'Der nächste Tour-Schritt ist nicht verfügbar. Du kannst die Tour später erneut starten.'
      notifyError(error.value)
      void record('skipped', stepId)
      return false
    },
    onDestroyStarted: (_element, _step, { driver: current }) => {
      if (!finishing) {
        finishing = true
        void record('skipped', activeStepId(current))
      }
      current.destroy()
      activeTour = null
    }
  })
  activeTour.drive()
  starting.value = false
  await followRequest()
}
watch(() => [props.helpRequest?.id, props.helpRequest?.stage, props.helpRequest?.nextActionId, props.helpQuestion, props.helpAnswer?.question, props.helpAnswer?.selected], followRequest, { flush: 'post' })
onMounted(() => {
  void loadProgress()
})
onBeforeUnmount(() => {
  if (activeTour && !finishing) finish('skipped')
  disposed = true
})
</script>

<style scoped>
.feature-tour-trigger {
  min-width: 32px;
  padding-inline: 5px;
}
.feature-tour-trigger :deep(.v-badge__badge) {
  left: calc(100% - 18px) !important;
  font-size: 8px;
  height: 15px;
  min-width: 24px;
}
.feature-checklist {
  position: fixed;
  right: 20px;
  bottom: 76px;
  z-index: 2400;
  width: min(360px, calc(100vw - 32px));
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  border: 2px solid #765035;
  border-radius: 14px;
  background: #fffaf0;
  color: #473722;
  box-shadow: 0 5px 16px rgb(50 33 20 / 25%);
}
.feature-checklist-header {
  position: relative;
  padding: 16px;
  background: #ffda86;
  border-bottom: 2px solid #b28a4d;
}
.feature-checklist-header strong {
  font-size: 1.05rem;
}
.feature-checklist-header p,
.feature-checklist-item p {
  margin: 4px 0 0;
  font-size: 0.8rem;
  line-height: 1.4;
}
.feature-checklist-note {
  margin-top: 10px;
  font-size: 0.8rem;
}
.feature-checklist-close {
  position: absolute;
  top: 8px;
  right: 12px;
  border: 0;
  background: transparent;
  color: #473722;
  cursor: pointer;
  font-size: 1.4rem;
}
.feature-checklist-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 0.8rem;
}
.feature-checklist-progress progress {
  flex: 1;
  height: 9px;
  accent-color: #765035;
}
.feature-checklist-body {
  padding: 16px;
}
.feature-checklist-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.feature-checklist-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 14px;
}
.feature-checklist-actions :deep(.v-btn) {
  letter-spacing: 0;
  text-transform: none;
}
.feature-checklist-toggle {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 2400;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 2px solid #765035;
  border-radius: 10px;
  background: #ffda86;
  color: #473722;
  box-shadow: 0 4px 10px rgb(50 33 20 / 20%);
  font-weight: 600;
}
.feature-checklist-toggle button {
  display: flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  cursor: pointer;
}
.feature-checklist-hide {
  font-size: 1.25rem;
  line-height: 1;
}
.feature-checklist-toggle span {
  padding: 1px 5px;
  border-radius: 8px;
  background: #765035;
  color: #fffaf0;
  font-size: 0.75rem;
}
@media (max-width: 480px) {
  .feature-checklist,
  .feature-checklist-toggle {
    right: 16px;
  }
}
</style>
