<template>
  <section class="help-settings mt-4" aria-label="Hilfe anfordern konfigurieren">
    <v-switch :model-value="config.enabled" label="Hilfe beim Modellieren aktivieren" color="primary" hide-details @update:model-value="update('enabled', Boolean($event))" />
    <p class="text-body-2 text-medium-emphasis mt-2 mb-4">Zeigt „Ich brauche Hilfe“ bei den Modellierungsaufgaben dieses Lernpfads. Der aktuelle Modellstand wird beim Hilfe-Klick gespeichert.</p>
    <template v-if="config.enabled">
      <div class="help-settings-summary">
        <p class="text-body-2">Problem benennen → Problemstellen markieren → Hilfebedarf klären → Hilfequelle wählen</p>
        <v-btn variant="outlined" size="small" prepend-icon="mdi-play-outline" :disabled="!blueprint || Boolean(issue)" @click="preview = true">Ablauf ausprobieren</v-btn>
      </div>
      <p class="text-caption text-medium-emphasis my-4">Änderungen gelten nur für diesen Lernpfad. Beim Speichern des Lernpfads werden sie direkt für neue Hilfe-Anfragen veröffentlicht. Begonnene Anfragen behalten ihre Version.</p>
      <v-progress-linear v-if="pending" indeterminate aria-label="Hilfe-Fragen laden" />
      <v-alert v-if="loadError" type="error" variant="tonal" density="compact">{{ loadError }}<v-btn variant="text" size="small" @click="load">Erneut laden</v-btn></v-alert>
      <template v-if="blueprint">
        <section class="help-fixed-step" aria-label="Fester Problembezug">
          <div class="d-flex align-center ga-2 mb-2"><v-icon size="17">mdi-lock-outline</v-icon><h3 class="text-subtitle-2">Problem benennen</h3><v-chip size="x-small" variant="tonal">Fester Ablauf</v-chip></div>
          <p class="text-body-2">Worauf bezieht sich dein Problem?</p>
          <p class="text-caption text-medium-emphasis mt-1">Aufgabenstellung/Modell · Bedienung des Tools · Anderes mit Freitext</p>
          <p class="text-caption text-medium-emphasis mt-2">Diese Auswahl steuert den Markierungsschritt und bleibt deshalb unverändert.</p>
        </section>
        <v-select :model-value="markingMode" :items="markingOptions" label="Problemstellen bei Aufgabenstellung/Modell markieren" variant="outlined" density="compact" persistent-hint :hint="markingMode === 'required' ? 'Mindestens ein Modellelement oder eine Textstelle muss markiert werden.' : markingMode === 'optional' ? 'Lernende können ohne Markierung fortfahren, etwa bei einem noch leeren Modell.' : 'Nach dem Problembezug folgen direkt die Fragen zum Hilfebedarf.'" class="my-4" @update:model-value="setMarkingMode" />
        <p class="text-subtitle-2 mb-1">Fragen und Antworten anpassen</p>
        <p class="text-caption text-medium-emphasis mb-3">Formulierungen und Antwortoptionen sind bearbeitbar. Anzahl, Reihenfolge und Funktion der Fragen bleiben gleich.</p>
        <v-expansion-panels v-model="editing" variant="accordion">
          <v-expansion-panel v-for="(item, index) in editableHelpQuestions" :key="item.name" :value="item.name">
            <v-expansion-panel-title>
              <div class="help-question-summary"><strong>{{ index + 1 }}. {{ item.title }}</strong><span>{{ question(item.name).title }}</span><span class="text-caption text-medium-emphasis">{{ question(item.name).choices.length }} Antwortoptionen · {{ config.questionEdits?.[item.name] ? 'Angepasst' : 'Standard' }} · Bearbeiten</span></div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <v-text-field :model-value="question(item.name).title" label="Frage" variant="outlined" density="compact" maxlength="256" hide-details class="mb-4" @update:model-value="editTitle(item.name, $event)" />
              <ol class="help-options">
                <li v-for="(choice, choiceIndex) in question(item.name).choices" :key="choice.id" class="help-option">
                  <v-text-field :id="`help-choice-${item.name}-${choice.id}`" :model-value="choice.text" :label="`Antwortoption ${choiceIndex + 1}`" variant="outlined" density="compact" maxlength="256" hide-details @update:model-value="editChoice(item.name, choice.id, $event)" />
                  <div class="help-option-actions">
                    <v-btn icon="mdi-arrow-up" size="x-small" variant="text" :disabled="choiceIndex === 0" :aria-label="`Antwortoption ${choiceIndex + 1} nach oben`" @click="moveChoice(item.name, choiceIndex, -1)" />
                    <v-btn icon="mdi-arrow-down" size="x-small" variant="text" :disabled="choiceIndex === question(item.name).choices.length - 1" :aria-label="`Antwortoption ${choiceIndex + 1} nach unten`" @click="moveChoice(item.name, choiceIndex, 1)" />
                    <v-btn icon="mdi-close" size="x-small" variant="text" :disabled="question(item.name).choices.length <= 2" :aria-label="`Antwortoption ${choiceIndex + 1} entfernen`" @click="removeChoice(item.name, choice.id)" />
                  </div>
                </li>
              </ol>
              <p v-if="helpQuestionIssue(question(item.name))" class="text-error text-caption mt-2" role="alert">{{ helpQuestionIssue(question(item.name)) }}</p>
              <div class="d-flex flex-wrap ga-2 mt-3">
                <v-btn variant="tonal" size="small" prepend-icon="mdi-plus" :disabled="question(item.name).choices.length >= 20" @click="addChoice(item.name)">Antwortoption hinzufügen</v-btn>
                <v-btn v-if="config.questionEdits?.[item.name]" variant="text" size="small" @click="resetQuestion(item.name)">Standard wiederherstellen</v-btn>
              </div>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        <p class="text-caption text-medium-emphasis mt-4">Eine ausgewählte Hilfequelle versendet keine Nachricht. Lernende nutzen das gewählte Angebot anschließend selbstständig.</p>
      </template>
      <v-dialog v-model="preview" max-width="420" scrollable aria-label="Vorschau des Hilfe-Ablaufs">
        <v-card>
          <v-card-title class="d-flex align-center text-subtitle-1">Hilfe-Ablauf ausprobieren<v-spacer /><v-btn icon="mdi-close" size="small" variant="text" aria-label="Vorschau schließen" @click="preview = false" /></v-card-title>
          <v-card-text><HelpFlowPreview v-if="preview && blueprint" :blueprint="blueprint" :config="config" /></v-card-text>
        </v-card>
      </v-dialog>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import paths, { defaultHelpRequestConfig, type HelpBlueprint, type HelpEditableQuestion, type HelpQuestionEdit, type HelpRequestConfig } from '@/services/learningPaths'
