<template>
  <Teleport v-if="container && visible" :to="container">
    <div class="mode-frame" :class="{ 'mode-frame--group': group }" :style="{ borderColor: color, '--mode-color': color }">
      <div class="mode-bar">
        <div class="mode-chip" :style="{ background: color }">
          <v-icon :icon="chip.icon" size="16" />
          {{ chip.text }}
        </div>
        <button v-for="button in buttons" :key="button.key" type="button" class="mode-button" :class="{ 'mode-button--on': button.on, 'mode-button--present': button.key === 'present', 'mode-button--info': button.kind === 'info' }" :title="button.title" :aria-label="button.title" :disabled="isHost && locked" @click="button.toggle()">
          <v-icon :icon="button.icon" size="18" />
        </button>
        <!-- A release by someone else shows here for a moment; the event log in the "Collab" tab keeps it. -->
        <v-fade-transition>
          <div v-if="recentRelease" class="mode-release" :title="`${recentRelease.by} created release ${recentRelease.label}`">
            <v-icon icon="mdi-tag-outline" size="14" />
            {{ recentRelease.label }} by {{ recentRelease.by }}
          </div>
        </v-fade-transition>
        <!-- A group is not left; the way back is "Group models". -->
        <div v-if="!group" class="mode-separator" />
        <button v-if="!group" type="button" class="mode-button mode-button--exit" :title="exit.title" :aria-label="exit.title" :disabled="isHost && locked" @click="exit.toggle()">
          <v-icon :icon="exit.icon" size="18" />
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { useGraphContext } from '@/composables/useGraphContext'
import { roomRole } from '@/collab/rooms/roomRole'
import { collabSettings } from '@/collab/settings/collabSettings'
import { showAuthors } from '@/collab/graph/authorMarks'
import { liveSession } from '@/collab/kit/liveSession'
import { COMMENTS_ENABLED, announcedRights, currentShare, hostAway, hostPresenting, hostToggles, isSharedModel, loadShareSettings, presenting, shareDialog, shareSettingsBusy, visitorRights } from './shareModel'

const GREEN = 'rgb(var(--v-theme-primary))'

const { graph } = useGraphContext()
const route = useRoute()
const { isConnected, anonymous, linkedWorkpieceId, recentRelease } = useCollabConnection()
// As in the "Collab" sidebar: the model lies in a group room, not in a share; then green and without switches.
const group = computed(() => Boolean(linkedWorkpieceId.value) && roomRole.value?.kind === 'group')

// The frame and the bar are no part of the model. They lie next to the container of the canvas, not in it:
// while panning, maxGraph moves every child of the container with the canvas (panGraph in PanningMixin.js).
const container = computed(() => graph.value?.container.parentElement)
// Only at the shared model; a second tab with another model shows no frame.
const shared = computed(() => !group.value && isSharedModel(route.params.modelId))
const visible = computed(() => (group.value || shared.value) && isConnected.value)
const isHost = computed(() => shared.value && Boolean(currentShare.value?.privateModelId))
const presentingNow = computed(() => (isHost.value ? presenting.value : hostPresenting.value))
// A visitor sees at once when the host is gone; the host does not need to be told about themselves.
const away = computed(() => !isHost.value && hostAway.value)
const color = computed(() => (group.value ? GREEN : away.value ? collabSettings.colors.barAwayColor : presentingNow.value ? collabSettings.colors.hostColor : collabSettings.colors.barColor))
const locked = computed(() => shareSettingsBusy() || shareDialog.value === 'quit')

watch([visible, isHost], ([shown, host]) => shown && host && void loadShareSettings(), { immediate: true })

// Who created and last edited each element: a view of one's own, only on this screen, remembered in the browser.
const AUTHORS_KEY = 'collab:showAuthors'
const authorsShown = ref(localStorage.getItem(AUTHORS_KEY) === 'true')
watch(authorsShown, (shown) => localStorage.setItem(AUTHORS_KEY, String(shown)))
let hideAuthors: (() => void) | null = null
watch(
  [() => group.value && visible.value && authorsShown.value, graph, linkedWorkpieceId],
  ([shown, current, workpieceId]) => {
    hideAuthors?.()
    hideAuthors = null
    const session = shown && current && workpieceId ? liveSession(workpieceId) : null
    if (current && session) hideAuthors = showAuthors(current, session)
  },
  { immediate: true }
)
onBeforeUnmount(() => hideAuthors?.())

