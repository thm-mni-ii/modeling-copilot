import { onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { isAxiosError } from 'axios'
import type { ApiId } from '@/services/api/types/common'
import type { EvaluationOutcome } from '@/services/api/types/evaluation'
import { useUserStore } from '@/stores/userStore'

/** Each display supplies its own endpoint; only request lifetime and polling are shared. */
export function useEvaluationResult<T extends EvaluationOutcome>(
  evaluationId: () => ApiId,
  read: (id: ApiId) => Promise<{ data: T }>,
  allowed: () => boolean = () => true
) {
  const user = useUserStore()
  const result = shallowRef<T | null>(null)
  const loading = ref(false)
  const polling = ref(false)
  const error = ref<string | null>(null)
  let generation = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let disposed = false

  const stop = () => {
    generation++
    clearTimeout(timer)
    timer = undefined
    polling.value = false
    loading.value = false
  }

  const refresh = async (request: number) => {
    if (disposed || request !== generation || !user.loaded || !allowed()) return
    loading.value = true
    try {
      const response = await read(evaluationId())
      if (disposed || request !== generation) return
      result.value = response.data
      error.value = null
      if (!['succeeded', 'failed', 'cancelled'].includes(response.data.state)) {
        polling.value = true
        timer = setTimeout(() => void refresh(request), 2_000)
      } else polling.value = false
    } catch (cause) {
      if (disposed || request !== generation) return
      if (isAxiosError(cause) && [401, 403, 404].includes(cause.response?.status ?? 0)) result.value = null
      error.value = 'Auswertung konnte nicht geladen werden.'
      polling.value = false
    } finally {
      if (!disposed && request === generation) loading.value = false
    }
  }

  const reload = async () => {
    stop()
    await refresh(generation)
  }

  watch([evaluationId, () => user.userId, () => user.globalRole, () => user.loaded, allowed], () => {
    stop()
    result.value = null
    error.value = null
    void refresh(generation)
  }, { immediate: true, flush: 'sync' })
  onBeforeUnmount(() => { disposed = true; stop() })

  return { result, loading, polling, error, reload }
}
