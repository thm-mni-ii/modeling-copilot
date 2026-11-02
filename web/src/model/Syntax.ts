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

/** Number of edges of an element in one direction; empty fields match everything */
export interface EdgeCardinality {
  /** Empty = any element */
  elementType: string
  /** Defaults to incoming; both = either edge end may be at the element */
  direction?: EdgeDirection
  /** Empty = all connection types */
  connectionTypes?: string[]
  /** Element types at the other edge end; empty = all */
  neighborTypes?: string[]
  cardinality: MultiplicityCardinality
  /** Empty = template of the rule */
  messageTemplate?: string
}

export interface MultiplicityConfig {
  messageTemplate: string
  relations: MultiplicityRelation[]
  /** Edge rules per element; the name stays so stored languages remain valid */
  incoming?: EdgeCardinality[]
}

export interface MultiplicityRule {
  ruleType: 'multiplicity'
  config: MultiplicityConfig
}

/** A container accepts only the listed element types; containers without an entry accept everything. */
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

/** forbid = no connection may close a cycle; every = every element lies on a cycle; any = at least one cycle in the diagram */
export type CycleMode = 'forbid' | 'every' | 'any'

/** Cycle rule; without a rule cycles are allowed. The name stays so stored languages remain valid. */
export interface AcyclicRule {
  ruleType: 'acyclic'
  config: {
    messageTemplate: string
    /** Only these connection types count for the cycle; empty = all */
    connectionTypes?: string[]
    /** Defaults to forbid */
    mode?: CycleMode
    /** Only for every: these element types must lie on a cycle; empty = all */
    elementTypes?: string[]
    /** Cycles regardless of edge direction, e.g. wires in a circuit diagram */
    ignoreDirection?: boolean
  }
}

export type DiagramSyntax = MultiplicityRule | ContainmentRule | AcyclicRule
