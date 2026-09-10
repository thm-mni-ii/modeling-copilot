<template>
  <div v-if="scopedConnections.length > 0" class="connection-toolbar" :class="{ 'connection-toolbar--compact': props.compact }">
    <v-menu v-model="paletteOpen" :close-on-content-click="false" location="bottom start" max-width="min(920px, calc(100vw - 32px))" min-width="400">
      <template #activator="{ props: activatorProps }">
        <button v-bind="activatorProps" type="button" class="active-connection" :aria-expanded="paletteOpen" aria-label="Choose connection">
          <ConnectionPreviewItem v-if="selectedConnection" :connection="selectedConnection.connection" :width="props.compact ? 62 : 104" :height="props.compact ? 28 : 38" />
          <span v-if="!props.compact" class="active-connection__label">{{ selectedConnection?.connection.label }}</span>
          <v-icon size="18" class="active-connection__arrow">mdi-chevron-down</v-icon>
        </button>
      </template>

      <v-card class="connection-palette" elevation="8">
        <v-text-field v-model="searchQuery" density="compact" variant="outlined" hide-details clearable autofocus prepend-inner-icon="mdi-magnify" label="Search connections" class="connection-palette__search" />

        <div class="connection-palette__body">
          <v-tabs v-model="paletteTab" direction="vertical" density="compact" class="connection-palette__tabs">
            <v-tab value="recent" prepend-icon="mdi-history">Recent</v-tab>
            <v-tab value="pinned" prepend-icon="mdi-pin">Pinned</v-tab>
            <v-tab value="all" prepend-icon="mdi-view-column">All</v-tab>
            <v-divider class="connection-palette__tab-divider" />
            <v-tab v-for="group in groups" :key="group.id" :value="`language:${group.id}`" :title="group.label" class="connection-palette__language-tab">
              {{ group.label }}
            </v-tab>
          </v-tabs>

          <v-window v-model="paletteTab" class="connection-palette__content">
            <v-window-item value="recent">
              <div v-if="recentConnections.length" class="connection-grid connection-grid--palette">
                <ConnectionOption v-for="option in recentConnections" :key="option.key" :item="option" :selected="option.key === selectedKey" :highlighted="matchesSearch(option)" :pinned="false" @select="selectConnection(option)" @toggle-pin="togglePinned(option)" />
              </div>
              <p v-else class="connection-palette__empty">Selected connections will appear here.</p>
            </v-window-item>

            <v-window-item value="pinned">
              <div v-if="favoriteConnections.length" class="connection-grid connection-grid--palette">
                <ConnectionOption v-for="option in favoriteConnections" :key="option.key" :item="option" :selected="option.key === selectedKey" :highlighted="matchesSearch(option)" :pinned="true" @select="selectConnection(option)" @toggle-pin="togglePinned(option)" />
              </div>
              <p v-else class="connection-palette__empty">Pinned connections will appear here.</p>
            </v-window-item>

            <v-window-item value="all">
              <div class="connection-grid connection-grid--palette">
                <ConnectionOption v-for="option in scopedConnections" :key="option.key" :item="option" :selected="option.key === selectedKey" :highlighted="matchesSearch(option)" :pinned="isPinned(option)" @select="selectConnection(option)" @toggle-pin="togglePinned(option)" />
              </div>
            </v-window-item>

            <v-window-item v-for="group in groups" :key="group.id" :value="`language:${group.id}`">
              <div class="connection-grid connection-grid--palette">
                <ConnectionOption v-for="option in scopedConnectionsByGroup(group.id)" :key="option.key" :item="option" :selected="option.key === selectedKey" :highlighted="matchesSearch(option)" :pinned="isPinned(option)" @select="selectConnection(option)" @toggle-pin="togglePinned(option)" />
              </div>
            </v-window-item>
          </v-window>
        </div>
      </v-card>
    </v-menu>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, ref, watch, type PropType } from 'vue'
import type { JsonObject } from '@/services/api/types/common'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'

interface Props {
  connections: DiagramConnection[]
  connectionGroups?: DiagramConnectionGroup[]
  preferences?: JsonObject
  compact?: boolean
}

interface ScopedConnection {
  key: string
  languageLabel: string
  connection: DiagramConnection
}

interface ConnectionToolbarPreferences {
  favorites: string[]
  recent: string[]
}

