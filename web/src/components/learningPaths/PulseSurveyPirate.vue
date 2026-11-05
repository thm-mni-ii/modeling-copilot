<template>
  <Teleport to="body">
    <div v-if="entering" ref="traveler" class="pirate-traveler" :style="flightPosition" aria-hidden="true">
      <PulsePirateArt :pose="flying ? 'dash' : 'peek'" />
    </div>
  </Teleport>
  <aside v-if="visible && (offer || state === 'thanks')" class="pulse-pirate" :class="{ 'pulse-pirate--expired': state === 'expired', 'pulse-pirate--reduced-motion': motion === 'reduce' }" aria-label="Impuls-Frage">
    <v-card v-if="state === 'thanks'" role="status" aria-live="polite" class="pirate-thanks pa-2" :class="{ 'pirate-thanks--reward': rewardCoins > 0 }">
      <template v-if="rewardCoins > 0">
        <PulsePirateArt pose="joy" class="reward-pirate" />
        <div class="earned-coin" aria-hidden="true"><TreasureMapArt kind="coin" /><span>+{{ rewardCoins }}</span></div>
        <strong class="reward-title">+{{ rewardCoins }} {{ rewardCoins === 1 ? 'Münze' : 'Münzen' }} verdient!</strong>
        <p class="text-body-2 mt-1">Danke für deine Antwort!</p>
        <p v-if="coinBalance !== null" class="text-caption mt-2">Dein Münzstand: {{ coinBalance }}</p>
      </template>
      <template v-else>Danke! Weiter geht’s.</template>
    </v-card>
    <template v-else>
      <div v-if="speech" class="pirate-speech" role="status">{{ speech }}</div>
      <div :key="offer?.id" class="pirate-arrival" :class="{ 'pirate-arrival--hidden': entering }">
        <button ref="pirateButton" type="button" id="pulse-pirate-button" class="pirate-button" :class="{ 'pirate-button--animated': pulsing }" :style="{ filter: `grayscale(${countdown})` }" :disabled="busy || state === 'expired'" aria-label="Impuls-Frage öffnen" :aria-expanded="state === 'open'" @click="$emit('open')">
          <PulsePirateArt :pose="state === 'expired' ? 'farewell' : state === 'open' || countdown > 0 ? 'listen' : 'invite'" class="pirate-art" />
          <span v-if="state === 'offered' && !offerOpened" class="pirate-invitation" aria-hidden="true"><TreasureMapArt kind="coin" /><span>+1</span></span>
          <span v-if="countdown > 0" class="pirate-countdown" aria-hidden="true"><span :style="{ transform: `scaleX(${1 - countdown})` }" /></span>
        </button>
      </div>
      <v-overlay :model-value="state === 'open'" target="#pulse-pirate-button" location-strategy="connected" location="left center" scroll-strategy="reposition" :close-on-back="false" :scrim="false" persistent no-click-animation max-width="360">
        <v-card v-if="offer" class="pulse-card">
          <v-card-title>Kurze Impuls-Frage</v-card-title>
          <v-card-text><SurveyRenderer :key="offer.id" ref="renderer" :survey-id="offer.surveyId" :activity="{ runId, stepId, phase: `pulse:${offer.id}` }" @completed="$emit('answered', $event)" /><v-alert v-if="error" type="error" class="mt-2">{{ error }}</v-alert></v-card-text>
          <v-card-actions><v-btn :loading="busy" :disabled="Boolean(renderer?.saving)" @click="dismiss">Später</v-btn></v-card-actions>
        </v-card>
      </v-overlay>
      <v-alert v-if="error && state !== 'open'" type="error" density="compact" class="mt-2">{{ error }}</v-alert>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useIntervalFn, usePreferredReducedMotion } from '@vueuse/core'
