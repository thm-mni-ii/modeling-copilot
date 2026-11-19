<template>
  <v-dialog :model-value="modelValue" max-width="640" scrollable :persistent="busy" @update:model-value="emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>Auswertung starten</v-card-title>
      <v-form v-model="valid" @submit.prevent="confirm">
        <v-card-text class="pt-0">
          <p class="text-body-2 text-medium-emphasis mb-4">So werden Beschriftungen zugeordnet. Die Schwellen gelten nur für diesen Lauf.</p>

          <section class="flow-step" aria-labelledby="flow-prepare">
            <h3 id="flow-prepare" class="flow-step__title"><span class="flow-step__number">1</span>Vorbereiten <span class="flow-step__note">immer</span></h3>
            <div class="flow-row">
              <span>Schreibweise vereinheitlichen</span>
              <span class="example">GebäudeNr. <v-icon icon="mdi-arrow-right" size="x-small" /> gebaeudenummer</span>
            </div>
            <div class="flow-row">
              <span>Ausschließen</span>
              <span class="d-flex flex-column align-end ga-1">
                <span class="example">Version 1 ≠ Version 2 <span class="text-medium-emphasis">Ziffern</span></span>
                <span class="example">VersuchsNr. ≠ BesuchsNr. <span class="text-medium-emphasis">Wortanfang</span></span>
              </span>
            </div>
          </section>

          <section class="flow-step" aria-labelledby="flow-tiers">
            <h3 id="flow-tiers" class="flow-step__title"><span class="flow-step__number">2</span>Stufen prüfen <span class="flow-step__note">erste passende Stufe entscheidet</span></h3>
            <div class="flow-row">
              <div>
                <div class="font-weight-medium">Gleiche Schreibweise</div>
                <div class="text-caption text-medium-emphasis">fest = 1,00</div>
              </div>
              <ExampleScore left="Labor-Raum" right="Laborraum" :score="1" :pass="true" />
            </div>
            <div class="flow-row">
              <div class="flow-row__control">
                <div class="font-weight-medium mb-1">Schreibvariante</div>
                <v-text-field v-model.number="draft.spelling" v-bind="numberField" label="Damerau ab" :rules="[rangeRule]" />
              </div>
              <ExampleScore left="Mitarbeiter" right="Mitarbieter" :score="0.909" :pass="passes(0.909, draft.spelling)" />
            </div>
            <div class="flow-row">
              <div class="flow-row__control">
                <div class="font-weight-medium mb-1">Bedeutung</div>
                <div class="d-flex ga-2">
                  <v-text-field v-model.number="draft.meaning" v-bind="numberField" label="Embedding ab" :rules="[rangeRule]" />
                  <v-text-field v-model.number="draft.meaningFloor" v-bind="numberField" label="Graubereich ab" :rules="[rangeRule, floorRule]" />
                </div>
              </div>
              <span class="d-flex flex-column align-end ga-1">
                <ExampleScore left="Bestellung" right="Order" :score="0.905" :pass="passes(0.905, draft.meaning)" />
                <ExampleScore left="Kunde" right="Customer" :score="0.78" :pass="passes(0.78, draft.meaning)" :grey="!passes(0.78, draft.meaning) && passes(0.78, draft.meaningFloor)" />
              </span>
            </div>
            <div class="scale" aria-hidden="true">
              <span class="scale__part scale__part--none" :style="{ width: `${share(0, draft.meaningFloor)}%` }">keine Evidenz</span>
              <span class="scale__part scale__part--grey" :style="{ width: `${share(draft.meaningFloor, draft.meaning)}%` }">Graubereich</span>
              <span class="scale__part scale__part--match" :style="{ width: `${share(draft.meaning, 1)}%` }">Treffer</span>
            </div>
            <p class="text-caption text-medium-emphasis mt-1 mb-0">Graubereich zählt nur, wenn die Struktur das Paar bestätigt.</p>
          </section>

          <section class="flow-step" aria-labelledby="flow-decide">
            <h3 id="flow-decide" class="flow-step__title"><span class="flow-step__number">3</span>Zuordnen <span class="flow-step__note">immer</span></h3>
            <div class="flow-row">
              <span>Eindeutig 1:1</span>
              <span class="example">Kunde ↔ 2× Kunde <v-icon icon="mdi-arrow-right" size="x-small" /> bleibt offen</span>
            </div>
            <div class="flow-row">
              <span>Struktur bestätigt</span>
              <span class="example">gleicher Besitzer, passende Kinder</span>
            </div>
          </section>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="text" :disabled="busy || isDefault" @click="Object.assign(draft, textEvidenceDefaults)">Standardwerte</v-btn>
          <v-spacer />
          <v-btn variant="text" :disabled="busy" @click="emit('update:modelValue', false)">Abbrechen</v-btn>
          <v-btn type="submit" color="primary" variant="flat" :loading="busy" :disabled="busy || valid === false">Auswertung starten</v-btn>
        </v-card-actions>
      </v-form>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { textEvidenceDefaults, type TextEvidenceThresholds } from '@/services/api/types/evaluation'

