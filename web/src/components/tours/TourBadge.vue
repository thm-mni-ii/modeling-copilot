<template>
  <v-badge v-if="count > 0" :content="label" color="error" floating class="tour-badge">
    <slot :count="count" />
  </v-badge>
  <slot v-else :count="0" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTours } from '@/composables/useTours'

// Zeigt „Neu“ an dem, was im Slot steht, solange eine (der gewählten) Touren noch nicht abgeschlossen oder übersprungen ist.
const props = withDefaults(defineProps<{ tourIds?: string[]; label?: string }>(), { label: 'Neu' })
const { tours } = useTours()
const count = computed(() => tours.value.filter((tour) => tour.pending && (!props.tourIds || props.tourIds.includes(tour.id))).length)
</script>

<style scoped>
.tour-badge :deep(.v-badge__badge) {
  left: calc(100% - 18px) !important;
  font-size: 8px;
  height: 15px;
  min-width: 24px;
}
</style>
