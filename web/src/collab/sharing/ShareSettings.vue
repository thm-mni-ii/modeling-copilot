<template>
  <div class="share-settings">
    <div class="share-settings__header">
      <span>Settings</span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse settings' : 'Expand settings'" @click="open = !open" />
    </div>
    <v-expand-transition>
      <div v-show="open" class="share-settings__body">
        <!-- Dieselben Schalter wie in der ModeBar; das Präsentieren wartet nicht auf geladene Einstellungen. -->
        <button v-for="item in hostToggles" :key="item.key" type="button" class="share-toggle" :class="{ 'share-toggle--on': item.on, 'share-toggle--present': item.key === 'present' }" :title="item.title" :aria-label="item.title" :aria-pressed="item.on" :disabled="item.key === 'present' ? shareDialog === 'quit' : disabled" @click="item.toggle()">
          <v-icon :icon="item.icon" size="20" />
          <span>{{ item.label }}</span>
        </button>
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
import { hostToggles, loadShareSettings, shareDialog, shareSettingsBusy } from './shareModel'

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
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px 10px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

/* In der Sidebar grün in der Primärfarbe, in der ModeBar blau; Präsentieren an beiden Stellen rot. */
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
  /* Dunkleres Grün, damit die Schrift auf dem hellen Grund gut lesbar ist. */
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
