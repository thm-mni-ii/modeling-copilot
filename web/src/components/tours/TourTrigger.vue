<template>
  <slot :start="start" :status="info?.status" :pending="info?.pending ?? false" :available="info?.available ?? false" :reason="info?.reason ?? ''" :active="info?.active ?? false">
    <v-btn variant="text" size="small" :disabled="!info?.available || info?.active" @click="start">{{ info?.title }}</v-btn>
  </slot>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTours } from '@/composables/useTours'

// Startet eine bestimmte Tour. Eigenes Aussehen über den Slot, z. B. ein Menüpunkt im Header.
const props = defineProps<{ tourId: string }>()
const { tours, start: startTour } = useTours()
const info = computed(() => tours.value.find((tour) => tour.id === props.tourId))
const start = () => startTour(props.tourId)
</script>