import { editableHelpQuestions, helpQuestion, helpQuestionIssue } from '@/utils/helpQuestionnaire'
import HelpFlowPreview from './HelpFlowPreview.vue'

const props = defineProps<{ modelValue?: HelpRequestConfig }>()
const emit = defineEmits<{ 'update:modelValue': [config: HelpRequestConfig]; validation: [issue: string] }>()
const config = computed(() => ({ ...defaultHelpRequestConfig(), ...props.modelValue }))
const blueprint = ref<HelpBlueprint | null>(null)
const pending = ref(false), loadError = ref(''), preview = ref(false), editing = ref<HelpEditableQuestion>()
let disposed = false
const update = <K extends keyof HelpRequestConfig>(key: K, value: HelpRequestConfig[K]) => emit('update:modelValue', { ...config.value, [key]: value })
const load = async () => {
  if (pending.value) return
  pending.value = true
  loadError.value = ''
  try { const result = await paths.helpBlueprint(); if (!disposed) blueprint.value = result.data }
  catch { if (!disposed) loadError.value = 'Die Standardfragen konnten nicht geladen werden.' }
  finally { if (!disposed) pending.value = false }
}
watch(() => config.value.enabled, (enabled) => { if (enabled && !blueprint.value) void load() }, { immediate: true })
const markingMode = computed(() => !config.value.markingEnabled ? 'off' : config.value.markingRequired ? 'required' : 'optional')
const markingOptions = [{ title: 'Freiwillig', value: 'optional' }, { title: 'Erforderlich', value: 'required' }, { title: 'Ausgeschaltet', value: 'off' }]
const setMarkingMode = (mode: string) => emit('update:modelValue', { ...config.value, markingEnabled: mode !== 'off', markingRequired: mode === 'required' })
const question = (name: HelpEditableQuestion) => helpQuestion(blueprint.value!, config.value, name)
const edit = (name: HelpEditableQuestion, change: (copy: HelpQuestionEdit) => void) => {
  const copy: HelpQuestionEdit = JSON.parse(JSON.stringify(question(name)))
  change(copy)
  update('questionEdits', { ...config.value.questionEdits, [name]: copy })
}
const editTitle = (name: HelpEditableQuestion, title: string) => edit(name, q => { q.title = title ?? '' })
const editChoice = (name: HelpEditableQuestion, id: string, text: string) => edit(name, q => { q.choices.find(c => c.id === id)!.text = text ?? '' })
const focusChoice = async (name: HelpEditableQuestion, id: string) => { await nextTick(); document.getElementById(`help-choice-${name}-${id}`)?.focus() }
const addChoice = (name: HelpEditableQuestion) => {
  const id = `choice_${crypto.randomUUID().replace(/-/g, '')}`
  edit(name, q => { q.choices.push({ id, text: '' }) })
  void focusChoice(name, id)
}
const removeChoice = (name: HelpEditableQuestion, id: string) => {
  const choices = question(name).choices
  const index = choices.findIndex(c => c.id === id)
  const target = choices[index + 1] ?? choices[index - 1]
  edit(name, q => { q.choices = q.choices.filter(c => c.id !== id) })
  if (target) void focusChoice(name, target.id)
}
const moveChoice = (name: HelpEditableQuestion, index: number, delta: number) => edit(name, q => { const [choice] = q.choices.splice(index, 1); q.choices.splice(index + delta, 0, choice) })
const resetQuestion = (name: HelpEditableQuestion) => { const edits = { ...config.value.questionEdits }; delete edits[name]; update('questionEdits', edits) }
const issue = computed(() => {
  if (!config.value.enabled) return ''
  if (loadError.value) return loadError.value
  if (!blueprint.value) return 'Die Hilfe-Fragen werden noch geladen.'
  for (const item of editableHelpQuestions) { const error = helpQuestionIssue(question(item.name)); if (error) return `${item.title}: ${error}` }
  return ''
})
watch(issue, value => emit('validation', value), { immediate: true })
onBeforeUnmount(() => { disposed = true; emit('validation', '') })
</script>

<style scoped>
.help-settings-summary { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 12px; border: 1px solid rgba(var(--v-theme-outline), 0.18); border-radius: 8px; }
.help-settings-summary p { flex: 1; min-width: 220px; }
.help-fixed-step { padding: 12px; background: rgba(var(--v-theme-on-surface), 0.035); border-radius: 8px; }
.help-question-summary { display: flex; flex-direction: column; gap: 5px; min-width: 0; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.help-options { padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; }
.help-option { display: flex; align-items: center; gap: 4px; }
.help-option :deep(.v-input) { min-width: 0; }
.help-option-actions { display: flex; flex-shrink: 0; }
@media (max-width: 600px) { .help-option { flex-wrap: wrap; } .help-option :deep(.v-input) { flex-basis: 100%; } .help-option-actions { margin-left: auto; } }
</style>
