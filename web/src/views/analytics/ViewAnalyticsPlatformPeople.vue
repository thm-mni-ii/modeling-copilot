<template>
  <div>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">
      {{ error }}
      <template #append><v-btn variant="text" @click="load">Try again</v-btn></template>
    </v-alert>

    <v-sheet border rounded="lg" class="table-panel">
      <div class="pa-4">
        <h2 class="text-subtitle-1 font-weight-medium">People</h2>
        <div class="text-caption text-medium-emphasis">Counts only; no access to models. Hover a column title for its definition.</div>
      </div>
      <v-divider />
      <v-data-table-server
        v-model:page="page" v-model:items-per-page="itemsPerPage" v-model:sort-by="personSort"
        :headers="personHeaders" :items="persons" :items-length="totalPersons" :loading="loading"
        hover class="platform-table" loading-text="Loading people …" no-data-text="No people recorded yet."
      >
        <template #[`item.name`]="{ item }">{{ item.userName }}</template>
        <template #[`item.lastSeenAt`]="{ value }">{{ date(value) }}</template>
        <template #[`item.sessionSeconds`]="{ value }">{{ duration(value) }}</template>
      </v-data-table-server>
    </v-sheet>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { usePlatformFilters } from '@/composables/usePlatformFilters'
import analytics, { type PlatformPerson, type PlatformPersonSort } from '@/services/analytics'

const { period, includeStaff } = usePlatformFilters()
const persons = ref<PlatformPerson[]>([])
const totalPersons = ref(0)
const loading = ref(false)
const error = ref('')
const page = ref(1)
const itemsPerPage = ref(25)
const personSort = ref<{ key: string; order: 'asc' | 'desc' }[]>([{ key: 'lastSeenAt', order: 'desc' }])

const date = (value: string | null) => value ? new Date(value).toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' }) : '—'
const duration = (seconds: number) => {
  const minutes = Math.round(seconds / 60)
  if (!minutes) return '—'
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

const personHeaders = [
  { key: 'name', title: 'Person', headerProps: { title: 'Display name from the Feedbacksystem.' } },
  { key: 'lastSeenAt', title: 'Last seen', headerProps: { title: 'Last visit to the app. Not limited by the period.' } },
  { key: 'models', title: 'Models', headerProps: { title: 'Models created in the period, including archived ones.' } },
  { key: 'tasks', title: 'Tasks', headerProps: { title: 'Different tasks the person created a model for in the period.' } },
  { key: 'evaluations', title: 'Evaluations', headerProps: { title: 'Evaluation runs started in the period.' } },
  { key: 'helpRequests', title: 'Help requests', headerProps: { title: 'Learning-path help requests made in the period.' } },
  { key: 'sessionSeconds', title: 'Editor time', headerProps: { title: 'Summed duration of finished editor sessions started in the period. Idle time is included; sessions still open are not counted.' } }
]

let generation = 0
const load = async () => {
  const request = ++generation
  loading.value = true
  error.value = ''
  const sort = personSort.value[0] ?? { key: 'lastSeenAt', order: 'desc' }
  try {
    const result = (await analytics.platformPersons(period.value, includeStaff.value, sort.key as PlatformPersonSort, sort.order === 'desc', (page.value - 1) * itemsPerPage.value, itemsPerPage.value)).data
    if (request === generation) {
      persons.value = result.items
      totalPersons.value = result.total
    }
  } catch {
    if (request === generation) error.value = 'Platform analytics could not be loaded.'
  } finally {
    if (request === generation) loading.value = false
  }
}

watch([period, includeStaff], () => {
  if (page.value === 1) load()
  else page.value = 1
})
watch([page, itemsPerPage, personSort], load)
onMounted(load)
onUnmounted(() => { generation++ })
</script>

<style scoped>
.table-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.platform-table :deep(thead) { background: rgba(var(--v-theme-on-surface), 0.035); }
</style>
