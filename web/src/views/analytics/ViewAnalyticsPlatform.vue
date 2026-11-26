<template>
  <div>
    <v-tabs :model-value="String(route.name)" density="compact" color="primary-dark" class="mb-4" @update:model-value="(name) => router.push({ name: String(name) })">
      <v-tab v-for="tab in tabs" :key="tab.name" :value="tab.name">{{ tab.title }}</v-tab>
    </v-tabs>

    <div class="d-flex flex-wrap align-center ga-4 mb-4">
      <v-select v-model="period" :items="periods" label="Period" density="compact" variant="outlined" hide-details class="period-select" />
      <v-switch v-model="includeStaff" color="primary-dark" label="Include staff" density="compact" hide-details />
      <span class="text-caption text-medium-emphasis flex-grow-1">
        Event counts cover the selected period. Counts are people or records, never model content. Staff are administrators and moderators.
      </span>
      <v-btn variant="tonal" prepend-icon="mdi-refresh" @click="refreshKey++">Refresh</v-btn>
    </div>

    <router-view v-slot="{ Component }">
      <component :is="Component" :key="refreshKey" />
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePlatformFilters } from '@/composables/usePlatformFilters'
import type { PlatformPeriod } from '@/services/analytics'

const route = useRoute()
const router = useRouter()
const { period, includeStaff } = usePlatformFilters()
// Changing the key remounts the active tab, which reloads its data.
const refreshKey = ref(0)

const tabs = [
  { title: 'Overview', name: 'AnalyticsPlatformOverview' },
  { title: 'Tasks', name: 'AnalyticsPlatformTasks' },
  { title: 'People', name: 'AnalyticsPlatformPeople' }
]
const periods: { title: string; value: PlatformPeriod }[] = [
  { title: 'Last 7 days', value: '7d' }, { title: 'Last 30 days', value: '30d' },
  { title: 'Semester (last 180 days)', value: 'semester' }, { title: 'All time', value: 'all' }
]
</script>

<style scoped>
.period-select { max-width: 240px; min-width: 200px; }
</style>
