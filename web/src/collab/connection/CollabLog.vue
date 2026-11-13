<template>
  <div class="collab-log" :class="{ 'collab-log--open': open }">
    <div class="collab-log__header">
      <span>Event Log</span>
      <v-btn :icon="open ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" :aria-label="open ? 'Collapse event log' : 'Expand event log'" @click="open = !open" />
    </div>
    <div v-show="open" class="collab-log__body">
      <div v-if="entries.length === 0" class="collab-log__empty">No events yet</div>
      <div v-for="block in blocks" :key="keyOf(block.entries[0])" class="collab-log__entry">
        <div v-if="block.by" class="collab-log__block">
          <div class="collab-log__person">
            <span class="collab-log__dot" :style="{ background: block.color ?? SOMEONE_COLOR }">{{ block.by.charAt(0).toUpperCase() }}</span>
            <span class="collab-log__name">{{ block.by }}</span>
            <span class="collab-log__time" :title="new Date(block.at).toLocaleTimeString()">{{ ago(block.at) }}</span>
          </div>
          <div
            v-for="entry in block.entries"
            :key="keyOf(entry)"
            class="collab-log__line"
            :class="{ 'collab-log__line--show': showable(entry) }"
            :role="showable(entry) ? 'button' : undefined"
            :tabindex="showable(entry) ? 0 : undefined"
            @mouseenter="showable(entry) && showEdits(entry, true)"
            @mouseleave="hideEdits()"
            @click="showable(entry) && showEdits(entry)"
            @keydown.enter="showable(entry) && showEdits(entry)"
          >
            <v-icon :icon="ICONS[entry.kind].icon" :color="ICONS[entry.kind].color" size="16" class="collab-log__icon" />
            <span v-if="entry.edits" class="collab-log__text">
              <span class="collab-log__verb">{{ entry.kind }}</span>
              <template v-if="countOf(entry) > 1">
                <b>{{ countOf(entry) }} elements</b>
              </template>
              <template v-else>
                <template v-if="entry.kind === 'renamed'">
                  <s class="collab-log__old">{{ elementName({ ...lastOf(entry), name: entry.edits[0].from }) }}</s> →
                </template>
                <s v-if="entry.kind === 'deleted'" class="collab-log__old">{{ elementName(lastOf(entry)) }}</s>
                <b v-else>{{ elementName(lastOf(entry)) }}</b>
              </template>
            </span>
            <span v-else class="collab-log__text collab-log__verb">{{ entry.text }}</span>
            <span v-if="showable(entry)" class="collab-log__go"><v-icon icon="mdi-eye-outline" size="14" />Show</span>
          </div>
        </div>
        <template v-else>
          <v-icon :icon="ICONS[block.entries[0].kind].icon" :color="ICONS[block.entries[0].kind].color" size="16" class="collab-log__icon" />
          <span class="collab-log__text">{{ block.entries[0].text }}</span>
          <span class="collab-log__time" :title="new Date(block.at).toLocaleTimeString()">{{ ago(block.at) }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { ref } from 'vue'

// Kept beside the component, so it stays closed while another sidebar tab is shown.
const open = ref(false)
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount } from 'vue'
import { elementName, hideEdits, showEdits, SOMEONE_COLOR, type LogEntry, type LogKind } from './useCollabConnection'

const props = defineProps<{ entries: LogEntry[] }>()

/** Aufeinanderfolgende Einträge derselben Person, unter ihrem Namen; Änderungen ohne Person unter Someone. */
interface Block {
  by?: string
  color?: string
  at: number
  entries: LogEntry[]
}
const blocks = computed(() =>
  props.entries.reduce<Block[]>((list, entry) => {
    const by = entry.by ?? (entry.edits ? 'Someone' : undefined)
    const last = list[list.length - 1]
    if (by && last?.by === by) last.entries.push(entry)
    else list.push({ by, color: entry.color, at: entry.at, entries: [entry] })
    return list
  }, [])
)

