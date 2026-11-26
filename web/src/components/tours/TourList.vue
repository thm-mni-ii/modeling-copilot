<template>
  <slot name="trigger" :toggle="toggle" :open="open" :done="doneCount" :total="list.length" :pending-count="pendingCount">
    <v-btn v-bind="$attrs" variant="text" size="small" :aria-label="label" :aria-expanded="open" @click="toggle">
      <TourBadge v-if="showBadge" :tour-ids="tourIds"
        ><v-icon>{{ icon }}</v-icon></TourBadge
      >
      <v-icon v-else>{{ icon }}</v-icon>
    </v-btn>
  </slot>
  <Teleport to="body">
    <aside v-if="open" v-bind="$attrs" class="tour-list" :aria-label="title">
      <header class="tour-list-header">
        <div>
          <strong>{{ title }}</strong>
          <p v-if="subtitle">{{ subtitle }}</p>
        </div>
        <button type="button" class="tour-list-close" aria-label="Liste zuklappen" @click="open = false">×</button>
        <div class="tour-list-progress">
          <progress :value="doneCount" :max="list.length || 1" aria-label="Fortschritt" />
          <span>{{ doneCount }}/{{ list.length }}</span>
        </div>
      </header>
      <div class="tour-list-body">
        <div v-for="tour in list" :key="tour.id" class="tour-list-item">
          <div class="tour-list-item-head">
            <v-icon :color="tour.done ? 'success' : undefined">{{ tour.done ? 'mdi-check-circle' : 'mdi-circle-outline' }}</v-icon>
            <div>
              <strong>{{ tour.title }}</strong>
              <p>{{ tour.done ? (tour.status === 'skipped' ? 'Übersprungen' : 'Angesehen') : tour.description }}</p>
            </div>
          </div>
          <v-alert v-if="tour.error" type="error" density="compact" variant="tonal" class="mb-2">{{ tour.error }}</v-alert>
          <p v-if="tour.reason" class="tour-list-note">{{ tour.reason }}</p>
          <div class="tour-list-actions">
            <v-btn size="small" variant="flat" class="tour-list-start" :disabled="!tour.available || tour.starting || tour.active" @click="startTour(tour.id)">{{ tour.done ? 'Erneut starten' : 'Tour starten' }}</v-btn>
            <v-btn v-if="!tour.done" size="small" variant="text" :disabled="tour.starting" @click="skip(tour.id)">Überspringen</v-btn>
          </div>
        </div>
      </div>
    </aside>
    <div v-if="showToggleBar && barVisible" v-bind="$attrs" class="tour-list-toggle">
      <button type="button" :aria-expanded="open" @click="toggle">
        {{ title }} <span>{{ doneCount }}/{{ list.length }}</span> <v-icon size="16">{{ open ? 'mdi-chevron-down' : 'mdi-chevron-up' }}</v-icon>
      </button>
      <button type="button" class="tour-list-hide" aria-label="Ausblenden" @click="hideBar">×</button>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, ref } from 'vue'
import TourBadge from './TourBadge.vue'
import { useTours } from '@/composables/useTours'
import type { TourEvent } from '@/tours/types'

// Checkliste der Touren einer Seite. Trigger über den Slot ersetzbar; Farben über --tour-* auf dem Wurzel-Attribut (class/style).
defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ tourIds?: string[]; title?: string; subtitle?: string; icon?: string; label?: string; showBadge?: boolean; showToggleBar?: boolean }>(), {
  title: 'Neue Funktionen entdecken',
  subtitle: '',
  icon: 'mdi-help-circle-outline',
  label: 'Touren öffnen',
  showBadge: true,
  showToggleBar: false
})
const emit = defineEmits<{
  start: [event: Extract<TourEvent, { type: 'start' }>]
  step: [event: Extract<TourEvent, { type: 'step' }>]
  completed: [event: Extract<TourEvent, { type: 'completed' }>]
  skipped: [event: Extract<TourEvent, { type: 'skipped' }>]
  unavailable: [event: Extract<TourEvent, { type: 'unavailable' }>]
}>()

