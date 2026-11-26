<template>
  <ConnectionToolbar v-if="connections.length" v-show="selectionCount === 0" ref="connectionToolbar" :enabled="canEdit" :connections="connections" :connection-groups="connectionGroups" :preferences="connectionPreferences" @select="emit('select-connection', $event)" @update:preferences="emit('update:connection-preferences', $event)" />
  <v-menu v-if="selectionCount > 0 || !connections.length" v-model="open" location="bottom start" :close-on-content-click="false" max-height="480">
    <template #activator="{ props: activatorProps }">
      <v-btn-group size="small" density="compact" variant="outlined" class="selected-type" :class="{ 'selected-type--active': selection && canEdit }" :title="triggerLabel">
        <v-btn v-bind="activatorProps" width="64" min-width="64" :disabled="!selection || !canEdit" :aria-label="triggerLabel" :aria-expanded="open">
          <span class="selected-type__icon">
            <v-icon size="20">{{ cell?.isEdge() ? 'mdi-vector-line' : 'mdi-shape-outline' }}</v-icon>
            <v-icon size="13" class="selected-type__switch">mdi-swap-horizontal</v-icon>
          </span>
          <v-icon size="14">mdi-chevron-down</v-icon>
        </v-btn>
      </v-btn-group>
    </template>
    <v-list v-if="selection" class="type-options" aria-label="Available types">
      <div v-for="(option, index) in selection.options" :key="option.type">
        <v-list-item :class="{ 'type-options__item--blocked': option.reasons.length }" :active="option.type === current?.type" :aria-current="option.type === current?.type ? 'true' : undefined" :aria-disabled="Boolean(option.reasons.length)" @click="choose(option)">
          <template #prepend>
            <DiagramPreviewItem v-if="option.element" :element="option.element" :width="76" :height="48" class="type-options__preview" />
            <ConnectionPreviewItem v-else-if="option.connection" :connection="option.connection" :width="76" :height="48" class="type-options__preview" />
          </template>
          <v-list-item-title>{{ option.connection?.label || option.type }}</v-list-item-title>
          <p v-if="option.reasons.length" class="type-options__reason">{{ option.reasons[0] }}</p>
          <template v-else>
            <p v-for="(text, lossIndex) in option.losses" :key="lossIndex" class="type-options__reason">Label “{{ text }}” will be removed when changing type.</p>
          </template>
          <template #append><v-icon v-if="option.type === current?.type" size="20" aria-label="Current type">mdi-check</v-icon><v-icon v-else-if="option.reasons.length" size="18">mdi-lock-outline</v-icon></template>
        </v-list-item>
        <div v-if="option.reasons.length > 1" class="type-options__details">
          <v-btn size="x-small" variant="text" :aria-expanded="expandedTypes.includes(option.type)" :aria-controls="`${detailsId}-${index}`" @click="toggleReasons(option.type)">{{ expandedTypes.includes(option.type) ? 'Fewer reasons' : `More reasons (${option.reasons.length - 1})` }}</v-btn>
          <ul v-if="expandedTypes.includes(option.type)" :id="`${detailsId}-${index}`" class="type-options__reason pl-4"><li v-for="reason in option.reasons.slice(1)" :key="reason">{{ reason }}</li></ul>
        </div>
      </div>
    </v-list>
  </v-menu>
  <v-dialog v-model="confirmOpen" max-width="480">
    <v-card title="Change type?">
      <v-card-text>
        <p>The following label text cannot be transferred to {{ pending?.type }}.</p>
        <ul class="pl-5 mt-2"><li v-for="(text, index) in losses" :key="index">{{ text }}</li></ul>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="confirmOpen = false">Cancel</v-btn><v-btn color="primary" @click="switchType(true)">Change type</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
  <v-snackbar v-model="errorOpen" color="error" :timeout="8000">{{ errorMessage }}<template #actions><v-btn @click="errorOpen = false">Close</v-btn></template></v-snackbar>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { InternalEvent, type Cell } from '@maxgraph/core'
import { useGraphContext } from '@/composables/useGraphContext'
import { applyTypeSwitch, typeSwitchOptions, type SwitchLanguage, type TypeSwitchOption } from '@/utils/typeSwitch'
import type { DiagramConnection, DiagramConnectionGroup } from '@/model/Connection'
import type { JsonObject } from '@/services/api/types/common'
import ConnectionToolbar from './ConnectionToolbar.vue'
import DiagramPreviewItem from '@/components/modeling/canvas/DiagramPreviewItem.vue'
import ConnectionPreviewItem from '@/components/modeling/canvas/ConnectionPreviewItem.vue'

