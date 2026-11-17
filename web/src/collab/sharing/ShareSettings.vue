<template>
  <CollabBox v-model="open" title="Settings" label="settings">
    <div class="share-settings__body">
      <!-- The same switches as in the ModeBar; presenting does not wait for the settings to load. -->
      <button v-for="item in hostToggles" :key="item.key" type="button" class="share-toggle" :class="{ 'share-toggle--on': item.on, 'share-toggle--present': item.key === 'present' }" :title="item.title" :aria-label="item.title" :aria-pressed="item.on" :disabled="item.key === 'present' ? shareDialog === 'quit' : disabled" @click="item.toggle()">
        <v-icon :icon="item.icon" size="20" />
        <span>{{ item.label }}</span>
      </button>
    </div>
  </CollabBox>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so it stays as it is while another sidebar tab is shown.
const open = ref(true)
</script>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import CollabBox from '@/collab/connection/CollabBox.vue'
import { hostToggles, loadShareSettings, shareDialog, shareSettingsBusy } from './shareModel'

// Until the values are read, the switches would show what is not set; while the host decides how to leave, nothing changes.
const disabled = computed(() => shareSettingsBusy() || shareDialog.value === 'quit')

onMounted(loadShareSettings)
</script>

<style scoped>
.share-settings__body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px 10px;
}

/* Green in the primary color in the sidebar, blue in the ModeBar; presenting is red in both. */
.share-toggle {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 58px;
  border: 1px solid rgba(var(--v-theme-outline), 0.25);
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-size: 12px;
  cursor: pointer;
}

.share-toggle--on {
  background: rgba(var(--v-theme-primary), 0.12);
  border-color: rgba(var(--v-theme-primary), 0.35);
  /* A darker green, so the text reads well on the light background. */
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 65%, black);
}

.share-toggle--present.share-toggle--on {
  background: #f8e1e0;
  border-color: #f0c4c2;
  color: #a63e3a;
}

.share-toggle:disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
