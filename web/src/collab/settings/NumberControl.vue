<template>
  <div class="num">
    <v-text-field :model-value="model" type="number" :suffix="suffix" density="compact" variant="outlined" hide-details :error="error" :disabled="disabled" :aria-label="label" @update:model-value="set" />
    <div class="num__sub">{{ sub }}</div>
    <div class="num__bar" aria-hidden="true">
      <i :style="{ left: defaultAt }" />
      <b :style="{ left: valueAt }" :class="{ 'num__bar--error': error }" />
    </div>
  </div>
</template>

<script setup lang="ts">
/** A number field with its unit, what it comes to in bigger units and the range, and a bar for the place in that range; used in a row and in a card. */
defineProps<{ label: string; suffix: string; sub: string; defaultAt: string; valueAt: string; error: boolean; disabled: boolean }>()
const model = defineModel<number | string | boolean | string[]>()

/** As v-model.number: a number when it parses, else the text, which the tab then reports. */
const set = (value: unknown) => {
  const parsed = typeof value === 'string' ? parseFloat(value) : NaN
  model.value = Number.isNaN(parsed) ? (value as string) : parsed
}
</script>

<style scoped>
.num {
  width: 100%;
}

.num__sub {
  margin-top: 3px;
  font-size: 11px;
  text-align: right;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.num__bar {
  position: relative;
  height: 4px;
  margin: 5px 0 0;
  border-radius: 2px;
  background: rgba(var(--v-theme-on-surface), 0.12);
}

.num__bar i {
  position: absolute;
  top: -2px;
  width: 2px;
  height: 8px;
  background: rgba(var(--v-theme-on-surface), 0.45);
}

.num__bar b {
  position: absolute;
  top: -3px;
  width: 10px;
  height: 10px;
  margin-left: -5px;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
}

.num__bar--error {
  background: rgb(var(--v-theme-error)) !important;
}
</style>
