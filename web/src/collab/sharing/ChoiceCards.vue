<template>
  <v-item-group v-model="selected" mandatory :class="{ 'share-history--busy': busy }">
    <v-item v-for="choice in choices" :key="choice.value" v-slot="{ isSelected, toggle }" :value="choice.value">
      <v-card :variant="isSelected ? 'tonal' : 'outlined'" :color="isSelected ? (choice.danger ? 'error' : 'primary') : undefined" class="share-history mb-2" :class="{ 'share-history--danger': choice.danger }" role="radio" tabindex="0" :aria-checked="isSelected" @click="toggle" @keydown.enter.prevent="toggle" @keydown.space.prevent="toggle">
        <v-icon :icon="choice.icon" class="mr-3" />
        <div class="flex-grow-1">
          <div class="share-history__title">{{ choice.title }}</div>
          <div v-if="choice.hint" class="text-caption share-history__hint">{{ choice.hint }}</div>
          <!-- What the chosen card asks for besides, such as a name. -->
          <slot v-if="isSelected" :choice="choice" />
        </div>
        <v-icon v-if="isSelected" icon="mdi-check" />
      </v-card>
    </v-item>
  </v-item-group>
</template>

<script setup lang="ts" generic="Value extends string">
/** The cards of a dialog to pick one of several ways, such as how much history to share or where the state goes on leaving. */
defineProps<{ choices: { value: Value; icon: string; title: string; hint?: string; danger?: boolean }[]; busy: boolean }>()
const selected = defineModel<Value>({ required: true })
</script>

<style scoped>
.share-history {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  cursor: pointer;
}

.share-history__title {
  font-size: 14px;
  font-weight: 500;
}

/* Selected, the text stays dark and the card light green (red for "Do not save"), only the icons carry the color; green text on green is hard to read. */
.share-history__title,
.share-history :deep(.v-field) {
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.share-history__hint {
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.share-history :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 75%, black);
}

.share-history--danger :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-error)) 75%, black);
}

.share-history--busy {
  pointer-events: none;
  opacity: 0.6;
}
</style>
