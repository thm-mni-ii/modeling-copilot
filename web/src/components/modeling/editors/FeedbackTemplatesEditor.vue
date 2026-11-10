<template>
  <v-container fluid class="pa-4">
    <div class="mb-5">
      <h2 class="text-h6">Validation feedback templates</h2>
      <p class="text-body-2 text-medium-emphasis mb-0">Choose a template to edit the messages used by syntax validation.</p>
    </div>

    <v-alert v-if="!config" type="info" variant="tonal">Load a language version to edit its validation templates.</v-alert>
    <div v-else class="templates-layout">
      <v-sheet border rounded="lg" class="template-navigation">
        <nav aria-label="Feedback templates">
          <v-list density="compact" class="py-2" color="primary-dark">
            <template v-for="group in groups" :key="group.title">
              <v-list-subheader class="template-group-title">
                <span class="d-flex align-center ga-2 w-100">
                  <v-icon :icon="group.icon" color="primary" size="18" aria-hidden="true" />
                  <span class="flex-grow-1">{{ group.title }}</span>
                  <v-btn icon="mdi-link-variant" size="x-small" variant="text" :title="`Open ${group.title} in Syntax`" :aria-label="`Open ${group.title} in Syntax`" @click="navigation.openSyntax({ kind: group.key })" />
                </span>
              </v-list-subheader>
              <v-list-item v-for="item in group.items" :key="item.key" :active="selectedKey === item.key" :aria-current="selectedKey === item.key ? 'true' : undefined" rounded="lg" class="mx-2 mb-1" @click="selectTemplate(item.key)">
                <v-list-item-title class="text-body-2 template-list-title">{{ item.title }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption">{{ item.value?.trim() && item.value !== item.fallback ? 'Configured' : 'Uses default' }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-list>
        </nav>
      </v-sheet>

      <section :id="feedbackTargetId('template', { kind: selectedGroup.key })" ref="detailSection" tabindex="-1" :aria-label="`${selectedGroup.title} template editor`" class="template-detail">
        <v-alert v-if="navigationMessage" type="info" variant="tonal" closable class="mb-4" @click:close="navigationMessage = ''">{{ navigationMessage }}</v-alert>
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-4 pb-3 border-b">
          <span class="d-flex align-center ga-2 text-overline">
            <v-icon :icon="selectedGroup.icon" color="primary" size="20" aria-hidden="true" />
            <span>{{ selectedGroup.title }}</span>
          </span>
          <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" @click="navigation.openSyntax({ kind: selectedGroup.key })">{{ selectedGroup.settingsLabel }}</v-btn>
        </div>

        <FeedbackTemplateField v-for="field in connectionFields" v-show="selectedKey === field.key" :key="field.key" kind="connection" :connection-code="field.code" :title="field.title" :description="field.description" :value="config[field.key]" :fallback="DEFAULT_CONNECTION_MESSAGE_TEMPLATES[field.key]" :placeholders="field.placeholders" :disabled="disabled" @update:value="config[field.key] = $event" />
        <FeedbackTemplateField v-for="field in endpointFields" v-show="selectedKey === field.key" :key="field.key" :title="field.title" :description="field.description" :value="config.endpointMessages?.[field.key]" :fallback="DEFAULT_ENDPOINT_MESSAGES[field.key]" :placeholders="field.placeholders" :disabled="disabled" @update:value="setEndpointMessage(field.key, $event)" />
        <FeedbackTemplateField v-show="selectedKey === 'quantity'" kind="quantity" title="Quantity message" description="Used for all connection, route and connection limit quantities." :value="config.messageTemplate" :fallback="DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE" :placeholders="quantityPlaceholders" :disabled="disabled" @update:value="config.messageTemplate = $event" />
        <FeedbackTemplateField v-if="containmentRule" v-show="selectedKey === 'containment'" title="Container message" description="Used when an element is not allowed in its container." :value="containmentRule.config.messageTemplate" :fallback="DEFAULT_CONTAINMENT_MESSAGE" :placeholders="['element', 'container']" :disabled="disabled" @update:value="containmentRule.config.messageTemplate = $event" />
        <FeedbackTemplateField v-if="cycleRule" v-show="selectedKey === 'cycle'" kind="cycle" title="Cycle message" :description="cycleDescription" :value="cycleRule.config.messageTemplate" :fallback="DEFAULT_CYCLE_MESSAGE_TEMPLATES[cycleRule.config.mode ?? 'forbid']" :placeholders="cyclePlaceholders" :disabled="disabled" @update:value="cycleRule.config.messageTemplate = $event" />

        <v-expansion-panels variant="accordion" class="mt-6">
          <v-expansion-panel title="Placeholder reference" elevation="0" rounded="lg" class="border">
            <v-expansion-panel-text>
              <dl class="placeholder-reference text-body-2">
                <dt>Elements &amp; connections</dt>
                <dd><code>{source}</code> and <code>{target}</code> are element types; <code>{connection}</code> identifies the connection type. <code>{sourceLabel}</code> and <code>{targetLabel}</code> are their displayed names. <code>{element}</code> is the affected element (its type in cycle templates); <code>{elementLabel}</code> is its displayed name in cycle templates. <code>{container}</code> identifies its container.</dd>
                <dt>Connection points</dt>
                <dd><code>{sourcePoint}</code> and <code>{targetPoint}</code> identify the chosen points; <code>{allowedPoints}</code> and <code>{allowedConnections}</code> describe the allowed choices. <code>{direction}</code> is the connection direction.</dd>
                <dt>Quantities</dt>
                <dd><code>{min}</code> and <code>{max}</code> are the quantity bounds; <code>{count}</code> is the current or proposed quantity. <code>{scope}</code> identifies the quantity scope, <code>{route}</code> the route, <code>{point}</code> the selected points or group, and <code>{other}</code> the other element.</dd>
                <dt>Calculated feedback</dt>
                <dd><code>{quantityContext}</code> describes the counted connections and their location; <code>{quantityResult}</code> gives the count and violated bound.</dd>
                <dt>Special values</dt>
                <dd>An unrestricted type, maximum or point selection is shown as <code>*</code>; a non-applicable route or other element is shown as <code>-</code>. For limits that count undirected connections or both directions, <code>{source}</code> and <code>{target}</code> list the possible types at either end.</dd>
              </dl>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </section>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref, watch } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { AcyclicRule, ContainmentRule, EndpointMessageKey, MultiplicityRule } from '@/model/Syntax'
