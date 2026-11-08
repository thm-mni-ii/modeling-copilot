<template>
  <v-card :variant="copied ? 'tonal' : 'outlined'" color="primary" class="copy-card" role="button" tabindex="0" @click="copy" @keydown.enter.prevent="copy" @keydown.space.prevent="copy">
    <v-icon icon="mdi-link-variant" class="mr-3" />
    <div class="flex-grow-1">
      <div class="copy-card__title">{{ copied ? 'Link copied' : 'Copy link' }}</div>
      <div class="text-caption copy-card__hint">{{ hint }}</div>
    </div>
    <v-icon :icon="copied ? 'mdi-check' : 'mdi-content-copy'" />
  </v-card>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { notifyError } from '@/composables/useNotifications'

const props = defineProps<{ link: string; hint: string }>()

/** How long the card says "Link copied" before it offers the copy again. */
const COPIED_MS = 2500

const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const copy = async () => {
  try {
    await navigator.clipboard.writeText(props.link)
    copied.value = true
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => (copied.value = false), COPIED_MS)
  } catch {
    notifyError('The link could not be copied.')
  }
}

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})
</script>

<style scoped>
.copy-card {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: rgba(var(--v-theme-primary), 0.1);
  cursor: pointer;
}

.copy-card__title {
  font-size: 14px;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.copy-card__hint {
  color: rgba(var(--v-theme-on-surface), 0.7);
}

/* Schrift dunkel, nur die Icons tragen das Grün; so bleibt es lesbar. */
.copy-card :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 75%, black);
}
</style>
