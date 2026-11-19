<template>
  <div class="collab-box" :class="{ 'collab-box--grow': grow && open }">
    <div class="collab-box__header">
      <span>{{ title }} <slot name="title" /></span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="`${open ? 'Collapse' : 'Expand'} ${label}`" @click="open = !open" />
    </div>
    <!-- Native: the transitions of Vuetify take disabled, then the body just shows and hides. -->
    <v-expand-transition :disabled="grow">
      <div v-show="open" class="collab-box__body">
        <slot />
      </div>
    </v-expand-transition>
  </div>
</template>

<script setup lang="ts">
/**
 * A box of the "Collab" sidebar that opens and closes: a title, what goes beside it, and the content.
 * `label` names it for the button. With `grow` it takes the space the sidebar leaves while open, and opens without animation.
 * Whether it is open lives with the caller, so it stays while another sidebar tab is shown.
 */
withDefaults(defineProps<{ title: string; label: string; grow?: boolean }>(), { grow: false })
const open = defineModel<boolean>({ required: true })
</script>

<style scoped>
.collab-box {
  display: flex;
  flex-direction: column;
  /* The sync sidebar scrolls instead; with overflow hidden it could squeeze the box down to its header. */
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
}

/* Open, it takes what the sync sidebar leaves, so it grows as the boxes above close. */
.collab-box--grow {
  flex: 1;
  min-height: 180px;
}

.collab-box__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.collab-box__body {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

.collab-box--grow .collab-box__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
