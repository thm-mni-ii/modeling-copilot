<template>
  <v-dialog :model-value="modelValue" max-width="1000" persistent @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="d-flex align-center">
        Manage collaboration
        <v-spacer />
        <v-btn icon="mdi-close" size="small" variant="text" aria-label="Close manage collaboration" @click="close" />
      </v-card-title>
      <v-tabs v-model="tab" density="compact" class="px-4">
        <v-tab value="rooms">Rooms</v-tab>
        <v-tab value="groups">Groups</v-tab>
      </v-tabs>
      <v-divider />
      <v-card-text>
        <!-- Mounted on every opening, so the lists show what collab-kit holds now. -->
        <CollabRoomsPanel v-if="modelValue && tab === 'rooms'" />
        <p v-else-if="tab === 'groups'" class="text-medium-emphasis mb-0">Groups follow in the next step.</p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="close">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import CollabRoomsPanel from './CollabRoomsPanel.vue'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const tab = ref<'rooms' | 'groups'>('rooms')

const close = () => emit('update:modelValue', false)
</script>
