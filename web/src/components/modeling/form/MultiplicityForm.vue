<template>
  <div class="d-flex flex-column ga-6">
    <v-sheet border rounded="lg" class="connection-rules">
      <div class="rules-heading">
        <v-icon color="primary" size="26">mdi-link-variant</v-icon>
        <div>
          <h3 class="text-h6">Connection Rules</h3>
          <p class="text-body-2 text-medium-emphasis mb-0">Allowed combinations, connection points and quantity limits.</p>
        </div>
      </div>
      <section :id="feedbackTargetId('syntax', { kind: 'connection' })" tabindex="-1" class="rules-section">
        <div class="d-flex align-center justify-space-between flex-wrap ga-3 mb-3">
          <h4 class="d-flex align-center text-subtitle-1 font-weight-bold">
            <v-icon color="primary" class="mr-2">mdi-grid</v-icon>
            <span>Connection Matrix</span>
          </h4>
          <v-select :model-value="config.defaultState ?? 'allowed'" :items="defaultStates" label="Undefined cells" density="compact" variant="outlined" hide-details :disabled="!hasLanguageVersion" class="matrix-default" @update:model-value="setDefaultState" />
        </div>

        <div class="matrix-legend text-caption text-medium-emphasis mb-2">
          <span>Click to cycle:</span>
          <span><v-icon color="primary" size="16">mdi-check</v-icon> Allowed</span>
          <span aria-hidden="true">→</span>
          <span><v-icon color="error" size="16">mdi-close</v-icon> Forbidden</span>
          <span aria-hidden="true">→</span>
          <span><v-icon size="16">mdi-minus</v-icon> Undefined</span>
        </div>

        <v-alert v-if="elementOptions.length === 0" type="info" variant="tonal" class="mt-3"> Add Elements first to define Connection rules. </v-alert>

        <v-sheet v-else class="matrix-wrapper elevation-1 mt-3 rounded-lg bg-white" border>
          <v-table density="compact" class="relation-matrix">
            <thead>
              <tr>
                <th class="matrix-corner">
                  <div class="d-flex align-center ga-1 text-caption text-uppercase text-medium-emphasis">
                    <span>From</span>
                    <span class="font-weight-bold">→</span>
                    <span>To</span>
                  </div>
                </th>
                <th v-for="target in elementOptions" :key="`head-${target}`" class="matrix-header matrix-header--column">
                  <ElementPreviewLabel :element="elementFor(target)" :label="target" />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="source in elementOptions" :key="`row-${source}`">
                <th class="matrix-header matrix-header--row"><ElementPreviewLabel :element="elementFor(source)" :label="source" /></th>
                <td v-for="target in elementOptions" :key="`cell-${source}-${target}`" class="matrix-cell">
                  <v-tooltip :text="`${source} → ${target}: ${stateLabel(getRelationState(source, target))}`" location="bottom">
                    <template #activator="{ props: tooltipProps }">
                      <v-btn v-bind="tooltipProps" :aria-label="`${source} → ${target}: ${stateLabel(getRelationState(source, target))}`" :disabled="!hasLanguageVersion" variant="elevated" class="matrix-button rounded-lg" :class="stateClass(getRelationState(source, target))" size="small" @click="cycleRelationState(source, target)">
                        <v-icon size="18">{{ stateIcon(getRelationState(source, target)) }}</v-icon>
                      </v-btn>
                    </template>
                  </v-tooltip>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-sheet>

        <p v-if="elementOptions.length" class="text-caption text-medium-emphasis mt-2 mb-0">Edit allowed combinations in the overview below. Undefined cells are {{ config.defaultState === 'forbidden' ? 'not allowed' : 'allowed' }} by default.</p>
        <v-btn class="mt-4" size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates({ kind: 'connection' })">Connection feedback templates</v-btn>
      </section>

      <v-divider />
      <section :id="feedbackTargetId('syntax', { kind: 'quantity' })" tabindex="-1" class="rules-section d-flex flex-column ga-3">
        <h4 class="d-flex align-center text-subtitle-1 font-weight-bold">
          <v-icon color="primary" class="mr-2">mdi-arrow-decision</v-icon>Allowed connections<v-chip size="x-small" variant="tonal" class="ml-2">{{ allowedRelations.length }}</v-chip>
        </h4>
        <v-alert v-if="configErrors.length" type="warning" variant="tonal" density="compact"
          ><div v-for="error in configErrors" :key="error">{{ error }}</div></v-alert
        >
        <div class="d-flex flex-wrap ga-2">
          <v-btn size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates({ kind: 'connection' })">Connection feedback templates</v-btn>
          <v-btn size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates({ kind: 'quantity' })">Default quantity feedback template</v-btn>
        </div>
        <p v-if="!allowedRelations.length" class="text-body-2 text-medium-emphasis mb-0">Set a matrix cell to <v-icon color="primary" size="16">mdi-check</v-icon> to define its connection types, points and limits.</p>
        <v-expansion-panels v-else v-model="activeRelationKey" variant="accordion" class="rule-overview">
          <v-expansion-panel v-for="relation in allowedRelations" :key="relationKey(relation.sourceType, relation.targetType)" :value="relationKey(relation.sourceType, relation.targetType)">
            <v-expansion-panel-title>
              <div class="rule-summary">
                <div class="d-flex align-center flex-wrap ga-2">
                  <div class="d-flex align-center ga-1">
                    <ElementPreviewLabel :element="elementFor(relation.sourceType)" :label="relation.sourceType" />
                    <v-icon size="18" aria-hidden="true">mdi-arrow-right</v-icon>
                    <ElementPreviewLabel :element="elementFor(relation.targetType)" :label="relation.targetType" />
                  </div>
                  <span class="text-body-2 text-medium-emphasis">{{ isIndividual(relation) ? 'Individual routes' : connectionTypesSummary(relation.refinement.connectionTypes) }}</span>
                </div>
                <div class="d-flex flex-wrap ga-1">
                  <v-chip v-if="isIndividual(relation)" size="small" variant="tonal" color="primary" class="text-caption">{{ relation.refinement.routes?.length }} routes</v-chip>
                  <template v-else>
                    <v-chip size="small" variant="tonal" class="text-caption">Per source: {{ boundsSummary(relation.refinement.cardinality) }}</v-chip>
                    <v-chip v-if="hasLimit(relation.refinement.targetCardinality)" size="small" variant="tonal" class="text-caption">Per target: {{ boundsSummary(relation.refinement.targetCardinality) }}</v-chip>
                    <v-chip v-if="hasLimit(relation.refinement.pairCardinality)" size="small" variant="tonal" class="text-caption">Per pair: {{ boundsSummary(relation.refinement.pairCardinality) }}</v-chip>
                  </template>
                </div>
                <div class="text-caption text-medium-emphasis"><v-icon size="14" class="mr-1">mdi-target</v-icon>{{ endpointPairsSummary(relation) }}</div>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text v-if="activeRelation && activeRelationKey === relationKey(relation.sourceType, relation.targetType)">
              <div :id="feedbackTargetId('syntax', relationTarget(relation))" tabindex="-1">
                <v-btn class="mb-3" size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates(relationTarget(relation))">Connection feedback template</v-btn>
              </div>
              <v-btn-toggle :model-value="isIndividual(activeRelation) ? 'individual' : 'basic'" mandatory density="compact" variant="outlined" divided color="primary" class="mb-4" :disabled="!hasLanguageVersion" @update:model-value="setMode">
                <v-btn value="basic" prepend-icon="mdi-tune">Basic</v-btn>
                <v-btn value="individual" prepend-icon="mdi-call-split">Individual routes</v-btn>
              </v-btn-toggle>
              <p class="text-caption text-medium-emphasis mb-4">
                {{ isIndividual(activeRelation) ? 'Every route has its own connection points, connection types and limits. A connection must match one route.' : 'Shared connection types and limits, optionally restricted to alternative point combinations.' }}
              </p>

              <RouteRuleFields
                v-if="!isIndividual(activeRelation)"
                :rule="activeRelation.refinement"
                :source="activeRelation.refinement.endpoints?.[0]?.source ?? {}"
                :target="activeRelation.refinement.endpoints?.[0]?.target ?? {}"
                :endpoint-pairs="activeRelation.refinement.endpoints ?? []"
                :source-type="activeRelation.sourceType"
                :target-type="activeRelation.targetType"
                :connection-options="connectionOptions"
                :disabled="!hasLanguageVersion"
                @patch="patchBase"
                @update:endpoint-pairs="patchBase({ endpoints: $event })"
              />

              <template v-else>
                <v-sheet v-for="(route, index) in activeRelation.refinement.routes" :id="feedbackTargetId('syntax', routeTarget(relation, index))" :key="index" tabindex="-1" border rounded class="pa-3 mb-3">
                  <div class="d-flex align-center ga-3 mb-3">
                    <v-text-field :model-value="route.name ?? ''" :label="`Route ${index + 1} name`" placeholder="Optional" density="compact" variant="outlined" hide-details :disabled="!hasLanguageVersion" @update:model-value="patchRoute(index, { name: $event ?? '' })" />
                    <v-btn icon="mdi-delete" variant="text" size="small" aria-label="Remove route" :disabled="!hasLanguageVersion || (activeRelation.refinement.routes?.length ?? 0) < 2" @click="removeRoute(index)" />
                  </div>
                  <v-btn class="mb-3" size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates(routeTarget(relation, index))">Route feedback template</v-btn>
                  <RouteRuleFields
                    :rule="route"
                    :source="route.source"
                    :target="route.target"
                    :source-type="activeRelation.sourceType"
                    :target-type="activeRelation.targetType"
                    :connection-options="connectionOptions"
                    :disabled="!hasLanguageVersion"
                    @patch="patchRoute(index, $event)"
                    @update:source="patchRoute(index, { source: $event })"
                    @update:target="patchRoute(index, { target: $event })"
                  />
                </v-sheet>
                <v-btn variant="tonal" prepend-icon="mdi-plus" size="small" :disabled="!hasLanguageVersion" @click="addRoute">Add route</v-btn>
                <p v-if="(activeRelation.refinement.routes?.length ?? 0) > 1" class="text-caption text-medium-emphasis mt-2 mb-0">Remove routes until one is left to switch back to Basic.</p>
              </template>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </section>

      <v-divider />
      <section class="rules-section d-flex flex-column ga-3">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2">
          <h4 class="d-flex align-center text-subtitle-1 font-weight-bold">
            <v-icon color="primary" class="mr-2">mdi-counter</v-icon>Connection Limits<v-chip size="x-small" variant="tonal" class="ml-2">{{ edgeRules.length }}</v-chip>
          </h4>
          <v-btn prepend-icon="mdi-plus" variant="tonal" color="primary" size="small" :disabled="!hasLanguageVersion || !elementOptions.length" @click="addEdgeRule">Add limit</v-btn>
        </div>
        <p class="text-caption text-medium-emphasis mb-0">Totals across combinations, per element, point or group. All matching limits apply together.</p>
        <p v-if="!edgeRules.length" class="text-body-2 text-medium-emphasis mb-0">No additional limits.</p>
        <v-expansion-panels v-model="openLimits" variant="accordion" multiple>
          <v-expansion-panel v-for="(entry, index) in edgeRules" :key="index" :value="index">
            <v-expansion-panel-title>
              <div class="d-flex align-center ga-3">
                <ElementPreviewLabel :element="elementFor(entry.elementType)" :label="entry.elementType || 'All elements'" />
                <div class="rule-summary">
                  <span class="font-weight-medium">{{ limitSummary(entry) }}</span>
                  <span class="text-caption text-medium-emphasis">{{ limitFiltersSummary(entry) }}</span>
                </div>
              </div>
            </v-expansion-panel-title>
            <v-expansion-panel-text>
              <div :id="feedbackTargetId('syntax', { kind: 'limit', index })" tabindex="-1">
                <v-btn size="small" variant="text" prepend-icon="mdi-message-text-outline" @click="navigation.openTemplates({ kind: 'limit', index })">Limit feedback template</v-btn>
              </div>
              <div class="d-flex justify-end mb-3"><v-btn size="small" variant="text" color="error" prepend-icon="mdi-delete" :disabled="!hasLanguageVersion" @click="removeEdgeRule(index)">Remove limit</v-btn></div>
              <v-row dense>
                <v-col cols="12" md="6"><v-select :model-value="entry.elementType || null" :items="elementOptions" label="Element" placeholder="All elements" clearable variant="outlined" density="compact" :disabled="!hasLanguageVersion" @update:model-value="setLimitElement(entry, $event)" /></v-col>
                <v-col cols="12" md="6"><v-select :model-value="entry.direction ?? 'incoming'" :items="directions" label="Direction" variant="outlined" density="compact" :disabled="!hasLanguageVersion" hint="Undirected connections count at both ends regardless of drawing direction." persistent-hint @update:model-value="setLimitField(entry, 'direction', $event)" /></v-col>
                <v-col cols="12" md="6"><v-select :model-value="entry.connectionTypes ?? []" :items="connectionOptions" label="Connection types" placeholder="All types" multiple chips closable-chips clearable variant="outlined" density="compact" :disabled="!hasLanguageVersion" @update:model-value="setLimitField(entry, 'connectionTypes', $event ?? [])" /></v-col>
                <v-col cols="12" md="6"><v-select :model-value="entry.neighborTypes ?? []" :items="elementOptions" label="Other end" placeholder="All elements" multiple chips closable-chips clearable variant="outlined" density="compact" :disabled="!hasLanguageVersion" @update:model-value="setLimitField(entry, 'neighborTypes', $event ?? [])" /></v-col>
              </v-row>
              <v-select :model-value="entry.countScope ?? 'element'" :items="countScopes" label="Count connections" variant="outlined" density="compact" :disabled="!hasLanguageVersion" @update:model-value="setLimitField(entry, 'countScope', $event)" />
              <ConnectionPointSelector :model-value="entry.endpoints ?? {}" :element="elementFor(entry.elementType)" :elements="elements" :groups-only="entry.countScope === 'group'" :label="entry.countScope === 'group' ? 'Connection point groups' : 'Limit to points or groups (optional)'" :disabled="!hasLanguageVersion" @update:model-value="setLimitField(entry, 'endpoints', $event)" />
              <CardinalityFields :model-value="entry.cardinality" label="Allowed number of connections" :disabled="!hasLanguageVersion" class="mt-4" @update:model-value="setLimitField(entry, 'cardinality', $event)" />
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </section>

    </v-sheet>

    <slot />

    <v-expansion-panels variant="accordion">
      <v-expansion-panel>
        <v-expansion-panel-title class="font-weight-semibold text-h6">
          <v-icon color="primary" class="mr-2">mdi-code-json</v-icon>
          <span>Syntax Data Structure</span>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-sheet border rounded="lg" class="structure-preview">
            <pre class="structure-preview__code">{{ uiStructureExampleJson }}</pre>
          </v-sheet>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { EdgeCardinality, EndpointSelector, MultiplicityCardinality, MultiplicityConfig, MultiplicityRefinement, MultiplicityRelation, MultiplicityRelationState, MultiplicityRoute } from '@/model/Syntax'
