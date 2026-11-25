<template>
  <div>
    <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/analytics/learning-paths" class="mb-3">All learning paths</v-btn>
    <div class="d-flex flex-wrap align-start ga-3 mb-2">
      <div class="flex-grow-1 path-heading">
        <div class="d-flex flex-wrap align-center ga-2">
          <h2 class="text-h5">{{ header.data?.name ?? 'Learning path' }}</h2>
          <v-chip v-if="header.data" size="small" variant="tonal">{{ pathVisibilityLabel(header.data.visibility) }}</v-chip>
          <v-chip v-if="header.data" size="small" variant="tonal">Revision {{ header.data.revision }}</v-chip>
        </div>
        <p v-if="header.data?.description" class="text-body-2 text-medium-emphasis mt-2">{{ header.data.description }}</p>
      </div>
      <div class="d-flex flex-wrap align-center ga-3">
        <v-switch v-model="includeStaff" color="primary-dark" label="Include staff" density="compact" hide-details />
        <v-btn variant="tonal" prepend-icon="mdi-refresh" :loading="busy" @click="refresh">Refresh</v-btn>
      </div>
    </div>
    <p v-if="header.data" class="text-caption text-medium-emphasis mb-3">
      <template v-if="includeStaff">Runs of administrators and moderators are included in all figures.</template>
      <template v-else-if="header.data.hiddenStaffRuns">{{ header.data.hiddenStaffRuns }} {{ header.data.hiddenStaffRuns === 1 ? 'run' : 'runs' }} of administrators and moderators {{ header.data.hiddenStaffRuns === 1 ? 'is' : 'are' }} hidden. Switch on "Include staff" to count them.</template>
      <template v-else>Staff runs are excluded from all figures; there are none in this path.</template>
    </p>
    <load-state :loading="header.loading && !header.data" :error="header.error" @retry="retryHeader" />
    <template v-if="!header.error">
      <v-tabs :model-value="tab" density="compact" color="primary-dark" show-arrows @update:model-value="selectTab">
        <v-tab v-for="item in TABS" :key="item.value" :value="item.value">{{ item.title }}</v-tab>
      </v-tabs>
      <v-window :key="templateId" :model-value="tab" :touch="false" class="mt-4">
        <v-window-item value="overview" :transition="false" :reverse-transition="false">
          <load-state :loading="rows.loading && !rows.data" :error="rows.error" @retry="rows.load" />
          <path-overview-tab v-if="header.data && rows.data" :template-id="templateId" :summary="header.data" :records="rows.data" />
        </v-window-item>
        <v-window-item value="participants" :transition="false" :reverse-transition="false">
          <load-state :loading="rows.loading && !rows.data" :error="rows.error" @retry="rows.load" />
          <load-state :loading="false" :error="activity.error" @retry="activity.load" />
          <path-participants-tab v-if="rows.data" :template-id="templateId" :rows="rows.data" :activity="activity.data" :loading="rows.loading" :hidden-staff-runs="header.data?.hiddenStaffRuns ?? 0" />
        </v-window-item>
        <v-window-item value="attempts" :transition="false" :reverse-transition="false">
          <load-state :loading="feedback.loading && !feedback.data" :error="feedback.error" @retry="feedback.load" />
          <attempts-feedback-section v-if="feedback.data" :steps="feedback.data.steps" />
        </v-window-item>
        <v-window-item value="help" :transition="false" :reverse-transition="false">
          <load-state :loading="feedback.loading && !feedback.data" :error="feedback.error" @retry="feedback.load" />
          <help-pulse-section v-if="feedback.data" :feedback="feedback.data" />
        </v-window-item>
        <v-window-item value="activity" :transition="false" :reverse-transition="false">
          <load-state :loading="activity.loading && !activity.data" :error="activity.error" @retry="activity.load" />
          <activity-section v-if="activity.data" :activity="activity.data" />
        </v-window-item>
        <v-window-item value="surveys" :transition="false" :reverse-transition="false">
          <load-state :loading="surveys.loading && !surveys.data" :error="surveys.error" @retry="surveys.load" />
          <path-surveys-tab v-if="surveys.data" :surveys="surveys.data" />
        </v-window-item>
      </v-window>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLazyResource } from '@/composables/useLazyResource'
import analytics from '@/services/analytics'
import paths, { pathVisibilityLabel, type PathProgressSummary } from '@/services/learningPaths'
import ActivitySection from '@/components/analytics/ActivitySection.vue'
import AttemptsFeedbackSection from '@/components/analytics/AttemptsFeedbackSection.vue'
import HelpPulseSection from '@/components/analytics/HelpPulseSection.vue'
import LoadState from '@/components/analytics/LoadState.vue'
import PathOverviewTab from '@/components/analytics/PathOverviewTab.vue'
import PathParticipantsTab from '@/components/analytics/PathParticipantsTab.vue'
import PathSurveysTab from '@/components/analytics/PathSurveysTab.vue'

const props = defineProps<{ templateId: string }>()
const route = useRoute()
const router = useRouter()
const TABS = [
  { value: 'overview', title: 'Overview' }, { value: 'participants', title: 'Participants' },
  { value: 'attempts', title: 'Attempts & feedback' }, { value: 'help', title: 'Help & pulse' },
  { value: 'activity', title: 'Activity' }, { value: 'surveys', title: 'Surveys' }
]
const includeStaff = ref(false)
const tab = computed(() => TABS.find((item) => item.value === route.query.tab)?.value ?? 'overview')
const selectTab = (value: unknown) => router.replace({ query: { ...route.query, tab: value === 'overview' ? undefined : String(value) } })

// Every endpoint is requested when a tab needs it for the first time; the result is kept across tab switches.
const header = useLazyResource(
  async () => (await analytics.path(props.templateId, includeStaff.value)).data,
  (e) => (e as { response?: { status?: number } }).response?.status === 404 ? 'This learning path does not exist.' : 'Learning path figures could not be loaded.'
)
const rows = useLazyResource(async () => {
  const result: PathProgressSummary[] = []
  for (let skip = 0; ; ) {
    const chunk = (await paths.progress(skip, props.templateId, includeStaff.value)).data
    result.push(...chunk.items)
    skip += chunk.items.length
    if (!chunk.items.length || skip >= chunk.total) return result
  }
}, 'Participants could not be loaded.')
const feedback = useLazyResource(async () => (await analytics.pathFeedback(props.templateId, includeStaff.value)).data, 'Attempts, help and pulse figures could not be loaded.')
const activity = useLazyResource(async () => (await analytics.pathActivity(props.templateId, includeStaff.value)).data, 'Activity figures could not be loaded.')
const surveys = useLazyResource(async () => (await analytics.pathSurveys(props.templateId, includeStaff.value)).data, 'Survey answers could not be loaded.')
const all = [header, rows, feedback, activity, surveys]
const tabResources: Record<string, { ensure: () => Promise<void> }[]> = {
  overview: [rows], participants: [rows, activity], attempts: [feedback], help: [feedback], activity: [activity], surveys: [surveys]
}
const busy = computed(() => all.some((resource) => resource.loading))

const ensureTab = () => tabResources[tab.value].forEach((resource) => void resource.ensure())
const retryHeader = async () => { await header.load(); ensureTab() }
const refresh = () => {
  void header.load()
  for (const resource of all) if (resource.data && resource !== header) void resource.load()
  ensureTab()
}
watch(tab, ensureTab)
watch([() => props.templateId, includeStaff], () => {
  all.forEach((resource) => resource.reset())
  void header.ensure()
  ensureTab()
}, { immediate: true })
</script>

<style scoped>
.path-heading { min-width: 220px; }
</style>
