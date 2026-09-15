import type { ModelPatch } from '@/services/api/types/model'

const PATCH_NAMESPACE = 'urn:ietf:rfc:7351'

const parseXml = (xml: string) => {
  const document = new DOMParser().parseFromString(xml, 'application/xml')
  if (document.querySelector('parsererror')) throw new Error('Invalid XML.')
  return document
}

const cellsById = (document: Document) => {
  const result = new Map<string, Element>()
  for (const cell of document.querySelectorAll('GraphDataModel > root > Cell')) {
    const id = cell.getAttribute('id')?.trim() ?? ''
    if (!id) throw new Error('Every model Cell needs a non-empty ID.')
    if (result.has(id)) throw new Error(`Duplicate model Cell ID: ${id}`)
    result.set(id, cell)
  }
  if (result.size === 0) throw new Error('The model contains no Cells.')
  return result
}

const selectorFor = (id: string) => {
  if (!id.includes("'")) return `GraphDataModel/root/Cell[@id='${id}']`
  if (!id.includes('"')) return `GraphDataModel/root/Cell[@id="${id}"]`
  throw new Error('Cell IDs must not contain both quote characters.')
}

const selectedId = (selector: string) => {
  const match = selector.match(/^\/?GraphDataModel\/root\/Cell\[@id=(['"])(.+)\1\]$/)
  if (!match) throw new Error('Unsupported model patch selector.')
  return match[2]
}

export const validateModelCellIds = (xml: string) => void cellsById(parseXml(xml))

/** Creates one ordered RFC-7351 document for the changed Cells. */
export const createModelPatch = (beforeXml: string, afterXml: string): string | null => {
  const before = parseXml(beforeXml)
  const after = parseXml(afterXml)
  const beforeCells = cellsById(before)
  const afterCells = cellsById(after)
  const patch = before.implementation.createDocument(PATCH_NAMESPACE, 'p:patch')
  const root = patch.documentElement

  for (const [id] of beforeCells) {
    if (afterCells.has(id)) continue
    const operation = patch.createElementNS(PATCH_NAMESPACE, 'p:remove')
    operation.setAttribute('sel', selectorFor(id))
    root.append(operation)
  }
  for (const [id, cell] of afterCells) {
    const oldCell = beforeCells.get(id)
    if (!oldCell) {
      const operation = patch.createElementNS(PATCH_NAMESPACE, 'p:add')
      operation.setAttribute('sel', 'GraphDataModel/root')
      operation.setAttribute('pos', 'append')
      operation.append(patch.importNode(cell, true))
      root.append(operation)
    } else if (!oldCell.isEqualNode(cell)) {
      const operation = patch.createElementNS(PATCH_NAMESPACE, 'p:replace')
      operation.setAttribute('sel', selectorFor(id))
      operation.append(patch.importNode(cell, true))
      root.append(operation)
    }
  }

  return root.childElementCount > 0 ? new XMLSerializer().serializeToString(patch) : null
}

export const applyModelPatches = (baseXml: string, patches: readonly Pick<ModelPatch, 'xml'>[]) => {
  const model = parseXml(baseXml)
  for (const entry of patches) {
    const patch = parseXml(entry.xml)
    if (patch.documentElement.namespaceURI !== PATCH_NAMESPACE || patch.documentElement.localName !== 'patch') throw new Error('Invalid model patch root.')
    for (const operation of Array.from(patch.documentElement.children)) {
      if (operation.namespaceURI !== PATCH_NAMESPACE) throw new Error('Invalid model patch operation.')
      if (operation.localName === 'add') {
        if (operation.getAttribute('sel')?.replace(/^\//, '') !== 'GraphDataModel/root') throw new Error('Unsupported add selector.')
        if ((operation.getAttribute('pos') ?? 'append') !== 'append') throw new Error('Unsupported add position.')
        const cell = Array.from(operation.children).find((child) => child.tagName === 'Cell')
        const container = model.querySelector('GraphDataModel > root')
        if (!cell || !container) throw new Error('Invalid add operation.')
        container.append(model.importNode(cell, true))
        continue
      }
      const id = selectedId(operation.getAttribute('sel') ?? '')
      const target = Array.from(cellsById(model).entries()).find(([candidate]) => candidate === id)?.[1]
      if (!target) throw new Error(`Missing model patch target: ${id}`)
      if (operation.localName === 'remove') target.remove()
      else if (operation.localName === 'replace') {
        const replacement = Array.from(operation.children).find((child) => child.tagName === 'Cell')
        if (!replacement || replacement.getAttribute('id') !== id) throw new Error('Invalid replace operation.')
        target.replaceWith(model.importNode(replacement, true))
      } else throw new Error('Unsupported model patch operation.')
    }
  }
  const result = new XMLSerializer().serializeToString(model)
  validateModelCellIds(result)
  return result
}
