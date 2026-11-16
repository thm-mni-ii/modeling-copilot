import { reactive } from 'vue'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'

/** Ein einstellbarer Wert: eine Zahl im Bereich von min bis max, ein Schalter, eine Wahl aus festen Werten, eine Farbe oder eine Liste verschiedener Farben. */
export type CollabLimit = { readonly default: number; readonly min: number; readonly max: number } | { readonly default: boolean } | { readonly default: string; readonly options: readonly string[] } | { readonly default: string; readonly color: true } | { readonly default: readonly string[]; readonly minItems: number; readonly maxItems: number }

/** Eine Farbe als #rrggbb. */
const HEX = /^#[0-9a-f]{6}$/i

/**
 * Die Collab-Einstellungen, ein Bereich je Dokument in collab-kit (ck.settings). collab-kit kennt
 * weder Bereiche noch Schlüssel; die Grenzen prüft nur der Copilot. Die Zeiten des Sweeps stehen mit
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
    hostAwayMs: { default: 30_000, min: 5_000, max: 600_000 },
    // So oft sieht der Sweep nach; kürzer hält die Wartezeiten genauer ein und fragt collab-kit öfter.
    sweepSeconds: { default: 30, min: 10, max: 120 },
    // So oft liest ein Besucher nach, was der Raum dazubekommen hat; nach dem Schließen ist nichts mehr zu lesen.
    followMs: { default: 30_000, min: 10_000, max: 300_000 }
  },
  presence: {
    // Nach so langer Untätigkeit gibt ein Client seine Auswahl ab und damit seine Sperren.
    idleMs: { default: 90_000, min: 15_000, max: 3_600_000 },
    // Höchstens so oft geht ein bewegter Zeiger hinaus, der letzte Stand immer; kürzer ist flüssiger und mehr Verkehr.
    cursorSendMs: { default: 50, min: 20, max: 500 }
  },
  shareDefaults: {
    // Die Vorauswahl im Teilen-Dialog; der Host ändert sie dort für seine Share.
    anonymous: { default: false },
    edit: { default: true },
    history: { default: 'none', options: ['none', 'versions', 'steps'] }
  },
  colors: {
    // Der Host ist als Einziger rot, so erkennt man den Vortragenden auf einen Blick.
    hostColor: { default: '#cf5c58', color: true },
    // Sechzehn Farben, gemessen auf gute Unterscheidbarkeit (CIEDE2000, auch bei Rot-Grün-Schwäche), keine rot wie der Host.
    // Die ersten liegen am weitesten auseinander, so bekommen die ersten Personen im Raum die deutlichsten Farben.
    palette: { default: ['#c29ed7', '#214b25', '#ee9813', '#0e26dc', '#12c19f', '#652f55', '#715c00', '#6e83b7', '#1d8a85', '#8f4ef1', '#6f5d8d', '#f657f2', '#194b78', '#8605a8', '#41a8ba', '#2da0fb'], minItems: 8, maxItems: 24 }
  },
  archive: {
    // Das Archiv von collab-kit im Copilot; aus fehlt der Reiter „Archive“, die Knöpfe zum Archivieren zeigt collab-kit weiter.
    enabled: { default: false },
    // Ob eine beendete Share ihre Werkstücke (Modell und Aufgabe) archiviert, statt sie ohne Raum liegen zu lassen; nur mit enabled. Das Backend liest beide in api/src/modeling_api/services/collab_kit/archive.py.
    archiveOnShareClose: { default: false },
    // Nach so vielen Tagen ohne Aktivität archiviert das Backend Werkstücke beendeter Shares, die ohne Raum liegen; 0 heißt nie, nur mit enabled.
    // Dieselben Grenzen stehen in archive.py (UNUSED_DAYS).
    archiveUnusedAfterDays: { default: 0, min: 0, max: 365 }
  }
} as const satisfies Record<string, Record<string, CollabLimit>>

export type CollabArea = keyof typeof COLLAB_LIMITS
export const COLLAB_AREAS = Object.keys(COLLAB_LIMITS) as CollabArea[]
type ValueOf<L> = L extends { readonly options: readonly (infer O)[] } ? O : L extends { readonly minItems: number } ? string[] : L extends { readonly color: true } ? string : L extends { readonly default: boolean } ? boolean : number
type AreaValues<A extends CollabArea> = { -readonly [K in keyof (typeof COLLAB_LIMITS)[A]]: ValueOf<(typeof COLLAB_LIMITS)[A][K]> }

/** Eine Liste als eigene Kopie, damit niemand die Standards selbst verändert. */
const copyOf = (value: unknown) => (Array.isArray(value) ? [...value] : value)
const defaultsOf = <A extends CollabArea>(area: A) => Object.fromEntries(Object.entries(COLLAB_LIMITS[area]).map(([key, limit]) => [key, copyOf(limit.default)])) as AreaValues<A>

/** Die geltenden Werte; wer sie bei jeder Verwendung liest, bekommt eine Änderung sofort. */
export const collabSettings = reactive({ sharing: defaultsOf('sharing'), presence: defaultsOf('presence'), shareDefaults: defaultsOf('shareDefaults'), colors: defaultsOf('colors'), archive: defaultsOf('archive') })

/** Ob ein Name aus settingsChanged ein Bereich des Copilots ist. */
export const isCollabArea = (key: string): key is CollabArea => COLLAB_AREAS.includes(key as CollabArea)

/** Ob ein Wert passt: eine ganze Zahl in den Grenzen, ein Wahrheitswert, einer der festen Werte, eine Farbe oder genug verschiedene Farben. */
export const fitsLimit = (limit: CollabLimit, value: unknown) => {
  if ('options' in limit) return limit.options.includes(value as string)
  if ('color' in limit) return typeof value === 'string' && HEX.test(value)
  if ('minItems' in limit) return Array.isArray(value) && value.length >= limit.minItems && value.length <= limit.maxItems && value.every((color) => typeof color === 'string' && HEX.test(color)) && new Set(value.map((color: string) => color.toLowerCase())).size === value.length
  if ('min' in limit) return typeof value === 'number' && Number.isInteger(value) && value >= limit.min && value <= limit.max
  return typeof value === 'boolean'
}

/** Übernimmt die Werte eines Bereichs; fehlt einer oder passt er nicht, gilt sein Standard. */
export const applyCollabSettings = (area: CollabArea, values: Record<string, unknown>) => {
  const target: Record<string, unknown> = collabSettings[area]
  for (const [key, limit] of Object.entries<CollabLimit>(COLLAB_LIMITS[area])) target[key] = copyOf(fitsLimit(limit, values[key]) ? values[key] : limit.default)
}

/** Liest einen Bereich aus collab-kit; ein nie gesetzter kommt als {} und gilt damit als Standard. */
export const loadCollabSettings = async (ck: CollabKitApi, area: CollabArea) => applyCollabSettings(area, await ck.settings.get(area))