// Module scope: survives reopening the dialog, resets on page reload.
let saved: TextEvidenceThresholds = { ...textEvidenceDefaults }
</script>

<script setup lang="ts">
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { VIcon } from 'vuetify/components'
import type { EvaluationParameters } from '@/services/api/types/evaluation'

const props = defineProps<{ modelValue: boolean; busy: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; confirm: [parameters: EvaluationParameters] }>()
const draft = reactive<TextEvidenceThresholds>({ ...saved })
const valid = ref<boolean | null>(null)

watch(() => props.modelValue, (open) => {
  if (open) Object.assign(draft, saved)
})

const number = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const numberField = computed(() => ({ type: 'number', min: 0, max: 1, step: 0.05, variant: 'outlined' as const, density: 'compact' as const, hideDetails: 'auto' as const, disabled: props.busy, class: 'number-field' }))
const isNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const rangeRule = (value: unknown) => (isNumber(value) && value >= 0 && value <= 1) || '0 bis 1'
const floorRule = (value: unknown) => !isNumber(value) || value <= draft.meaning || 'höchstens Bedeutung'
const passes = (score: number, threshold: number) => isNumber(threshold) && score >= threshold
const clamp = (value: number) => Math.min(1, Math.max(0, isNumber(value) ? value : 0))
const share = (from: number, to: number) => Math.max(0, 100 * (clamp(to) - clamp(from)))
const isDefault = computed(() => (Object.keys(textEvidenceDefaults) as (keyof TextEvidenceThresholds)[]).every(key => draft[key] === textEvidenceDefaults[key]))

// Example pair with its real score; the mark follows the thresholds currently entered.
const ExampleScore = defineComponent({
  props: { left: { type: String, required: true }, right: { type: String, required: true }, score: { type: Number, required: true }, pass: Boolean, grey: Boolean },
  setup: (example) => () => h('span', { class: 'example' }, [
    `${example.left} ↔ ${example.right} `,
    h('span', { class: 'text-medium-emphasis' }, number.format(example.score)),
    h(VIcon, { icon: example.pass ? 'mdi-check' : example.grey ? 'mdi-help' : 'mdi-close', size: 'small',
      color: example.pass ? 'primary' : undefined, class: 'ml-1',
      'aria-label': example.pass ? 'zugeordnet' : example.grey ? 'nur mit Strukturbestätigung' : 'nicht zugeordnet' }),
  ]),
})

const confirm = () => {
  if (props.busy || Object.values(draft).some(value => rangeRule(value) !== true) || floorRule(draft.meaningFloor) !== true) return
  saved = { ...draft }
  // Defaults are sent as null so the run records "workflow defaults" instead of a copy of them.
  emit('confirm', { textEvidence: isDefault.value ? null : { ...draft } })
}
</script>

<style scoped>
.flow-step {
  border-left: 2px solid rgba(var(--v-border-color), var(--v-border-opacity));
  margin-left: 11px;
  padding: 0 0 16px 20px;
}
.flow-step:last-child {
  padding-bottom: 0;
}
.flow-step__title {
  position: relative;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 8px;
}
.flow-step__number {
  position: absolute;
  left: -33px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
.flow-step__note {
  font-size: 0.75rem;
  font-weight: 400;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  margin-left: 6px;
}
.flow-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 12px;
  padding: 6px 0;
  font-size: 0.875rem;
}
.flow-row + .flow-row {
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.flow-row__control {
  min-width: 0;
}
.number-field {
  width: 132px;
  flex: 0 0 auto;
}
:deep(.example) {
  display: inline-flex;
  align-items: center;
  font-size: 0.8125rem;
  white-space: nowrap;
  gap: 4px;
}
.scale {
  display: flex;
  height: 18px;
  border-radius: 4px;
  overflow: hidden;
  font-size: 0.6875rem;
  line-height: 18px;
}
.scale__part {
  overflow: hidden;
  white-space: nowrap;
  text-align: center;
  text-overflow: clip;
}
.scale__part--none {
  background: rgba(var(--v-theme-on-surface), 0.06);
}
.scale__part--grey {
  background: rgba(var(--v-theme-on-surface), 0.16);
}
.scale__part--match {
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
</style>
