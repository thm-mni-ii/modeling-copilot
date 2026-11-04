import type { JsonObject } from '@/services/api/types/common'

export interface JsonPatch { op: 'add' | 'remove' | 'replace'; path: string; value?: unknown }

const escape = (key: string) => key.replace(/~/g, '~0').replace(/\//g, '~1')

/** RFC 6902 operations; array edits preserve unchanged prefixes and suffixes. */
export const createJsonPatch = (before: unknown, after: unknown, path = ''): JsonPatch[] => {
  if (JSON.stringify(before) === JSON.stringify(after)) return []
  if (before && after && typeof before === 'object' && typeof after === 'object' && !Array.isArray(before) && !Array.isArray(after)) {
    const left = before as Record<string, unknown>, right = after as Record<string, unknown>
    return [...new Set([...Object.keys(left), ...Object.keys(right)])].flatMap((key): JsonPatch[] => {
      const childPath = `${path}/${escape(key)}`
      if (!(key in right)) return [{ op: 'remove', path: childPath }]
      if (!(key in left)) return [{ op: 'add', path: childPath, value: right[key] }]
      return createJsonPatch(left[key], right[key], childPath)
    })
  }
  if (Array.isArray(before) && Array.isArray(after)) {
    if (before.length === after.length) return after.flatMap((item, index) => createJsonPatch(before[index], item, `${path}/${index}`))
    let start = 0, endBefore = before.length, endAfter = after.length
    while (start < endBefore && start < endAfter && JSON.stringify(before[start]) === JSON.stringify(after[start])) start++
    while (endBefore > start && endAfter > start && JSON.stringify(before[endBefore - 1]) === JSON.stringify(after[endAfter - 1])) { endBefore--; endAfter-- }
    const shared = Math.min(endBefore - start, endAfter - start)
    const operations = after.slice(start, start + shared).flatMap((item, index) => createJsonPatch(before[start + index], item, `${path}/${start + index}`))
    for (let index = endBefore - 1; index >= start + shared; index--) operations.push({ op: 'remove', path: `${path}/${index}` })
    for (let index = start + shared; index < endAfter; index++) operations.push({ op: 'add', path: `${path}/${index}`, value: after[index] })
    return operations
  }
  return [{ op: 'replace', path, value: after }]
}

export const applyJsonPatches = (document: JsonObject, patches: JsonPatch[]): JsonObject => {
  let result = JSON.parse(JSON.stringify(document)) as JsonObject
  for (const patch of patches) {
    if (!patch.path) { result = structuredClone(patch.value) as JsonObject; continue }
    const keys = patch.path.slice(1).split('/').map((key) => key.replace(/~1/g, '/').replace(/~0/g, '~'))
    if (keys.some((key) => ['__proto__', 'constructor', 'prototype'].includes(key))) throw new Error('Invalid JSON patch path.')
    let parent: Record<string, unknown> = result
    for (const key of keys.slice(0, -1)) parent = parent[key] as Record<string, unknown>
    const key = keys[keys.length - 1]
    if (patch.op === 'remove') {
      if (Array.isArray(parent)) parent.splice(Number(key), 1)
      else delete parent[key]
    } else if (patch.op === 'add' && Array.isArray(parent)) parent.splice(Number(key), 0, structuredClone(patch.value))
    else parent[key] = structuredClone(patch.value)
  }
  return result
}
