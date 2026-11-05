<template>
  <section class="journey-dock" aria-label="Deine Schatzreise">
    <div class="journey-landscape">
      <JourneyIslandArt class="journey-island" />
      <slot name="pulse" />
      <div class="journey-actions">
        <v-btn class="journey-map" variant="text" size="small" prepend-icon="mdi-map-outline" :disabled="busy" @click="emit('leave')">Zur Karte</v-btn>
        <v-btn class="journey-complete" variant="flat" size="small" :prepend-icon="completed ? 'mdi-check-circle-outline' : 'mdi-flag-checkered'" :loading="busy" :disabled="completeDisabled || busy || completed" @click="completionDialog = true">{{ completed ? 'Geschafft!' : 'Abschließen' }}</v-btn>
        <div class="journey-coins" role="status" aria-live="polite" :aria-label="`${coins} Münzen gesammelt`">
          <TreasureMapArt kind="coin" /><strong>{{ coins }}</strong>
        </div>
      </div>
    </div>
    <v-dialog v-model="completionDialog" max-width="460" aria-label="Aufgabe abschließen?">
      <v-card>
        <v-card-title class="text-wrap">Aufgabe wirklich abschließen?</v-card-title>
        <v-card-text>
          <p>Nach dem Abschluss steht deine erreichte Punktzahl fest. Du kannst sie anschließend nicht mehr erhöhen.</p>
          <p class="mt-3">Du kannst die Aufgabe danach weiterhin selbstständig bearbeiten. Deine Punktzahl bleibt dabei unverändert.</p>
          <v-checkbox v-model="completionAcknowledged" class="mt-3" color="#a33d32" density="compact" hide-details label="Ich habe verstanden, dass ich meine Punktzahl danach nicht mehr erhöhen kann." />
        </v-card-text>
        <v-card-actions class="flex-wrap">
          <v-btn variant="text" @click="completionDialog = false">Weiter bearbeiten</v-btn>
          <v-btn color="#a33d32" variant="flat" prepend-icon="mdi-lock-outline" :disabled="!completionAcknowledged || completeDisabled || busy || completed" @click="confirmCompletion">Aufgabe abschließen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import JourneyIslandArt from './JourneyIslandArt.vue'
import TreasureMapArt from './TreasureMapArt.vue'
const props = defineProps<{ coins: number; completed: boolean; completeDisabled: boolean; busy: boolean }>()
const emit = defineEmits<{ leave: []; complete: [] }>()
const completionDialog = defineModel<boolean>('completionDialog', { default: false })
const completionAcknowledged = ref(false)
watch(completionDialog, () => { completionAcknowledged.value = false }, { flush: 'sync' })
const confirmCompletion = () => {
  if (!completionAcknowledged.value || props.completeDisabled || props.busy || props.completed) return
  completionDialog.value = false
  emit('complete')
}
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
