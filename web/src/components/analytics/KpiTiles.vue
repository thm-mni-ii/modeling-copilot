<template>
  <section class="kpis" aria-label="Key figures">
    <div v-for="kpi in tiles" :key="kpi.label" class="kpi" tabindex="0">
      <span class="kpi-value">{{ kpi.value }}</span>
      <span class="kpi-label">{{ kpi.label }}</span>
      <span v-if="kpi.hint" class="kpi-hint">{{ kpi.hint }}</span>
      <span v-if="kpi.items?.length" class="d-flex flex-wrap ga-1 mt-1">
        <v-chip v-for="item in kpi.items" :key="item.key" size="x-small" variant="tonal">{{ humanize(item.key) }} {{ item.count }}</v-chip>
      </span>
      <v-tooltip activator="parent" location="bottom" max-width="320">{{ kpi.tip }}</v-tooltip>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { CountItem } from '@/services/analytics'

defineProps<{ tiles: { label: string; value: string | number; hint?: string; tip: string; items?: CountItem[] }[] }>()

const humanize = (key: string) => key.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
</script>

<style scoped>
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
.kpi { display: flex; flex-direction: column; padding: 14px 16px; border: 1px solid rgba(var(--v-theme-primary), 0.18); border-radius: 10px; background: rgba(var(--v-theme-primary), 0.04); }
.kpi-value { font-size: 1.5rem; line-height: 1.2; font-weight: 600; font-variant-numeric: tabular-nums; }
.kpi-label { font-size: 0.875rem; font-weight: 500; }
.kpi-hint { font-size: 0.75rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
</style>