import type { PulseOffer, PulseState } from '@/services/learningPaths'
import type { SurveyResponse } from '@/services/surveys'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
import TreasureMapArt from './TreasureMapArt.vue'
import PulsePirateArt from './PulsePirateArt.vue'
const props = defineProps<{ runId: string; stepId: string; visible: boolean; offer: PulseOffer | null; offerOpened: boolean; rewardCoins: number; coinBalance: number | null; state: PulseState; busy: boolean; error: string }>()
const emit = defineEmits<{ open: []; dismiss: []; answered: [response?: SurveyResponse]; expired: [] }>()
const motion = usePreferredReducedMotion()
const renderer = ref<InstanceType<typeof SurveyRenderer> | null>(null)
// The traveler is outside the clipped sidebar; its destination remains the real button.
const pirateButton = ref<HTMLButtonElement | null>(null)
const traveler = ref<HTMLDivElement | null>(null)
const entering = ref(false)
const flying = ref(false)
const flightPosition = ref({ left: '0px', top: '0px' })
let introducedOffer: string | undefined
watch([() => props.offer?.id, () => props.visible, () => props.state, () => props.offerOpened, motion, pirateButton], async ([id, visible, state, opened, preference, button], _previous, onCleanup) => {
  if (!id || !visible || state !== 'offered' || opened || !button || id === introducedOffer) return
  introducedOffer = id
  if (preference === 'reduce') return
  const frame = button.closest('.canvas-area')?.querySelector('.graph-container')
  if (!frame) return
  const bounds = frame.getBoundingClientRect()
  const destination = button.getBoundingClientRect()
  if (bounds.width < 180 || bounds.height < 120 || destination.width === 0) return
  let cancelled = false
  let animation: Animation | undefined
  const finish = () => {
    cancelled = true
    animation?.cancel()
    entering.value = false
    window.removeEventListener('resize', finish)
    window.removeEventListener('scroll', finish, true)
  }
  // Resizing or scrolling invalidates the measured route: land immediately.
  window.addEventListener('resize', finish)
  window.addEventListener('scroll', finish, true)
  onCleanup(finish)
  const x = Math.max(8, Math.min(window.innerWidth - 112, bounds.right - 140))
  const y = Math.max(8, bounds.top - 12)
  flightPosition.value = { left: `${x}px`, top: `${y}px` }
  entering.value = true
  flying.value = false
  await nextTick()
  if (cancelled || !traveler.value) {
    finish()
    return
  }
  try {
    animation = traveler.value.animate([
      { transform: 'translateY(-45px) rotate(180deg) scale(.7)', opacity: 0 },
      { transform: 'translateY(0) rotate(180deg)', opacity: 1, offset: .35 },
      { transform: 'translateY(3px) rotate(170deg)', offset: .7 },
      { transform: 'translateY(0) rotate(180deg)' }
    ], { duration: 1100, easing: 'ease-in-out', fill: 'forwards' })
    await animation.finished
    if (cancelled) return
    flying.value = true
    const dx = destination.left - x, dy = destination.top - y
    animation.cancel()
    animation = traveler.value.animate([
      { transform: 'translate(0, 0) rotate(180deg)' },
      { transform: `translate(${dx * .45}px, ${Math.min(dy, -35)}px) rotate(310deg) scale(1.08, .88)`, offset: .45 },
      { transform: `translate(${dx}px, ${dy}px) rotate(360deg) scale(1.08, .86)`, offset: .82 },
      { transform: `translate(${dx}px, ${dy}px) rotate(360deg) scale(1)` }
    ], { duration: 800, easing: 'ease-in-out', fill: 'forwards' })
    await animation.finished
  } catch {
    // Cancellation also covers navigation, opening the question and reduced motion.
  } finally {
    finish()
  }
}, { flush: 'post' })
const elapsed = ref(0)
let trackedOffer: string | undefined, startedAt: number | undefined, lastExpiryAttempt = -Infinity
const countdown = computed(() => props.state === 'expired' ? 1 : props.state !== 'offered' || props.offerOpened ? 0 : Math.min(1, Math.max(0, (elapsed.value - 20_000) / 20_000)))
const pulsing = computed(() => props.state === 'offered' && !props.offerOpened && elapsed.value < 20_000 && motion.value !== 'reduce')
const speech = computed(() => props.state === 'expired' ? 'Ich komme später wieder.' : props.state === 'offered' && !props.offerOpened && elapsed.value >= 10_000 ? 'Willst du eine Münze verdienen?' : '')
const clock = useIntervalFn(() => {
  if (startedAt === undefined) return
  const now = performance.now()
  elapsed.value = now - startedAt
  if (elapsed.value >= 40_000 && !props.busy && now - lastExpiryAttempt >= 5000) {
    lastExpiryAttempt = now
    emit('expired')
  }
}, 100, { immediate: false })
watch([() => props.offer?.id, () => props.visible, () => props.state, () => props.offerOpened], ([id, visible, state, opened]) => {
  if (id !== trackedOffer) {
    trackedOffer = id
    startedAt = undefined
    elapsed.value = 0
    lastExpiryAttempt = -Infinity
  }
  if (id && visible && state === 'offered' && !opened) {
    startedAt ??= performance.now()
    clock.resume()
  } else clock.pause()
}, { immediate: true })
const dismiss = async () => {
  if (renderer.value?.saving) return
  await renderer.value?.saveDraft()
  emit('dismiss')
}
</script>

