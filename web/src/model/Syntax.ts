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

/** Eingehende Kanten pro Elementtyp, über alle Quelltypen gezählt */
export interface IncomingCardinality {
  elementType: string
  cardinality: MultiplicityCardinality
}

export interface MultiplicityConfig {
  messageTemplate: string
  relations: MultiplicityRelation[]
  /** Ohne Eintrag ist die Zahl eingehender Kanten frei */
  incoming?: IncomingCardinality[]
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
