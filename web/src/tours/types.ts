import type { Config, Side } from 'driver.js'

/** driver.js-Optionen einer Tour, ohne die Schritte und die Hooks, die die Engine für Events und Fortschritt besitzt. */
export type TourOptions = Omit<Config, 'steps' | 'onHighlighted' | 'onNextClick' | 'onDestroyStarted' | 'onElementMissing'>

export type TourButton = 'next' | 'previous' | 'close'
export type TourStatus = 'new' | 'seen' | 'completed' | 'skipped'

export interface TourStep {
  /** Muss zur Step-ID im Tour-Register der API (services/tours.py) passen. */
  id: string
  /** CSS-Selektor des hervorgehobenen Elements, bevorzugt [data-tour="..."]. */
  element: string
  title: string
  description: string
  side?: Side
  /** Standard: zurück (ab Schritt 2), weiter, schließen. */
  buttons?: TourButton[]
  /** Weitere Selektoren, die während des Schritts bedienbar bleiben. */
  allowedElements?: string[]
}

export interface TourDefinition {
  /** Muss zur Tour-ID im Register der API (services/tours.py) passen. */
  id: string
  title: string
  description: string
  steps: TourStep[]
  /** Interaktionsmodus und Darstellung; ohne Angabe gelten die Standardwerte von driver.js. */
  options?: TourOptions
  /** `true` oder der Grund, warum die Tour gerade nicht startbar ist. */
  available?: () => true | string
}

/** Ereignisse einer Tour; Komponenten leiten sie als Emits weiter. */
export type TourEvent = { type: 'start'; tourId: string } | { type: 'step'; tourId: string; stepId: string; index: number } | { type: 'completed'; tourId: string } | { type: 'skipped'; tourId: string; stepId?: string } | { type: 'unavailable'; tourId: string; stepId?: string }
