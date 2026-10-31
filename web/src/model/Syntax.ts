export type MultiplicityRelationState = 'allowed' | 'forbidden'

export interface MultiplicityCardinality {
  min: number
  max: number | null
}

export interface MultiplicityRefinement {
  /** Leeres Array = alle Verbindungstypen erlaubt */
  connectionTypes: string[]
  cardinality: MultiplicityCardinality
}

export interface MultiplicityRelation {
  sourceType: string
  targetType: string
  state: MultiplicityRelationState
  refinement: MultiplicityRefinement
}

export type EdgeDirection = 'incoming' | 'outgoing' | 'both'

/** Zahl der Kanten eines Elements in einer Richtung; leere Felder passen auf alles */
export interface EdgeCardinality {
  /** Leer = jedes Element */
  elementType: string
  /** Ohne Angabe eingehend; both = egal, welches Kantenende am Element hängt */
  direction?: EdgeDirection
  /** Leer = alle Verbindungstypen */
  connectionTypes?: string[]
  /** Elementtypen am anderen Kantenende; leer = alle */
  neighborTypes?: string[]
  cardinality: MultiplicityCardinality
  /** Leer = Template der Regel */
  messageTemplate?: string
}

export interface MultiplicityConfig {
  messageTemplate: string
  relations: MultiplicityRelation[]
  /** Kantenregeln pro Element; der Name bleibt, damit gespeicherte Sprachen gültig bleiben */
  incoming?: EdgeCardinality[]
}

export interface MultiplicityRule {
  ruleType: 'multiplicity'
  config: MultiplicityConfig
}

/** Ein Container nimmt nur die genannten Elementtypen auf; Container ohne Eintrag nehmen alles auf. */
export interface ContainmentRelation {
  containerType: string
  childTypes: string[]
}

export interface ContainmentRule {
  ruleType: 'containment'
  config: {
    relations: ContainmentRelation[]
  }
}

/** Keine Verbindung darf einen Zyklus schließen; ohne Regel sind Zyklen erlaubt. */
export interface AcyclicRule {
  ruleType: 'acyclic'
  config: {
    messageTemplate: string
  }
}

export type DiagramSyntax = MultiplicityRule | ContainmentRule | AcyclicRule
