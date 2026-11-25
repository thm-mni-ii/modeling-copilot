import { constants, TextShape, type AbstractGraph, type Cell, type CellEditorHandler, type CellState, type Graph, type TooltipHandler } from '@maxgraph/core'

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

/** Inline tags kept when an existing label is edited; new formatting uses the whole-label style instead. */
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

const FORMAT_TAG_NAMES: Record<TextFormat, readonly string[]> = { bold: ['b', 'strong'], italic: ['i', 'em'], underline: ['u'] }

const labelRoot = (label: string): HTMLElement => {
  const root = document.createElement('div')
  root.innerHTML = sanitizeLabelHtml(label) // inspection only; sanitized tags carry no attributes
  return root
}

/** Whether tags of the format cover all visible text: the rule the evaluation applies (model-label-extraction). */
function coveredByTags(root: HTMLElement, format: TextFormat): boolean {
  const tags = FORMAT_TAG_NAMES[format]
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  let visible = false
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.textContent?.trim()) continue
    visible = true
    let parent = node.parentElement
    while (parent && parent !== root && !tags.includes(parent.tagName.toLowerCase())) parent = parent.parentElement
    if (!parent || parent === root) return false
  }
  return visible
}

/**
 * Toggles a format for the whole label, also in the open label editor.
 * New formatting only sets `fontStyle`; switching off also drops tags of this format
 * when they cover the whole text. Partial inline formatting is never touched.
 */
export function formatText(graph: AbstractGraph, format: TextFormat): void {
  const editor = graph.getPlugin<CellEditorHandler>('CellEditorHandler')
  const editing = graph.isEditing() ? editor?.getEditingCell() ?? null : null
  const textarea = editing ? editor?.textarea ?? null : null
  const cells = editing ? [editing] : graph.getSelectionCells()
  if (cells.length === 0) return

  const flag = FONT_STYLE_FLAGS[format]
  const fontStyleOf = (cell: Cell) => Number(graph.getCurrentCellStyle(cell).fontStyle ?? 0)
  const textOf = (cell: Cell) => (cell === editing && textarea ? textarea : labelRoot(graph.convertValueToString(cell)))
  const enable = !cells.every((cell) => (fontStyleOf(cell) & flag) !== 0 || coveredByTags(textOf(cell), format))
  const model = graph.getDataModel()
  model.batchUpdate(() => {
    for (const cell of cells) {
      // Effective value incl. the language default, so other default flags survive an explicit override.
      const fontStyle = fontStyleOf(cell)
      model.setStyle(cell, { ...cell.getClonedStyle(), fontStyle: enable ? fontStyle | flag : fontStyle & ~flag })
      if (enable) continue
      if (cell === editing && textarea && coveredByTags(textarea, format)) {
        textarea.querySelectorAll(FORMAT_TAG_NAMES[format].join(',')).forEach((element) => element.replaceWith(...element.childNodes))
      }
      // Also the stored label while editing, so cancelling the editor leaves no covering tag behind.
      const label = cell.getValue()
      if (typeof label === 'string' && coveredByTags(labelRoot(label), format)) {
        model.setValue(cell, label.replace(new RegExp(`</?(${FORMAT_TAG_NAMES[format].join('|')})\\s*/?>`, 'gi'), ''))
      }
    }
  })

  // maxGraph applies fontStyle to the in-place editor only when editing starts.
  if (editing && textarea) {
    const fontStyle = fontStyleOf(editing)
    const masks = constants.FONT_STYLE_MASK
    textarea.style.fontWeight = fontStyle & masks.BOLD ? 'bold' : 'normal'
    textarea.style.fontStyle = fontStyle & masks.ITALIC ? 'italic' : ''
    textarea.style.textDecoration = [fontStyle & masks.UNDERLINE ? 'underline' : '', fontStyle & masks.STRIKETHROUGH ? 'line-through' : ''].filter(Boolean).join(' ')
  }
}

/** Bereinigt Labels und Tooltips eines Graphen mit HTML-Labels vor der Anzeige. */
export function protectHtmlLabels(graph: Graph): void {
  const getLabel = graph.getLabel.bind(graph)
  graph.getLabel = (cell?: Cell | null) => {
    const alternative = cell?.isCollapsed() ? (cell as any).collapsedConfig?.label : undefined
    const showAlternative = typeof alternative === 'string' && alternative.length > 0 && cell && graph.isLabelsVisible() && !graph.getCurrentCellStyle(cell).noLabel
    const label = showAlternative ? alternative : getLabel(cell)
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

/** maxGraph reads the style `labelPadding` but never draws it; here it grows the label background. */
class PaddedTextShape extends TextShape {
  // apply() skips labelPadding, so refresh it on every style change
  override apply(state: CellState): void {
    super.apply(state)
    this.labelPadding = Number(this.style?.labelPadding) || 0
  }

  override createSvgCanvas() {
    const canvas = super.createSvgCanvas()
    if (canvas && this.labelPadding > 0) {
      const getTextCss = canvas.getTextCss.bind(canvas)
      canvas.getTextCss = () => `${getTextCss()}padding: ${this.labelPadding}px; `
    }
    return canvas
  }
}

/** Draws the style `labelPadding` (px) on all labels of the graph. */
export function enableLabelPadding(graph: Graph): void {
  graph.cellRenderer.defaultTextShape = PaddedTextShape
}
