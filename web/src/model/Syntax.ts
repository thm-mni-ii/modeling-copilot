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

/** forbid = keine Verbindung darf einen Zyklus schließen; every = jedes Element liegt auf einem Zyklus; any = mindestens ein Zyklus im Diagramm */
export type CycleMode = 'forbid' | 'every' | 'any'

/** Zyklus-Regel; ohne Regel sind Zyklen erlaubt. Der Name bleibt, damit gespeicherte Sprachen gültig bleiben. */
export interface AcyclicRule {
  ruleType: 'acyclic'
  config: {
    messageTemplate: string
    /** Nur diese Verbindungstypen zählen für den Zyklus; leer = alle */
    connectionTypes?: string[]
    /** Ohne Angabe forbid */
    mode?: CycleMode
    /** Nur bei every: diese Elementtypen müssen auf einem Zyklus liegen; leer = alle */
    elementTypes?: string[]
    /** Zyklen unabhängig von der Kantenrichtung, z.B. Leitungen im Schaltplan */
    ignoreDirection?: boolean
  }
}

export type DiagramSyntax = MultiplicityRule | ContainmentRule | AcyclicRule
