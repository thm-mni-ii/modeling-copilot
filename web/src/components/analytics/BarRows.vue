<template>
  <div>
    <div v-for="row in rows" :key="row.label" class="bar-row" :title="`${row.label}: ${row.text ?? row.value}`">
      <span class="bar-label text-caption">{{ row.label }}</span>
      <span class="bar-track"><span class="bar-fill" :style="{ width: `${Math.min(100, row.value / limit * 100)}%` }" /></span>
      <span class="bar-count text-caption">{{ row.text ?? row.value }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ rows: { label: string; value: number; text?: string }[]; max?: number }>()
const limit = computed(() => props.max ?? Math.max(1, ...props.rows.map((row) => row.value)))
</script>

<style scoped>
.bar-row { display: grid; grid-template-columns: minmax(48px, 150px) 1fr minmax(32px, auto); align-items: center; gap: 8px; margin-top: 6px; }
.bar-label { text-align: right; overflow-wrap: anywhere; }
.bar-track { height: 14px; border-radius: 4px; background: rgba(var(--v-theme-on-surface), 0.06); overflow: hidden; }
.bar-fill { display: block; height: 100%; background: rgb(var(--v-theme-primary-dark)); }
.bar-count { font-variant-numeric: tabular-nums; white-space: nowrap; }
</style>
