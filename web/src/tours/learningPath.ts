import type { HelpRequest, HelpTourAnswer } from '@/services/learningPaths'
import type { TourDefinition } from './types'

// Schritt-IDs müssen zum Tour-Register der API passen (services/tours.py).
export const learningPathTour: TourDefinition = {
  id: 'help-feedback',
  title: 'Automatisches Feedback entdecken',
  description: 'Eine geführte Hilfeanfrage mit Modellprüfung.',
  // Die Lernenden bedienen die Seite selbst; die Tour folgt ihrem Zustand und wird nicht per Tastatur oder Overlay gesteuert.
  options: { allowPageInteraction: true, disableActiveInteraction: false, allowKeyboardControl: false, overlayClickBehavior: 'none', showProgress: false },
  steps: [
    { id: 'intro', element: '[data-help-feedback-legend]', title: 'Neue Hilfe für deine Aufgabe', description: 'Entdecke die fünf neuen Hilfefunktionen und Wie du sie nutzen kannst.', side: 'left', buttons: ['next', 'close'] },
    { id: 'check', element: '[data-help-feedback-type="help.check"]', title: 'Prüfung', description: 'Prüfe deinen bisherigen Modellstand. Die Anzeige zeigt deine Nutzungen und das für diese Aufgabe erlaubte Kontingent. ∞ bedeutet unbegrenzt.', side: 'left', buttons: ['previous', 'next', 'close'] },
    { id: 'clarify', element: '[data-help-feedback-type="help.clarify"]', title: 'Erklärung', description: 'Lass dir eine ausgewählte Problemstelle erklären. Wie oft diese Hilfe verfügbar ist, zeigt das Kontingent darunter.', side: 'left', buttons: ['previous', 'next', 'close'] },
    { id: 'next-step', element: '[data-help-feedback-type="help.next_step"]', title: 'Nächster Schritt', description: 'Erhalte einen Hinweis, wie du an deiner Problemstelle weiterarbeiten kannst. Wie oft diese Hilfe verfügbar ist, zeigt das Kontingent darunter.', side: 'left', buttons: ['previous', 'next', 'close'] },
    { id: 'example', element: '[data-help-feedback-type="help.example"]', title: 'Beispiel', description: 'Ein Beispiel kann dir bei deiner Problemstelle helfen. Die Anzeige zeigt links deine Nutzungen und rechts das verfügbare Kontingent.', side: 'left', buttons: ['previous', 'next', 'close'] },
    { id: 'solution', element: '[data-help-feedback-type="help.solution"]', title: 'Lösung', description: 'Zeigt eine konkrete Lösung zur Problemstelle. Ist das eingestellte Kontingent aufgebraucht, wird die Anzeige ausgegraut und die Hilfe kann nicht mehr ausgewählt werden.', side: 'left', buttons: ['previous', 'next', 'close'] },
    { id: 'request-help', element: '[data-help-sign]', title: 'Hilfe anfordern', description: 'Um Hilfe zu erhalten, klicke zunächst auf "Ich brauche Hilfe".', side: 'left', buttons: ['close'] },
    { id: 'describe-problem', element: '.help-flow-card', title: 'Dein Problem beschreiben', description: 'Wähle "Aufgabenstellung/Modell" und klicke dort auf "Weiter".', side: 'left', buttons: ['close'] },
    { id: 'load-questionnaire', element: '.help-flow-card', title: 'Fragebogen laden', description: 'Der nächste Fragebogen wird geladen.', side: 'left', buttons: ['close'] },
    { id: 'estimate-duration', element: '.help-flow-card', title: 'Dauer einschätzen', description: 'Gib an, wie lange du bei deinem Problem feststeckst, und klicke im Fragebogen auf "Weiter".', side: 'left', buttons: ['close'] },
    { id: 'choose-support', element: '[data-help-tour-choice="support_need"]', allowedElements: ['.help-flow-card'], title: 'Unterstützung auswählen', description: 'Wähle für diese Tour die Prüfung deiner bisherigen Lösung. Eine erfolgreiche Auswertung zählt als Nutzung der Feedbackart „Prüfung“.', side: 'left', buttons: ['close'] },
    { id: 'confirm-support', element: '.help-flow-card .sd-navigation__complete-btn', allowedElements: ['.help-flow-card'], title: 'Auswahl bestätigen', description: 'Klicke auf "Weiter", um deine Unterstützungsauswahl zu bestätigen.', side: 'left', buttons: ['close'] },
    { id: 'mark-problem', element: '[data-help-marking-panel]', title: 'Problemstelle markieren', description: 'Für die gewählte Unterstützung kannst du hier ein passendes Modellelement markieren und danach auf "Weiter" klicken.', side: 'left', buttons: ['close'] },
    { id: 'choose-action', element: '[data-help-tour-choice="next_action"]', allowedElements: ['.help-flow-card'], title: 'Modell automatisch prüfen', description: 'Wähle "Automatische Überprüfung des Modells".', side: 'left', buttons: ['close'] },
    { id: 'start-check', element: '.help-flow-card .sd-navigation__complete-btn', allowedElements: ['.help-flow-card'], title: 'Überprüfung starten', description: 'Klicke auf "Hilfe auswählen". Damit startest du eine echte Auswertung.', side: 'left', buttons: ['close'] },
    { id: 'choose-source', element: '.help-flow-card', title: 'Hilfequelle auswählen', description: 'Wähle eine verfügbare Hilfequelle und bestätige deine Auswahl im Fragebogen.', side: 'left', buttons: ['close'] }
  ]
}

/** Ab diesem Schritt (Index) folgt die Tour der Hilfeanfrage; davor sind es reine Erklärschritte. */
export const learningPathHelpStep = 6

/** Schritt-Index, der zum Zustand der laufenden Hilfeanfrage passt. */
export const learningPathStepIndex = (request: HelpRequest, question?: string | null, answer?: HelpTourAnswer | null) =>
  learningPathHelpStep + (request.stage === 'reflection' ? (question === 'stuck_duration' ? 3 : question === 'support_need' ? (answer?.question === 'support_need' && answer.selected ? 5 : 4) : 2) : request.stage === 'action' ? (request.supportKind !== 'help.check' ? 9 : answer?.question === 'next_action' && answer.selected ? 8 : 7) : { topic: 1, marking: 6 }[request.stage as 'topic' | 'marking'])
