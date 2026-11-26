import { computed, ref } from 'vue'
import { driver, type Driver, type DriveStep } from 'driver.js'
import 'driver.js/dist/driver.css'
import tours, { type TourEventName, type TourProgress } from '@/services/tours'
import { notifyError } from '@/composables/useNotifications'
import type { TourDefinition, TourEvent, TourStatus, TourStep } from '@/tours/types'

const toDriveStep = (step: TourStep, index: number): DriveStep => ({
  element: step.element,
  allowedElements: step.allowedElements,
  popover: {
    title: step.title,
    description: step.description,
    side: step.side,
    showButtons: step.buttons ?? (index === 0 ? ['next', 'close'] : ['previous', 'next', 'close'])
  }
})

/** Führt genau eine Tour aus: Driver, Fortschritt und Events der API. Kennt keine Seite und keine Anzeige. */
export function useTour(definition: TourDefinition, emit: (event: TourEvent) => void = () => undefined) {
  const stepIds = definition.steps.map((step) => step.id)
  const progress = ref<TourProgress>({ completed: false, skipped: false })
  const loaded = ref(false)
  const starting = ref(false)
  const active = ref(false)
  const error = ref('')
  const seen = ref(false)
  let current: Driver | null = null
  let finishing = false
  let disposed = false
  let loadPromise: Promise<void> | null = null

  const done = computed(() => progress.value.completed || progress.value.skipped)
  const status = computed<TourStatus>(() => {
    if (progress.value.completed) return 'completed'
    if (progress.value.skipped) return 'skipped'
    return seen.value ? 'seen' : 'new'
  })
  const stepId = () => stepIds[current?.getActiveIndex() ?? -1]

  const merge = (value: TourProgress) => {
    progress.value = { completed: progress.value.completed || value.completed, skipped: progress.value.skipped || value.skipped }
    loaded.value = true
    error.value = ''
  }
  const load = () => {
    if (loadPromise) return loadPromise
    loadPromise = (async () => {
      try {
        const result = await tours.progress(definition.id)
        if (!disposed) merge(result.data)
      } catch {
        if (!disposed) error.value = 'Der Tour-Fortschritt konnte nicht geladen werden.'
      } finally {
        loadPromise = null
      }
    })()
    return loadPromise
  }
  const record = async (event: TourEventName, step?: string) => {
    try {
      const result = await tours.recordEvent(definition.id, event, step)
      if (!disposed) merge(result.data)
    } catch {
      if (!disposed) {
        error.value = 'Der Tour-Fortschritt konnte nicht gespeichert werden. Bitte versuche es erneut.'
        notifyError(error.value)
      }
    }
  }

  const end = (event: 'completed' | 'skipped', step?: string) => {
    if (finishing) return
    finishing = true
    const last = step ?? stepId()
    const instance = current
    current = null
    active.value = false
    instance?.destroy()
    void record(event, event === 'skipped' ? last : undefined)
    emit(event === 'completed' ? { type: 'completed', tourId: definition.id } : { type: 'skipped', tourId: definition.id, stepId: last })
  }
  /** Beendet die laufende Tour; ohne Tour passiert nichts. */
  const finish = (event: 'completed' | 'skipped') => {
    if (current) end(event)
  }
  const moveTo = (id: string) => {
    const index = stepIds.indexOf(id)
    if (current && !finishing && index >= 0 && current.getActiveIndex() !== index) current.moveTo(index)
  }
  /** Vom Menü beim Öffnen der Liste aufrufen; zählt die Tour als gesehen. */
  const opened = async () => {
    seen.value = true
    if (!loaded.value) await load()
    await record('opened')
  }
  const skip = () => record('skipped')

  const start = async () => {
    if (starting.value || current || (definition.available && definition.available() !== true)) return
    starting.value = true
    await record('started')
    if (disposed) return
    finishing = false
    current = driver({
      waitForElement: 10000,
      closeBtnLabel: 'Tour schließen',
      nextBtnText: 'Weiter',
      prevBtnText: 'Zurück',
      doneBtnText: 'Fertig',
      ...definition.options,
      steps: definition.steps.map(toDriveStep),
      onHighlighted: (_element, _step, { driver: instance }) => {
        const index = instance.getActiveIndex() ?? -1
        const id = stepIds[index]
        if (!id) return
        // Step-Events dienen nur der Auswertung; ein Fehler darf die Tour nicht stören.
        void tours.recordEvent(definition.id, 'step', id).catch(() => undefined)
        emit({ type: 'step', tourId: definition.id, stepId: id, index })
      },
      onElementMissing: () => {
        if (finishing) return false
        const missing = stepId()
        error.value = 'Der nächste Tour-Schritt ist nicht verfügbar. Du kannst die Tour später erneut starten.'
        notifyError(error.value)
        emit({ type: 'unavailable', tourId: definition.id, stepId: missing })
        end('skipped', missing)
        return false
      },
      // driver.js nennt den Grund: "done" = Fertig auf dem letzten Schritt, sonst wurde die Tour geschlossen (Kreuz, Escape, Overlay).
      onDestroyStarted: (_element, _step, { driver: instance, reason }) => {
        end(reason === 'done' ? 'completed' : 'skipped')
        instance.destroy()
      }
    })
    active.value = true
    starting.value = false
    current.drive()
    emit({ type: 'start', tourId: definition.id })
  }

  /** Beim Verlassen der Seite aufrufen. */
  const dispose = () => {
    if (current && !finishing) end('skipped')
    disposed = true
  }

  return { progress, status, done, loaded, active, starting, error, load, opened, start, skip, finish, moveTo, dispose }
}
