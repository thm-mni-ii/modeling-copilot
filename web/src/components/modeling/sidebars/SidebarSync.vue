<template>
  <div class="sidebar-sync">
    <SidebarPanelHeader v-if="showHeader" title="Collab" />
    <div class="sidebar-sync__content">
      <div class="sync-status-row">
        <span class="sync-status-label">Sharing</span>
        <div class="sync-status-pills">
          <div v-if="isConnected && anonymous" class="sync-status sync-status--anonymous" title="Others see a pseudonym instead of your name">
            <v-icon icon="mdi-incognito" size="12" />
            anonymous
          </div>
          <div class="sync-status" :class="isConnected ? 'sync-status--connected' : 'sync-status--disconnected'">
            <span class="sync-status-dot" />
            {{ !share ? 'not shared' : isConnected ? 'live' : 'connecting' }}
          </div>
        </div>
      </div>

      <v-btn v-if="!share" color="primary" variant="flat" size="small" prepend-icon="mdi-share-variant" :disabled="Boolean(linkedWorkpieceId)" @click="shareDialog = 'ask'">Share</v-btn>
      <div v-if="!share && linkedWorkpieceId" class="sync-hint">This model is part of a shared room.</div>

      <template v-if="share">
        <template v-if="isHost">
          <v-text-field :model-value="link" class="sync-link" label="Link for visitors" readonly density="compact" variant="outlined" hide-details append-inner-icon="mdi-content-copy" @click:append-inner="copy" />
          <v-btn color="error" variant="flat" size="small" prepend-icon="mdi-logout" :loading="quitting" @click="quit">Quit sharing</v-btn>
          <ShareSettings />
        </template>
        <template v-else>
          <div class="sync-hint">You joined a model shared by someone else.</div>
          <v-btn variant="outlined" size="small" prepend-icon="mdi-logout" @click="shareDialog = 'leave'">Leave sharing</v-btn>
        </template>
        <CollabPeople :people="people" />
        <CollabLog :entries="logEntries" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import CollabLog from '@/collab/connection/CollabLog.vue'
import CollabPeople from '@/collab/presence/CollabPeople.vue'
import ShareSettings from '@/collab/sharing/ShareSettings.vue'
import { currentShare as share, openQuitDialog, shareDialog, shareLink } from '@/collab/sharing/shareModel'
import { notifyError } from '@/composables/useNotifications'
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

const router = useRouter()
const { isConnected, linkedWorkpieceId, logEntries, people, anonymous } = useCollabConnection()

const isHost = computed(() => Boolean(share.value?.privateModelId))
const link = computed(() => (share.value ? shareLink(router, share.value.roomId) : ''))
const quitting = ref(false)

const copy = async () => {
  try {
    await navigator.clipboard.writeText(link.value)
  } catch {
    notifyError('The link could not be copied.')
  }
}

// Locks the room first, so everyone keeps the state the host is about to save.
const quit = async () => {
  quitting.value = true
  try {
    await openQuitDialog()
  } catch (error) {
    notifyError(`Sharing could not be quit: ${(error as Error).message}`)
  } finally {
    quitting.value = false
  }
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

.sync-link {
  flex: none;
}

.sync-hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}
</style>
