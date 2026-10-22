import { useBearerToken } from '@/composables/useBearerToken'
import { collabUrl } from './collabApi'
import type { CollabKitApi } from './collabKitV1'

let loading: Promise<CollabKitApi> | null = null

// collab-kit serves its own client library, so it always fits the running instance; manage-v1.js defines <ck-management>.
export const loadCollabKit = (): Promise<CollabKitApi> => {
  const url = collabUrl
  if (!url) return Promise.reject(new Error('VITE_COLLAB_URL is not set.'))
  loading ??= Promise.all([import(/* @vite-ignore */ `${url}/client/v1.js`) as Promise<typeof import('./collabKitV1')>, import(/* @vite-ignore */ `${url}/client/manage-v1.js`)])
    .then(([{ createCollabKitApi }]) => createCollabKitApi({ url, getToken: () => useBearerToken().bearerToken.value }))
    .catch((error) => {
      // Forgotten, so the next connect tries again once collab-kit is up.
      loading = null
      throw error
    })
  return loading
}
