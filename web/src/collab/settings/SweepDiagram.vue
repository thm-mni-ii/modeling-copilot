<template>
  <svg viewBox="0 0 190 64" width="190" height="64" role="img" :aria-label="`The backend looks every ${seconds} seconds; a host who drops out is only noticed at the next look`">
    <line x1="6" y1="38" x2="184" y2="38" class="axis" />
    <line v-for="at in ticks" :key="at" :x1="at" :x2="at" y1="28" y2="48" class="tick" />
    <circle cx="80" cy="38" r="5" class="gone" />
    <line x1="86" x2="112" y1="38" y2="38" class="wait" />
    <text x="80" y="20" class="label" text-anchor="middle">host drops out</text>
    <text x="114" y="62" class="label" text-anchor="middle">noticed at the next look</text>
  </svg>
</template>

<script setup lang="ts">
/** The look of the backend as ticks; the host leaves between two of them and is only noticed at the next. */
defineProps<{ seconds: number }>()
const ticks = [14, 64, 114, 164]
</script>

<style scoped>
.axis {
  stroke: rgba(var(--v-theme-on-surface), 0.25);
  stroke-width: 2;
}

.tick {
  stroke: rgb(var(--v-theme-info));
  stroke-width: 2;
}

.gone {
  fill: rgb(var(--v-theme-error));
}

.wait {
  stroke: rgb(var(--v-theme-error));
  stroke-dasharray: 3 2;
}

.label {
  font-size: 11px;
  fill: rgba(var(--v-theme-on-surface), 0.65);
}
</style>
