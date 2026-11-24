<template>
  <!-- Two parts, so the grid of the sharing area can place them apart (areas "try" and "steps"). -->
  <div class="try">
    <div class="title">Try it: the host is gone</div>
    <div class="try__row">
      <span>
        The host has been away for
        <strong>{{ timeLabel(shown) }}</strong>
      </span>
      <span class="stage" :class="`stage--${stage.tone}`">{{ stage.name }}</span>
    </div>
    <v-slider v-model="at" :min="0" :max="maxAt" :step="1" :ticks="ticks" show-ticks="always" :tick-size="4" hide-details density="compact" :color="stage.color" class="try__slider" aria-label="Time the host has been away" />
    <div class="try__panels">
      <div class="panel">
        <small>Ben, a visitor, sees</small>
        <span class="chip" :style="{ background: stage.chip.color }"><v-icon :icon="stage.chip.icon" size="14" />{{ stage.chip.text }}</span>
        <div v-if="stage.toast" class="toast"><v-icon icon="mdi-alert-outline" size="14" />{{ stage.toast }}</div>
        <div v-if="stage.dialog" class="dialog">
          <b>{{ stage.dialog.title }}</b>
          <span>{{ stage.dialog.text }}</span>
        </div>
        <p>{{ stage.text }}</p>
      </div>
      <div class="panel">
        <small>If Anna, the host, is back now</small>
        <p>{{ stage.back }}</p>
      </div>
    </div>
  </div>

  <div class="steps">
    <div class="title">What visitors see, step by step</div>
    <div class="cards">
      <div class="card card--ok">
        <div class="card__title">After {{ timeLabel(notice) }}: visitors are told</div>
        <slot name="field" field-key="hostAwayMs" />
        <span class="chip" :style="{ background: away }"><v-icon icon="mdi-lan-disconnect" size="14" />Host disconnected</span>
        <p>The bar above the model changes. Editing goes on.</p>
      </div>
      <div class="card card--warn">
        <div class="card__title">After {{ timeLabel(lock) }}: the room locks</div>
        <slot name="field" field-key="hostGraceSeconds" />
        <div class="toast"><v-icon icon="mdi-alert-outline" size="14" />The host is disconnected, editing is paused.</div>
        <p>Visitors can look, but not edit, and nobody can join. If the host is back, the room opens again.</p>
      </div>
      <div class="card card--bad">
        <div class="card__title">After {{ timeLabel(end) }}: visitors leave</div>
        <slot name="field" field-key="hostEndSeconds" />
        <div class="dialog">
          <b>The host has left</b>
          <span>The room is closed. Keep the current state to continue on your own.</span>
        </div>
        <p>The model stays with the host. The share goes on, and visitors can rejoin through the link.</p>
      </div>
      <div class="card">
        <div class="card__title">A visitor away for {{ timeLabel(visitor) }}</div>
        <slot name="field" field-key="visitorGraceSeconds" />
        <p>Only that visitor is removed from the room, and their working copy is deleted.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { collabSettings } from '@/collab/settings/collabSettings'
import { timeLabel } from '@/collab/settings/timeLabel'

/** The waits as the form shows them, in seconds. */
const props = defineProps<{ values: Record<string, unknown> }>()
/** The number field of each step comes from the tab, as it owns the form, the limits and the checks. */
defineSlots<{ field(props: { fieldKey: string }): unknown }>()

const numberOf = (key: string, fallback: number) => {
  const value = props.values[key]
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : fallback
}
const notice = computed(() => numberOf('hostAwayMs', 30))
const lock = computed(() => numberOf('hostGraceSeconds', 120))
const end = computed(() => numberOf('hostEndSeconds', 300))
const visitor = computed(() => numberOf('visitorGraceSeconds', 120))

// The bar shows its colors from the settings: normal and while the host is away.
const normal = computed(() => collabSettings.colors.barColor)
const away = computed(() => collabSettings.colors.barAwayColor)

// The slider starts between the notice and the lock, where there is something to see; it reaches a bit beyond the end.
const at = ref(Math.round((notice.value + lock.value) / 2))
const maxAt = computed(() => Math.ceil((end.value * 1.25) / 5) * 5)
const shown = computed(() => Math.min(at.value, maxAt.value))

