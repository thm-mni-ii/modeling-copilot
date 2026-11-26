<template>
  <SidebarFrame v-model:width="sidebarWidth" side="right" :class="{ 'sidebar-help-active': helpFlowActive }" :show-tabs="!helpFlowActive" :collapsed="hasJourney ? false : collapsed" :min-width="hasJourney ? 280 : 105" :max-width="maxWidth">
    <template v-if="hasJourney" #top><slot name="top" /></template>
    <template #tabs>
      <SidebarTabs :inert="toolsDisabled || undefined" :model-value="shownTab" :tabs="tabs" icons-only aria-label="Model tools" @update:model-value="selectTab" />
    </template>
    <template #default>
      <SidebarPanelHeader v-show="!helpFlowActive" :title="activeTabLabel" />
      <div v-show="!helpFlowActive" class="sidebar-tab-content" :inert="toolsDisabled || undefined">
        <FeedbackSidebar v-if="shownTab === 'feedback'" :feedback-shapes="feedbackShapes" :show-header="false" />
        <SidebarPersistence v-else-if="shownTab === 'persistence'" :show-header="false" />
        <SidebarSync v-else-if="shownTab === 'sync'" :show-header="false" />
        <TaskEditsSidebar v-else-if="shownTab === 'task'" :task-edit="taskEdit ?? null" :sync-state="taskEditSyncState" :selected-edit-ids="selectedTaskEditIds" @focus-edit="emit('focus-task-edit', $event)" @remove-edit="emit('remove-task-edit', $event)" />
        <EvaluationSidebar v-else-if="shownTab === 'evaluations'" :model-id="evaluationModelId" :open-evaluation-id="openEvaluationId ?? null" :evaluation-perspective="evaluationPerspective" :hint-request="hintRequest" @evaluation-updated="emit('evaluation-updated', $event)" @service-detail-opened="sidebarWidth = maxWidth" />
        <SidebarLibrary v-else-if="shownTab === 'languages'" ref="languageLibrary" />
      </div>
    </template>
  </SidebarFrame>
</template>

<script lang="ts">
import { ref } from 'vue'

// Neben der Komponente gehalten, damit der Tab beim Teilen (Neuaufbau der Ansicht) erhalten bleibt.
const activeTab = ref<'feedback' | 'persistence' | 'sync' | 'languages' | 'task' | 'evaluations'>('languages')
</script>

<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import type { EvaluationOutcome } from '@/services/api/types/evaluation'
import type { TaskEditDocument } from '@/services/api/types/model'
import type { TaskEditFocus, TaskEditSyncState } from '@/utils/taskEdits'
import SidebarLibrary from './SidebarLibrary.vue'
import SidebarFrame from './SidebarFrame.vue'
import SidebarPanelHeader from './SidebarPanelHeader.vue'
import SidebarPersistence from './SidebarPersistence.vue'
import SidebarSync from './SidebarSync.vue'
import SidebarTabs, { type SidebarTabItem } from './SidebarTabs.vue'
import FeedbackSidebar from './FeedbackSidebar.vue'
import TaskEditsSidebar from './TaskEditsSidebar.vue'
import EvaluationSidebar from './EvaluationSidebar.vue'
import { currentShare } from '@/collab/sharing/shareModel'
import { sharedTaskSettings } from '@/collab/worksheet/sharedTask'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'

type SidebarTab = 'feedback' | 'persistence' | 'sync' | 'languages' | 'task' | 'evaluations'

const props = defineProps<{
  collapsed: boolean
  toolsDisabled?: boolean
  helpFlowActive?: boolean
  hasJourney?: boolean
  taskActive?: boolean
  taskEdit?: TaskEditDocument | null
  taskEditSyncState?: TaskEditSyncState
  selectedTaskEditIds?: string[]
  modelId?: string | null
  openEvaluationId?: string | null
  evaluationPerspective?: 'service' | 'student'
  hintRequest?: { evaluationId: string; cellId?: string; seq: number; noticeViewed?: boolean } | null
  feedbackShapes?: Array<{
    name: string
    label: string
    style?: Record<string, any>
  }>
}>()

