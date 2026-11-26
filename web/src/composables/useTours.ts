import { computed, getCurrentScope, onScopeDispose, shallowReactive } from 'vue'
import { useTour } from '@/composables/useTour'
import type { TourDefinition, TourEvent } from '@/tours/types'

type TourHandler = (event: TourEvent) => void
interface TourEntry {
  definition: TourDefinition
  tour: ReturnType<typeof useTour>
}

// Gemeinsamer Zustand: Seiten registrieren ihre Touren, Anzeigen (Badge, Liste, Banner, Trigger) lesen nur von hier.
const entries = shallowReactive(new Map<string, TourEntry>())
const handlers = new Set<TourHandler>()
const emit: TourHandler = (event) => handlers.forEach((handler) => handler(event))

const get = (id: string) => entries.get(id)?.tour
const hasActive = () => [...entries.values()].some((entry) => entry.tour.active.value)

const tours = computed(() =>
  [...entries.values()].map(({ definition, tour }) => {
    const availability = definition.available?.() ?? true
    return {
      id: definition.id,
      title: definition.title,
      description: definition.description,
      status: tour.status.value,
      done: tour.done.value,
      loaded: tour.loaded.value,
      // Offen: Fortschritt geladen und weder abgeschlossen noch übersprungen. Das zeigen Badge, Liste und Trigger an.
      pending: tour.loaded.value && !tour.done.value,
      active: tour.active.value,
      starting: tour.starting.value,
      error: tour.error.value,
      available: availability === true,
      reason: availability === true ? '' : availability
    }
  })
)
const pendingCount = computed(() => tours.value.filter((tour) => tour.pending).length)

/** Meldet eine Tour an; innerhalb einer Komponente wird sie beim Verlassen automatisch abgemeldet. */
const register = (definition: TourDefinition) => {
  if (!entries.has(definition.id)) {
    const tour = useTour(definition, emit)
    entries.set(definition.id, { definition, tour })
    void tour.load()
  }
  if (getCurrentScope()) onScopeDispose(() => unregister(definition.id))
}
const unregister = (id: string) => {
  get(id)?.dispose()
  entries.delete(id)
}

/** Es läuft höchstens eine Tour gleichzeitig. */
const start = async (id: string) => {
  if (!hasActive()) await get(id)?.start()
}
const skip = (id: string) => get(id)?.skip()
const opened = (id: string) => get(id)?.opened()
const finish = (id: string, event: 'completed' | 'skipped') => get(id)?.finish(event)
const moveTo = (id: string, stepId: string) => get(id)?.moveTo(stepId)

/** Hört auf Tour-Ereignisse (optional nur eines Typs oder einer Tour); in einer Komponente wird automatisch abgemeldet. */
const on = (handler: TourHandler, filter: { type?: TourEvent['type']; tourId?: string } = {}) => {
  const wrapped: TourHandler = (event) => {
    if ((!filter.type || filter.type === event.type) && (!filter.tourId || filter.tourId === event.tourId)) handler(event)
  }
  handlers.add(wrapped)
  const off = () => handlers.delete(wrapped)
  if (getCurrentScope()) onScopeDispose(off)
  return off
}

export function useTours() {
  return { tours, pendingCount, register, unregister, start, skip, opened, finish, moveTo, on }
}
