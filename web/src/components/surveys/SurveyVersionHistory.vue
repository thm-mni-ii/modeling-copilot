<template>
  <v-dialog :model-value="modelValue" max-width="850" scrollable @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title class="d-flex align-center">Versionsverlauf<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Versionsverlauf schließen" @click="$emit('update:modelValue', false)" /></v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" density="compact" class="mb-4">Alle Versionen enthalten den vollständigen Stand. Ein Release bleibt dauerhaft ein Release. Die Aktivierung einer älteren Version verändert den aktuellen Entwurf nicht.</v-alert>
        <v-alert v-if="error" type="error" class="mb-3">{{ error }}<v-btn variant="text" @click="load">Erneut laden</v-btn></v-alert>
        <v-progress-linear v-if="loading" indeterminate />
        <v-card v-for="version in versions" :key="version.id" variant="outlined" class="pa-4 mt-3">
          <div class="d-flex flex-wrap align-center ga-2">
            <strong>Version {{ version.version }}</strong
            ><v-chip size="small">{{ version.kind === 'release' ? 'Release' : 'Checkpoint' }}</v-chip>
            <v-chip v-if="version.id === activeReleaseId" size="small" color="success">Aktiv</v-chip>
            <v-chip v-if="version.id === latestVersionId" size="small">Letzter Stand</v-chip>
          </div>
          <p class="my-2">{{ version.title }}</p>
          <p class="text-caption text-medium-emphasis">Gespeichert: {{ date(version.createdAt) }} · {{ version.createdBy ?? 'Unbekannt (Altdaten)' }}</p>
          <p v-if="version.kind === 'release'" class="text-caption text-medium-emphasis">Veröffentlicht: {{ version.releasedAt ? date(version.releasedAt) : 'Altdaten' }} · {{ version.releasedBy ?? 'Unbekannt (Altdaten)' }}</p>
          <div class="d-flex flex-wrap ga-2 mt-2">
            <v-btn size="small" variant="text" @click="$emit('preview', version)">Vorschau</v-btn>
            <v-btn size="small" variant="tonal" :disabled="version.id === activeReleaseId" @click="$emit('release', version)">{{ version.kind === 'release' ? 'Release aktivieren' : 'Als Release veröffentlichen' }}</v-btn>
          </div>
        </v-card>
        <v-btn v-if="versions.length < versionTotal" class="mt-3" :loading="loading" @click="moreVersions">Weitere Versionen</v-btn>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import surveys, { surveyError, type SurveyVersionInfo } from '@/services/surveys'
const props = defineProps<{ modelValue: boolean; surveyId: string; latestVersionId: string; activeReleaseId: string | null; revision: number }>()
defineEmits<{ 'update:modelValue': [value: boolean]; preview: [version: SurveyVersionInfo]; release: [version: SurveyVersionInfo] }>()
const versions = ref<SurveyVersionInfo[]>([])
const versionTotal = ref(0),
  loading = ref(false),
  error = ref('')
const date = (value: string) => new Date(value).toLocaleString('de-DE')
let generation = 0
async function load() {
  if (!props.modelValue || !props.surveyId) return
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    const history = await surveys.versions(props.surveyId)
    if (current !== generation) return
    versions.value = history.data.items
    versionTotal.value = history.data.total
  } catch (e) {
    if (current === generation) error.value = surveyError(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
async function moreVersions() {
  if (loading.value) return
  const current = generation
  loading.value = true
  try {
    const page = (await surveys.versions(props.surveyId, versions.value.length)).data
    if (current === generation) {
      versions.value.push(...page.items)
      versionTotal.value = page.total
    }
  } catch (e) {
    if (current === generation) error.value = surveyError(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
watch(
  () => [props.modelValue, props.surveyId, props.revision],
  () => {
    void load()
  },
  { immediate: true }
)
</script>
