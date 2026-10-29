import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'
import { useDocumentVisibility, useIdle, useIntervalFn, useTimeoutPoll, useWindowFocus } from '@vueuse/core'
import paths, { type PulseOffer, type PulseState } from '@/services/learningPaths'
import { surveyError, type SurveyResponse } from '@/services/surveys'

/** One session per visit to the modeling view; step changes reset only local signals. */
export function usePulseSurvey(runId: Ref<string | undefined>, stepId: Ref<string | undefined>, enabled: Ref<boolean>) {
  const sessionKey = crypto.randomUUID()
  const { idle } = useIdle(60_000)
  const visibility = useDocumentVisibility()
  const focused = useWindowFocus()
  const active = computed(() => enabled.value && !idle.value && visibility.value === 'visible' && focused.value && Boolean(runId.value && stepId.value))
  const offer = ref<PulseOffer | null>(null)
  const state = ref<PulseState>('idle')
  const offerOpened = ref(false)
  const rewardCoins = ref(0)
  const coinBalance = ref<number | null>(null)
  const error = ref('')
  const pollError = ref('')
  const busy = ref(false)
  const visible = ref(false)
  const pollInterval = ref(1000)
  const canPoll = computed(() => active.value && !busy.value && (state.value === 'idle' || state.value === 'offered'))
  let seconds = 0, generation = 0, disposed = false, pollInFlight = false
  let thanksTimer: ReturnType<typeof setTimeout> | undefined
  const counter = useIntervalFn(() => { seconds = Math.min(seconds + 1, 30) }, 1000, { immediate: false })
  const polling = useTimeoutPoll(async () => {
    if (!canPoll.value || !runId.value || !stepId.value || pollInFlight) return
    const current = generation
    const delta = seconds
    seconds = 0
    pollInFlight = true
    try {
      const result = (await paths.pollPulse(runId.value, stepId.value, sessionKey, delta)).data
      if (disposed || current !== generation) return
      pollInterval.value = Math.max(1, Math.min(30, result.nextPollSeconds ?? 30)) * 1000
      pollError.value = ''
      if (state.value === 'thanks' || state.value === 'expired') return
      if (!result.offer) {
        offer.value = null
        state.value = 'idle'
      } else {
        const same = offer.value?.id === result.offer.id
        if (!same) offerOpened.value = false
        // Cache an offer while inactive; the component reveals it on return.
        offer.value = result.offer
        if (!same || state.value === 'idle') state.value = 'offered'
      }
    } catch (e) {
      if (!disposed && current === generation) {
        const response = (e as { response?: { status?: number; data?: { message?: string } } }).response
        // A competing tab may hold the short run lock; retry normally.
        if (response?.status !== 409) pollError.value = response?.data?.message ?? 'Die Verbindung zur API ist fehlgeschlagen.'
      }
    } finally {
      pollInFlight = false
    }
  }, pollInterval, { immediate: false })
  watch(active, (value) => {
    if (value) counter.resume()
    else counter.pause()
  }, { immediate: true })
  watch(canPoll, (value) => {
    if (value) polling.resume()
    else polling.pause()
  }, { immediate: true })
  watch([active, offer, state], () => {
    if (!offer.value && state.value !== 'thanks') visible.value = false
    else if (active.value) visible.value = true
  })
  watch([runId, stepId], () => {
    generation++
    pollInterval.value = 1000
    seconds = 0
    offer.value = null
    offerOpened.value = false
    rewardCoins.value = 0
    coinBalance.value = null
    state.value = 'idle'
    visible.value = false
    error.value = ''
    pollError.value = ''
    clearTimeout(thanksTimer)
  })
  const open = () => {
    if (offer.value && enabled.value && !busy.value && state.value === 'offered') { error.value = ''; state.value = 'open' }
  }
  const answered = (response?: SurveyResponse) => {
    error.value = ''
    rewardCoins.value = response?.rewardCoins ?? 0
    coinBalance.value = response?.coinBalance ?? null
    state.value = 'thanks'
    offer.value = null
    pollInterval.value = 1000
    clearTimeout(thanksTimer)
    thanksTimer = setTimeout(() => { state.value = 'idle' }, rewardCoins.value > 0 ? 3800 : 2500)
  }
  const dismiss = async () => {
    if (!offer.value || !runId.value || busy.value) return
    const current = generation
    busy.value = true
    error.value = ''
    try {
      await paths.dismissPulse(runId.value, offer.value.id)
      if (!disposed && current === generation) answered()
    } catch (e) {
      if (!disposed && current === generation) error.value = surveyError(e)
    } finally { busy.value = false }
  }
  const expire = async () => {
    if (!offer.value || !runId.value || busy.value || state.value !== 'offered' || offerOpened.value) return
    const current = generation
    busy.value = true
    error.value = ''
    try {
      const result = (await paths.expirePulse(runId.value, offer.value.id)).data
      if (disposed || current !== generation) return
      if (result.event === 'opened') {
        offerOpened.value = true
      } else if (result.event === 'expired') {
        state.value = 'expired'
        pollInterval.value = 1000
        clearTimeout(thanksTimer)
        thanksTimer = setTimeout(() => {
          offer.value = null
          state.value = 'idle'
        }, 2200)
      } else answered()
    } catch (e) {
      if (!disposed && current === generation) error.value = surveyError(e)
    } finally { busy.value = false }
  }
  onScopeDispose(() => { disposed = true; generation++; clearTimeout(thanksTimer) })
  return { active, visible, offer, offerOpened, rewardCoins, coinBalance, state, error, pollError, busy, open, dismiss, expire, answered }
}