const { tours, start, skip, opened, on } = useTours()
const open = ref(false)
const barVisible = ref(false)
const list = computed(() => tours.value.filter((tour) => !props.tourIds || props.tourIds.includes(tour.id)))
const doneCount = computed(() => list.value.filter((tour) => tour.done).length)
const pendingCount = computed(() => list.value.filter((tour) => tour.pending).length)

const toggle = () => {
  barVisible.value = true
  open.value = !open.value
  if (open.value) list.value.forEach((tour) => void opened(tour.id))
}
const hideBar = () => {
  open.value = false
  barVisible.value = false
}
const startTour = (id: string) => {
  open.value = false
  void start(id)
}

// Ereignisse der angezeigten Touren als Vue-Emits weiterreichen.
const off = on((event) => {
  if (props.tourIds && !props.tourIds.includes(event.tourId)) return
  emit(event.type as 'start', event as never)
})
onScopeDispose(off)
</script>

<style scoped>
.tour-list {
  position: fixed;
  right: 20px;
  bottom: 76px;
  z-index: 2400;
  width: min(360px, calc(100vw - 32px));
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  border: 2px solid var(--tour-accent, rgb(var(--v-theme-primary)));
  border-radius: 14px;
  background: var(--tour-bg, rgb(var(--v-theme-surface)));
  color: var(--tour-text, rgb(var(--v-theme-on-surface)));
  box-shadow: 0 5px 16px rgb(0 0 0 / 25%);
}
.tour-list-header {
  position: relative;
  padding: 16px;
  background: var(--tour-header-bg, rgb(var(--v-theme-surface-variant)));
  border-bottom: 2px solid var(--tour-border, var(--tour-accent, rgb(var(--v-theme-primary))));
}
.tour-list-header strong {
  font-size: 1.05rem;
}
.tour-list-header p,
.tour-list-item p {
  margin: 4px 0 0;
  font-size: 0.8rem;
  line-height: 1.4;
}
.tour-list-note {
  margin-top: 10px;
}
.tour-list-close {
  position: absolute;
  top: 8px;
  right: 12px;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 1.4rem;
}
.tour-list-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  font-size: 0.8rem;
}
.tour-list-progress progress {
  flex: 1;
  height: 9px;
  accent-color: var(--tour-accent, rgb(var(--v-theme-primary)));
}
.tour-list-body {
  padding: 16px;
}
.tour-list-item + .tour-list-item {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--tour-border, rgb(var(--v-theme-on-surface), 0.2));
}
.tour-list-item-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.tour-list-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 14px;
}
.tour-list-actions :deep(.v-btn) {
  letter-spacing: 0;
  text-transform: none;
}
.tour-list-start {
  background: var(--tour-accent, rgb(var(--v-theme-primary))) !important;
  color: var(--tour-accent-text, rgb(var(--v-theme-on-primary))) !important;
}
.tour-list-toggle {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 2400;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 2px solid var(--tour-accent, rgb(var(--v-theme-primary)));
  border-radius: 10px;
  background: var(--tour-header-bg, rgb(var(--v-theme-surface-variant)));
  color: var(--tour-text, rgb(var(--v-theme-on-surface)));
  box-shadow: 0 4px 10px rgb(0 0 0 / 20%);
  font-weight: 600;
}
.tour-list-toggle button {
  display: flex;
  align-items: center;
  gap: 8px;
  color: inherit;
  cursor: pointer;
}
.tour-list-hide {
  font-size: 1.25rem;
  line-height: 1;
}
.tour-list-toggle span {
  padding: 1px 5px;
  border-radius: 8px;
  background: var(--tour-accent, rgb(var(--v-theme-primary)));
  color: var(--tour-accent-text, rgb(var(--v-theme-on-primary)));
  font-size: 0.75rem;
}
@media (max-width: 480px) {
  .tour-list,
  .tour-list-toggle {
    right: 16px;
  }
}
</style>
