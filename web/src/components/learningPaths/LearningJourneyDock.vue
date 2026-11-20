<template>
  <section class="journey-dock" aria-label="Deine Schatzreise">
    <div class="journey-landscape">
      <JourneyIslandArt class="journey-island" />
      <slot name="pulse" />
      <div class="journey-actions">
        <v-btn class="journey-map" variant="text" size="small" prepend-icon="mdi-map-outline" :disabled="busy" @click="emit('leave')">Zur Karte</v-btn>
        <v-btn class="journey-complete" variant="flat" size="small" :prepend-icon="completed ? 'mdi-check-circle-outline' : 'mdi-flag-checkered'" :loading="busy" :disabled="completeDisabled || busy || completed" @click="requestCompletion">{{ completed ? 'Geschafft!' : 'Abschließen' }}</v-btn>
        <div class="journey-actions-end">
          <div class="journey-coins" role="status" aria-live="polite" :aria-label="`${coins} Münzen gesammelt`">
            <TreasureMapArt kind="coin" /><strong>{{ coins }}</strong>
          </div>
          <FeatureTourMenu v-if="featureTourEnabled && feedbackAvailable" :feedback-legend-available="Boolean(helpUsage)" :check-available="!exhausted({ type: 'help.check' })" :help-request="helpRequest" :help-question="helpQuestion" :help-answer="helpAnswer" />
        </div>
      </div>
    </div>
    <div v-if="featureTourEnabled && feedbackAvailable && helpUsage" class="help-feedback-legend" data-help-feedback-legend aria-label="Verbrauch der automatischen Hilfe">
      <v-tooltip v-for="item in feedbackTypes" :key="item.type" :text="usageLabel(item)">
        <template #activator="{ props: tooltipProps }">
          <span v-bind="tooltipProps" class="help-feedback-type" :class="{ 'help-feedback-type--exhausted': exhausted(item) }" :aria-label="usageLabel(item)" :data-help-feedback-type="item.type">
            <v-icon size="19">{{ item.icon }}</v-icon>
            <small>{{ helpUsage[item.type].used }}/{{ helpUsage[item.type].limit ?? '∞' }}</small>
            <span>{{ item.short }}</span>
          </span>
        </template>
      </v-tooltip>
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
import FeatureTourMenu from './FeatureTourMenu.vue'
import type { HelpFeedbackType, HelpRequest, HelpUsage, HelpTourAnswer } from '@/services/learningPaths'
import { helpFeedbackOptions as feedbackTypes } from '@/services/learningPaths'
const props = defineProps<{ coins: number; completed: boolean; completeDisabled: boolean; busy: boolean; evaluationRequired?: boolean; helpUsage?: HelpUsage; featureTourEnabled?: boolean; feedbackAvailable?: boolean; helpRequest?: HelpRequest | null; helpQuestion?: string | null; helpAnswer?: HelpTourAnswer | null }>()
const emit = defineEmits<{ leave: []; complete: [] }>()
const completionDialog = defineModel<boolean>('completionDialog', { default: false })
const completionAcknowledged = ref(false)
const exhausted = (item: { type: HelpFeedbackType }) => {
  const usage = props.helpUsage?.[item.type]
  return Boolean(usage && usage.limit !== null && usage.used + usage.pending >= usage.limit)
}
const usageLabel = (item: { type: HelpFeedbackType; title: string }) => {
  const usage = props.helpUsage?.[item.type]
  const pending = usage?.pending ? ` (+${usage.pending} in Prüfung)` : ''
  return `${item.title}: ${usage?.used ?? 0} genutzt${pending}${usage?.limit === null ? ', unbegrenzt' : `, ${Math.max(0, (usage?.limit ?? 0) - (usage?.used ?? 0) - (usage?.pending ?? 0))} von ${usage?.limit ?? 0} übrig`}`
}
watch(completionDialog, () => { completionAcknowledged.value = false }, { flush: 'sync' })
const requestCompletion = () => {
  if (props.completeDisabled || props.busy || props.completed) return
  if (props.evaluationRequired) emit('complete')
  else completionDialog.value = true
}
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
.journey-actions { position: absolute; inset: 8px 6px auto; z-index: 3; display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 3px; }
.journey-actions-end { display: flex; justify-content: flex-end; align-items: center; gap: 3px; min-width: 0; }
.journey-map { justify-self: start; }
.help-feedback-legend { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 3px; padding: 7px 5px 8px; border-top: 2px solid #d5aa62; background: #f9e9c5; color: #694719; }
.help-feedback-type { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; min-width: 0; padding: 3px 1px; border: 1px solid #e6ca94; border-radius: 7px; background: #fff9ec; font-size: 9px; line-height: 1.15; font-variant-numeric: tabular-nums; white-space: nowrap; }
.help-feedback-type small, .help-feedback-type span { font-size: 9px; }
.help-feedback-type--exhausted { color: #8a332b; opacity: 0.62; }
.journey-coins { display: flex; align-items: center; gap: 2px; min-width: 0; padding: 3px 5px; border-radius: 9px; background: #fff4dce8; color: #694719; }
.journey-coins svg { width: 24px; height: 24px; flex-shrink: 0; }
.journey-coins strong { font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.journey-actions :deep(.v-btn) { padding-inline: 5px; min-width: 0; font-size: 0.6rem; letter-spacing: 0; text-transform: none; border-radius: 9px; min-height: 30px; }
.journey-actions :deep(.v-btn__prepend) { margin-inline: 0 3px; }
.journey-actions :deep(.v-btn__prepend .v-icon) { font-size: 16px; }
.journey-actions :deep(.feature-tour-trigger) { width: 30px; min-width: 30px; height: 30px; padding: 0; color: #365b56; background: #fff9eceb; }
.journey-map { color: #365b56; background: #fff9eceb; }
.journey-complete { background: #ffda86; color: #473722; }
</style>
