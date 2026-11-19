<template>
  <div class="historical-evaluation">
    <EvaluationSidebar :model-id="modelId" :open-evaluation-id="evaluationId" :evaluation-perspective="perspective" historical @evaluation-updated="emit('evaluation-updated', $event)" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Graph } from '@maxgraph/core'
import type { EvaluationOutcome } from '@/services/api/types/evaluation'
import { provideGraphContext } from '@/composables/useGraphContext'
import { provideModelFileContext, useModelFileContext } from '@/composables/useModelFileContext'
import EvaluationSidebar from '../sidebars/EvaluationSidebar.vue'

const props = defineProps<{ modelId: string; evaluationId: string; perspective?: 'student' | 'service'; graph?: Graph }>()
const emit = defineEmits<{ 'evaluation-updated': [evaluation: EvaluationOutcome] }>()
// Historical feedback must never inherit the editor's graph or completion criteria.
provideGraphContext({ graph: computed(() => props.graph), isPanning: ref(false), gridSize: ref(10),
  snapToGrid: ref(false), tolerance: ref(0), useGridForPanning: ref(false) })
const files = useModelFileContext()
if (files) provideModelFileContext({ ...files, completionGate: ref(null) })
</script>

<style scoped>
.historical-evaluation :deep(.evaluation-sidebar) { height: auto; }
.historical-evaluation :deep(.evaluation-sidebar__body),
.historical-evaluation :deep(.evaluation-sidebar__toolbar-title),
.historical-evaluation :deep(.feedback-catalog__name) { overflow: visible; white-space: normal; overflow-wrap: anywhere; }
.historical-evaluation :deep(.json-result-viewer__pre) { max-height: none; overflow: visible; }
.historical-evaluation :deep(.v-slide-group__container) { overflow: visible; }
.historical-evaluation :deep(.v-slide-group__content) { flex-wrap: wrap; }
</style>
