import { computed, ref, shallowRef, watch } from 'vue'
import { InternalEvent } from '@maxgraph/core'
import { useGraphContextOptional } from './useGraphContext'
import { createFeedbackValidity } from '@/utils/feedbackValidity'

export function useFeedbackValidity(snapshotXml: () => string | null | undefined) {
  const context = useGraphContextOptional()
  const currentIds = shallowRef(new Set<string>())
  const changed = ref(false)
  watch([() => context?.graph.value, snapshotXml], ([graph, xml], _, onCleanup) => {
    currentIds.value = new Set()
    changed.value = false
    if (!graph) return
    const evaluate = createFeedbackValidity(xml)
    const refresh = () => {
      const next = evaluate(graph)
      changed.value = Boolean(xml) && next.changed
      if (currentIds.value.size !== next.currentIds.size || [...currentIds.value].some(id => !next.currentIds.has(id))) currentIds.value = next.currentIds
    }
    graph.getDataModel().addListener(InternalEvent.CHANGE, refresh)
    refresh()
    onCleanup(() => graph.getDataModel().removeListener(refresh))
  }, { immediate: true })
  const isCurrent = computed(() => { const ids = currentIds.value; return (id: string) => ids.has(id) })
  return { isCurrent, changed }
}