<style scoped>
.pulse-pirate { position: absolute; left: 8px; bottom: 2px; z-index: 2; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; max-width: calc(100% - 28px); }
.pirate-arrival { width: 104px; height: 104px; transform-origin: 50% 90%; }
.pirate-arrival--hidden { opacity: 0; }
.pirate-traveler { position: fixed; width: 104px; height: 104px; pointer-events: none; z-index: 1900; filter: drop-shadow(0 0 5px #ffe3a2); }
.pirate-traveler svg { width: 100%; height: 100%; }
.reward-pirate { width: 64px; height: 64px; float: left; margin-right: 5px; animation: pirate-celebrate 650ms ease-out both; }
.pirate-button { position: relative; isolation: isolate; width: 104px; height: 104px; border: 0; padding: 0; background: transparent; cursor: pointer; transition: transform 160ms ease; transform-origin: bottom center; }
.pirate-button::before { content: ""; position: absolute; inset: -8px -12px -2px; z-index: -1; border-radius: 50%; background: radial-gradient(ellipse, #fffbe8 0%, #ffe89bd9 30%, #ffd34d99 50%, #ffc13b40 65%, transparent 78%); filter: blur(5px); pointer-events: none; }
.pirate-button--animated::before { animation: pirate-glow 2s ease-in-out infinite; }
.pirate-button:disabled { cursor: default; }
.pirate-button:hover:not(:disabled), .pirate-button:focus-visible { transform: scale(1.08); }
.pirate-button:focus-visible { outline: 2px dashed #805b20; outline-offset: 2px; border-radius: 8px; }
.pirate-art { width: 104px; height: 104px; filter: drop-shadow(0 0 3px #fff8d6) drop-shadow(0 0 7px #ffc94b); }
.pirate-invitation { position: absolute; right: 0; top: 1px; display: flex; align-items: center; gap: 2px; padding: 3px 5px; border-radius: 8px; background: #fff7dd; color: #70471a; box-shadow: 0 2px 5px #71491c33; font-size: 0.8rem; font-weight: 800; }
.pirate-invitation svg { width: 20px; height: 20px; }
.pirate-countdown { position: absolute; bottom: 0; left: 10px; width: 84px; height: 9px; border: 2px solid #fff3cf; border-radius: 6px; overflow: hidden; background: #514733; box-shadow: 0 1px 5px #47331a80; }
.pirate-countdown > span { display: block; width: 100%; height: 100%; background: linear-gradient(90deg, #e9a217, #ffe58a); transform-origin: left; transition: transform 100ms linear; }
.pirate-button--animated .pirate-invitation { animation: pirate-invite 1.8s ease-in-out infinite; }
.pirate-speech { position: absolute; left: 108px; bottom: 26px; width: 120px; padding: 7px 10px; border: 1px solid rgb(var(--v-theme-on-surface), 0.15); border-radius: 14px; background: rgb(var(--v-theme-surface)); color: rgb(var(--v-theme-on-surface)); box-shadow: 0 3px 12px rgb(0 0 0 / 12%); font-size: 0.75rem; }
.pirate-speech::after { content: ''; position: absolute; left: -6px; bottom: 18px; width: 11px; height: 11px; background: inherit; border-left: 1px solid rgb(var(--v-theme-on-surface), 0.15); border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.15); transform: rotate(45deg); }
.pulse-pirate--expired { pointer-events: none; animation: pirate-farewell 1.2s ease 1s forwards; }
.pulse-pirate--reduced-motion, .pulse-pirate--reduced-motion .pirate-arrival, .pulse-pirate--reduced-motion .pirate-button, .pulse-pirate--reduced-motion .pirate-invitation, .pulse-pirate--reduced-motion .pirate-button::before { animation: none; transition: none; }
.pirate-thanks--reward { min-width: 200px; text-align: center; border: 1px solid #b98b35; animation: reward-appear 300ms ease-out both; }
.earned-coin { position: relative; width: 34px; height: 34px; margin: 0 auto 4px; animation: reward-coin 900ms ease-out both; }
.earned-coin svg { width: 100%; height: 100%; }
.earned-coin span { position: absolute; right: -15px; top: 0; color: #825b16; font-weight: 800; font-size: 1.25rem; }
.reward-title { display: block; color: #825b16; font-size: 0.9rem; }
.pulse-pirate--reduced-motion .reward-pirate, .pulse-pirate--reduced-motion .pirate-thanks, .pulse-pirate--reduced-motion .earned-coin { animation: none; }
.pulse-card { width: min(360px, calc(100vw - 32px)); max-height: 70vh; overflow-y: auto; }
.pulse-card :deep(.v-card-title) { padding: 12px 16px 8px; font-size: 1rem; }
.pulse-card :deep(.v-card-text) { padding: 0 16px; }
.pulse-card :deep(.v-card-actions) { min-height: 44px; padding: 4px 12px 8px; }
.pulse-card :deep(.sd-body), .pulse-card :deep(.sd-page) { padding: 0; row-gap: 8px; }
.pulse-card :deep(.sd-body__page) { min-width: 0; }
.pulse-card :deep(.sd-question__container) { padding: 0; }
.pulse-card :deep(.sd-question__header-and-content-container) { padding: 12px; gap: 8px; }
.pulse-card :deep(.sd-question__title) { font-size: 0.95rem; line-height: 1.4; padding: 0; }
.pulse-card :deep(.sd-item) { padding-block: 2px; }
.pulse-card :deep(.sd-selectbase__label) { min-height: 32px; align-items: center; gap: 8px; }
.pulse-card :deep(.sd-item__control-label) { font-size: 0.875rem; line-height: 1.4; }
.pulse-card :deep(.sd-item__decorator) { width: 20px; height: 20px; margin-bottom: 0; }
.pulse-card :deep(.sd-body__navigation) { padding: 8px 0 4px; }
.pulse-card :deep(.sd-btn) { min-height: 34px; padding: 8px 16px; font-size: 0.875rem; line-height: 1.3; }
@keyframes pirate-celebrate { 0% { transform: translateY(6px) scale(.9); } 45% { transform: translateY(-8px) rotate(-8deg); } 75% { transform: rotate(5deg); } 100% { transform: none; } }
@keyframes pirate-glow { 50% { opacity: 0.75; transform: scale(1.08); } }
@keyframes pirate-invite { 50% { transform: translateY(-5px) scale(1.1); box-shadow: 0 4px 12px #e0a52c66; } }
@keyframes pirate-farewell { to { opacity: 0; } }
@keyframes reward-appear { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
@keyframes reward-coin { 0% { opacity: 0; transform: translateY(14px) scale(0.6) rotate(-25deg); } 55% { opacity: 1; transform: translateY(-7px) scale(1.15) rotate(10deg); } 100% { opacity: 1; transform: translateY(0) scale(1) rotate(0); } }
</style>
