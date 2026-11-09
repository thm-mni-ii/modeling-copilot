<template>
  <Teleport v-if="container && visible" :to="container">
    <div class="mode-frame" :style="{ borderColor: color, '--mode-color': color }">
      <div class="mode-bar">
        <div class="mode-chip" :style="{ background: color }">
          <v-icon :icon="chip.icon" size="16" />
          {{ chip.text }}
        </div>
        <button v-for="button in buttons" :key="button.key" type="button" class="mode-button" :class="{ 'mode-button--on': button.on, 'mode-button--present': button.key === 'present', 'mode-button--info': button.kind === 'info' }" :title="button.title" :aria-label="button.title" :disabled="isHost && locked" @click="button.toggle()">
          <v-icon :icon="button.icon" size="18" />
        </button>
        <div class="mode-separator" />
        <button type="button" class="mode-button mode-button--exit" :title="exit.title" :aria-label="exit.title" :disabled="isHost && locked" @click="exit.toggle()">
          <v-icon :icon="exit.icon" size="18" />
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { useGraphContext } from '@/composables/useGraphContext'
import { announcedRights, currentShare, hostAway, hostPresenting, loadShareSettings, presenting, shareDialog, shareSettings, shareSettingsBusy, toggleShareSetting, visitorRights } from './shareModel'

const BLUE = '#3f8ad6'
const CORAL = '#cf5c58'
const AMBER = '#c77d0a'

const { graph } = useGraphContext()
const { isConnected, anonymous } = useCollabConnection()

// The frame and the bar are no part of the model. They lie next to the container of the canvas, not in it:
// while panning, maxGraph moves every child of the container with the canvas (panGraph in PanningMixin.js).
const container = computed(() => graph.value?.container.parentElement)
const visible = computed(() => Boolean(currentShare.value) && isConnected.value)
const isHost = computed(() => Boolean(currentShare.value?.privateModelId))
const presentingNow = computed(() => (isHost.value ? presenting.value : hostPresenting.value))
// A visitor sees at once when the host is gone; the host does not need to be told about themselves.
const away = computed(() => !isHost.value && hostAway.value)
const color = computed(() => (away.value ? AMBER : presentingNow.value ? CORAL : BLUE))
const locked = computed(() => shareSettingsBusy() || shareDialog.value === 'quit')

watch([visible, isHost], ([shown, host]) => shown && host && void loadShareSettings(), { immediate: true })

const chip = computed(() => {
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
  if (isHost.value) {
    const { edit, comment, anonymous: hidden } = shareSettings
    return [
      { key: 'edit', kind: 'toggle', on: edit, icon: edit ? 'mdi-pencil' : 'mdi-pencil-off', title: edit ? 'Visitors may edit' : 'Visitors may not edit', toggle: () => void toggleShareSetting('edit') },
      { key: 'comment', kind: 'toggle', on: comment, icon: comment ? 'mdi-comment-outline' : 'mdi-comment-off-outline', title: comment ? 'Visitors may comment' : 'Visitors may not comment', toggle: () => void toggleShareSetting('comment') },
      { key: 'anonymous', kind: 'toggle', on: hidden, icon: hidden ? 'mdi-incognito' : 'mdi-account-outline', title: hidden ? 'Visitors are anonymous' : 'Visitors are named', toggle: () => void toggleShareSetting('anonymous') },
      { key: 'present', kind: 'toggle', on: presenting.value, icon: 'mdi-cursor-default-outline', title: presenting.value ? 'Stop presenting' : 'Presentation mode: others only see your cursor', toggle: () => (presenting.value = !presenting.value) }
    ]
  }
  // The host's announcement comes at once; CK tells editing only after a reconnect and commenting not at all.
  const announced = announcedRights.value
  const mayEdit = !visitorRights.locked && (announced?.edit ?? visitorRights.edit)
  const mayComment = announced?.comment ?? visitorRights.comment
  const isAnonymous = announced?.anonymous ?? anonymous.value
  const held: ModeButton[] = []
  if (mayEdit) held.push({ key: 'edit', kind: 'info', on: true, icon: 'mdi-pencil', title: 'You can edit', toggle: () => undefined })
  if (mayComment) held.push({ key: 'comment', kind: 'info', on: true, icon: 'mdi-comment-outline', title: 'You can comment', toggle: () => undefined })
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