const keyOf = (entry: LogEntry) => `${entry.at}-${entry.kind}-${entry.text}`
// Gelöschtes ist nicht mehr im Modell, also nichts zu zeigen.
const showable = (entry: LogEntry) => Boolean(entry.edits) && entry.kind !== 'deleted'
const countOf = (entry: LogEntry) => new Set(entry.edits?.map(({ id }) => id)).size
const lastOf = (entry: LogEntry) => entry.edits![entry.edits!.length - 1]
// Ein Eintrag, der beim Wegräumen noch gehovert ist, nimmt seine Rahmen mit.
onBeforeUnmount(hideEdits)

/** Icon und Farbe je Art. */
const ICONS: Record<LogKind, { icon: string; color?: string }> = {
  failed: { icon: 'mdi-alert-circle-outline', color: 'error' },
  joined: { icon: 'mdi-account-plus-outline' },
  left: { icon: 'mdi-account-minus-outline' },
  added: { icon: 'mdi-plus-box-outline' },
  deleted: { icon: 'mdi-delete-outline' },
  renamed: { icon: 'mdi-form-textbox' },
  moved: { icon: 'mdi-cursor-move' },
  changed: { icon: 'mdi-pencil-outline' },
  saved: { icon: 'mdi-content-save-outline' },
  release: { icon: 'mdi-tag-outline' },
  conflict: { icon: 'mdi-alert-outline', color: 'warning' },
  connected: { icon: 'mdi-lan-connect', color: 'success' },
  offline: { icon: 'mdi-wifi-off', color: 'warning' },
  closed: { icon: 'mdi-lan-disconnect', color: 'error' },
  rights: { icon: 'mdi-shield-account-outline' },
  undo: { icon: 'mdi-undo', color: 'warning' }
}

// Die relative Zeit geht mit, solange das Log zu sehen ist.
const now = ref(Date.now())
const timer = setInterval(() => (now.value = Date.now()), 30_000)
onBeforeUnmount(() => clearInterval(timer))

const ago = (at: number) => {
  const minutes = Math.floor((now.value - at) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  return new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.collab-log {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  border: 1px solid rgba(var(--v-theme-outline), 0.2);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.01);
}

/* Open, it takes what the sync sidebar leaves, so it grows as the boxes above close. */
.collab-log--open {
  flex: 1;
  min-height: 180px;
}

.collab-log__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 6px 4px 10px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(var(--v-theme-on-surface), 0.62);
  text-transform: uppercase;
}

.collab-log__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.15);
}

.collab-log__empty {
  padding: 10px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.52);
}

.collab-log__entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-top: 1px solid rgba(var(--v-theme-outline), 0.08);
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.75);
}

.collab-log__icon {
  flex-shrink: 0;
  margin-top: 1px;
  color: rgba(var(--v-theme-on-surface), 0.6);
}

.collab-log__text {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}

.collab-log__block {
  flex: 1;
  min-width: 0;
}

.collab-log__person {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.collab-log__dot {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 600;
  color: #fff;
}

.collab-log__name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

/* Eine Zeile je Tat, eingerückt unter den Namen; zeigbare werden beim Hovern hell und nennen Show. */
.collab-log__line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0 -4px 0 20px;
  padding: 3px 4px;
  border-radius: 4px;
}

.collab-log__line--show {
  cursor: pointer;
}

.collab-log__line--show:hover,
.collab-log__line--show:focus-visible {
  background: rgba(var(--v-theme-on-surface), 0.06);
  outline: none;
}

.collab-log__verb {
  color: rgba(var(--v-theme-on-surface), 0.6);
}

/* Vue nimmt den Umbruch zwischen Verb und Name weg, also der Abstand hier. */
.collab-log__text > .collab-log__verb {
  margin-right: 0.3em;
}

.collab-log__text b {
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.collab-log__old {
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.collab-log__go {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.6);
  opacity: 0;
}

.collab-log__line--show:hover .collab-log__go,
.collab-log__line--show:focus-visible .collab-log__go {
  opacity: 1;
}

.collab-log__time {
  flex-shrink: 0;
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.45);
}
</style>