import CardinalityFields from './CardinalityFields.vue'
import ConnectionPointSelector from './ConnectionPointSelector.vue'
import ElementPreviewLabel from './ElementPreviewLabel.vue'
import RouteRuleFields from './RouteRuleFields.vue'
import { resolveQuantityMessage } from '@/utils/syntaxMessages'
import { feedbackTargetId, feedbackTemplateNavigationKey, type FeedbackTemplateTarget } from '@/components/modeling/editors/feedbackTemplateNavigation'
import { connectionConfigErrors } from '@/utils/connectionRules'
import { pointId, pointLabel } from '@/utils/connectionPoints'

type RelationState = MultiplicityRelationState | 'unset'
const props = defineProps<{ config: MultiplicityConfig; elementOptions: string[]; connectionOptions: string[] }>()
const emit = defineEmits<{ update: [] }>()
const store = useDiagramLanguages()
const navigation = inject(feedbackTemplateNavigationKey)!
const hasLanguageVersion = computed(() => store.currentVersion !== null)
const elements = computed(() => store.definition?.elements ?? [])
const elementFor = (type: string) => elements.value.find((e) => e.type === type)
const elementOptions = computed(() => props.elementOptions)
const connectionOptions = computed(() => props.connectionOptions)
const unlimited = (): MultiplicityCardinality => ({ min: 0, max: null })
const update = () => emit('update')
const relationKey = (source: string, target: string) => JSON.stringify([source, target])
const allowedRelations = computed(() => props.config.relations.filter((r) => r.state === 'allowed'))
const activeRelationKey = ref<string>()
const activeRelation = computed(() => allowedRelations.value.find((r) => relationKey(r.sourceType, r.targetType) === activeRelationKey.value))
const relationTarget = (relation: MultiplicityRelation): FeedbackTemplateTarget => ({ kind: 'relation', source: relation.sourceType, target: relation.targetType })
const routeTarget = (relation: MultiplicityRelation, index: number): FeedbackTemplateTarget => ({ kind: 'route', source: relation.sourceType, target: relation.targetType, index })
watch(allowedRelations, (relations) => {
  if (!relations.some((r) => relationKey(r.sourceType, r.targetType) === activeRelationKey.value)) activeRelationKey.value = undefined
})
const configErrors = computed(() => connectionConfigErrors({ config: props.config, elements: elements.value, connections: store.definition?.connections ?? [] }))
const getRelationState = (source: string, target: string): RelationState => props.config.relations.find((r) => r.sourceType === source && r.targetType === target)?.state ?? 'unset'
const stateIcon = (state: RelationState) => (state === 'allowed' ? 'mdi-check' : state === 'forbidden' ? 'mdi-close' : 'mdi-minus')
const stateClass = (state: RelationState) => `matrix-button--${state}`
const stateLabel = (state: RelationState) => (state === 'unset' ? `Undefined (default: ${props.config.defaultState ?? 'allowed'})` : state === 'allowed' ? 'Allowed' : 'Forbidden')
const defaultStates = [
  { title: 'Not allowed', value: 'forbidden' },
  { title: 'Allowed', value: 'allowed' }
]
const setDefaultState = (state: MultiplicityRelationState) => {
  Object.assign(props.config, { defaultState: state })
  update()
}
const cycleRelationState = (source: string, target: string) => {
  if (!hasLanguageVersion.value) return
  const current = getRelationState(source, target)
  const next = current === 'unset' ? 'allowed' : current === 'allowed' ? 'forbidden' : 'unset'
  store.setMultiplicityRelationState(source, target, next)
  update()
}
const isIndividual = (relation: MultiplicityRelation) => Boolean(relation.refinement.routes?.length)
const emptySelector = (): EndpointSelector => ({})
const setMode = (value: unknown) => {
  const mode = value === 'individual' ? 'individual' : 'basic'
  const relation = activeRelation.value
  if (!relation || mode === (isIndividual(relation) ? 'individual' : 'basic')) return
  const ref = relation.refinement
  if (mode === 'individual') {
    const base = { messageTemplate: ref.messageTemplate, connectionTypes: [...ref.connectionTypes], cardinality: { ...ref.cardinality }, targetCardinality: ref.targetCardinality && { ...ref.targetCardinality }, pairCardinality: ref.pairCardinality && { ...ref.pairCardinality } }
    const pairs = ref.endpoints?.length ? ref.endpoints : [{ source: emptySelector(), target: emptySelector() }]
    ref.routes = pairs.map((pair) => ({ ...structuredClone(base), source: pair.source, target: pair.target }))
    ref.endpoints = undefined
  } else if ((ref.routes?.length ?? 0) <= 1) {
    const [route] = ref.routes ?? []
    if (route) Object.assign(ref, { messageTemplate: route.messageTemplate, connectionTypes: route.connectionTypes, cardinality: route.cardinality, targetCardinality: route.targetCardinality, pairCardinality: route.pairCardinality, endpoints: [{ source: route.source, target: route.target }] })
    ref.routes = undefined
  }
  update()
}
const patchBase = (values: Partial<MultiplicityRefinement>) => {
  if (activeRelation.value) Object.assign(activeRelation.value.refinement, values)
  update()
}
const patchRoute = (index: number, values: Partial<MultiplicityRoute>) => {
  const route = activeRelation.value?.refinement.routes?.[index]
  if (route) Object.assign(route, values)
  update()
}
const addRoute = () => {
  activeRelation.value?.refinement.routes?.push({ source: emptySelector(), target: emptySelector(), connectionTypes: [], cardinality: unlimited() })
  update()
}
const removeRoute = (index: number) => {
  const routes = activeRelation.value?.refinement.routes
  if (routes && routes.length > 1) routes.splice(index, 1)
  update()
}
const boundsSummary = (bounds?: MultiplicityCardinality) => `${bounds?.min ?? 0}…${bounds?.max ?? '∞'}`
const hasLimit = (bounds?: MultiplicityCardinality) => bounds && (bounds.min > 0 || bounds.max !== null)
const connectionTypesSummary = (types?: string[]) => (types?.length ? types.join(', ') : 'All connection types')
const selectorSummary = (selector: EndpointSelector | undefined, type: string) => {
  const candidates = elements.value.filter((e) => !type || e.type === type)
  const points = (selector?.pointIds ?? []).map((id) => {
    const matches = candidates.flatMap((e) => e.anchorPoints.filter((p) => pointId(p) === id).map((p) => (type ? pointLabel(p) : `${e.type}: ${pointLabel(p)}`)))
    return matches.length ? matches.join(', ') : `Missing point (${id})`
  })
  const groups = (selector?.groups ?? []).map((group) => `Group: ${group}`)
  return [...points, ...groups].join(' or ') || 'Any point / outline'
}
const endpointPairsSummary = (relation: MultiplicityRelation) => {
  const pairs = relation.refinement.routes?.length ? relation.refinement.routes.map((route) => ({ source: route.source, target: route.target })) : relation.refinement.endpoints
  return pairs?.length ? pairs.map((pair) => `${selectorSummary(pair.source, relation.sourceType)} → ${selectorSummary(pair.target, relation.targetType)}`).join(' · OR · ') : 'All permitted source and target points'
}
const edgeRules = computed(() => props.config.incoming ?? [])
const openLimits = ref<number[]>([])
watch(navigation.syntaxTarget, (target) => {
  if (!target) return
  if (target.kind === 'relation' || target.kind === 'route') activeRelationKey.value = relationKey(target.source, target.target)
  if (target.kind === 'limit') openLimits.value = [...new Set([...openLimits.value, target.index])]
}, { flush: 'sync' })
const directions = [
  { title: 'Incoming', value: 'incoming' },
  { title: 'Outgoing', value: 'outgoing' },
  { title: 'Both / undirected', value: 'both' }
]
const countScopes = [
  { title: 'Per element (selected connections together)', value: 'element' },
  { title: 'Per individual point', value: 'point' },
  { title: 'Per group (all member points together)', value: 'group' }
]
const limitSummary = (r: EdgeCardinality) => `${directions.find((d) => d.value === (r.direction ?? 'incoming'))?.title} · ${boundsSummary(r.cardinality)} per ${r.countScope === 'point' ? 'point' : r.countScope === 'group' ? 'group' : 'element'}`
const limitFiltersSummary = (r: EdgeCardinality) => {
  const selector: EndpointSelector | undefined = r.countScope === 'group' ? { groups: r.endpoints?.groups } : r.endpoints
  const points = selector?.pointIds?.length || selector?.groups?.length ? selectorSummary(selector, r.elementType) : r.countScope === 'point' ? 'Every connection point' : r.countScope === 'group' ? 'No group selected' : 'Any point / outline'
  return `${connectionTypesSummary(r.connectionTypes)} · Other end: ${r.neighborTypes?.join(', ') || 'Any element'} · ${points}`
}
const setLimitField = <K extends keyof EdgeCardinality>(rule: EdgeCardinality, key: K, value: EdgeCardinality[K]) => {
  rule[key] = value
  update()
}
const setLimitElement = (rule: EdgeCardinality, value: string | null) => {
  rule.elementType = value ?? ''
  rule.endpoints = {}
  update()
}
const addEdgeRule = () => {
  const index = edgeRules.value.length
  Object.assign(props.config, { incoming: [...edgeRules.value, { elementType: activeRelation.value?.sourceType ?? '', direction: 'both', cardinality: unlimited(), messageTemplate: resolveQuantityMessage(props.config.messageTemplate) }] })
  openLimits.value = [...openLimits.value, index]
  update()
}
const removeEdgeRule = (index: number) => {
  Object.assign(props.config, { incoming: edgeRules.value.filter((_, i) => i !== index) })
  openLimits.value = openLimits.value.filter((i) => i !== index).map((i) => (i > index ? i - 1 : i))
  update()
}
const uiStructureExampleJson = computed(() => JSON.stringify({ ruleType: 'multiplicity', config: props.config }, null, 2))
</script>

