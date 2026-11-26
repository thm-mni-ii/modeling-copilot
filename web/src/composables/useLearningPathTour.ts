import { computed, nextTick, onBeforeUnmount, watch } from 'vue'
import { useTours } from '@/composables/useTours'
import { learningPathHelpStep, learningPathStepIndex, learningPathTour } from '@/tours/learningPath'
import type { HelpRequest, HelpTourAnswer, HelpUsage } from '@/services/learningPaths'

interface LearningPathTourState {
  featureTourEnabled?: boolean
  feedbackAvailable?: boolean
  helpUsage?: HelpUsage
  helpRequest?: HelpRequest | null
  helpQuestion?: string | null
  helpAnswer?: HelpTourAnswer | null
}

// Farben der Schatzreise für TourList (siehe --tour-* dort).
const tourTheme = { '--tour-accent': '#765035', '--tour-accent-text': '#fffaf0', '--tour-bg': '#fffaf0', '--tour-header-bg': '#ffda86', '--tour-text': '#473722', '--tour-border': '#b28a4d' }

/** Meldet die Lernpfad-Tour an und lässt sie dem Zustand der Hilfeanfrage folgen. `props` muss reaktiv sein. */
export function useLearningPathTour(props: LearningPathTourState, checkExhausted: () => boolean) {
  const tourId = learningPathTour.id
  const { tours, register, unregister, moveTo, finish, on } = useTours()
  const tourEnabled = computed(() => Boolean(props.featureTourEnabled && props.feedbackAvailable))
  const tourAvailable = () => {
    if (props.helpRequest) return 'Beende zuerst deine laufende Hilfeanfrage, bevor du die Tour startest.'
    if (!props.helpUsage) return 'Die Hilfeanzeigen sind noch nicht verfügbar. Lade die Seite erneut, um die Tour zu starten.'
    if (checkExhausted()) return 'Für die geführte Modellprüfung ist in dieser Aufgabe keine Nutzung mehr verfügbar.'
    return true as const
  }
  watch(tourEnabled, (enabled) => (enabled ? register({ ...learningPathTour, available: tourAvailable }) : unregister(tourId)), { immediate: true })
  onBeforeUnmount(() => unregister(tourId))

  let activeIndex = -1
  let followVersion = 0
  const tourActive = () => Boolean(tours.value.find((tour) => tour.id === tourId)?.active)
  const followRequest = async () => {
    const version = ++followVersion
    if (!tourActive()) return
    const request = props.helpRequest
    if (!request || request.stage === 'cancelled') {
      if (request?.stage === 'cancelled' || activeIndex > learningPathHelpStep) finish(tourId, 'skipped')
      return
    }
    if (request.stage === 'completed') {
      finish(tourId, request.supportKind === 'help.check' && request.nextActionId === 'automatic_feedback' ? 'completed' : 'skipped')
      return
    }
    const stepId = learningPathTour.steps[learningPathStepIndex(request, props.helpQuestion, props.helpAnswer)].id
    await nextTick()
    if (version === followVersion && tourActive()) moveTo(tourId, stepId)
  }
  on(
    (event) => {
      activeIndex = event.type === 'step' ? event.index : -1
    },
    { tourId }
  )
  on(followRequest, { type: 'start', tourId })
  watch(() => [props.helpRequest?.id, props.helpRequest?.stage, props.helpRequest?.nextActionId, props.helpQuestion, props.helpAnswer?.question, props.helpAnswer?.selected], followRequest, { flush: 'post' })

  return { tourId, tourEnabled, tourTheme }
}
