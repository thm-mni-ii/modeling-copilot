import type { DiagramElement } from './Element'
import type { DiagramConnection } from './Connection'
import type { DiagramSyntax, MultiplicityCardinality } from './Syntax'
import type { GlobalSettings } from './GlobalSettings'
import type { DiagramFeedbackConfig } from './Feedback'
import { createEmptyFeedbackConfig } from '@/utils/feedbackConfig'
import { DEFAULT_CONNECTION_MESSAGE_TEMPLATES, DEFAULT_CONTAINMENT_MESSAGE, DEFAULT_ENDPOINT_MESSAGES, DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE } from '@/utils/syntaxMessages'

export type { DiagramElement } from './Element'
export type { DiagramConnection } from './Connection'
export type { DiagramSyntax } from './Syntax'
export type { GlobalSettings } from './GlobalSettings'
export type { DiagramFeedbackConfig } from './Feedback'

/** Members within each category are pairwise candidates; overlapping groups do not imply transitivity. */
export interface ComparisonGroup {
  id: string
  name: string
  elementTypes?: string[]
  connectionTypes?: string[]
  /** Nur Elementgruppen: Verbindungen werden gegen die Elemente hinter Mitgliedern geprüft, z. B. Ereignis → AND → Ereignis wie Ereignis → Ereignis */
  passThrough?: boolean
  /** Nur Elementgruppen: Jedes Mitglied muss mindestens eine Form erfüllen */
  branching?: { forms: BranchingForm[] }
}

/** Form eines verzweigenden Elements, z. B. Split (1 rein, ≥2 raus) oder Join (≥2 rein, 1 raus) */
export interface BranchingForm {
  name: string
  incoming: MultiplicityCardinality
  outgoing: MultiplicityCardinality
  /** Mitglied → Elementtypen, nach denen es diese Form nicht haben darf */
  notAfter?: Record<string, string[]>
  /** Nur diese Verbindungstypen zählen für die Form; leer oder fehlend = alle */
  connectionTypes?: string[]
}

export interface DiagramEvaluationConfig {
  comparisonGroups: ComparisonGroup[]
}

/** Complete editor payload stored unchanged in `LanguageVersion.data`. */
export interface DiagramLanguage {
  elements: DiagramElement[]
  connections: DiagramConnection[]
  syntax: DiagramSyntax[]
  globalSettings?: GlobalSettings
  feedback: DiagramFeedbackConfig
  /** Absent in older definitions: only identical types are candidates. */
  evaluation?: DiagramEvaluationConfig
}

export const createEmptyDiagramLanguage = (): DiagramLanguage => ({
  elements: [],
  connections: [],
  evaluation: { comparisonGroups: [] },
  syntax: [
    {
      ruleType: 'multiplicity',
      config: {
        messageTemplate: DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE,
        ...DEFAULT_CONNECTION_MESSAGE_TEMPLATES,
        endpointMessages: { ...DEFAULT_ENDPOINT_MESSAGES },
        defaultState: 'forbidden',
        relations: [],
        incoming: []
      }
    },
    { ruleType: 'containment', config: { relations: [], messageTemplate: DEFAULT_CONTAINMENT_MESSAGE } }
  ],
  feedback: createEmptyFeedbackConfig()
})
