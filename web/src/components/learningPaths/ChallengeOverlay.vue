<template>
  <aside class="challenge-overlay" :style="{ borderColor: attempt.config.color ?? '#598878' }" aria-label="Active challenge">
    <div class="overlay-header">
      <v-icon :color="attempt.config.color ?? undefined" size="22">{{ attempt.config.icon }}</v-icon>
      <strong>{{ attempt.config.title }}</strong>
      <v-btn size="small" variant="text" :icon="collapsed ? 'mdi-chevron-up' : 'mdi-chevron-down'" :aria-label="collapsed ? 'Expand challenge' : 'Collapse challenge'" :aria-expanded="!collapsed" aria-controls="challenge-overlay-content" @click="collapsed = !collapsed" />
    </div>
    <div v-if="attempt.config.type === 'time'" class="timer-display" :class="{ 'timer-display--elapsed': remaining === 0, 'timer-display--ending': remaining > 0 && remaining <= 120 }">
      <v-icon size="18">mdi-timer-outline</v-icon>
      <span v-if="attempt.stoppedAt" role="status">Ended early</span>
      <span v-else-if="remaining > 0" role="timer" aria-label="Remaining challenge time" aria-live="off">{{ formattedRemaining }}</span>
      <span v-else role="status">Time budget reached</span>
    </div>
    <div v-show="!collapsed" id="challenge-overlay-content" class="overlay-content">
      <p class="overlay-description">{{ attempt.config.description }}</p>
      <p class="text-body-2 font-weight-medium mt-3">{{ challengeGoal(attempt.config) }}</p>
      <p v-if="attempt.config.type === 'time' && remaining === 0" class="text-body-2 mt-2">You can continue at your own pace. Your model remains editable.</p>
      <p class="text-caption mt-3">Help remains available at any time.</p>
      <p v-if="attempt.stoppedAt" class="text-caption mt-2">Ended at {{ new Date(attempt.stoppedAt).toLocaleString('en-GB') }}. You can continue working on the task.</p>
      <v-btn v-if="attempt.config.type === 'time' && remaining > 0 && !attempt.stoppedAt" class="mt-3" size="small" variant="tonal" :loading="stopping" :disabled="stopping" @click="emit('stop')">End time challenge</v-btn>
    </div>
  </aside>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { challengeGoal, type ChallengeAttempt } from '@/services/challenges'
import { serverNow, synchronizeServerTime } from '@/utils/serverTime'
const props = withDefaults(defineProps<{ attempt: ChallengeAttempt; stopping?: boolean }>(), { stopping: false })
const emit = defineEmits<{ stop: [] }>()
const collapsed = ref(false)
const now = ref(serverNow())
const remaining = computed(() => (props.attempt.endsAt && !props.attempt.stoppedAt ? Math.max(0, Math.ceil((Date.parse(props.attempt.endsAt) - now.value) / 1000)) : 0))
const formattedRemaining = computed(() => {
  const seconds = remaining.value
  const minutes = Math.floor(seconds / 60)
  return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
})
let timer: ReturnType<typeof setInterval> | undefined
const updateClock = () => {
  now.value = serverNow()
}
onMounted(() => {
  if (props.attempt.config.type !== 'time') return
  void synchronizeServerTime()
    .then(updateClock)
    .catch(() => undefined)
  timer = setInterval(updateClock, 1000)
  document.addEventListener('visibilitychange', updateClock)
})
onUnmounted(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', updateClock)
})
</script>
<style scoped>
.challenge-overlay {
  position: absolute;
  bottom: 24px;
  right: 24px;
  z-index: 10;
  width: min(330px, calc(100% - 32px));
  border: 1px solid;
  border-left-width: 4px;
  border-radius: 14px;
  background: rgb(var(--v-theme-surface));
  color: rgb(var(--v-theme-on-surface));
  box-shadow: 0 4px 20px #223c3226;
}
.overlay-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 8px 14px;
}
.overlay-header strong {
  flex: 1;
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}
.overlay-content {
  padding: 0 16px 16px;
  max-height: 240px;
  overflow-y: auto;
}
.overlay-description {
  white-space: pre-line;
  overflow-wrap: anywhere;
  font-size: 0.82rem;
  line-height: 1.5;
}
.timer-display {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px 12px;
  font-size: 1.2rem;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  color: #356458;
}
.timer-display--ending {
  color: #93691d;
}
.timer-display--elapsed {
  font-size: 0.9rem;
  color: #6b6555;
}
@media (max-width: 600px) {
  .challenge-overlay {
    right: 16px;
    bottom: 16px;
  }
}
</style>