import { DEFAULT_CYCLE_MESSAGE_TEMPLATES } from '@/utils/acyclic'
import { DEFAULT_CONNECTION_MESSAGE_TEMPLATES, DEFAULT_CONTAINMENT_MESSAGE, DEFAULT_ENDPOINT_MESSAGES, DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE } from '@/utils/syntaxMessages'
import FeedbackTemplateField from './FeedbackTemplateField.vue'
import { feedbackTargetId, feedbackTemplateNavigationKey, type FeedbackTemplateTarget } from './feedbackTemplateNavigation'

const store = useDiagramLanguages()
const navigation = inject(feedbackTemplateNavigationKey)!
const config = computed(() => store.definition?.syntax.find((rule): rule is MultiplicityRule => rule.ruleType === 'multiplicity')?.config)
const cycleRule = computed(() => store.definition?.syntax.find((rule): rule is AcyclicRule => rule.ruleType === 'acyclic'))
const containmentRule = computed(() => store.definition?.syntax.find((rule): rule is ContainmentRule => rule.ruleType === 'containment'))
const disabled = computed(() => !store.currentVersion)
const connectionPlaceholders = ['source', 'target', 'sourceLabel', 'targetLabel', 'connection']
const quantityPlaceholders = ['quantityContext', 'quantityResult', 'source', 'target', 'connection', 'min', 'max', 'count', 'element', 'other', 'direction', 'point', 'scope', 'route']
const connectionFields = [
  { key: 'forbiddenMessageTemplate', code: 'connection.forbidden', title: 'Forbidden combination', description: 'Used when the selected elements may not be connected.', placeholders: connectionPlaceholders },
  { key: 'connectionTypeMessageTemplate', code: 'connection.type', title: 'Connection type', description: 'Used when the connection type is not allowed for the selected elements.', placeholders: [...connectionPlaceholders, 'allowedConnections'] },
  { key: 'endpointMessageTemplate', code: 'connection.endpoint', title: 'Connection points', description: 'Used when the selected connection points are not allowed together.', placeholders: [...connectionPlaceholders, 'sourcePoint', 'targetPoint', 'allowedPoints'] }
] as const
const endpointFields: { key: EndpointMessageKey; title: string; description: string; placeholders: string[] }[] = [
  { key: 'loop', title: 'Self-connection', description: 'Used when a connection cannot connect an element to itself.', placeholders: ['element', 'connection'] },
  { key: 'looseEnd', title: 'Open connection end', description: 'Used when both ends must be attached.', placeholders: ['element', 'connection'] },
  { key: 'missingPoint', title: 'Missing connection point', description: 'Used when a saved connection point no longer exists.', placeholders: ['element'] },
  { key: 'notConnectable', title: 'Element cannot be connected', description: 'Used when an element does not accept connections.', placeholders: ['element'] },
  { key: 'pointRequired', title: 'Connection point required', description: 'Used when an element requires an explicit connection point.', placeholders: ['element'] },
  { key: 'pointDirection', title: 'Connection point direction', description: 'Used when the chosen point does not allow this direction.', placeholders: ['element', 'point', 'direction'] }
]
const setEndpointMessage = (key: EndpointMessageKey, value: string) => {
  if (!config.value) return
  config.value.endpointMessages = { ...config.value.endpointMessages, [key]: value }
}
const cyclePlaceholders = computed(() => cycleRule.value?.config.mode === 'every' ? ['element', 'elementLabel'] : cycleRule.value?.config.mode === 'any' ? [] : ['source', 'target', 'sourceLabel', 'targetLabel'])
const cycleDescription = computed(() => cycleRule.value?.config.mode === 'every' ? 'Used when an element must be part of a cycle.' : cycleRule.value?.config.mode === 'any' ? 'Used when the diagram must contain a cycle.' : 'Used when a connection would create a forbidden cycle.')

