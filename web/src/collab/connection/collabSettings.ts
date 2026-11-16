import { reactive } from 'vue'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'

/** Ein einstellbarer Wert: der Standard und der erlaubte Bereich, beide Enden eingeschlossen. */
export interface CollabLimit {
  readonly default: number
  readonly min: number
  readonly max: number
}

/**
 * Die Collab-Einstellungen, ein Bereich je Dokument in collab-kit (ck.settings). collab-kit kennt
 * weder Bereiche noch Schlüssel; die Grenzen prüft nur der Copilot. Die drei Zeiten des Sweeps stehen mit
 * denselben Grenzen auch in api/src/modeling_api/services/collab_kit/sweep.py (SHARING_LIMITS).
 */
export const COLLAB_LIMITS = {
  sharing: {
    // So lange darf ein Besucher fehlen, bevor der Sweep ihn aus der Gruppe nimmt.
    visitorGraceSeconds: { default: 120, min: 30, max: 3600 },
    // So lange darf der Host fehlen, bevor der Sweep den Raum sperrt.
    hostGraceSeconds: { default: 120, min: 30, max: 3600 },
    // So lange darf der Host fehlen, bevor der Sweep alle Besucher hinausnimmt.
    hostEndSeconds: { default: 300, min: 30, max: 7200 },
    // So lange fehlt der Host, bevor ein Besucher davon erfährt; ein Neuladen des Hosts dauert kürzer.
    hostAwayMs: { default: 30_000, min: 5_000, max: 600_000 }
  },
  presence: {
    // Nach so langer Untätigkeit gibt ein Client seine Auswahl ab und damit seine Sperren.
    idleMs: { default: 90_000, min: 15_000, max: 3_600_000 }
  }
} as const satisfies Record<string, Record<string, CollabLimit>>

export type CollabArea = keyof typeof COLLAB_LIMITS
export const COLLAB_AREAS = Object.keys(COLLAB_LIMITS) as CollabArea[]
type AreaValues<A extends CollabArea> = { -readonly [K in keyof (typeof COLLAB_LIMITS)[A]]: number }

const defaultsOf = <A extends CollabArea>(area: A) => Object.fromEntries(Object.entries(COLLAB_LIMITS[area]).map(([key, limit]) => [key, limit.default])) as AreaValues<A>

/** Die geltenden Werte; wer sie bei jeder Verwendung liest, bekommt eine Änderung sofort. */
export const collabSettings = reactive({ sharing: defaultsOf('sharing'), presence: defaultsOf('presence') })

/** Ob ein Name aus settingsChanged ein Bereich des Copilots ist. */
export const isCollabArea = (key: string): key is CollabArea => COLLAB_AREAS.includes(key as CollabArea)

/** Übernimmt die Werte eines Bereichs; fehlt einer oder liegt er außerhalb der Grenzen, gilt sein Standard. */
export const applyCollabSettings = (area: CollabArea, values: Record<string, unknown>) => {
  const target: Record<string, number> = collabSettings[area]
  for (const [key, { default: fallback, min, max }] of Object.entries<CollabLimit>(COLLAB_LIMITS[area])) {
    const value = values[key]
    target[key] = typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max ? value : fallback
  }
}

/** Liest einen Bereich aus collab-kit; ein nie gesetzter kommt als {} und gilt damit als Standard. */
export const loadCollabSettings = async (ck: CollabKitApi, area: CollabArea) => applyCollabSettings(area, await ck.settings.get(area))
