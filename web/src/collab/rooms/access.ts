import { loadCollabKit } from '@/collab/connection/collabKit'
import type { Right } from '@/collab/connection/collabKitV1'

/** The six rights of collab-kit; plan and decide matter once tasks come in. */
const ALL_RIGHTS: Right[] = ['see', 'speak', 'edit', 'plan', 'decide', 'manage']

export type AccessLevel = 'read' | 'edit' | 'manage'

/** What the dialog offers instead of the single rights. */
export const ACCESS_LEVELS: { value: AccessLevel; title: string; rights: Right[] }[] = [
  { value: 'read', title: 'Read', rights: ['see'] },
  { value: 'edit', title: 'Edit', rights: ['see', 'speak', 'edit'] },
  { value: 'manage', title: 'Manage', rights: ALL_RIGHTS }
]

export const rightsOf = (level: AccessLevel) => ACCESS_LEVELS.find((entry) => entry.value === level)?.rights ?? []

/** The level these rights make up, or null when they were set some other way. */
export const levelOf = (rights: readonly Right[]): AccessLevel | null => ACCESS_LEVELS.find((entry) => entry.rights.length === rights.length && entry.rights.every((right) => rights.includes(right)))?.value ?? null

export const describeRights = (rights: readonly Right[]) => ACCESS_LEVELS.find((entry) => entry.value === levelOf(rights))?.title ?? `Custom (${rights.join(', ')})`

/** Rooms and groups lie in nothing, so creating them takes manage everywhere; false when collab-kit cannot be reached. */
export const mayManageAll = async () => {
  try {
    const ck = await loadCollabKit()
    return (await ck.me.rights()).includes('manage')
  } catch {
    return false
  }
}
