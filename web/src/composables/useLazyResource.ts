import { onUnmounted, reactive, ref, type Ref } from 'vue'

/** Data of one endpoint that is fetched on demand (`ensure`), kept afterwards and ignored when it arrives stale. */
export const useLazyResource = <T>(fetcher: () => Promise<T>, failure: string | ((error: unknown) => string)) => {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref('')
  let generation = 0
  const load = async () => {
    const request = ++generation
    loading.value = true
    error.value = ''
    try {
      const result = await fetcher()
      if (request === generation) data.value = result
    } catch (e) {
      if (request === generation) error.value = typeof failure === 'function' ? failure(e) : failure
    } finally {
      if (request === generation) loading.value = false
    }
  }
  const ensure = () => (data.value || loading.value ? Promise.resolve() : load())
  const reset = () => {
    generation++
    data.value = null
    loading.value = false
    error.value = ''
  }
  onUnmounted(() => { generation++ })
  return reactive({ data, loading, error, load, ensure, reset })
}