const emit = defineEmits<{
  'evaluation-updated': [evaluation: EvaluationOutcome]
  'remove-task-edit': [id: string]
  'update-task-edit-document': [document: JsonObject]
  'focus-task-edit': [target: TaskEditFocus]
}>()

const workspace = useModelWorkspaceStore()
// The share of this browser only counts as this view's room while its room model is open.
const share = computed(() => (currentShare.value?.linkedModelId === props.modelId ? currentShare.value : null))
const foreignShare = computed(() => Boolean(currentShare.value) && !share.value)
// In a room only the host evaluates, on the private model; otherwise the open model needs a task with a sample solution.
const canEvaluate = computed(() => Boolean(share.value ? share.value.privateModelId && sharedTaskSettings.value?.evaluationAvailable : workspace.taskVersion?.evaluationAvailable))
const evaluationModelId = computed(() => share.value?.privateModelId ?? props.modelId ?? null)

// One rule for every tab: it shows while it has something to work with (`active`) or something to report (`notice`).
// Both come from state, not from the panel: a hidden panel is not mounted and could not report anything.
const tabs = computed(() => {
  // In learning paths (hasJourney, only set with stepRun) everyone works alone with the task's languages: no sharing, no model import/export, no language setup.
  const freeModeling = !props.hasJourney
  const all: Array<SidebarTabItem & { active: boolean }> = [
    { value: 'task', icon: 'mdi-clipboard-edit-outline', label: 'Task', active: Boolean(props.taskActive) },
    { value: 'evaluations', icon: 'mdi-chart-timeline-variant', label: 'Auswertungen', active: Boolean(props.openEvaluationId || props.hintRequest || (props.taskActive && canEvaluate.value)) },
    { value: 'persistence', icon: 'mdi-import', label: 'Import/Export', active: freeModeling },
    { value: 'sync', icon: 'mdi-sync', label: 'Collab', active: freeModeling, notice: foreignShare.value ? 'Another model is still shared in this browser' : undefined },
    { value: 'languages', icon: 'mdi-bookshelf', label: 'Languages', active: freeModeling }
  ]
  return all.filter((tab) => tab.active || tab.notice)
})
// `activeTab` is what the user chose; while that tab is hidden another one stands in, without taking focus to a notice.
const shownTab = computed(() => (tabs.value.find((tab) => tab.value === activeTab.value) ?? tabs.value.find((tab) => tab.value === 'task') ?? tabs.value.find((tab) => tab.value === 'languages') ?? tabs.value[0])?.value ?? '')

const DEFAULT_WIDTH = 210
const sidebarWidth = ref(DEFAULT_WIDTH)
const maxWidth = computed(() => (props.hasJourney ? 484 : 347))
const languageLibrary = ref<InstanceType<typeof SidebarLibrary> | null>(null)
const openLanguages = async () => {
  if (props.hasJourney) return
  activeTab.value = 'languages'
  await nextTick()
  void languageLibrary.value?.openGuidedDialog()
}
defineExpose({ openLanguages })
watch(() => props.hintRequest, request => {
  if (!request || request.noticeViewed === false) return
  activeTab.value = 'evaluations'
  sidebarWidth.value = maxWidth.value
}, { immediate: true })
watch(() => props.hasJourney, (hasJourney) => {
  sidebarWidth.value = hasJourney ? Math.max(280, sidebarWidth.value) : DEFAULT_WIDTH
}, { immediate: true })
const activeTabLabel = computed(() => tabs.value.find((tab) => tab.value === shownTab.value)?.label ?? '')
const selectTab = (value: string) => {
  activeTab.value = value as SidebarTab
}
watch(
  () => props.openEvaluationId,
  (id) => { if (id) activeTab.value = 'evaluations' },
  { immediate: true }
)
</script>

<style scoped>
.sidebar-help-active :deep(.sidebar-frame__top) {
  max-height: 100%;
}

.sidebar-tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
