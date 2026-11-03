<template>
  <Teleport v-if="container && visible" :to="container">
    <div class="mode-frame" :style="{ borderColor: color }">
      <div class="mode-bar">
        <div class="mode-chip" :style="{ background: color }">
          <v-icon :icon="chip.icon" size="16" />
          {{ chip.text }}
        </div>
        <div class="mode-buttons">
          <button v-for="button in buttons" :key="button.key" type="button" class="mode-button" :class="{ 'mode-button--on': button.on, 'mode-button--present': button.key === 'present', 'mode-button--shown': !isHost }" :title="button.title" :aria-label="button.title" :disabled="isHost && locked" @click="isHost && button.toggle()">
            <v-icon :icon="button.icon" size="18" />
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { useGraphContext } from '@/composables/useGraphContext'
import { announcedRights, currentShare, hostPresenting, loadShareSettings, presenting, shareDialog, shareSettings, shareSettingsBusy, toggleShareSetting, visitorRights } from './shareModel'

const BLUE = '#3f8ad6'
const CORAL = '#cf5c58'

const { graph } = useGraphContext()
const { isConnected, anonymous } = useCollabConnection()

// The frame and the bar lie in the container of the canvas, as the cursors do, and are no part of the model.
const container = computed(() => graph.value?.container)
const visible = computed(() => Boolean(currentShare.value) && isConnected.value)
const isHost = computed(() => Boolean(currentShare.value?.privateModelId))
const presentingNow = computed(() => (isHost.value ? presenting.value : hostPresenting.value))
const color = computed(() => (presentingNow.value ? CORAL : BLUE))
const locked = computed(() => shareSettingsBusy() || shareDialog.value === 'quit')

watch([visible, isHost], ([shown, host]) => shown && host && void loadShareSettings(), { immediate: true })

const chip = computed(() => {
  if (!presentingNow.value) return { icon: 'mdi-account-group-outline', text: 'Collaborating' }
  return { icon: 'mdi-cursor-default-outline', text: isHost.value ? 'Presenting' : 'Host is presenting' }
})

interface ModeButton {
  key: string
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
      { key: 'edit', on: edit, icon: edit ? 'mdi-pencil' : 'mdi-pencil-off', title: edit ? 'Visitors may edit' : 'Visitors may not edit', toggle: () => void toggleShareSetting('edit') },
      { key: 'comment', on: comment, icon: comment ? 'mdi-comment-outline' : 'mdi-comment-off-outline', title: comment ? 'Visitors may comment' : 'Visitors may not comment', toggle: () => void toggleShareSetting('comment') },
      { key: 'anonymous', on: hidden, icon: hidden ? 'mdi-incognito' : 'mdi-account-outline', title: hidden ? 'Visitors are anonymous' : 'Visitors are named', toggle: () => void toggleShareSetting('anonymous') },
      { key: 'present', on: presenting.value, icon: 'mdi-cursor-default-outline', title: presenting.value ? 'Stop presenting' : 'Presentation mode: others only see your cursor', toggle: () => (presenting.value = !presenting.value) }
    ]
  }
  // The host's announcement comes at once; CK tells editing only after a reconnect and commenting not at all.
  const announced = announcedRights.value
  const mayEdit = !visitorRights.locked && (announced?.edit ?? visitorRights.edit)
  const mayComment = announced?.comment ?? visitorRights.comment
  const isAnonymous = announced?.anonymous ?? anonymous.value
  const held: ModeButton[] = []
  if (mayEdit) held.push({ key: 'edit', on: true, icon: 'mdi-pencil', title: 'You can edit', toggle: () => undefined })
  if (mayComment) held.push({ key: 'comment', on: true, icon: 'mdi-comment-outline', title: 'You can comment', toggle: () => undefined })
  if (isAnonymous) held.push({ key: 'anonymous', on: true, icon: 'mdi-incognito', title: 'You appear anonymous', toggle: () => undefined })
  return held.length > 0 ? held : [{ key: 'view', on: true, icon: 'mdi-eye-outline', title: 'You can only view', toggle: () => undefined }]
})
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
  gap: 8px;
  padding-right: 8px;
  background: #ffffff;
  border-right: 0.5px solid rgba(var(--v-theme-outline), 0.3);
  border-bottom: 0.5px solid rgba(var(--v-theme-outline), 0.3);
  border-bottom-right-radius: 8px;
  pointer-events: auto;
}

.mode-chip {
  display: flex;
  align-items: center;
  align-self: stretch;
  gap: 6px;
  padding: 6px 10px;
  border-bottom-right-radius: 6px;
  color: #ffffff;
  font-size: 12px;
  font-weight: 500;
}

.mode-buttons {
  display: flex;
  overflow: hidden;
  border: 0.5px solid rgba(var(--v-theme-outline), 0.5);
  border-radius: 6px;
}

.mode-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 28px;
  background: #ffffff;
  color: rgba(var(--v-theme-on-surface), 0.87);
  cursor: pointer;
}

.mode-button + .mode-button {
  border-left: 0.5px solid rgba(var(--v-theme-outline), 0.3);
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
.mode-button--shown {
  cursor: default;
}
</style>
