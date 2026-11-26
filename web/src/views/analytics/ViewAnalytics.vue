<template>
  <v-container max-width="1440" class="py-8">
    <div class="d-flex flex-wrap align-start ga-3 mb-4">
      <span class="page-icon"><v-icon size="26" color="primary-dark">mdi-chart-box-outline</v-icon></span>
      <div class="flex-grow-1 page-heading">
        <h1 class="text-h4">Analytics</h1>
        <p class="text-body-2 text-medium-emphasis mt-2">Usage, tours, learning path progress and survey results.</p>
      </div>
    </div>
    <v-tabs :model-value="activeTab" color="primary-dark" class="mb-5" @update:model-value="(to) => router.push(String(to))">
      <v-tab v-for="tab in tabs" :key="tab.to" :value="tab.to">{{ tab.title }}</v-tab>
    </v-tabs>
    <router-view />
  </v-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const tabs = [
  { title: 'Platform', to: '/analytics/platform' },
  { title: 'Tours', to: '/analytics/tours' },
  { title: 'Learning paths', to: '/analytics/learning-paths' },
  { title: 'Surveys', to: '/analytics/surveys' }
]
// Tabs match by prefix so sub-pages and detail pages keep their tab active.
const activeTab = computed(() => tabs.find((tab) => route.path.startsWith(tab.to))?.to ?? tabs[0].to)
</script>

<style scoped>
.page-icon { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius: 12px; background: rgba(var(--v-theme-primary), 0.1); flex-shrink: 0; }
.page-heading { min-width: 220px; }
</style>
