/** One cell as the Yjs document keeps it: its place among its siblings and its XML. */
export interface SharedCell {
  index: number
  xml: string
}

const CELLS = 'GraphDataModel > root > Cell'

const parseXml = (xml: string) => {
  const document = new DOMParser().parseFromString(xml, 'application/xml')
  if (document.querySelector('parsererror')) throw new Error('Invalid model XML.')
  return document
}

/** Splits an exported model into its cells by ID; the export lists siblings in their order. */
export const splitModel = (xml: string) => {
  const cells = new Map<string, SharedCell>()
  const siblings = new Map<string, number>()
  const serializer = new XMLSerializer()

  for (const cell of parseXml(xml).querySelectorAll(CELLS)) {
    const id = cell.getAttribute('id')
    if (!id) continue
    const parent = cell.getAttribute('parent') ?? ''
    const index = siblings.get(parent) ?? 0
    siblings.set(parent, index + 1)
    cells.set(id, { index, xml: serializer.serializeToString(cell) })
  }
  return cells
}

/**
 * Builds the model from shared cells: parents before children, siblings by index, then by ID.
 * Leaves out what concurrent deletes strand, cells without parent and edges without an end,
 * as maxGraph would read a cell without parent as the root. Null without a root cell.
 */
export const joinModel = (cells: ReadonlyMap<string, SharedCell>) => {
  const document = parseXml(`<GraphDataModel><root>${Array.from(cells.values(), (cell) => cell.xml).join('')}</root></GraphDataModel>`)
  const elements = new Map<string, Element>()
  const children = new Map<string, string[]>()

  for (const element of document.querySelectorAll(CELLS)) {
    const id = element.getAttribute('id')
    if (!id) continue
    const parent = element.getAttribute('parent') ?? ''
    const siblings = children.get(parent) ?? []
    siblings.push(id)
    children.set(parent, siblings)
    elements.set(id, element)
  }

  // Plain comparison, so every browser sorts the same way whatever its locale.
  const place = (id: string) => cells.get(id)?.index ?? 0
  for (const ids of children.values()) ids.sort((a, b) => place(a) - place(b) || (a < b ? -1 : a > b ? 1 : 0))

  // Only what hangs below the root is reachable, so a cell whose parent is gone drops out.
  const reachable = new Set<string>()
  const reach = (parent: string) => {
    for (const id of children.get(parent) ?? []) {
      reachable.add(id)
      reach(id)
    }
  }
  reach('')

  const isLoose = (element: Element) => ['source', 'target'].some((end) => element.hasAttribute(end) && !reachable.has(element.getAttribute(end) ?? ''))
  const ordered: Element[] = []
  const collect = (parent: string) => {
    for (const id of children.get(parent) ?? []) {
      const element = elements.get(id)
      if (!element || isLoose(element)) continue
      ordered.push(element)
      collect(id)
    }
  }
  collect('')
  if (ordered.length === 0) return null

  document.querySelector('GraphDataModel > root')?.replaceChildren(...ordered)
  return new XMLSerializer().serializeToString(document)
}
