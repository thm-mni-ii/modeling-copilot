<template>
  <v-sheet border rounded="lg" class="progress-stats mb-4" aria-labelledby="progress-overview-title">
    <div class="d-flex align-center ga-3 mb-4">
      <span class="section-icon"><v-icon size="21" color="info">mdi-chart-bar</v-icon></span>
      <div>
        <h2 id="progress-overview-title" class="text-subtitle-1 font-weight-medium">Progress overview</h2>
        <p class="text-caption text-medium-emphasis mb-0">{{ records.length }} filtered participations · all pages</p>
      </div>
    </div>
    <div v-if="!records.length" class="empty-stats text-body-2 text-medium-emphasis">
      <v-icon size="24" class="mr-2">mdi-filter-remove-outline</v-icon>No matching participations.
    </div>
    <template v-else>
      <section class="participation-statuses" aria-label="Participation status">
        <div v-for="status in participationStatuses" :key="status.key" class="participation-tile" :style="{ '--status-color': `var(--v-theme-${status.color})` }">
          <div class="d-flex align-center justify-space-between ga-2 mb-2">
            <span class="participation-label text-body-2 font-weight-medium">{{ status.label }}</span>
            <v-icon class="participation-icon" size="20" :color="status.color">{{ status.icon }}</v-icon>
          </div>
          <div class="d-flex align-baseline ga-2 mb-3">
            <span class="participation-count">{{ status.count }}</span>
            <span class="text-caption text-medium-emphasis">{{ percent(status.count, records.length) }}% of selection</span>
          </div>
          <div class="stat-bar" role="img" :aria-label="`${status.label}: ${status.count} of ${records.length} participations`">
            <div class="stat-segment" :class="`stat-segment--${status.key}`" :style="{ width: `${status.count / records.length * 100}%` }" />
          </div>
        </div>
      </section>
      <div v-if="!templateId" class="step-hint text-caption mt-4">
        <v-icon size="17" color="info" class="mr-2">mdi-information-outline</v-icon>Select a learning path to compare progress at each step.
      </div>
      <section v-else class="step-chart mt-5" aria-label="Progress by step">
        <div class="d-flex flex-wrap align-center justify-space-between ga-2 mb-3">
          <h3 class="text-body-2 font-weight-medium">Progress by step</h3>
          <div v-if="steps.length" class="d-flex flex-wrap ga-3 text-caption" aria-label="Step status legend">
            <span v-for="status in stepStatuses" :key="status.key" class="d-inline-flex align-center ga-1"><span class="legend-swatch" :class="`stat-segment--${status.key}`" aria-hidden="true" />{{ status.label }}</span>
          </div>
        </div>
        <div v-if="steps.length" class="step-chart-list" tabindex="0" aria-label="Step progress chart, scroll for more steps">
          <div v-for="(step, index) in steps" :key="step.id" class="step-row">
            <div class="step-label"><span class="step-number">{{ index + 1 }}</span><span class="step-title text-body-2 font-weight-medium">{{ step.title }}</span></div>
            <div class="step-distribution">
              <div class="stat-bar stat-bar--stacked" role="img" :aria-label="`${step.title}: ${step.summary}`">
                <div v-for="segment in step.segments" :key="segment.key" class="stat-segment" :class="`stat-segment--${segment.key}`" :style="{ width: `${segment.count / step.total * 100}%` }" :title="`${segment.label}: ${segment.count}`" />
              </div>
              <div class="text-caption text-medium-emphasis mt-1">{{ step.summary }}</div>
            </div>
            <div class="step-finished"><span class="text-body-2 font-weight-medium">{{ step.finished }} / {{ step.total }}</span><span class="text-caption text-medium-emphasis">finished</span></div>
          </div>
        </div>
        <p v-else class="text-body-2 text-medium-emphasis mb-0">No step progress available for these participations.</p>
        <p v-if="steps.length" class="text-caption text-medium-emphasis mt-3 mb-0">Finished includes completed and skipped steps. Each participant is counted per step; archived steps are excluded.</p>
      </section>
    </template>
  </v-sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PathProgressSummary, StepRun } from '@/services/learningPaths'

