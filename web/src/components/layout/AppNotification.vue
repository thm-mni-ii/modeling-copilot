<template>
  <v-snackbar :model-value="visible" :color="current?.tone" :timeout="current?.timeout ?? -1" location="top center" max-width="640" min-width="320" rounded="lg" elevation="12" z-index="10000" @update:model-value="onVisibilityChange">
    <div v-if="current" class="app-notification">
      <v-icon :icon="icons[current.tone]" size="22" />
      <span class="app-notification__message">{{ current.message }}</span>
    </div>

    <template v-if="current" #actions>
      <v-btn v-if="current.action" color="white" variant="text" @click="runAction">{{ current.action.label }}</v-btn>
      <v-btn color="white" icon="mdi-close" variant="text" size="small" aria-label="Close notification" @click="dismissNotification" />
    </template>
  </v-snackbar>
</template>

<script setup lang="ts">
import { useNotifications, type NotificationTone } from '@/composables/useNotifications'

const { current, visible, dismissNotification } = useNotifications()

const icons: Record<NotificationTone, string> = {
  error: 'mdi-alert-circle-outline',
  warning: 'mdi-alert-outline',
  success: 'mdi-check-circle-outline'
}

const onVisibilityChange = (value: boolean) => {
  if (!value) dismissNotification()
}

const runAction = () => {
  const handler = current.value?.action?.handler
  dismissNotification()
  void handler?.()
}
</script>

<style scoped>
.app-notification {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.app-notification__message {
  min-width: 0;
  overflow-wrap: anywhere;
  white-space: pre-line;
  line-height: 1.45;
}
</style>
