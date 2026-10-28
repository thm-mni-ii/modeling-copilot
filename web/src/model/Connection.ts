import type { CellStyle } from '@maxgraph/core'

export interface ConnectionLabelCell {
  id?: string
  type: string // Typ-Identifikator fuer das Label
  text: string
  geometry?: {
    x: number
    y: number
    relative?: boolean
    offsetX?: number
    offsetY?: number
    width?: number
    height?: number
  }
  style?: CellStyle
  connectable?: boolean
  allowLabelEdit?: boolean
}

export interface DiagramConnection {
  type: string // Typ-Identifikator (z.B. "uml-inheritance") - entspricht maxGraph's Typ-Konzept
  label: string // Anzeigename fuer UI (z.B. "Vererbung")
  defaultLabel?: string // Optionales Standard-Label fuer neue Instanzen im Graph
  connectionType?: string // Semantischer Typ (z.B. "inheritance", "association")
  style: CellStyle
  connectable?: boolean
  // Position des Haupt-Labels: x relativ entlang der Kante (-1 Start, 0 Mitte, 1 Ende), y in Pixeln, positiv nach oben
  labelOffset?: {
    x?: number
    y?: number
  }
  points?: { x: number; y: number }[]
  additionalLabels?: ConnectionLabelCell[]
}

export interface DiagramConnectionGroup {
  id: string
  label: string
  connections: DiagramConnection[]
}