/** The values on the slider, so they need not be looked for; two that are the same share a label. */
const ticks = computed(() => {
  const marks: Record<number, string> = {}
  for (const [seconds, text] of [
    [notice.value, 'told'],
    [lock.value, 'locks'],
    [end.value, 'leave']
  ] as const)
    marks[seconds] = marks[seconds] ? `${marks[seconds]} / ${text}` : `${timeLabel(seconds)} ${text}`
  return marks
})

/** What a visitor sees at the time on the slider, and what happens if the host is back then. */
const stage = computed(() => {
  const time = shown.value
  if (time < notice.value) return { chip: { icon: 'mdi-account-group-outline', text: 'Collaborating', color: normal.value }, name: 'Everything is fine', tone: 'ok', color: 'success', text: 'Everything works as usual.', back: 'Nothing happened, nobody noticed.' }
  if (time < lock.value) return { chip: { icon: 'mdi-lan-disconnect', text: 'Host disconnected', color: away.value }, name: 'Visitors are told', tone: 'warn', color: 'warning', text: 'The bar above the model says so. Editing goes on.', back: 'The notice disappears.' }
  if (time < end.value) return { chip: { icon: 'mdi-lan-disconnect', text: 'Host disconnected', color: away.value }, name: 'Room locked', tone: 'bad', color: 'error', toast: 'The host is disconnected, editing is paused.', text: 'Ben can look at the model, but not edit it.', back: 'The room opens again and Ben can edit.' }
  return { chip: { icon: 'mdi-lock-outline', text: 'Room closed', color: '#e24b4a' }, name: 'Visitors have left', tone: 'gone', color: 'grey', dialog: { title: 'The host has left', text: 'The room is closed. Keep the current state to continue on your own.' }, text: 'Ben keeps the current state as a model of his own, or lets it go.', back: 'Her share goes on, and Ben can rejoin through the link.' }
})
</script>

<style scoped>
.try,
.steps {
  font-size: 13px;
}

.title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}

.try {
  grid-area: try;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.try__slider {
  margin: 0 8px 26px;
}

.try__slider :deep(.v-slider-track__tick-label) {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.stage {
  padding: 2px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.stage--ok {
  background: rgba(var(--v-theme-success), 0.18);
  color: rgb(var(--v-theme-success));
}

.stage--warn {
  background: rgba(var(--v-theme-warning), 0.2);
  color: rgb(var(--v-theme-warning));
}

.stage--bad {
  background: rgba(var(--v-theme-error), 0.15);
  color: rgb(var(--v-theme-error));
}

.try__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.try__panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
  margin-top: 8px;
}

.panel {
  min-height: 120px;
  padding: 8px 10px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.panel small {
  display: block;
  margin-bottom: 6px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.panel p,
.card p {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

/* In a step card the chip sits below the number field and its slider, with air between. */
.card .chip {
  margin-top: 12px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 8px;
  font-size: 12px;
  color: #fff;
}

.toast {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  margin-top: 8px;
  border-radius: 6px;
  background: rgba(var(--v-theme-warning), 0.18);
  font-size: 12px;
}

.dialog {
  padding: 8px 10px;
  margin-top: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 8px;
  background: rgb(var(--v-theme-surface));
}

.dialog b {
  display: block;
  font-size: 12px;
  font-weight: 600;
}

.dialog span {
  display: block;
  font-size: 12px;
  line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.steps {
  display: flex;
  flex-direction: column;
  grid-area: steps;
  align-self: stretch;
}

/* Always two by two, all cards as wide and as high as each other, and as high as the column beside them. */
.cards {
  display: grid;
  flex: 1 1 auto;
  grid-auto-rows: 1fr;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

@container (max-width: 560px) {
  .cards {
    grid-template-columns: minmax(0, 1fr);
  }
}

.card {
  padding: 10px 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-top: 3px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 8px;
}

.card--ok {
  border-top-color: rgb(var(--v-theme-success));
}

.card--warn {
  border-top-color: rgb(var(--v-theme-warning));
}

.card--bad {
  border-top-color: rgb(var(--v-theme-error));
}

.card__title {
  font-size: 12px;
  font-weight: 600;
}
</style>
