<template>
  <SidebarFrame v-model:width="sidebarWidth" side="right" :collapsed="collapsed">
    <template #tabs>
      <SidebarTabs :model-value="activeTab" :tabs="tabs" icons-only aria-label="Model tools" @update:model-value="selectTab" />
    </template>
    <template #default>
      <SidebarPanelHeader :title="activeTabLabel" />
      <div class="sidebar-tab-content">
        <FeedbackSidebar v-if="activeTab === 'feedback'" :feedback-shapes="feedbackShapes" :show-header="false" />
        <SidebarPersistence v-else-if="activeTab === 'persistence'" :show-header="false" />
        <SidebarSync v-else-if="activeTab === 'sync'" :show-header="false" />
        <TaskEditsSidebar v-else-if="activeTab === 'task'" :task-edit="taskEdit ?? null" :sync-state="taskEditSyncState" @focus-edit="emit('focus-task-edit', $event)" @remove-edit="emit('remove-task-edit', $event)" @restore-document="emit('update-task-edit-document', $event)" />
        <EvaluationSidebar v-else-if="activeTab === 'evaluations'" :model-id="modelId ?? null" :open-evaluation-id="openEvaluationId ?? null" />
        <SidebarLibrary v-else />
      </div>
    </template>
  </SidebarFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import type { TaskEditDocument } from '@/services/api/types/model'
import type { TaskEditSyncState } from '@/utils/taskEdits'
import SidebarLibrary from './SidebarLibrary.vue'
import SidebarFrame from './SidebarFrame.vue'
import SidebarPanelHeader from './SidebarPanelHeader.vue'
import SidebarPersistence from './SidebarPersistence.vue'
import SidebarSync from './SidebarSync.vue'
import SidebarTabs, { type SidebarTabItem } from './SidebarTabs.vue'
import FeedbackSidebar from './FeedbackSidebar.vue'
import TaskEditsSidebar from './TaskEditsSidebar.vue'
import EvaluationSidebar from './EvaluationSidebar.vue'

type SidebarTab = 'feedback' | 'persistence' | 'sync' | 'languages' | 'task' | 'evaluations'

const props = defineProps<{
  collapsed: boolean
  taskActive?: boolean
  taskEdit?: TaskEditDocument | null
  taskEditSyncState?: TaskEditSyncState
  modelId?: string | null
  openEvaluationId?: string | null
  feedbackShapes?: Array<{
    name: string
    label: string
    style?: Record<string, any>
  }>
}>()

const emit = defineEmits<{
  'remove-task-edit': [id: string]
  'update-task-edit-document': [document: JsonObject]
  'focus-task-edit': [id: string]
}>()

const baseTabs: SidebarTabItem[] = [
  { value: 'feedback', icon: 'mdi-comment-text-multiple-outline', label: 'Feedback' },
  { value: 'persistence', icon: 'mdi-import', label: 'Import/Export' },
  { value: 'sync', icon: 'mdi-sync', label: 'Sync' },
  { value: 'languages', icon: 'mdi-bookshelf', label: 'Languages' }
]
const tabs = computed<SidebarTabItem[]>(() => (props.taskActive ? [{ value: 'task', icon: 'mdi-clipboard-edit-outline', label: 'Task' }, { value: 'evaluations', icon: 'mdi-chart-timeline-variant', label: 'Auswertungen' }, ...baseTabs] : baseTabs))

const DEFAULT_WIDTH = 210
const sidebarWidth = ref(DEFAULT_WIDTH)
const activeTab = ref<SidebarTab>('languages')
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
  (id) => { if (id) activeTab.value = 'evaluations' }
)
</script>

<style scoped>
.sidebar-tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
