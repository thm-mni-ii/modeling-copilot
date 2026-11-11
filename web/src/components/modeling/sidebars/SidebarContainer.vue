<template>
  <SidebarFrame v-model:width="sidebarWidth" side="left" :show-tabs="!modelManagement">
    <template v-if="!modelManagement" #tabs>
      <SidebarTabs :model-value="activeTab" :tabs="tabs" aria-label="Sidebar content" @update:model-value="selectTab" />
    </template>
    <template #default>
      <template v-if="modelManagement">
        <div v-if="!workspace.languages.length" class="language-actions">
          <h2 class="text-subtitle-2 mb-2">No model language added yet</h2>
          <p class="text-body-2 text-medium-emphasis mb-3">Model languages provide the elements for your model.</p>
          <v-btn size="small" block color="primary" prepend-icon="mdi-plus" @click="emit('manage-languages')">Add model language</v-btn>
        </div>
        <ElementsSidebar v-show="workspace.languages.length > 0" :languages="languages" :sidebar-width="sidebarWidth" expand-new-languages />
      </template>
      <SidebarPersistence v-else-if="activeTab === 'persistence'" />
      <ElementsSidebar v-else :languages="languages" :sidebar-width="sidebarWidth" />
    </template>
  </SidebarFrame>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import ElementsSidebar, { type SidebarLanguage } from './ElementsSidebar.vue'
import SidebarFrame from './SidebarFrame.vue'
import SidebarPersistence from './SidebarPersistence.vue'
import SidebarTabs, { type SidebarTabItem } from './SidebarTabs.vue'

type SidebarTab = 'elements' | 'persistence'

defineProps<{
  languages?: SidebarLanguage[]
  modelManagement?: boolean
}>()
const emit = defineEmits<{
  'manage-languages': []
}>()
const tabs: SidebarTabItem[] = [
  { value: 'elements', icon: 'mdi-shape-outline', label: 'Elements' },
  { value: 'persistence', icon: 'mdi-import', label: 'Import/Export' }
]
const DEFAULT_WIDTH = 210
const workspace = useModelWorkspaceStore()
const sidebarWidth = ref(DEFAULT_WIDTH)
const activeTab = ref<SidebarTab>('elements')
const selectTab = (value: string) => {
  activeTab.value = value as SidebarTab
}
</script>

<style scoped>
.language-actions {
  margin: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.14);
  flex-shrink: 0;
}
.language-actions :deep(.v-btn) {
  height: auto;
  min-height: 32px;
  padding: 6px 8px;
  letter-spacing: normal;
  text-transform: none;
  white-space: normal;
}
.language-actions :deep(.v-btn__content) {
  min-width: 0;
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
