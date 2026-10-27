<template>
  <section class="journey-dock" aria-label="Deine Schatzreise">
    <div class="journey-landscape">
      <JourneyIslandArt class="journey-island" />
      <slot name="pulse" />
      <div class="journey-actions">
        <v-btn class="journey-map" variant="text" size="small" prepend-icon="mdi-map-outline" :disabled="busy" @click="emit('leave')">Zur Karte</v-btn>
        <v-btn class="journey-complete" variant="flat" size="small" :prepend-icon="completed ? 'mdi-check-circle-outline' : 'mdi-flag-checkered'" :loading="busy" :disabled="completeDisabled || busy || completed" @click="emit('complete')">{{ completed ? 'Geschafft!' : 'Abschließen' }}</v-btn>
        <div class="journey-coins" role="status" aria-live="polite" :aria-label="`${coins} Münzen gesammelt`">
          <TreasureMapArt kind="coin" /><strong>{{ coins }}</strong>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import JourneyIslandArt from './JourneyIslandArt.vue'
import TreasureMapArt from './TreasureMapArt.vue'
defineProps<{ coins: number; completed: boolean; completeDisabled: boolean; busy: boolean }>()
const emit = defineEmits<{ leave: []; complete: [] }>()
</script>

<style scoped>
.journey-dock { margin: 8px; border-radius: 14px; overflow: hidden; background: #a5e2f2; box-shadow: 0 2px 8px rgb(18 43 66 / 10%); user-select: text; }
.journey-landscape { position: relative; height: 160px; isolation: isolate; }
.journey-island { position: absolute; inset: 0; width: 100%; height: 100%; }
.journey-actions { position: absolute; inset: 6px 6px auto; z-index: 3; display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.journey-coins { display: flex; align-items: center; gap: 2px; min-width: 0; padding: 3px 5px; border-radius: 9px; background: #fff4dce8; color: #694719; }
.journey-coins svg { width: 24px; height: 24px; flex-shrink: 0; }
.journey-coins strong { font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.journey-actions :deep(.v-btn) { padding-inline: 7px; min-width: 0; font-size: 0.65rem; letter-spacing: 0; text-transform: none; border-radius: 9px; min-height: 30px; }
.journey-actions :deep(.v-btn__prepend) { margin-inline: 0 4px; }
.journey-map { color: #365b56; background: #fff9eceb; }
.journey-complete { background: #ffda86; color: #473722; }
</style>
