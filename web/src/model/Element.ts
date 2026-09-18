export interface ElementStyle {
  shape?: string
  strokeColor: string
  fillColor: string
  strokeWidth: number
  fontSize: number
  fontColor: string
  fontFamily: string
  fontStyle?: number
  align: string
  verticalAlign: string
  // Swimlane-spezifische Eigenschaften (basierend auf MaxGraph Beispielen)
  startSize?: number
  horizontal?: boolean
  labelBackgroundColor?: string
  swimlaneLine?: boolean // Trennlinie zwischen Titel- und Inhaltsbereich
  swimlaneFillColor?: string // Füllfarbe des Inhaltsbereichs (separat von fillColor der Titelleiste)
  separatorColor?: string // Farbe der Trennlinien zwischen Lanes
  direction?: 'north' | 'south' | 'east' | 'west' // Ausrichtung von Titel/Inhalt
  // Auto-Layout Optionen für Container/Swimlanes
  layoutPreset?: 'free' | 'list' | 'custom' // UI-Vorauswahl: 'free'/'list' setzen die Optionen unten fest, 'custom' macht sie editierbar
  containerLayout?: 'free' | 'list' // Grundverhalten: 'free' = freie Positionierung (z.B. Aktivitätsdiagramm-Pool/Lane), 'list' = geordnete, automatisch gestapelte Liste (z.B. UML-Attribute)
  // Optionen für containerLayout === 'list'
  listDirection?: 'vertical' | 'horizontal' // Stapelrichtung der Children
  listItemSpacing?: number // Abstand zwischen Elementen in Stapelrichtung
  listCrossPadding?: number // Innenabstand quer zur Stapelrichtung
  listStretchCrossAxis?: boolean // Elemente quer zur Stapelrichtung auf Container-Maß strecken
  resizeMainAxis?: boolean // Container in Stapelrichtung automatisch an Inhalt anpassen
  resizeCrossAxis?: boolean // Container quer zur Stapelrichtung anpassen (nur wirksam wenn listStretchCrossAxis = false)
  minWidth?: number // Untere Größengrenze (z.B. damit der Titel nicht abgeschnitten wird)
  minHeight?: number
  // Optionen für containerLayout === 'free'
  resizeToContent?: 'none' | 'grow' // 'grow': Container wächst bei Bedarf, schrumpft aber nie automatisch
  contentPadding?: number // Mindestabstand der Elemente zum Rand für die Wachstumsberechnung
  // Collapse/Folding
  foldable?: boolean // Ob Element zusammenklappbar ist
  // Allgemeine Shape-Feinabstimmung
  rounded?: boolean | number
  spacingLeft?: number
  whiteSpace?: string
  // Optional: semantische Rollen/Layer-Bindungen (z.B. fuer Feedback-Elemente)
  cellRole?: string
  lockToLayer?: boolean | number
}

export interface AnchorPoint {
  x: number
  y: number
}

export interface CollapsedAppearance {
  width?: number
  height?: number
  label?: string
  style?: ElementStyle
}

interface BaseElement<TChild> {
  type: string // Typ-Identifikator (z.B. "uml-class") - entspricht maxGraph's Multiplicity.type und dient als Bezeichnung
  defaultLabel: string // Standard-Label für neue Instanzen im Graph (z.B. "Klassenname")
  renderMode: 'canvas2d' | 'predefined' | 'swimlane' // Art der Darstellung
  canvas?: string
  predefinedShape?: string
  style: ElementStyle
  children: TChild[]
  connectable?: boolean // Optional mit Default false für ChildElements
  // Collapse-Konfiguration
  collapsible?: boolean // Ob das Element zusammenklappbar ist
  collapsed?: CollapsedAppearance // Darstellung im zusammengeklappten Zustand
  allowLabelEdit?: boolean // Ob das Label im Canvas bearbeitet werden darf (Standard: true)
}

export interface DiagramElement extends BaseElement<ChildElement> {
  x: number
  y: number
  width: number
  height: number
  anchorPoints: AnchorPoint[]
  resizable: boolean
  movable: boolean
  connectable: boolean // Überschreibt das optionale connectable von BaseElement
}

export interface ChildElement extends BaseElement<ChildElement> {
  position: {
    x: number
    y: number
    width: number
    height: number
    relative: boolean
  }
}
