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
        <SidebarLibrary v-else />
      </div>
    </template>
  </SidebarFrame>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SidebarLibrary from './SidebarLibrary.vue'
import SidebarFrame from './SidebarFrame.vue'
import SidebarPanelHeader from './SidebarPanelHeader.vue'
import SidebarPersistence from './SidebarPersistence.vue'
import SidebarSync from './SidebarSync.vue'
import SidebarTabs, { type SidebarTabItem } from './SidebarTabs.vue'
import FeedbackSidebar from './FeedbackSidebar.vue'

type SidebarTab = 'feedback' | 'persistence' | 'sync' | 'languages'

defineProps<{
  collapsed: boolean
  feedbackShapes?: Array<{
    name: string
    label: string
    style?: Record<string, any>
  }>
}>()

const tabs: SidebarTabItem[] = [
  { value: 'feedback', icon: 'mdi-comment-text-multiple-outline', label: 'Feedback' },
  { value: 'persistence', icon: 'mdi-import', label: 'Import/Export' },
  { value: 'sync', icon: 'mdi-sync', label: 'Sync' },
  { value: 'languages', icon: 'mdi-bookshelf', label: 'Languages' }
]

const DEFAULT_WIDTH = 210
const sidebarWidth = ref(DEFAULT_WIDTH)
const activeTab = ref<SidebarTab>('languages')
const activeTabLabel = computed(() => tabs.find((tab) => tab.value === activeTab.value)?.label ?? '')
const selectTab = (value: string) => {
  activeTab.value = value as SidebarTab
}
</script>

<style scoped>
.sidebar-tab-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