const props = defineProps<{ records: PathProgressSummary[]; templateId: string | null }>()
const percent = (count: number, total: number) => total ? Math.round(count / total * 100) : 0
const participationStatuses = computed(() => [
  { key: 'not_started', label: 'Not started', color: 'medium-gray', icon: 'mdi-clock-outline' },
  { key: 'in_progress', label: 'In progress', color: 'info', icon: 'mdi-progress-clock' },
  { key: 'completed', label: 'Completed', color: 'success', icon: 'mdi-check-circle-outline' }
].map((status) => ({ ...status, count: props.records.filter((record) => record.status === status.key).length })))
const stepStatuses: { key: StepRun['status']; label: string }[] = [
  { key: 'completed', label: 'Completed' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'available', label: 'Available' },
  { key: 'locked', label: 'Locked' },
  { key: 'skipped', label: 'Skipped' }
]
const steps = computed(() => {
  const byId = new Map<string, { id: string; title: string; counts: Record<StepRun['status'], number> }>()
  for (const record of props.records) {
    if (record.templateId !== props.templateId) continue
    for (const stage of record.stepProgress ?? []) {
      let step = byId.get(stage.id)
      if (!step) {
        step = { id: stage.id, title: stage.title, counts: { completed: 0, in_progress: 0, available: 0, locked: 0, skipped: 0 } }
        byId.set(stage.id, step)
      }
      step.counts[stage.status]++
    }
  }
  return [...byId.values()].map((step) => {
    const segments = stepStatuses.map((status) => ({ ...status, count: step.counts[status.key] })).filter((segment) => segment.count > 0)
    return { id: step.id, title: step.title, segments, total: segments.reduce((total, segment) => total + segment.count, 0),
      finished: step.counts.completed + step.counts.skipped,
      summary: segments.map((segment) => `${segment.label}: ${segment.count}`).join(' · ') }
  })
})
</script>

<style scoped>
.progress-stats { padding: 20px; border-color: rgba(var(--v-theme-on-surface), 0.12); }
.section-icon { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 10px; background: rgba(var(--v-theme-info), 0.08); flex-shrink: 0; }
.participation-statuses { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.participation-tile { padding: 14px 16px; border: 1px solid rgba(var(--status-color), 0.18); border-radius: 10px; background: rgba(var(--status-color), 0.05); }
.participation-count { font-size: 1.8rem; line-height: 1.1; font-weight: 600; font-variant-numeric: tabular-nums; }
.stat-bar { height: 6px; overflow: hidden; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.08); }
.stat-bar--stacked { display: flex; height: 12px; }
.stat-segment { height: 100%; }
.stat-segment--not_started, .stat-segment--locked { background: rgba(var(--v-theme-on-surface), 0.35); }
.stat-segment--in_progress { background: rgb(var(--v-theme-info)); }
.stat-segment--completed { background: rgb(var(--v-theme-success)); }
.stat-segment--available { background: rgb(var(--v-theme-warning)); }
.stat-segment--skipped { background: rgb(var(--v-theme-secondary)); }
.legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
.step-chart { border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08); padding-top: 16px; }
.step-chart-list { max-height: 270px; overflow: auto; }
.step-row { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(0, 2fr) 70px; gap: 16px; align-items: center; padding: 12px 8px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06); }
.step-row:nth-child(even) { background: rgba(var(--v-theme-on-surface), 0.018); }
.step-label { display: flex; align-items: center; gap: 10px; min-width: 0; }
.step-number { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; flex-shrink: 0; border-radius: 7px; background: rgba(var(--v-theme-primary), 0.1); color: rgb(var(--v-theme-primary-dark)); font-size: 0.75rem; font-weight: 600; }
.step-title { min-width: 0; overflow-wrap: anywhere; }
.step-finished { display: flex; flex-direction: column; align-items: flex-end; font-variant-numeric: tabular-nums; }
.step-distribution { min-width: 0; }
.step-hint { display: flex; align-items: center; padding: 10px 12px; background: rgba(var(--v-theme-info), 0.05); border-radius: 8px; }
.empty-stats { display: flex; align-items: center; padding: 20px 0; }
@media (max-width: 700px) {
  .progress-stats { padding: 16px; }
  .participation-statuses { gap: 8px; }
  .participation-tile { padding: 12px 10px; }
  .participation-label { font-size: 0.75rem !important; }
  .participation-icon { display: none; }
  .participation-tile > div:nth-child(2) { flex-wrap: wrap; gap: 4px !important; }
  .step-row { grid-template-columns: minmax(0, 1fr) 70px; gap: 8px 12px; }
  .step-distribution { grid-column: 1 / -1; grid-row: 2; }
}
</style>
