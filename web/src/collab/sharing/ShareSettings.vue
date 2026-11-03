<template>
  <div class="share-settings">
    <div class="share-settings__header">
      <span>Settings</span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse settings' : 'Expand settings'" @click="open = !open" />
    </div>
    <v-expand-transition>
      <div v-show="open" class="share-settings__body">
        <v-switch :model-value="shareSettings.joinable" color="primary" density="compact" hide-details label="Accept new visitors" :disabled="disabled" @update:model-value="toggleShareSetting('joinable')" />
        <v-switch :model-value="shareSettings.edit" color="primary" density="compact" hide-details label="Visitors may edit" :disabled="disabled" @update:model-value="toggleShareSetting('edit')" />
        <v-switch :model-value="shareSettings.comment" color="primary" density="compact" hide-details label="Visitors may comment" :disabled="disabled" @update:model-value="toggleShareSetting('comment')" />
        <v-switch :model-value="shareSettings.anonymous" color="primary" density="compact" hide-details label="Visitors anonymous" :disabled="disabled" @update:model-value="toggleShareSetting('anonymous')" />
        <v-switch v-model="presenting" color="primary" density="compact" label="Presentation mode" hint="Others only see your cursor." persistent-hint :disabled="shareDialog === 'quit'" />
      </div>
    </v-expand-transition>
  </div>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so it stays as it is while another sidebar tab is shown.
const open = ref(true)
</script>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { loadShareSettings, presenting, shareDialog, shareSettingsBusy, shareSettings, toggleShareSetting } from './shareModel'

// Until the values are read, the switches would show what is not set; while the host decides how to leave, nothing changes.
const disabled = computed(() => shareSettingsBusy() || shareDialog.value === 'quit')

onMounted(loadShareSettings)
</script>

<style scoped>
.share-settings {
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
}

.share-settings__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.share-settings__body {
  padding: 2px 10px 6px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}
</style>
