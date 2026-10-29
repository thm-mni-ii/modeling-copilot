<template>
  <section class="mt-5" aria-label="Impuls-Fragen">
    <v-switch :model-value="config.enabled" label="Impuls-Fragen aktivieren" color="primary" @update:model-value="update('enabled', Boolean($event))">
      <template #append><PulseSettingHelp label="Impuls-Fragen aktivieren" text="Aktiviert freiwillige Impuls-Fragen während der Aufgabenbearbeitung. Lernende öffnen sie per Klick auf den Piraten und können sie mit ‚Später‘ wegklicken. Beim Deaktivieren bleiben die Einstellungen für eine spätere Aktivierung erhalten." /></template>
    </v-switch>
    <p class="text-caption mb-3">Änderungen gelten nach dem Speichern auch für laufende Lernpfade.</p>
    <p class="text-caption text-medium-emphasis mb-4">Die Abfrage passt sich den eingestellten Wartezeiten an. Zum Ausprobieren eine noch offene Aufgabe im Lernpfad bearbeiten und das Browserfenster aktiv halten. Nach 60 Sekunden ohne Aktivität pausiert die Abfrage. Der Fragebogen öffnet sich per Klick auf den Piraten unten rechts.</p>
    <div class="d-flex align-center ga-2">
      <v-btn variant="tonal" prepend-icon="mdi-plus" @click="picker = true">Fragebögen auswählen</v-btn>
      <PulseSettingHelp label="Fragebogen-Pool" text="Wähle mindestens einen veröffentlichten Fragebogen. Für jeden neuen Impuls wird ein Fragebogen mit gleicher Wahrscheinlichkeit aus diesem Pool gezogen. Bereits beantwortete Fragebögen können erneut erscheinen. Verwendet wird die aktuelle veröffentlichte Version." />
    </div>
    <div class="my-3">
      <v-chip v-for="id in config.surveyIds" :key="id" closable class="ma-1" @click:close="update('surveyIds', config.surveyIds.filter((item) => item !== id))">{{ surveys.find((survey) => survey.id === id)?.title ?? id }}</v-chip>
    </div>
    <v-row dense>
      <v-col v-for="field in fields" :key="field.key" cols="12" sm="6">
        <v-text-field :model-value="config[field.key]" :label="field.label" type="number" :min="field.min" :max="field.max" :clearable="field.nullable" :hint="field.hint" persistent-hint variant="outlined" @update:model-value="number(field.key, $event, field.nullable)">
          <template #append><PulseSettingHelp :label="field.label" :text="field.help" /></template>
        </v-text-field>
      </v-col>
    </v-row>
    <v-select :model-value="config.excludeStepIds" :items="steps.filter((step) => step.type !== 'survey').map((step) => ({ title: step.title, value: step.id }))" label="Tasks ohne Impulse" multiple chips closable-chips class="mt-3" @update:model-value="update('excludeStepIds', $event)">
      <template #append><PulseSettingHelp label="Tasks ohne Impulse" text="Bei den ausgewählten Aufgaben werden keine Impulse angeboten. Ohne Auswahl gelten die Impuls-Einstellungen für alle Aufgaben des Lernpfads. Fragebogen-Aktivitäten erhalten grundsätzlich keine Impulse; Challenges verhindern Impulse nicht." /></template>
    </v-select>
    <v-alert v-if="validation" type="warning" density="compact" variant="tonal">{{ validation }}</v-alert>
    <LearningPathSurveyPicker v-model="picker" purpose="pulse" :surveys="surveys" :steps="[]" :loading="loading" @add="add" />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { defaultPulseSurveyConfig, type PulseSurveyConfig, type PathStep } from '@/services/learningPaths'
import type { Survey } from '@/services/surveys'
import { validatePulseConfig } from '@/utils/learningPathEditor'
import LearningPathSurveyPicker from './LearningPathSurveyPicker.vue'
import PulseSettingHelp from './PulseSettingHelp.vue'

