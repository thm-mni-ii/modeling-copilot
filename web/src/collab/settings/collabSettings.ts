import { reactive } from 'vue'
import type { CollabKitApi } from '@/collab/kit/collabKitV1'

/** A value to set: a number from min to max, a switch, a choice of fixed values, a color or a list of distinct colors. */
export type CollabLimit = { readonly default: number; readonly min: number; readonly max: number } | { readonly default: boolean } | { readonly default: string; readonly options: readonly string[] } | { readonly default: string; readonly color: true } | { readonly default: readonly string[]; readonly minItems: number; readonly maxItems: number }

/** A color as #rrggbb. */
const HEX = /^#[0-9a-f]{6}$/i

/**
 * The collab settings, one area per document in collab-kit (ck.settings). collab-kit knows neither
 * areas nor keys; only the Copilot checks the limits. The areas the backend reads (sharing, archive)
 * are also in api/src/modeling_api/services/collab_kit/collab_settings.py (LIMITS), with the same limits.
 */
export const COLLAB_LIMITS = {
  sharing: {
    // How long a visitor may be away before the sweep takes them out of the group.
    visitorGraceSeconds: { default: 120, min: 30, max: 3600 },
    // How long the host may be away before the sweep locks the room.
    hostGraceSeconds: { default: 120, min: 30, max: 3600 },
    // How long the host may be away before the sweep takes all visitors out.
    hostEndSeconds: { default: 300, min: 30, max: 7200 },
    // How long the host is away before a visitor is told; a reload of the host takes less.
    hostAwayMs: { default: 30_000, min: 5_000, max: 600_000 },
    // How often the sweep looks; shorter keeps the waits more exact and asks collab-kit more often.
    sweepSeconds: { default: 30, min: 10, max: 120 },
    // How often a visitor reads what the room added; once it is closed there is nothing left to read.
    followMs: { default: 30_000, min: 10_000, max: 300_000 }
  },
  presence: {
    // After this long without activity a client gives up its selection and with it its locks.
    idleMs: { default: 90_000, min: 15_000, max: 3_600_000 },
    // A moving pointer goes out at most this often, the last position always; shorter is smoother and more traffic.
    cursorSendMs: { default: 50, min: 20, max: 500 }
  },
  shareDefaults: {
    // What the share dialog has chosen; the host changes it there for their share.
    anonymous: { default: false },
    edit: { default: true },
    history: { default: 'none', options: ['none', 'versions', 'steps'] }
  },
  colors: {
    // Only the host is red, so the presenter stands out at a glance.
    hostColor: { default: '#cf5c58', color: true },
    // Sixteen colors, measured to tell apart well (CIEDE2000, also with red-green weakness), none red like the host.
    // The first ones lie furthest apart, so the first people in the room get the clearest colors.
    palette: { default: ['#c29ed7', '#214b25', '#ee9813', '#0e26dc', '#12c19f', '#652f55', '#715c00', '#6e83b7', '#1d8a85', '#8f4ef1', '#6f5d8d', '#f657f2', '#194b78', '#8605a8', '#41a8ba', '#2da0fb'], minItems: 8, maxItems: 24 }
  },
  archive: {
    // The archive of collab-kit in the Copilot; off, the "Archive" tab is missing, collab-kit still shows its buttons to archive.
    enabled: { default: false },
    // Whether an ended share archives its workpieces (model and task) instead of leaving them without a room; only with enabled.
    archiveOnShareClose: { default: false },
    // After this many days without activity the backend archives workpieces of ended shares that lie in no room; 0 means never, only with enabled.
    archiveUnusedAfterDays: { default: 0, min: 0, max: 365 }
  }
} as const satisfies Record<string, Record<string, CollabLimit>>

export type CollabArea = keyof typeof COLLAB_LIMITS
export const COLLAB_AREAS = Object.keys(COLLAB_LIMITS) as CollabArea[]
type ValueOf<L> = L extends { readonly options: readonly (infer O)[] } ? O : L extends { readonly minItems: number } ? string[] : L extends { readonly color: true } ? string : L extends { readonly default: boolean } ? boolean : number
type AreaValues<A extends CollabArea> = { -readonly [K in keyof (typeof COLLAB_LIMITS)[A]]: ValueOf<(typeof COLLAB_LIMITS)[A][K]> }

/** A list as a copy of its own, so nobody changes the defaults themselves. */
const copyOf = (value: unknown) => (Array.isArray(value) ? [...value] : value)
const defaultsOf = <A extends CollabArea>(area: A) => Object.fromEntries(Object.entries(COLLAB_LIMITS[area]).map(([key, limit]) => [key, copyOf(limit.default)])) as AreaValues<A>

/** The values in effect; whoever reads them on every use gets a change at once. */
export const collabSettings = reactive({ sharing: defaultsOf('sharing'), presence: defaultsOf('presence'), shareDefaults: defaultsOf('shareDefaults'), colors: defaultsOf('colors'), archive: defaultsOf('archive') })

/** Whether a name from settingsChanged is an area of the Copilot. */
export const isCollabArea = (key: string): key is CollabArea => COLLAB_AREAS.includes(key as CollabArea)

/** Whether a value fits: an integer within the limits, a boolean, one of the fixed values, a color or enough distinct colors. */
export const fitsLimit = (limit: CollabLimit, value: unknown) => {
  if ('options' in limit) return limit.options.includes(value as string)
  if ('color' in limit) return typeof value === 'string' && HEX.test(value)
  if ('minItems' in limit) return Array.isArray(value) && value.length >= limit.minItems && value.length <= limit.maxItems && value.every((color) => typeof color === 'string' && HEX.test(color)) && new Set(value.map((color: string) => color.toLowerCase())).size === value.length
  if ('min' in limit) return typeof value === 'number' && Number.isInteger(value) && value >= limit.min && value <= limit.max
  return typeof value === 'boolean'
}

/** Takes the values of an area; one that is missing or does not fit falls back to its default. */
export const applyCollabSettings = (area: CollabArea, values: Record<string, unknown>) => {
  const target: Record<string, unknown> = collabSettings[area]
  for (const [key, limit] of Object.entries<CollabLimit>(COLLAB_LIMITS[area])) target[key] = copyOf(fitsLimit(limit, values[key]) ? values[key] : limit.default)
}

/** Reads an area from collab-kit; one never set comes as {} and so counts as the defaults. */
export const loadCollabSettings = async (ck: CollabKitApi, area: CollabArea) => applyCollabSettings(area, await ck.settings.get(area))
