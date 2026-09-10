<template>
  <SidebarFrame v-model:width="sidebarWidth" side="left" :show-tabs="!modelManagement">
    <template v-if="!modelManagement" #tabs>
      <SidebarTabs :model-value="activeTab" :tabs="tabs" aria-label="Sidebar content" @update:model-value="selectTab" />
    </template>
    <template #default>
      <ElementsSidebar v-if="modelManagement" :languages="languages" :sidebar-width="sidebarWidth" />
      <SidebarSync v-else-if="activeTab === 'sync'" />
      <SidebarPersistence v-else-if="activeTab === 'persistence'" />
      <ElementsSidebar v-else :languages="languages" :sidebar-width="sidebarWidth" />
    </template>
  </SidebarFrame>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ElementsSidebar, { type SidebarLanguage } from './ElementsSidebar.vue'
import SidebarFrame from './SidebarFrame.vue'
import SidebarPersistence from './SidebarPersistence.vue'
import SidebarSync from './SidebarSync.vue'
import SidebarTabs, { type SidebarTabItem } from './SidebarTabs.vue'

type SidebarTab = 'elements' | 'persistence' | 'sync'

defineProps<{
  languages?: SidebarLanguage[]
  modelManagement?: boolean
}>()
const tabs: SidebarTabItem[] = [
  { value: 'elements', icon: 'mdi-shape-outline', label: 'Elements' },
  { value: 'persistence', icon: 'mdi-import', label: 'Import/Export' },
  { value: 'sync', icon: 'mdi-sync', label: 'Sync' }
]
const DEFAULT_WIDTH = 210
const sidebarWidth = ref(DEFAULT_WIDTH)
const activeTab = ref<SidebarTab>('elements')
const selectTab = (value: string) => {
  activeTab.value = value as SidebarTab
}
</script>