<style scoped>
.connection-rules {
  overflow: hidden;
}
.rules-heading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: rgba(var(--v-theme-primary), 0.06);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.rules-section {
  padding: 16px;
  min-width: 0;
}
.matrix-default {
  flex: 0 1 220px;
  min-width: 180px;
}
.matrix-legend {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.matrix-legend > span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.rule-summary {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding-right: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.rule-overview :deep(.v-expansion-panel-title) {
  padding: 12px 16px;
}
.relation-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 16px;
}
@media (max-width: 1100px) {
  .relation-fields {
    grid-template-columns: 1fr;
  }
}
.matrix-wrapper {
  overflow: auto;
  max-width: 100%;
  max-height: 320px;
  scrollbar-gutter: stable;
}
.matrix-wrapper :deep(.v-table__wrapper) {
  overflow: visible;
}
.relation-matrix {
  min-width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.relation-matrix thead th {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #f6f8fb;
  white-space: nowrap;
}
.matrix-header {
  padding: 8px 12px;
  white-space: nowrap;
}
.relation-matrix :deep(th.matrix-header) {
  text-align: center;
}
.matrix-header--row {
  position: sticky;
  left: 0;
  z-index: 2;
  background: #f6f8fb;
}
.matrix-corner {
  position: sticky;
  left: 0;
  z-index: 4;
  background: #eef2f8;
}
.matrix-cell {
  padding: 6px;
  text-align: center;
  background: #fff;
}
.matrix-button {
  width: 38px;
  height: 30px;
  min-width: 38px;
}
.matrix-button--allowed {
  background: rgb(var(--v-theme-primary));
  color: rgb(var(--v-theme-on-primary));
}
.matrix-button--forbidden {
  background: rgb(var(--v-theme-error));
  color: rgb(var(--v-theme-on-error));
}
.matrix-button--unset {
  background: rgba(var(--v-theme-outline), 0.18);
  color: rgba(var(--v-theme-on-surface), 0.6);
}
.structure-preview {
  background: #0f172a;
  color: #e2e8f0;
  overflow: auto;
  max-height: 280px;
}
.structure-preview__code {
  margin: 0;
  padding: 12px;
  font-size: 12px;
  line-height: 1.45;
  font-family: 'Cascadia Code', 'Consolas', monospace;
}
</style>
