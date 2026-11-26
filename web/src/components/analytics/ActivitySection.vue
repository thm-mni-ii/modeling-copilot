<template>
  <v-sheet border rounded="lg" class="analytics-panel mb-4" aria-labelledby="activity-title">
    <div class="d-flex align-center ga-3 pa-4">
      <v-icon color="primary-dark" size="22">mdi-timer-outline</v-icon>
      <div>
        <h2 id="activity-title" class="text-subtitle-1 font-weight-medium">Activity<InfoTip :text="intro" /></h2>
        <div class="text-caption text-medium-emphasis">Editor sessions, work time and window switches in the task steps.</div>
      </div>
    </div>
    <v-divider />
    <p v-if="!activity.path.sessions" class="pa-5 text-body-2 text-medium-emphasis mb-0">No editor sessions have been recorded for this learning path yet.</p>
    <v-expansion-panels v-else v-model="open" multiple variant="accordion" elevation="0">
      <v-expansion-panel v-for="scope in scopes" :key="scope.id" :value="scope.id">
        <v-expansion-panel-title>
          <div class="d-flex flex-wrap align-center ga-2">
            <span class="font-weight-medium">{{ scope.title }}</span>
            <v-chip size="x-small" variant="tonal">{{ scope.stats.persons }} {{ scope.stats.persons === 1 ? 'person' : 'people' }} · {{ scope.stats.sessions }} sessions</v-chip>
          </div>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <p v-if="!scope.stats.sessions" class="text-body-2 text-medium-emphasis mb-0">No sessions recorded for this task.</p>
          <template v-else>
            <section class="tiles mb-4" :aria-label="`Key figures for ${scope.title}`">
              <div v-for="tile in tiles(scope.stats)" :key="tile.label" class="tile" tabindex="0">
                <span class="tile-value">{{ tile.value }}</span>
                <span class="tile-label">{{ tile.label }}</span>
                <v-tooltip activator="parent" location="bottom" max-width="340">{{ tile.tip }}</v-tooltip>
              </div>
            </section>
            <h3 class="text-body-2 font-weight-medium">Sessions per person<InfoTip text="Number of editor sessions per person, counting people with at least one session. A session starts when the editor is opened and ends when it is closed or left." /></h3>
            <BarRows :rows="scope.stats.sessionDistribution.map((bin) => ({ label: bin.label, value: bin.users }))" />
          </template>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ActivityStats, PathActivity } from '@/services/analytics'
import BarRows from '@/components/analytics/BarRows.vue'
import InfoTip from '@/components/analytics/InfoTip.vue'
import { durationText, percentText } from '@/components/analytics/labels'

const props = defineProps<{ activity: PathActivity }>()
const open = ref<string[]>(['path'])
const intro = 'Values are approximations from browser events: idle detection, tab behaviour (background tabs, mobile browsers that suspend pages) and sessions that were never closed cannot be measured exactly. Only aggregated values are shown.'
const scopes = computed(() => [
  { id: 'path', title: 'Whole path (all task steps)', stats: props.activity.path as ActivityStats },
  ...props.activity.steps.map((step) => ({ id: step.stepId, title: step.title, stats: step as ActivityStats }))
])
const perText = (value: number | null) => value === null ? '—' : String(value)
const tiles = (stats: ActivityStats) => [
  { label: 'Sessions per person', value: perText(stats.avgSessionsPerPerson), tip: 'Mean number of editor sessions per person with at least one session.' },
  { label: 'Work time (avg / median)', value: `${durationText(stats.avgGrossSeconds)} / ${durationText(stats.medianGrossSeconds)}`, tip: 'Per person: sum of all session durations, including idle time. Sessions without a recorded end count up to their last interaction.' },
  { label: 'Active time (avg / median)', value: `${durationText(stats.avgActiveSeconds)} / ${durationText(stats.medianActiveSeconds)}`, tip: 'Work time minus idle intervals. The editor reports idle after 5 minutes without input, so idle time is underestimated by up to 5 minutes per interval. Sessions without idle events have no idle time.' },
  { label: 'Avg session', value: durationText(stats.avgSessionSeconds), tip: 'Mean duration of one session (gross).' },
  { label: 'Tab switches per person / session', value: `${perText(stats.tabHiddenPerPerson)} / ${perText(stats.tabHiddenPerSession)}`, tip: 'The browser tab was hidden (switching tabs or minimising). The state at session start is not counted.' },
  { label: 'Focus losses per person / session', value: `${perText(stats.focusLostPerPerson)} / ${perText(stats.focusLostPerSession)}`, tip: 'The browser window lost focus (clicking another application or window). Tab switches usually also lose focus, so the two counts overlap.' },
  { label: 'Time outside window', value: percentText(stats.outsideShare), tip: 'Share of session time with a hidden tab or a window without focus.' },
  ...(stats.openSessions ? [{ label: 'Sessions without end', value: String(stats.openSessions), tip: 'Sessions whose end was never received (for example a closed browser or lost connection). Their time is a lower bound.' }] : [])
]
</script>

<style scoped>
.analytics-panel { overflow: hidden; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }
.tile { display: flex; flex-direction: column; padding: 10px 14px; border: 1px solid rgba(var(--v-theme-primary), 0.18); border-radius: 10px; background: rgba(var(--v-theme-primary), 0.04); }
.tile-value { font-size: 1.25rem; line-height: 1.2; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile-label { font-size: 0.8125rem; font-weight: 500; }
</style>
