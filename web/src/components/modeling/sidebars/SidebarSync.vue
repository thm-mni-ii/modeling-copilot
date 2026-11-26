<template>
  <div class="sidebar-sync">
    <SidebarPanelHeader v-if="showHeader" title="Collab" />
    <div class="sidebar-sync__content">
      <div class="sync-status-row">
        <span class="sync-status-label">{{ group ? 'Group room' : 'Sharing' }}</span>
        <div class="sync-status-pills">
          <div v-if="isConnected && anonymous" class="sync-status sync-status--anonymous" title="Others see a pseudonym instead of your name">
            <v-icon icon="mdi-incognito" size="12" />
            anonymous
          </div>
          <div class="sync-status" :class="isConnected ? 'sync-status--connected' : 'sync-status--disconnected'">
            <span class="sync-status-dot" />
            {{ group || inShare ? (isConnected ? 'live' : 'connecting') : 'not shared' }}
          </div>
        </div>
      </div>

      <v-btn v-if="!share && !group" color="primary" variant="flat" size="small" prepend-icon="mdi-share-variant" :disabled="Boolean(linkedWorkpieceId)" @click="shareDialog = 'ask'">Share</v-btn>
      <div v-if="!share && !group && linkedWorkpieceId" class="sync-hint">This model is part of a shared room.</div>

      <!-- Ein anderes Modell wird in diesem Browser geteilt; beenden lässt es sich nur dort. -->
      <div v-if="elsewhere" class="sync-busy">
        <div class="sync-busy__icon"><v-icon icon="mdi-share-off-outline" size="22" /></div>
        <div class="sync-busy__title">Sharing is busy</div>
        <div class="sync-hint">{{ tabOpen !== false ? 'Another model is shared in this browser. Switch to its tab to quit sharing.' : 'Another model is shared in this browser. Open it to quit sharing.' }}</div>
        <v-btn v-if="tabOpen === false" variant="outlined" color="primary" size="small" prepend-icon="mdi-open-in-app" @click="openShared">Open shared model</v-btn>
      </div>

      <template v-if="inShare">
        <template v-if="isHost">
          <ShareCopyCard :link="link" hint="Send it to visitors" class="sync-link" />
          <v-btn color="error" variant="flat" size="small" prepend-icon="mdi-logout" :loading="quitting" @click="quit">Quit sharing</v-btn>
          <ShareSettings />
        </template>
        <template v-else>
          <div class="sync-hint">You joined a model shared by someone else.</div>
          <v-btn variant="outlined" size="small" prepend-icon="mdi-logout" @click="shareDialog = 'leave'">Leave sharing</v-btn>
        </template>
      </template>
      <!-- Im Gruppenraum dürfen alle dasselbe: nur der Raum, ohne Schalter. -->
      <div v-if="group" class="sync-room"><v-icon icon="mdi-account-group-outline" size="16" />{{ roomRole?.name }}</div>
      <template v-if="group || inShare">
        <CollabPeople :people="people" />
        <CollabLog :entries="logEntries" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CollabLog from '@/collab/connection/CollabLog.vue'
import CollabPeople from '@/collab/presence/CollabPeople.vue'
import ShareCopyCard from '@/collab/sharing/ShareCopyCard.vue'
import ShareSettings from '@/collab/sharing/ShareSettings.vue'
import { askSharedTab, currentShare as share, isSharedModel, openQuitDialog, sharedTabOpen as tabOpen, shareDialog, shareLink } from '@/collab/sharing/shareModel'
import { notifyError } from '@/composables/useNotifications'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { roomRole } from '@/collab/rooms/roomRole'
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

const route = useRoute()
const isHost = computed(() => Boolean(share.value?.privateModelId))
// Das Modell liegt in einem Gruppenraum, nicht in einer Share.
const group = computed(() => Boolean(linkedWorkpieceId.value) && roomRole.value?.kind === 'group')
// Die Share gehört zu einem anderen Modell, etwa in einem zweiten Tab; den Gruppenraum betrifft sie nicht.
const elsewhere = computed(() => Boolean(share.value) && !group.value && !isSharedModel(route.params.modelId))
// Dieses Modell ist das geteilte, als Host oder Visitor.
const inShare = computed(() => Boolean(share.value) && !group.value && !elsewhere.value)
// Danach hält der Kanal den Wert aktuell, wenn der geteilte Tab schließt oder wieder aufgeht.
watch(elsewhere, (busy) => busy && askSharedTab(), { immediate: true })
// Der Editor lädt ein Modell nur beim Mounten, daher erst verlassen wie in openWorkpiece.
const openShared = async () => {
  const modelId = share.value?.linkedModelId
  if (!modelId) return
  await router.replace('/')
  await router.push({ name: 'Modeling', params: { modelId } })
}
const link = computed(() => (share.value ? shareLink(router, share.value.roomId) : ''))
const quitting = ref(false)

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

.sync-room {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

.sync-hint {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.sync-busy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 4px;
  text-align: center;
}

.sync-busy__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), 0.12);
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 65%, black);
}

.sync-busy__title {
  font-size: 13px;
  font-weight: 600;
}
</style>
