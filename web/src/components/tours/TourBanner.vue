<template>
  <v-alert v-if="info && info.loaded && info.status === 'new' && info.available && !dismissed" type="info" variant="tonal" density="compact" closable class="tour-banner" @click:close="dismissed = true">
    <strong>{{ info.title }}</strong>
    <span> – {{ info.description }}</span>
    <template #append>
      <v-btn size="small" variant="text" @click="start">Tour starten</v-btn>
    </template>
  </v-alert>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTours } from '@/composables/useTours'

// Hinweis auf eine Tour, deren Liste noch nie geöffnet wurde (status "new"), nicht auf jede offene Tour; das Schließen blendet ihn nur für diesen Seitenbesuch aus.
const props = defineProps<{ tourId: string }>()
const { tours, start: startTour } = useTours()
const dismissed = ref(false)
const info = computed(() => tours.value.find((tour) => tour.id === props.tourId))
const start = () => startTour(props.tourId)
</script>
