<template>
  <SidebarFrame v-model:width="sidebarWidth" side="right" :class="{ 'sidebar-help-active': helpFlowActive }" :show-tabs="!helpFlowActive" :collapsed="hasJourney ? false : collapsed" :min-width="hasJourney ? 280 : 105" :max-width="hasJourney ? 440 : 315">
    <template v-if="hasJourney" #top><slot name="top" /></template>
    <template #tabs>
      <SidebarTabs :inert="toolsDisabled || undefined" :model-value="activeTab" :tabs="tabs" icons-only aria-label="Model tools" @update:model-value="selectTab" />
    </template>
    <template #default>
      <SidebarPanelHeader v-show="!helpFlowActive" :title="activeTabLabel" />
      <div v-show="!helpFlowActive" class="sidebar-tab-content" :inert="toolsDisabled || undefined">
        <FeedbackSidebar v-if="activeTab === 'feedback'" :feedback-shapes="feedbackShapes" :show-header="false" />
        <SidebarPersistence v-else-if="activeTab === 'persistence'" :show-header="false" />
        <SidebarSync v-else-if="activeTab === 'sync'" :show-header="false" />
        <TaskEditsSidebar v-else-if="activeTab === 'task'" :task-edit="taskEdit ?? null" :sync-state="taskEditSyncState" :selected-edit-ids="selectedTaskEditIds" @focus-edit="emit('focus-task-edit', $event)" @remove-edit="emit('remove-task-edit', $event)" />
        <EvaluationSidebar v-else-if="activeTab === 'evaluations'" :model-id="evaluationModelId" :open-evaluation-id="openEvaluationId ?? null" :evaluation-perspective="evaluationPerspective" @evaluation-updated="emit('evaluation-updated', $event)" />
        <SidebarLibrary v-else ref="languageLibrary" />
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
import type { EvaluationDetail } from '@/services/api/types/evaluation'
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
  feedbackShapes?: Array<{
    name: string
    label: string
    style?: Record<string, any>
  }>
}>()

const emit = defineEmits<{
  'evaluation-updated': [evaluation: EvaluationDetail]
  'remove-task-edit': [id: string]
  'update-task-edit-document': [document: JsonObject]
  'focus-task-edit': [target: TaskEditFocus]
}>()

const baseTabs: SidebarTabItem[] = [
  { value: 'persistence', icon: 'mdi-import', label: 'Import/Export' },
  { value: 'sync', icon: 'mdi-sync', label: 'Collab' },
  { value: 'languages', icon: 'mdi-bookshelf', label: 'Languages' }
]
// In learning paths (hasJourney, only set with stepRun) everyone works on the task alone, so there is no sharing.
const visibleBaseTabs = computed(() => (props.hasJourney ? baseTabs.filter((tab) => tab.value !== 'sync') : baseTabs))
// In a room only the host evaluates, on the private model, and only if the task has a workflow.
const evaluationsActive = computed(() => !currentShare.value || Boolean(currentShare.value.privateModelId && sharedTaskSettings.value?.evaluationAvailable))
const evaluationModelId = computed(() => currentShare.value?.privateModelId ?? props.modelId ?? null)
const tabs = computed<SidebarTabItem[]>(() => (props.taskActive ? [{ value: 'task', icon: 'mdi-clipboard-edit-outline', label: 'Task' }, ...(evaluationsActive.value ? [{ value: 'evaluations', icon: 'mdi-chart-timeline-variant', label: 'Auswertungen' }] : []), ...visibleBaseTabs.value] : visibleBaseTabs.value))

const DEFAULT_WIDTH = 210
const sidebarWidth = ref(DEFAULT_WIDTH)
const languageLibrary = ref<InstanceType<typeof SidebarLibrary> | null>(null)
const openLanguages = async () => {
  activeTab.value = 'languages'
  await nextTick()
  void languageLibrary.value?.openGuidedDialog()
}
defineExpose({ openLanguages })
watch(() => props.hasJourney, (hasJourney) => {
  sidebarWidth.value = hasJourney ? Math.max(280, sidebarWidth.value) : DEFAULT_WIDTH
}, { immediate: true })
// A previously opened collab tab would otherwise stay visible in a learning path without its tab.
watch(
  () => props.hasJourney,
  (hasJourney) => {
    if (hasJourney && activeTab.value === 'sync') activeTab.value = 'languages'
  },
  { immediate: true }
)
const activeTabLabel = computed(() => tabs.value.find((tab) => tab.value === activeTab.value)?.label ?? '')
const selectTab = (value: string) => {
  activeTab.value = value as SidebarTab
}
watch(
  () => props.taskActive,
  (taskActive) => {
    if (!taskActive && activeTab.value === 'task') activeTab.value = 'languages'
  }
)
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