const chip = computed(() => {
  // Without the name of the group, which can be long; the "Collab" sidebar shows it.
  if (group.value) return { icon: 'mdi-account-group-outline', text: 'Group model' }
  if (away.value) return { icon: 'mdi-lan-disconnect', text: 'Host disconnected' }
  if (!presentingNow.value) return { icon: 'mdi-account-group-outline', text: 'Collaborating' }
  return { icon: 'mdi-cursor-default-outline', text: isHost.value ? 'Presenting' : 'Host is presenting' }
})

interface ModeButton {
  key: string
  /** toggle: the host switches a setting; info: a visitor only reads it. */
  kind: 'toggle' | 'info'
  on: boolean
  icon: string
  title: string
  toggle: () => void
}

/** The host switches each setting; a visitor sees only what they may do, and nothing of what they may not. */
const buttons = computed<ModeButton[]>(() => {
  // In a group room everyone may do the same: see, comment, edit.
  if (group.value)
    return [
      { key: 'edit', kind: 'info', on: true, icon: 'mdi-pencil', title: 'Everyone in the group can edit', toggle: () => undefined },
      { key: 'authors', kind: 'toggle', on: authorsShown.value, icon: 'mdi-account-circle-outline', title: authorsShown.value ? 'Hide who added and last edited each element' : 'Show who added and last edited each element', toggle: () => (authorsShown.value = !authorsShown.value) }
    ]
  if (isHost.value) return hostToggles.value.filter((item) => !item.sidebarOnly).map((item) => ({ ...item, kind: 'toggle' as const }))
  // The host's announcement comes at once; CK tells editing only after a reconnect and commenting not at all.
  const announced = announcedRights.value
  const mayEdit = !visitorRights.locked && (announced?.edit ?? visitorRights.edit)
  const mayComment = announced?.comment ?? visitorRights.comment
  const isAnonymous = announced?.anonymous ?? anonymous.value
  const held: ModeButton[] = []
  if (mayEdit) held.push({ key: 'edit', kind: 'info', on: true, icon: 'mdi-pencil', title: 'You can edit', toggle: () => undefined })
  if (COMMENTS_ENABLED && mayComment) held.push({ key: 'comment', kind: 'info', on: true, icon: 'mdi-comment-outline', title: 'You can comment', toggle: () => undefined })
  if (isAnonymous) held.push({ key: 'anonymous', kind: 'info', on: true, icon: 'mdi-incognito', title: 'You appear anonymous', toggle: () => undefined })
  if (held.length === 0) held.push({ key: 'view', kind: 'info', on: true, icon: 'mdi-eye-outline', title: 'You can only view', toggle: () => undefined })
  return held
})

/** Host and visitor can always end the sharing, whatever the rights and whatever the connection does. */
const exit = computed(() => ({
  icon: 'mdi-logout',
  title: isHost.value ? 'Quit sharing' : 'Leave sharing',
  toggle: () => (shareDialog.value = isHost.value ? 'quit' : 'leave')
}))
</script>

<style scoped>
.mode-frame {
  position: absolute;
  inset: 0;
  z-index: 5;
  box-sizing: border-box;
  border: 3px solid;
  pointer-events: none;
}

.mode-bar {
  position: absolute;
  top: 0;
  left: 0;
  display: flex;
  align-items: center;
  gap: 2px;
  height: 34px;
  padding-right: 6px;
  background: #ffffff;
  border-right: 2px solid var(--mode-color);
  border-bottom: 2px solid var(--mode-color);
  border-bottom-right-radius: 8px;
  pointer-events: auto;
}

.mode-chip {
  display: flex;
  align-items: center;
  align-self: stretch;
  gap: 6px;
  margin-right: 6px;
  padding: 0 10px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 500;
}

.mode-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 26px;
  border-radius: 6px;
  color: rgba(var(--v-theme-on-surface), 0.87);
  cursor: pointer;
}

.mode-button--on {
  background: #dcebfa;
  color: #1d5fa5;
}

.mode-release {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 220px;
  margin-left: 4px;
  padding: 2px 8px;
  overflow: hidden;
  border-radius: 10px;
  background: color-mix(in srgb, var(--mode-color) 15%, transparent);
  color: var(--mode-color);
  font-size: 11px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.mode-frame--group .mode-button--on {
  background: rgba(var(--v-theme-primary), 0.15);
  color: rgb(var(--v-theme-primary));
}

.mode-button--present.mode-button--on {
  background: #f8e1e0;
  color: #a63e3a;
}

/* A visitor only reads what the buttons say. */
.mode-button--info {
  cursor: default;
}

/* Ending the sharing is an action, no state: set apart by the line and in red. */
.mode-separator {
  width: 2px;
  height: 20px;
  margin: 0 4px;
  background: var(--mode-color);
}

.mode-button--exit {
  color: #a63e3a;
}

.mode-button--exit:hover {
  background: #f8e1e0;
}
</style>
