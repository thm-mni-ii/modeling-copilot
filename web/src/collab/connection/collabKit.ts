import { useBearerToken } from '@/composables/useBearerToken'
import { collabUrl } from './collabApi'
import type { CollabKitApi } from './collabKitV1'

type CollabKitV1 = typeof import('./collabKitV1')

let loading: Promise<CollabKitApi> | null = null
let library: CollabKitV1 | null = null

// collab-kit serves its own client library, so it always fits the running instance; manage-v1.js defines <ck-management>.
export const loadCollabKit = (): Promise<CollabKitApi> => {
  const url = collabUrl
  if (!url) return Promise.reject(new Error('VITE_COLLAB_URL is not set.'))
  loading ??= Promise.all([import(/* @vite-ignore */ `${url}/client/v1.js`) as Promise<CollabKitV1>, import(/* @vite-ignore */ `${url}/client/manage-v1.js`)])
    .then(([loaded]) => {
      library = loaded
      return loaded.createCollabKitApi({ url, getToken: () => useBearerToken().bearerToken.value })
    })
    .catch((error) => {
      // Forgotten, so the next connect tries again once collab-kit is up.
      loading = null
      throw error
    })
  return loading
}

/** Whether a key collab-kit answered with is a pseudonym; keys come only from it, so the library is loaded by then. */
export const isPseudonym = (key: string) => library?.isPseudonym(key) ?? false
