<template>
  <v-sheet border rounded="lg" class="feature-tour-report mb-4">
    <div class="d-flex flex-wrap align-center ga-3 mb-4">
      <span class="report-icon"><v-icon size="20" color="info">mdi-help-circle-outline</v-icon></span>
      <div class="flex-grow-1">
        <h2 class="text-subtitle-1 font-weight-medium">Hilfe-Tour: Nutzung</h2>
        <p class="text-caption text-medium-emphasis mb-0">Individuelle Aufrufe und Fortschritt der neuen Hilfefunktionen</p>
      </div>
      <v-btn size="small" variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">Aktualisieren</v-btn>
    </div>
    <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-3">{{ error }}</v-alert>
    <div class="report-stats mb-4">
      <div><strong>{{ report.openedUsers }}</strong><span>Personen mit Aufruf</span></div>
      <div><strong>{{ report.openedEvents }}</strong><span>Aufrufe gesamt</span></div>
      <div><strong>{{ report.tourStarts }}</strong><span>Gestartete Touren</span></div>
    </div>
    <v-data-table :headers="headers" :items="report.participants" :loading="loading" :items-per-page="10" :items-per-page-options="[10, 25, 50]" density="compact" no-data-text="Noch keine Tour-Aufrufe erfasst.">
      <template #[`item.userName`]="{ item }">
        <div>{{ item.userName }}<div class="text-caption text-medium-emphasis">ID: {{ item.userId }}</div></div>
      </template>
      <template #[`item.progress`]="{ item }">
        <span>{{ item.completedItems.length ? item.completedItems.map(itemTitle).join(', ') : '—' }}</span>
        <div class="text-caption text-medium-emphasis">Übersprungen: {{ item.skippedItems.length ? item.skippedItems.map(itemTitle).join(', ') : '—' }}</div>
      </template>
      <template #[`item.firstOpenedAt`]="{ value }">{{ date(value) }}</template>
      <template #[`item.lastEventAt`]="{ value }">{{ date(value) }}</template>
      <template #[`item.tourStarts`]="{ value }">{{ value }}</template>
    </v-data-table>
  </v-sheet>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import paths, { type FeatureTourReport as Report } from '@/services/learningPaths'

const emptyReport = (): Report => ({ openedUsers: 0, openedEvents: 0, tourStarts: 0, participants: [] })
const report = ref<Report>(emptyReport())
const loading = ref(false)
const error = ref('')
const headers = [
  { key: 'userName', title: 'Person' },
  { key: 'openedCount', title: 'Menü-Aufrufe' },
  { key: 'tourStarts', title: 'Tour-Starts' },
  { key: 'progress', title: 'Fortschritt', sortable: false },
  { key: 'firstOpenedAt', title: 'Erster Aufruf' },
  { key: 'lastEventAt', title: 'Letztes Ereignis' }
]
const itemTitles: Record<string, string> = {
  'feedback-types': 'Hilfemöglichkeiten',
  'help-request': 'Hilfe anfordern',
  'mark-object': 'Element markieren',
  'automatic-feedback': 'Automatische Prüfung',
  'help-feedback-walkthrough': 'Automatisches Feedback entdecken'
}
const itemTitle = (item: string) => itemTitles[item] ?? item
const date = (value: string | null) => value ? new Date(value).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const load = async () => {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try { report.value = (await paths.featureTourReport()).data }
  catch { error.value = 'Die Tour-Auswertung konnte nicht geladen werden.' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.feature-tour-report { padding: 18px; }
.report-icon { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: rgba(var(--v-theme-info), 0.08); }
.report-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.report-stats > div { display: flex; flex-direction: column; padding: 12px; border-radius: 8px; background: rgba(var(--v-theme-primary), 0.04); }
.report-stats strong { font-size: 1.45rem; font-variant-numeric: tabular-nums; }
.report-stats span { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); font-size: 0.75rem; }
@media (max-width: 600px) { .report-stats { grid-template-columns: 1fr; gap: 6px; } }
</style>