const props = defineProps<{ modelValue?: PulseSurveyConfig; steps: PathStep[]; surveys: Survey[]; loading: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: PulseSurveyConfig] }>()
const config = computed(() => props.modelValue ?? defaultPulseSurveyConfig())
const picker = ref(false)
const validation = computed(() => validatePulseConfig(config.value, props.steps))
const update = <K extends keyof PulseSurveyConfig>(key: K, value: PulseSurveyConfig[K]) => emit('update:modelValue', { ...config.value, [key]: value })
type NumberKey = 'minGapSeconds' | 'maxGapSeconds' | 'maxPerSession' | 'maxPerTask' | 'minActiveSeconds'
const number = (key: NumberKey, value: string | number | null, nullable: boolean) => update(key, nullable && (value === '' || value === null) ? null : Number(value))
const add = (ids: string[]) => {
  update('surveyIds', [...new Set([...config.value.surveyIds, ...ids])])
  picker.value = false
}
const fields: { key: NumberKey; label: string; min: number; max: number; nullable: boolean; hint: string; help: string }[] = [
  { key: 'minGapSeconds', label: 'Mindestabstand (Sekunden)', min: 1, max: 86400, nullable: false, hint: 'Nach Anzeige, Antwort, Wegklicken oder Ablauf', help: 'Frühestens nach dieser Wartezeit darf der nächste Impuls erscheinen. Anzeige, Antwort, Wegklicken und automatischer Ablauf starten die Wartezeit jeweils neu. Beispiel: 600 Sekunden sind 10 Minuten. Wird der Pirat nicht angeklickt, läuft das Angebot nach 40 Sekunden ab und zählt nicht als Antwort.' },
  { key: 'maxGapSeconds', label: 'Maximalabstand (Sekunden)', min: 1, max: 86400, nullable: true, hint: 'Leer = exakt der Mindestabstand', help: 'Der Abstand wird zufällig zwischen Mindest- und Maximalabstand gewählt. Dieser Wert muss mindestens dem Mindestabstand entsprechen. Leer bedeutet: keine Zufallsstreuung. Inaktivität oder erreichte Antwortlimits können die nächste Anzeige weiter verzögern.' },
  { key: 'maxPerSession', label: 'Antworten pro Besuch', min: 1, max: 100, nullable: false, hint: 'Wegklicken zählt nicht', help: 'Begrenzt die beantworteten Impulse während eines Besuchs der Modeling-Ansicht. Ein erneutes Öffnen oder Neuladen beginnt einen neuen Besuch. Nur abgesendete Antworten zählen; Wegklicken verbraucht kein Kontingent, startet aber die Wartezeit neu.' },
  { key: 'maxPerTask', label: 'Antworten pro Task und Run', min: 1, max: 1000, nullable: true, hint: 'Leer = unbegrenzt', help: 'Begrenzt die beantworteten Impulse für eine einzelne Aufgabenstation im persönlichen Lernpfad-Durchlauf, auch über mehrere Besuche hinweg. Leer bedeutet unbegrenzt. Zusätzlich gilt immer das Limit pro Besuch.' },
  { key: 'minActiveSeconds', label: 'Aktive Zeit vor erstem Impuls (Sekunden)', min: 0, max: 86400, nullable: false, hint: 'Nur aktive Bearbeitungszeit zählt', help: 'So viel aktive Bearbeitungszeit muss sich an dieser Aufgabe angesammelt haben, bevor der erste Impuls angeboten wird. Gezählt wird nur bei sichtbarem, fokussiertem Browserfenster ohne längere Inaktivität. Beispiel: 120 Sekunden sind 2 Minuten. Die Abfrage richtet sich nach der verbleibenden Wartezeit und erfolgt spätestens nach 30 Sekunden aktiver Bearbeitung erneut.' }
]
</script>