const ConnectionOption = defineComponent({
  name: 'ConnectionOption',
  props: {
    item: { type: Object as PropType<ScopedConnection>, required: true },
    selected: { type: Boolean, required: true },
    highlighted: { type: Boolean, required: true },
    pinned: { type: Boolean, required: true }
  },
  emits: ['select', 'toggle-pin'],
  setup(optionProps, { emit }) {
    return () =>
      h(
        'div',
        {
          role: 'button',
          tabindex: 0,
          class: ['connection-option', { 'connection-option--selected': optionProps.selected, 'connection-option--highlighted': optionProps.highlighted }],
          onClick: () => emit('select'),
          onKeydown: (event: KeyboardEvent) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              emit('select')
            }
          }
        },
        [
          h(ConnectionPreviewItem, { connection: optionProps.item.connection, width: 86, height: 30 }),
          h('span', { class: 'connection-option__label' }, optionProps.item.connection.label),
          h('button', { type: 'button', class: ['connection-option__pin', { 'connection-option__pin--active': optionProps.pinned }], title: optionProps.pinned ? 'Unpin connection' : 'Pin connection', 'aria-label': optionProps.pinned ? 'Unpin connection' : 'Pin connection', onClick: (event: MouseEvent) => { event.stopPropagation(); emit('toggle-pin') } }, [h('i', { class: 'v-icon notranslate mdi mdi-pin', 'aria-hidden': 'true' })])
        ]
      )
  }
})

const props = withDefaults(defineProps<Props>(), {
  connectionGroups: () => [],
  preferences: () => ({}),
  compact: false
})

const emit = defineEmits<{
  select: [connection: DiagramConnection]
  'update:preferences': [preferences: JsonObject]
}>()

const selectedKey = ref<string>()
const paletteOpen = ref(false)
const paletteTab = ref<'recent' | 'all'>('all')
const searchQuery = ref('')

const groups = computed<DiagramConnectionGroup[]>(() => {
  if (props.connectionGroups.length > 0) return props.connectionGroups.filter((group) => group.connections.length > 0)
  return props.connections.length > 0 ? [{ id: 'default', label: 'Connections', connections: props.connections }] : []
})

const scopedConnections = computed<ScopedConnection[]>(() =>
  groups.value.flatMap((group) =>
    group.connections.map((connection, index) => ({
      key: `${group.id}:${connection.type}:${index}`,
      languageLabel: group.label,
      connection
    }))
  )
)

const toolbarPreferences = computed<ConnectionToolbarPreferences>(() => {
  const value = props.preferences?.connectionToolbar
  const asKeys = (entry: unknown) => (Array.isArray(entry) ? entry.filter((key): key is string => typeof key === 'string') : [])
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { favorites: [], recent: [] }
  return { favorites: asKeys((value as Record<string, unknown>).favorites), recent: asKeys((value as Record<string, unknown>).recent) }
})

const selectedConnection = computed(() => scopedConnections.value.find((item) => item.key === selectedKey.value))
const scopedConnectionsByGroup = (groupId: string) => scopedConnections.value.filter((item) => item.key.startsWith(`${groupId}:`))
const connectionsForKeys = (keys: string[]) => keys.map((key) => scopedConnections.value.find((item) => item.key === key)).filter((item): item is ScopedConnection => Boolean(item))
const favoriteConnections = computed(() => connectionsForKeys(toolbarPreferences.value.favorites))
const isPinned = (item: ScopedConnection) => toolbarPreferences.value.favorites.includes(item.key)
const recentConnections = computed(() => connectionsForKeys(toolbarPreferences.value.recent).filter((item) => !isPinned(item)))

const normalizedSearch = computed(() => searchQuery.value.trim().toLocaleLowerCase())
const matchesSearch = (item: ScopedConnection) => {
  const query = normalizedSearch.value
  if (!query) return false
  return [item.connection.label, item.connection.type, item.connection.connectionType, item.languageLabel].filter((value): value is string => Boolean(value)).some((value) => value.toLocaleLowerCase().includes(query))
}

const updateToolbarPreferences = (patch: Partial<ConnectionToolbarPreferences>) => {
  const current = toolbarPreferences.value
  emit('update:preferences', {
    ...props.preferences,
    connectionToolbar: {
      favorites: patch.favorites ?? current.favorites,
      recent: patch.recent ?? current.recent
    }
  })
}

const selectConnection = (item: ScopedConnection) => {
  selectedKey.value = item.key
  emit('select', item.connection)
  updateToolbarPreferences({ recent: [item.key, ...toolbarPreferences.value.recent.filter((key) => key !== item.key)].slice(0, 12) })
  paletteOpen.value = false
}

