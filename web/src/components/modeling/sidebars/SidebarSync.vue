<template>
  <div class="sidebar-sync">
    <SidebarPanelHeader v-if="showHeader" title="Sync" />
    <div class="sidebar-sync__content">
      <div class="sync-status-row">
        <span class="sync-status-label">Connection</span>
        <div class="sync-status-pills">
          <div v-if="isConnected && anonymous" class="sync-status sync-status--anonymous" title="Others see a pseudonym instead of your name">
            <v-icon icon="mdi-incognito" size="12" />
            anonymous
          </div>
          <div class="sync-status" :class="isConnected ? 'sync-status--connected' : 'sync-status--disconnected'">
            <span class="sync-status-dot" />
            {{ isConnected ? 'connected' : 'disconnected' }}
          </div>
        </div>
      </div>

      <div class="sync-actions">
        <v-text-field v-model="workpieceId" label="Workpiece ID" density="compact" variant="outlined" hide-details :disabled="isConnected || connecting" />
        <v-btn :color="isConnected ? 'error' : 'primary'" variant="flat" size="small" :loading="connecting" :prepend-icon="isConnected ? 'mdi-lan-disconnect' : 'mdi-lan-connect'" @click="toggleConnection">
          {{ isConnected ? 'Disconnect' : 'Connect' }}
        </v-btn>
      </div>

      <CollabRoomList :active-workpiece-id="linkedWorkpieceId" :connected="isConnected" @open="openFromRoom" />
      <CollabPeople v-if="isConnected" :people="people" />
      <CollabLog :entries="logEntries" />
    </div>
  </div>
</template>

<script setup lang="ts">
import CollabLog from '@/collab/connection/CollabLog.vue'
import CollabPeople from '@/collab/presence/CollabPeople.vue'
import CollabRoomList from '@/collab/rooms/CollabRoomList.vue'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
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

const { isConnected, connecting, workpieceId, linkedWorkpieceId, logEntries, people, anonymous, toggleConnection, openFromRoom } = useCollabConnection()
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
  flex: 1;
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

.sync-status-pills {
  display: flex;
  gap: 6px;
}

.sync-status--anonymous {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.75);
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
</style>
