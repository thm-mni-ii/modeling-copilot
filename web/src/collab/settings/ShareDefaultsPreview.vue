<template>
  <div class="preview">
    <v-card variant="outlined" title="Share this model" text="Others join through a link. You can change these settings later.">
      <v-card-text class="pt-0">
        <div class="share-section">Visitors</div>
        <v-switch v-for="setting in visitorSettings" :key="setting.key" :model-value="Boolean(values[setting.key])" color="primary" density="compact" :label="setting.label" :hint="setting.hint" persistent-hint @update:model-value="emit('update', setting.key, Boolean($event))" />
        <div class="share-section">Share history</div>
        <ChoiceCards :model-value="historyValue" :choices="historyChoices" :busy="false" @update:model-value="emit('update', 'history', $event)" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" disabled>Cancel</v-btn>
        <v-btn color="primary" variant="text" disabled>Share</v-btn>
      </v-card-actions>
    </v-card>
    <div class="preview__note">
      <span>The dialog as the host sees it. Change the defaults right here.</span>
      <v-btn variant="outlined" size="small" prepend-icon="mdi-restore" :disabled="!resettable" @click="emit('reset')">Reset to defaults</v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ChoiceCards from '@/collab/sharing/ChoiceCards.vue'
import { historyChoices, visitorSettings } from '@/collab/sharing/shareChoices'

/** The share defaults as the form shows them; a change goes back to the form. */
const props = defineProps<{ values: Record<string, unknown>; resettable: boolean }>()
const emit = defineEmits<{ update: [key: string, value: boolean | string]; reset: [] }>()

const historyValue = computed(() => historyChoices.find((choice) => choice.value === props.values.history)?.value ?? 'none')
</script>

<style scoped>
.preview {
  width: 440px;
  max-width: 100%;
}

.preview__note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  margin-top: 6px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.share-section {
  margin: 12px 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
</style>
