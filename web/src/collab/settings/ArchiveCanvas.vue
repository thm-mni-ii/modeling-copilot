<template>
  <div class="canvas">
    <div class="title">Where a shared workpiece ends up</div>
    <div class="canvas__body">
      <svg viewBox="0 0 420 200" class="canvas__svg" :class="{ 'canvas__svg--dim': active !== 0 }" role="img" aria-label="The way of a shared model: the share runs, the host ends it, it lies without a room, and it goes to the archive, at once or after some days">
        <defs>
          <marker id="archive-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M2 1L8 5L2 9" fill="none" stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </marker>
        </defs>
        <rect x="10" y="10" width="400" height="180" rx="6" fill="#fff" stroke="#d6d6d6" />

        <rect x="20" y="50" width="78" height="36" rx="6" fill="#e1f5ee" stroke="#0f6e56" stroke-width="0.5" />
        <text x="59" y="68" text-anchor="middle" dominant-baseline="central" class="box-text">Share runs</text>
        <rect x="120" y="50" width="78" height="36" rx="6" fill="#faeeda" stroke="#854f0b" stroke-width="0.5" />
        <text x="159" y="68" text-anchor="middle" dominant-baseline="central" class="box-text">Host ends it</text>
        <line x1="98" y1="68" x2="118" y2="68" class="arrow" marker-end="url(#archive-arrow)" />

        <!-- 3: it lies without a room until nobody has used it for the set time. -->
        <g class="part" :class="{ 'part--on': active === 3, 'part--off': !enabled }" @mouseenter="active = 3" @mouseleave="active = 0">
          <rect x="220" y="50" width="78" height="36" rx="6" fill="#f1efe8" stroke="#5f5e5a" stroke-width="0.5" />
          <text x="259" y="68" text-anchor="middle" dominant-baseline="central" class="box-text">No room</text>
          <line x1="198" y1="68" x2="218" y2="68" class="arrow" marker-end="url(#archive-arrow)" />
          <line x1="298" y1="68" x2="318" y2="68" class="arrow" marker-end="url(#archive-arrow)" />
          <text x="259" y="106" text-anchor="middle" class="small-text">{{ never ? 'never archived' : `unused for ${daysLabel(days)}` }}</text>
          <circle cx="259" cy="126" r="9" class="badge" />
          <text x="259" y="126" text-anchor="middle" dominant-baseline="central" class="badge-text">3</text>
        </g>

        <!-- 2: an ended share goes to the archive at once, past the waiting. -->
        <g class="part" :class="{ 'part--on': active === 2, 'part--off': !enabled }" @mouseenter="active = 2" @mouseleave="active = 0">
          <path d="M159 86 V160 H359 V90" fill="none" class="arrow" :class="{ 'arrow--idle': !onClose }" stroke-dasharray="5 4" marker-end="url(#archive-arrow)" />
          <text x="259" y="180" text-anchor="middle" class="small-text">{{ onClose ? 'at once' : 'not at once' }}</text>
          <circle cx="139" cy="123" r="9" class="badge" />
          <text x="139" y="123" text-anchor="middle" dominant-baseline="central" class="badge-text">2</text>
        </g>

        <!-- 1: the archive and its tab. -->
        <g class="part" :class="{ 'part--on': active === 1 }" @mouseenter="active = 1" @mouseleave="active = 0">
          <rect x="320" y="50" width="78" height="36" rx="6" :fill="enabled ? '#eeedfe' : '#f1efe8'" :stroke="enabled ? '#534ab7' : '#888780'" stroke-width="0.5" :stroke-dasharray="enabled ? undefined : '4 3'" />
          <text x="359" y="68" text-anchor="middle" dominant-baseline="central" class="box-text">Archive</text>
          <circle cx="336" cy="108" r="9" class="badge" />
          <text x="336" y="108" text-anchor="middle" dominant-baseline="central" class="badge-text">1</text>
        </g>

        <!-- 4: deleting for good, out of the archive; only when it is allowed. -->
        <g class="part" :class="{ 'part--on': active === 4, 'part--off': !enabled }" @mouseenter="active = 4" @mouseleave="active = 0">
          <line x1="359" y1="50" x2="359" y2="40" class="arrow" :class="{ 'arrow--idle': !allowDelete }" marker-end="url(#archive-arrow)" />
          <rect x="333" y="16" width="66" height="22" rx="4" :fill="allowDelete ? '#fcebeb' : '#f1efe8'" :stroke="allowDelete ? '#a32d2d' : '#b4b2a9'" stroke-width="0.5" :stroke-dasharray="allowDelete ? undefined : '4 3'" />
          <text x="366" y="27" text-anchor="middle" dominant-baseline="central" class="small-text">{{ allowDelete ? 'Delete' : 'no delete' }}</text>
          <circle cx="317" cy="27" r="9" class="badge" />
          <text x="317" y="27" text-anchor="middle" dominant-baseline="central" class="badge-text">4</text>
        </g>
      </svg>

      <div class="rows">
        <div class="prow" :class="{ 'prow--on': active === 1 }" @mouseenter="active = 1" @mouseleave="active = 0" @focusin="active = 1" @focusout="active = 0">
          <span class="prow__n">1</span>
          <div class="prow__main">
            <div class="prow__head">
              <b>Archive</b>
              <v-tooltip text="Turned off, there is no archive: no tab, no buttons to archive, and nothing is archived by itself. The collab-kit server must allow it too (ARCHIVE_ENABLED=true)." location="top" max-width="280">
                <template #activator="{ props: tip }">
                  <v-icon v-bind="tip" icon="mdi-information-outline" size="16" class="prow__info" tabindex="0" aria-label="About Archive" />
                </template>
              </v-tooltip>
            </div>
            <div class="ctl">
              <span v-if="changed('enabled')" class="ctl__dot" title="Unsaved change" />
              <v-switch :model-value="enabled" density="compact" color="primary" hide-details label="Use the archive" @update:model-value="emit('update', 'enabled', Boolean($event))" />
            </div>
            <div v-if="serverOff" class="ctl__warn">collab-kit has the archive switched off on the server (ARCHIVE_ENABLED), so it is not offered until it is turned on there.</div>
          </div>
        </div>

        <div class="prow" :class="{ 'prow--on': active === 2, 'prow--locked': !enabled }" @mouseenter="active = 2" @mouseleave="active = 0" @focusin="active = 2" @focusout="active = 0">
          <span class="prow__n">2</span>
          <div class="prow__main">
            <div class="prow__head">
              <b>Ended shares</b>
              <v-tooltip text="The model and the task of a share go to the archive when the host ends it, instead of staying in collab-kit without a room." location="top" max-width="280">
                <template #activator="{ props: tip }">
                  <v-icon v-bind="tip" icon="mdi-information-outline" size="16" class="prow__info" tabindex="0" aria-label="About Ended shares" />
                </template>
              </v-tooltip>
            </div>
            <div class="ctl" :class="{ 'ctl--locked': !enabled }" :inert="!enabled">
              <span v-if="changed('archiveOnShareClose')" class="ctl__dot" title="Unsaved change" />
              <v-switch :model-value="onClose" density="compact" color="primary" hide-details label="Archive at once when the host ends a share" @update:model-value="emit('update', 'archiveOnShareClose', Boolean($event))" />
              <v-icon v-if="!enabled" icon="mdi-lock-outline" size="14" title="Only while the archive is on" />
            </div>
          </div>
        </div>

        <div class="prow" :class="{ 'prow--on': active === 3, 'prow--locked': !enabled }" @mouseenter="active = 3" @mouseleave="active = 0" @focusin="active = 3" @focusout="active = 0">
          <span class="prow__n">3</span>
          <div class="prow__main">
            <div class="prow__head">
              <b>Unused workpieces</b>
              <v-tooltip text="Models and tasks of ended shares that lie in no room and nobody has used. The backend checks once a day, at 03:00 UTC. Never archives at 0." location="top" max-width="280">
                <template #activator="{ props: tip }">
                  <v-icon v-bind="tip" icon="mdi-information-outline" size="16" class="prow__info" tabindex="0" aria-label="About Unused workpieces" />
                </template>
              </v-tooltip>
            </div>
            <div class="ctl ctl--wide" :class="{ 'ctl--locked': !enabled }">
              <div class="ctl__head">
                <span>Archive after being unused for</span>
                <span v-if="changed('archiveUnusedAfterDays')" class="ctl__dot" title="Unsaved change" />
                <v-icon v-if="!enabled" icon="mdi-lock-outline" size="14" title="Only while the archive is on" />
                <v-btn v-else-if="days !== DEFAULT" icon="mdi-restore" size="x-small" density="comfortable" variant="text" aria-label="Reset the time to the default" title="Reset to the default" @click="set(DEFAULT)" />
              </div>
              <div class="ctl__body" :inert="!enabled">
                <!-- A dot on a day axis; the left end is 0, which never archives, the rest runs on a logarithmic scale. -->
                <svg viewBox="0 0 320 52" class="axis" role="slider" tabindex="0" aria-label="Archive after being unused for" :aria-valuemin="MIN" :aria-valuemax="MAX" :aria-valuenow="days" :aria-valuetext="daysLabel(days)" @pointerdown.prevent="drag" @pointermove="drag" @keydown="press">
                  <line :x1="X0" :x2="X1" y1="30" y2="30" class="axis__line" />
                  <line :x1="X0" :x2="axisOf(days)" y1="30" y2="30" class="axis__fill" />
                  <g v-for="tick in TICKS" :key="tick">
                    <line :x1="axisOf(tick)" :x2="axisOf(tick)" y1="25" y2="35" class="axis__tick" />
                    <text :x="axisOf(tick)" y="50" text-anchor="middle" class="axis__text">{{ tick === 0 ? 'never' : `${tick} d` }}</text>
                  </g>
                  <circle :cx="axisOf(days)" cy="30" r="9" class="axis__dot" />
                  <text :x="Math.min(Math.max(axisOf(days), 24), 296)" y="12" text-anchor="middle" class="axis__value">{{ daysLabel(days) }}</text>
                </svg>
                <span class="ctl__exact"><input type="number" class="ctl__num" :value="days" :min="MIN" :max="MAX" aria-label="Days exactly" @change="typed" />days</span>
              </div>
              <div v-if="problem('archiveUnusedAfterDays')" class="ctl__error">{{ problem('archiveUnusedAfterDays') }}</div>
            </div>
          </div>
        </div>

        <div class="prow" :class="{ 'prow--on': active === 4, 'prow--locked': !enabled }" @mouseenter="active = 4" @mouseleave="active = 0" @focusin="active = 4" @focusout="active = 0">
          <span class="prow__n">4</span>
          <div class="prow__main">
            <div class="prow__head">
              <b>Deleting for good</b>
              <v-tooltip text="Lets people with full rights delete archived items for good, after a confirmation. The collab-kit server must allow it too (ARCHIVE_DELETE=true); otherwise collab-kit refuses it." location="top" max-width="280">
                <template #activator="{ props: tip }">
                  <v-icon v-bind="tip" icon="mdi-information-outline" size="16" class="prow__info" tabindex="0" aria-label="About Deleting for good" />
                </template>
              </v-tooltip>
            </div>
            <div class="ctl" :class="{ 'ctl--locked': !enabled }" :inert="!enabled">
              <span v-if="changed('allowDelete')" class="ctl__dot" title="Unsaved change" />
              <v-switch :model-value="allowDelete" density="compact" color="primary" hide-details label="Offer deleting in the archive" @update:model-value="emit('update', 'allowDelete', Boolean($event))" />
              <v-icon v-if="!enabled" icon="mdi-lock-outline" size="14" title="Only while the archive is on" />
            </div>
            <div v-if="deleteHint" class="ctl__warn">{{ deleteHint }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { archiveCapabilities, COLLAB_LIMITS } from '@/collab/settings/collabSettings'

/** The archive settings as the form shows them: two switches and the days. */
const props = defineProps<{ values: Record<string, unknown>; changed: (key: string) => boolean; problem: (key: string) => string | undefined }>()
const emit = defineEmits<{ update: [key: string, value: number | boolean] }>()

const { default: DEFAULT, min: MIN, max: MAX } = COLLAB_LIMITS.archive.archiveUnusedAfterDays

/** Hovering a row or a part lights up the other one. */
const active = ref(0)

const enabled = computed(() => props.values.enabled === true)
const onClose = computed(() => props.values.archiveOnShareClose === true)
const allowDelete = computed(() => props.values.allowDelete === true)
const days = computed(() => {
  const value = props.values.archiveUnusedAfterDays
  return typeof value === 'number' && Number.isFinite(value) && value >= MIN ? Math.min(MAX, Math.round(value)) : DEFAULT
})
const never = computed(() => days.value === 0)

// What the collab-kit server refuses although it is turned on here; unknown at a collab-kit without the route, then no hint.
const serverOff = computed(() => enabled.value && archiveCapabilities.value?.enabled === false)
const deleteHint = computed(() => {
  const caps = archiveCapabilities.value
  if (!enabled.value || !allowDelete.value || !caps?.enabled) return undefined
  if (!caps.deleteEnabled) return 'The collab-kit server does not allow deleting for good (ARCHIVE_DELETE), so the archive offers no deleting.'
  if (!caps.deleteAllowed) return 'Deleting for good needs manage everywhere, which you lack, so the archive does not offer it to you.'
  return undefined
})
const daysLabel = (value: number) => (value === 0 ? 'never' : value === 1 ? '1 day' : `${value} days`)

const set = (value: number) => emit('update', 'archiveUnusedAfterDays', Math.min(MAX, Math.max(MIN, Math.round(value))))
const typed = (event: Event) => {
  const value = (event.target as HTMLInputElement).valueAsNumber
  if (Number.isFinite(value)) set(value)
}

// The day axis: 0 (never) sits at the left end, 1 to 365 days on a logarithmic scale after a gap.
const X0 = 10
const X1 = 310
const XS = 40
const TICKS = [0, 7, 30, 90, 365]
const axisOf = (value: number) => (value <= 0 ? X0 : XS + (Math.log(value) / Math.log(MAX)) * (X1 - XS))
/** Coarser steps for more days, so the dot lands on round values. */
const stepOf = (value: number) => (value < 30 ? 1 : value < 100 ? 5 : 10)
const roundTo = (value: number) => Math.round(value / stepOf(value)) * stepOf(value)

const drag = (event: PointerEvent) => {
  const svg = event.currentTarget as SVGSVGElement
  if (event.type === 'pointerdown') svg.setPointerCapture(event.pointerId)
  else if ((event.buttons & 1) === 0) return
  const box = svg.getBoundingClientRect()
  const x = ((event.clientX - box.left) / box.width) * 320
  // Left of the gap's middle is never.
  if (x < (X0 + XS) / 2) return set(0)
  const share = Math.min(1, Math.max(0, (x - XS) / (X1 - XS)))
  set(Math.max(1, roundTo(Math.exp(share * Math.log(MAX)))))
}
/** Arrow keys move the dot by one step. */
const press = (event: KeyboardEvent) => {
  const direction = ['ArrowRight', 'ArrowUp'].includes(event.key) ? 1 : ['ArrowLeft', 'ArrowDown'].includes(event.key) ? -1 : 0
  if (direction === 0) return
  event.preventDefault()
  set(direction > 0 ? days.value + stepOf(days.value) : days.value - stepOf(days.value - 1))
}
</script>

<style scoped src="./canvasRows.css"></style>

<style scoped>
.title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}

