<template>
  <div class="sidebar-sync">
    <SidebarPanelHeader v-if="showHeader" title="Sync" />
    <div class="sidebar-sync__content">
      <div class="sync-status-row">
        <span class="sync-status-label">Connection</span>
        <div class="sync-status" :class="isConnected ? 'sync-status--connected' : 'sync-status--disconnected'">
          <span class="sync-status-dot" />
          {{ isConnected ? 'connected' : 'disconnected' }}
        </div>
      </div>

      <div class="sync-actions">
        <v-btn :color="isConnected ? 'error' : 'primary'" variant="flat" size="small" :prepend-icon="isConnected ? 'mdi-lan-disconnect' : 'mdi-lan-connect'" @click="toggleConnection">
          {{ isConnected ? 'Disconnect' : 'Connect' }}
        </v-btn>
        <p v-if="errorMessage" class="sync-error">{{ errorMessage }}</p>
      </div>

      <div class="sync-log">
        <div class="sync-log-header">Event Log</div>
        <div class="sync-log-body">
          <div v-if="logEntries.length === 0" class="sync-log-empty">No events yet</div>
          <div v-for="(entry, index) in logEntries" :key="index" class="sync-log-entry">{{ entry }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useGraphContext } from '@/composables/useGraphContext'
import { exportModelAsJson, exportModelAsXml, importModelFromJson, importModelFromXml } from '@/utils/modelPersistence'
import SidebarPanelHeader from './SidebarPanelHeader.vue'

withDefaults(defineProps<{ showHeader?: boolean }>(), { showHeader: true })

const { graph } = useGraphContext()

const modelIo = {
  exportModelAsXml,
  exportModelAsJson,
  importModelFromXml,
  importModelFromJson
}

defineExpose({ graph, modelIo })

const isConnected = ref(false)
const errorMessage = ref('')
const logEntries = ref<string[]>([])

const toggleConnection = () => {
  if (isConnected.value) {
    isConnected.value = false
    return
  }

  if (!graph.value) {
    errorMessage.value = 'No graph available.'
    return
  }

  errorMessage.value = ''
  isConnected.value = true
}
</script>

<style scoped>
.sidebar-sync {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  background: #ffffff;
  overflow: hidden;
}

.sidebar-sync__content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 12px;
  overflow-y: auto;
}

.sidebar-sync__content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-sync__content::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-sync__content::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-on-surface), 0.2);
  border-radius: 4px;
}

.sync-status-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sync-status-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: rgba(var(--v-theme-on-surface), 0.82);
}

.sync-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.sync-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.sync-status--connected {
  background: rgba(var(--v-theme-success, 76, 175, 80), 0.12);
  color: rgb(46, 125, 50);
}

.sync-status--connected .sync-status-dot {
  background: rgb(56, 142, 60);
}

.sync-status--disconnected {
  background: rgba(var(--v-theme-on-surface), 0.06);
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.sync-status--disconnected .sync-status-dot {
  background: rgba(var(--v-theme-on-surface), 0.3);
}

.sync-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sync-error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.08);
}

.sync-log {
  display: flex;
  flex-direction: column;
  min-height: 180px;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.01);
}

.sync-log-header {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.15);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.sync-log-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.sync-log-empty {
  padding: 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.52);
}

.sync-log-entry {
  padding: 8px 10px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.08);
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.75);
}
</style>