const selection = ref<string>(connectionFields[0].key)
const navigationMessage = ref('')
const detailSection = ref<HTMLElement>()
const groups = computed(() => {
  const result: { key: FeedbackTemplateTarget['kind']; icon: string; title: string; settingsLabel: string; items: { key: string; title: string; value?: string; fallback: string }[] }[] = [
    { key: 'connection', icon: 'mdi-grid', title: 'Connection rules', settingsLabel: 'Connection settings', items: connectionFields.map((field) => ({ key: field.key, title: field.title, value: config.value?.[field.key], fallback: DEFAULT_CONNECTION_MESSAGE_TEMPLATES[field.key] })) },
    { key: 'connection', icon: 'mdi-target', title: 'Connection and point restrictions', settingsLabel: 'Connection settings', items: endpointFields.map((field) => ({ key: field.key, title: field.title, value: config.value?.endpointMessages?.[field.key], fallback: DEFAULT_ENDPOINT_MESSAGES[field.key] })) },
    { key: 'quantity', icon: 'mdi-counter', title: 'Connection quantities', settingsLabel: 'Quantity settings', items: [{ key: 'quantity', title: 'Quantity message', value: config.value?.messageTemplate, fallback: DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE }] }
  ]
  if (containmentRule.value) result.push({ key: 'containment', icon: 'mdi-tray-arrow-down', title: 'Container contents', settingsLabel: 'Container settings', items: [{ key: 'containment', title: 'Container message', value: containmentRule.value.config.messageTemplate, fallback: DEFAULT_CONTAINMENT_MESSAGE }] })
  if (cycleRule.value) result.push({ key: 'cycle', icon: 'mdi-sync-off', title: 'Cycles', settingsLabel: 'Cycle settings', items: [{ key: 'cycle', title: 'Cycle message', value: cycleRule.value.config.messageTemplate, fallback: DEFAULT_CYCLE_MESSAGE_TEMPLATES[cycleRule.value.config.mode ?? 'forbid'] }] })
  return result
})
const selectedGroup = computed(() => groups.value.find((group) => group.items.some((item) => item.key === selection.value)) ?? groups.value[0])
const selectedKey = computed(() => selectedGroup.value.items.some((item) => item.key === selection.value) ? selection.value : selectedGroup.value.items[0].key)
const selectTemplate = async (key: string) => {
  navigationMessage.value = ''
  selection.value = key
  await nextTick()
  detailSection.value?.focus({ preventScroll: true })
  if (window.matchMedia('(max-width: 800px)').matches) detailSection.value?.scrollIntoView({ block: 'start' })
}
watch(navigation.templateTarget, (target) => {
  navigationMessage.value = ''
  if (!target || selectedGroup.value.key === target.kind) return
  const group = groups.value.find((group) => group.key === target.kind)
  if (group) selection.value = group.items[0].key
  else navigationMessage.value = 'This feedback template is no longer available. Check whether its rule is configured in Syntax.'
})
</script>

<style scoped>
.templates-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}

.template-navigation {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}

.template-detail {
  min-width: 0;
  scroll-margin-top: 16px;
}

.template-detail:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary-dark));
  outline-offset: 4px;
}

.template-group-title {
  line-height: 1.4;
  padding-top: 12px;
  padding-bottom: 8px;
}

.template-list-title {
  white-space: normal;
}

.placeholder-reference dt {
  font-weight: 600;
  margin-top: 12px;
}

.placeholder-reference dd {
  margin: 4px 0 0;
  color: rgb(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
  overflow-wrap: anywhere;
}

@media (max-width: 800px) {
  .templates-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }

  .template-navigation {
    position: static;
    max-height: 260px;
  }
}
</style>
