import { loadCollabKit } from '@/collab/kit/collabKit'

/** Rooms and groups lie in nothing, so creating them takes manage everywhere; false when collab-kit cannot be reached. */
export const mayManageAll = async () => {
  try {
    const ck = await loadCollabKit()
    return (await ck.me.rights()).includes('manage')
  } catch {
    return false
  }
}