const togglePinned = (item: ScopedConnection) => {
  const favorites = isPinned(item) ? toolbarPreferences.value.favorites.filter((key) => key !== item.key) : [...toolbarPreferences.value.favorites, item.key]
  updateToolbarPreferences({ favorites })
}

const preferredSelection = () => toolbarPreferences.value.recent.find((key) => scopedConnections.value.some((item) => item.key === key)) ?? scopedConnections.value[0]?.key

watch(normalizedSearch, (query) => {
  if (query) paletteTab.value = 'all'
})

watch(
  [scopedConnections, () => toolbarPreferences.value.recent],
  () => {
    if (!scopedConnections.value.some((item) => item.key === selectedKey.value)) selectedKey.value = preferredSelection()
    if (selectedConnection.value) emit('select', selectedConnection.value.connection)
  },
  { immediate: true }
)

defineExpose({
  closePalette: () => {
    paletteOpen.value = false
  }
})
</script>

<style scoped>
.connection-toolbar { display: flex; align-items: center; min-width: 0; }
.active-connection { display: flex; align-items: center; gap: 6px; min-height: 42px; max-width: min(320px, 100%); padding: 2px 7px 2px 4px; border: 1px solid rgba(var(--v-theme-outline), 0.28); border-radius: 7px; background: rgb(var(--v-theme-surface)); color: rgb(var(--v-theme-on-surface)); cursor: pointer; }
.active-connection:hover, .active-connection[aria-expanded='true'] { border-color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.06); }
.active-connection__label { max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; font-weight: 600; }
.active-connection__arrow { color: rgba(var(--v-theme-on-surface), 0.65); }
.connection-toolbar--compact .active-connection { min-height: 30px; padding: 1px 4px; border-radius: 4px; }
.connection-toolbar--compact .active-connection__arrow { margin-left: -2px; }
.connection-palette { width: min(920px, calc(100vw - 32px)); overflow: hidden; }
.connection-palette__search { padding: 12px 12px 8px; }
.connection-palette__body { display: flex; min-height: 250px; max-height: min(560px, calc(100vh - 160px)); border-top: 1px solid rgba(var(--v-theme-outline), 0.13); }
.connection-palette__tabs { flex: 0 0 150px; border-right: 1px solid rgba(var(--v-theme-outline), 0.13); }
.connection-palette__tabs :deep(.v-tab) { justify-content: flex-start; min-width: 0; padding-inline: 12px; text-transform: none; }
.connection-palette__language-tab { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; }
.connection-palette__language-tab :deep(.v-btn__content) { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.connection-palette__tab-divider { margin: 4px 8px; }
.connection-palette__content { flex: 1; min-width: 0; overflow: auto; }
.connection-grid { display: grid; gap: 6px; }
.connection-grid--palette { grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); padding: 12px; }
.connection-palette__empty { margin: 0; padding: 16px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 12px; }
:deep(.connection-option) { position: relative; display: grid; grid-template-columns: 86px minmax(0, 1fr); gap: 8px; width: 100%; min-height: 42px; padding: 5px 28px 5px 5px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: rgb(var(--v-theme-on-surface)); text-align: left; cursor: pointer; }
:deep(.connection-option:hover) { background: rgba(var(--v-theme-primary), 0.06); }
:deep(.connection-option--selected) { border-color: rgb(var(--v-theme-primary)); background: rgba(var(--v-theme-primary), 0.1); }
:deep(.connection-option--highlighted) { background: rgba(var(--v-theme-warning), 0.16); box-shadow: inset 3px 0 rgb(var(--v-theme-warning)); }
:deep(.connection-option__label) { align-self: center; overflow-wrap: anywhere; font-size: 12px; font-weight: 600; line-height: 1.25; }
:deep(.connection-option__pin) { position: absolute; top: 3px; right: 3px; width: 24px; height: 24px; border: 0; border-radius: 50%; background: transparent; color: rgba(var(--v-theme-on-surface), 0.38); cursor: pointer; }
:deep(.connection-option__pin:hover), :deep(.connection-option__pin--active) { color: #1976d2; background: rgba(25, 118, 210, 0.12); }
@media (max-width: 600px) { .connection-palette__tabs { flex-basis: 48px; } .connection-palette__tabs :deep(.v-tab__prepend) { margin: 0; } .connection-palette__tabs :deep(.v-tab__text), .connection-palette__language-tab { display: none; } .active-connection__label { max-width: 100px; } .connection-grid--palette { grid-template-columns: 1fr; } }
</style>
