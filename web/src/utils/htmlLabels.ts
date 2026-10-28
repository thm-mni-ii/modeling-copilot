import { constants, type Cell, type Graph, type TooltipHandler } from '@maxgraph/core'

/** Formatierungen, die in HTML-Labels als Tag erhalten bleiben (nur ohne Attribute). */
const ALLOWED_TAGS = ['b', 'strong', 'i', 'em', 'u', 'br', 'div']

const ALLOWED_TAG_PATTERN = new RegExp(`&lt;(/?)(${ALLOWED_TAGS.join('|')})\\s*/?&gt;`, 'gi')

const escapeHtml = (text: string): string => text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/**
 * Macht einen Label-Text sicher für HTML-Labels: Alles wird als Text maskiert,
 * nur einfache Formatierungs-Tags ohne Attribute werden wieder zu Tags.
 * Verhindert, dass Labels Script ausführen (z.B. `<img onerror=…>`), und zeigt
 * Text wie `<<abstract>>` unverändert an.
 */
export function sanitizeLabelHtml(label: string): string {
  return escapeHtml(label).replace(ALLOWED_TAG_PATTERN, '<$1$2>')
}

/** Formatierungen, die der Label-Editor (Cmd/Strg+B, I, U) ins Label übernimmt. */
const FORMAT_TAGS = new Set(['b', 'strong', 'i', 'em', 'u'])
const BLOCK_TAGS = new Set(['div', 'p'])

/** HTML für den Label-Editor: Formatierungen als Tags, Zeilenumbrüche als `<br>`. */
export function labelToEditorHtml(label: string): string {
  return sanitizeLabelHtml(label)
    .replace(/\n+$/, (newlines) => '<div><br></div>'.repeat(newlines.length))
    .replace(/\n/g, '<br>')
}

/**
 * Liest den Inhalt des Label-Editors zurück: Text bleibt Text, Formatierungen
 * bleiben als Tag ohne Attribute, Zeilen werden zu `\n`. Alles andere fällt weg.
 */
export function editorHtmlToLabel(root: Node): string {
  let label = ''

  const walk = (node: Node) => {
    node.childNodes.forEach((child) => {
      if (child.nodeType === Node.TEXT_NODE) {
        label += child.textContent ?? ''
        return
      }
      if (!(child instanceof HTMLElement)) return

      const tag = child.tagName.toLowerCase()
      if (tag === 'br') {
        label += '\n'
        return
      }
      if (BLOCK_TAGS.has(tag) && label.length > 0 && !label.endsWith('\n')) {
        label += '\n'
      }

      const keep = FORMAT_TAGS.has(tag)
      if (keep) label += `<${tag}>`
      walk(child)
      if (keep) label += `</${tag}>`
    })
  }

  walk(root)
  return label.replace(/\n$/, '')
}

export type TextFormat = 'bold' | 'italic' | 'underline'

const FONT_STYLE_FLAGS: Record<TextFormat, number> = {
  bold: constants.FONT_STYLE_MASK.BOLD,
  italic: constants.FONT_STYLE_MASK.ITALIC,
  underline: constants.FONT_STYLE_MASK.UNDERLINE
}

/**
 * Formatiert Text: Im offenen Label-Editor nur die Markierung (wie Cmd/Strg+B),
 * sonst das ganze Label der ausgewählten Elemente über `fontStyle`.
 */
export function formatText(graph: Graph, format: TextFormat): void {
  if (graph.isEditing()) {
    document.execCommand(format)
    return
  }

  const cells = graph.getSelectionCells()
  if (cells.length > 0) {
    graph.toggleCellStyleFlags('fontStyle', FONT_STYLE_FLAGS[format], cells)
  }
}

/** Bereinigt Labels und Tooltips eines Graphen mit HTML-Labels vor der Anzeige. */
export function protectHtmlLabels(graph: Graph): void {
  const getLabel = graph.getLabel.bind(graph)
  graph.getLabel = (cell?: Cell | null) => {
    const label = getLabel(cell)
    return label === null ? null : sanitizeLabelHtml(label)
  }

  const tooltipHandler = graph.getPlugin<TooltipHandler>('TooltipHandler')
  if (tooltipHandler) {
    const getTooltipForCell = tooltipHandler.getTooltipForCell.bind(tooltipHandler)
    tooltipHandler.getTooltipForCell = (cell: Cell) => {
      const tooltip = getTooltipForCell(cell)
      return typeof tooltip === 'string' ? sanitizeLabelHtml(tooltip) : tooltip
    }
  }
}