const props = withDefaults(defineProps<{
  languages: SwitchLanguage[]
  enabled: boolean
  connections?: DiagramConnection[]
  connectionGroups?: DiagramConnectionGroup[]
  connectionPreferences?: JsonObject
}>(), { connections: () => [], connectionGroups: () => [], connectionPreferences: undefined })
const emit = defineEmits<{
  'select-connection': [connection: DiagramConnection]
  'update:connection-preferences': [preferences: JsonObject]
}>()
const { graph } = useGraphContext()
const connectionToolbar = ref<InstanceType<typeof ConnectionToolbar> | null>(null)
const revision = ref(0)
const open = ref(false)
const confirmOpen = ref(false)
const pending = ref<TypeSwitchOption>()
let pendingCell: Cell | undefined
const losses = ref<string[]>([])
const errorMessage = ref('')
const errorOpen = ref(false)
const expandedTypes = ref<string[]>([])
const detailsId = `type-switch-reasons-${globalThis.crypto.randomUUID()}`

watch(graph, (current, _previous, onCleanup) => {
  if (!current) return
  const update = () => { revision.value += 1 }
  current.getSelectionModel().addListener(InternalEvent.CHANGE, update)
  current.getDataModel().addListener(InternalEvent.CHANGE, update)
  update()
  onCleanup(() => {
    current.getSelectionModel().removeListener(update)
    current.getDataModel().removeListener(update)
  })
}, { immediate: true })

const selectionCount = computed(() => {
  void revision.value
  return graph.value?.getSelectionCount() ?? 0
})
const cell = computed(() => {
  void revision.value
  return selectionCount.value === 1 ? graph.value?.getSelectionCell() : undefined
})
const selection = computed(() => {
  void revision.value
  return graph.value && cell.value ? typeSwitchOptions(graph.value, cell.value, props.languages) : undefined
})
const current = computed(() => selection.value?.options[0])
const canEdit = computed(() => {
  void revision.value
  return Boolean(props.enabled && graph.value?.isEnabled() && !graph.value.isCellsLocked())
})
const triggerLabel = computed(() => current.value ? `Change type (${current.value.connection?.label || current.value.type})` : 'Change type — select one object')
watch([cell, selectionCount, () => props.enabled], () => {
  open.value = false
  confirmOpen.value = false
  connectionToolbar.value?.closePalette()
})
watch(open, () => { expandedTypes.value = [] })

const toggleReasons = (type: string) => {
  expandedTypes.value = expandedTypes.value.includes(type) ? expandedTypes.value.filter((entry) => entry !== type) : [...expandedTypes.value, type]
}

const choose = (option: TypeSwitchOption) => {
  if (!props.enabled || !graph.value?.isEnabled() || graph.value.isCellsLocked() || option.reasons.length || option.type === current.value?.type) return
  pending.value = option
  pendingCell = cell.value
  switchType(false)
}
const switchType = (confirmed: boolean) => {
  const selected = selection.value
  if (!props.enabled || !graph.value?.isEnabled() || graph.value.isCellsLocked() || !cell.value || cell.value !== pendingCell || !selected || !pending.value) { confirmOpen.value = false; return }
  try {
    graph.value.stopEditing(false)
    const option = selected.options.find((entry) => entry.type === pending.value?.type)
    if (!option) throw new Error('The destination type is no longer available.')
    const currentLosses = option.losses
    const accepted = confirmed && JSON.stringify(currentLosses) === JSON.stringify(losses.value)
    const result = applyTypeSwitch(graph.value, cell.value, option, selected.language, props.languages, accepted)
    open.value = false
    losses.value = result
    confirmOpen.value = result.length > 0
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
    errorOpen.value = true
    confirmOpen.value = false
  }
}

defineExpose({
  closePalette: () => {
    open.value = false
    connectionToolbar.value?.closePalette()
  },
  selectConnectionByReference: (languageId: string, connectionType: string) => connectionToolbar.value?.selectConnectionByReference(languageId, connectionType) ?? false
})
</script>

<style scoped>
.selected-type { flex: 0 0 auto; }
.selected-type--active { background: rgba(var(--v-theme-primary), 0.1); border-color: rgb(var(--v-theme-dark-gray)); color: rgb(var(--v-theme-primary)); }
.selected-type :deep(.v-btn) { padding-inline: 4px; }
.selected-type__icon { position: relative; display: inline-flex; margin-right: 5px; }
.selected-type__switch { position: absolute; right: -6px; bottom: -4px; background: rgb(var(--v-theme-surface)); border-radius: 50%; }
.type-options { width: min(420px, calc(100vw - 24px)); }
.type-options__preview { margin-right: 12px; pointer-events: none; }
.type-options__item--blocked .type-options__preview { opacity: .55; }
.type-options__reason { margin-top: 4px; white-space: normal; overflow-wrap: anywhere; font-size: 12px; line-height: 1.4; }
.type-options__details { padding: 0 16px 12px 104px; }
.type-options__details .v-btn { margin-left: -8px; text-transform: none; }
</style>