.part--off {
  opacity: 0.35;
}

.badge-text {
  font-size: 11px;
  font-weight: 600;
  fill: #fff;
}

.box-text {
  font-size: 12px;
  font-weight: 500;
  fill: #222;
}

.small-text {
  font-size: 11px;
  fill: #666;
}

.arrow {
  stroke: #555;
  stroke-width: 1.5;
  fill: none;
}

.arrow--idle {
  stroke: #bbb;
}

.prow__main {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  gap: 4px 12px;
  min-width: 0;
}

.prow__head {
  display: flex;
  flex: 0 0 130px;
  align-items: center;
  align-self: flex-start;
  gap: 4px;
  min-height: 26px;
}

.ctl {
  display: flex;
  flex: 1;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 8px;
  min-width: 0;
  min-height: 26px;
  font-size: 12px;
}

.ctl--wide {
  flex-basis: 100%;
}

/* Without the archive these are only explained: grey, faded and not clickable. */
.ctl--locked {
  cursor: not-allowed;
  filter: grayscale(1);
  opacity: 0.4;
}

/* The server refuses what is turned on here; a notice, since the setting itself may stay. */
.ctl__warn {
  flex-basis: 100%;
  font-size: 12px;
  color: rgb(var(--v-theme-warning));
}

.ctl__num {
  width: 64px;
  padding: 2px 6px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.25);
  border-radius: 4px;
  color: rgb(var(--v-theme-on-surface));
}
</style>
