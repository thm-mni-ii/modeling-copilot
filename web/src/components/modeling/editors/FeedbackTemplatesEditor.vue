<template>
  <v-container fluid class="pa-4">
    <div class="d-flex align-center justify-space-between flex-wrap ga-3 mb-4">
      <div>
        <h2 class="text-h6">Validation feedback templates</h2>
        <p class="text-body-2 text-medium-emphasis mb-0">Edit the messages used by syntax validation. Rules are configured in the Syntax tab.</p>
      </div>
      <v-btn variant="tonal" prepend-icon="mdi-code-braces" @click="navigation.openSyntax({ kind: 'connection' })">Open syntax</v-btn>
    </div>

    <v-alert v-if="!config" type="info" variant="tonal">Load a language version to edit its validation templates.</v-alert>
    <template v-else>
      <p class="text-body-2 text-medium-emphasis">
        A configured template is saved with the language version. Empty templates use the default shown below the field.
        For individual connection and limit templates, the default is the general quantity message.
      </p>
      <p class="text-body-2 text-medium-emphasis">
        Placeholders: <code>{source}</code> and <code>{target}</code> are element types; <code>{connection}</code> is the connection type;
        <code>{element}</code> is the element type; <code>{min}</code> and <code>{max}</code> are the quantity bounds.
        Depending on the rule, an unrestricted type or maximum is shown as <code>*</code>.
      </p>
      <section :id="feedbackTargetId('template', { kind: 'connection' })" tabindex="-1" class="mb-6">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <h2 class="text-h6">Connection rules</h2>
          <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" @click="navigation.openSyntax({ kind: 'connection' })">Connection settings</v-btn>
        </div>
        <div class="d-flex flex-column ga-3">
          <FeedbackTemplateField v-for="field in connectionFields" :key="field.key" :title="field.title" :description="field.description" :value="config[field.key]" :fallback="DEFAULT_CONNECTION_MESSAGE_TEMPLATES[field.key]" :placeholders="connectionPlaceholders" :disabled="disabled" @update:value="config[field.key] = $event" />
        </div>
      </section>

      <section :id="feedbackTargetId('template', { kind: 'quantity' })" tabindex="-1" class="mb-6">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <h2 class="text-h6">Connection quantities</h2>
          <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" @click="navigation.openSyntax({ kind: 'quantity' })">Quantity settings</v-btn>
        </div>
        <FeedbackTemplateField title="Default quantity message" description="Used for connection quantity rules without their own template." :value="config.messageTemplate" :fallback="DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE" :placeholders="quantityPlaceholders" :disabled="disabled" @update:value="config.messageTemplate = $event" />
      </section>

      <section v-if="config.relations.length" class="mb-6">
        <h2 class="text-h6 mb-2">Messages for individual connections and routes</h2>
        <p class="text-body-2 text-medium-emphasis">These templates override the default quantity message for the selected combination or route.</p>
        <template v-for="relation in config.relations" :key="relationKey(relation)">
          <div v-if="relation.state === 'allowed' || relation.refinement.messageTemplate?.trim()" :id="feedbackTargetId('template', relationTarget(relation))" tabindex="-1" class="mb-3">
            <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-2">
              <h3 class="text-subtitle-1">{{ relation.sourceType }} → {{ relation.targetType }}</h3>
              <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" :aria-label="`Settings for ${relation.sourceType} to ${relation.targetType}`" @click="navigation.openSyntax(relation.state === 'allowed' ? relationTarget(relation) : { kind: 'connection' })">Connection settings</v-btn>
            </div>
            <FeedbackTemplateField title="Connection quantity message" :description="relation.state !== 'allowed' ? 'This combination is not currently allowed, so this template is inactive.' : relation.refinement.routes?.length ? 'Inactive while individual routes are enabled; each route uses its own template.' : 'Used for quantity limits on this connection combination.'" :value="relation.refinement.messageTemplate" :fallback="resolveQuantityMessage(config.messageTemplate)" :placeholders="quantityPlaceholders" :disabled="disabled" @update:value="relation.refinement.messageTemplate = $event" />
          </div>
          <div v-for="(route, index) in relation.refinement.routes ?? []" :id="feedbackTargetId('template', routeTarget(relation, index))" :key="index" tabindex="-1" class="mb-3 ml-4">
            <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-2">
              <h3 class="text-subtitle-1">{{ relation.sourceType }} → {{ relation.targetType }} · {{ route.name?.trim() || `Route ${index + 1}` }}</h3>
              <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" :aria-label="`Settings for ${relation.sourceType} to ${relation.targetType}, ${route.name?.trim() || `route ${index + 1}`}`" @click="navigation.openSyntax(relation.state === 'allowed' ? routeTarget(relation, index) : { kind: 'connection' })">{{ relation.state === 'allowed' ? 'Route settings' : 'Connection settings' }}</v-btn>
            </div>
            <FeedbackTemplateField title="Route quantity message" :description="relation.state === 'allowed' ? 'Used for quantity limits on this route.' : 'This combination is not currently allowed, so this template is inactive.'" :value="route.messageTemplate" :fallback="resolveQuantityMessage(config.messageTemplate)" :placeholders="quantityPlaceholders" :disabled="disabled" @update:value="route.messageTemplate = $event" />
          </div>
        </template>
      </section>

      <section v-if="config.incoming?.length" class="mb-6">
        <h2 class="text-h6 mb-2">Messages for individual connection limits</h2>
        <p class="text-body-2 text-medium-emphasis">These templates override the default quantity message for a specific connection limit.</p>
        <div v-for="(limit, index) in config.incoming" :id="feedbackTargetId('template', { kind: 'limit', index })" :key="index" tabindex="-1" class="mb-3">
          <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-2">
            <h3 class="text-subtitle-1">Limit {{ index + 1 }} · {{ limit.elementType || 'All elements' }} · {{ limit.direction ?? 'incoming' }} · {{ limit.cardinality.min }}–{{ limit.cardinality.max ?? '∞' }} per {{ limit.countScope ?? 'element' }}</h3>
            <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" :aria-label="`Settings for connection limit ${index + 1}`" @click="navigation.openSyntax({ kind: 'limit', index })">Limit settings</v-btn>
          </div>
          <FeedbackTemplateField title="Connection limit message" description="Used when this connection limit is violated." :value="limit.messageTemplate" :fallback="resolveQuantityMessage(config.messageTemplate)" :placeholders="quantityPlaceholders" :disabled="disabled" @update:value="limit.messageTemplate = $event" />
        </div>
      </section>

      <section v-if="cycleRule" :id="feedbackTargetId('template', { kind: 'cycle' })" tabindex="-1" class="mb-6">
        <div class="d-flex align-center justify-space-between flex-wrap ga-2 mb-3">
          <h2 class="text-h6">Cycles</h2>
          <v-btn size="small" variant="text" prepend-icon="mdi-code-braces" @click="navigation.openSyntax({ kind: 'cycle' })">Cycle settings</v-btn>
        </div>
        <FeedbackTemplateField title="Cycle message" :description="cycleDescription" :value="cycleRule.config.messageTemplate" :fallback="DEFAULT_CYCLE_MESSAGE_TEMPLATES[cycleRule.config.mode ?? 'forbid']" :placeholders="cyclePlaceholders" :disabled="disabled" @update:value="cycleRule.config.messageTemplate = $event" />
      </section>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import type { AcyclicRule, MultiplicityRelation, MultiplicityRule } from '@/model/Syntax'
import { DEFAULT_CYCLE_MESSAGE_TEMPLATES } from '@/utils/acyclic'
import { DEFAULT_CONNECTION_MESSAGE_TEMPLATES, DEFAULT_MULTIPLICITY_MESSAGE_TEMPLATE, resolveQuantityMessage } from '@/utils/syntaxMessages'
import FeedbackTemplateField from './FeedbackTemplateField.vue'
import { feedbackTargetId, feedbackTemplateNavigationKey, type FeedbackTemplateTarget } from './feedbackTemplateNavigation'

const store = useDiagramLanguages()
const navigation = inject(feedbackTemplateNavigationKey)!
const config = computed(() => store.definition?.syntax.find((rule): rule is MultiplicityRule => rule.ruleType === 'multiplicity')?.config)
const cycleRule = computed(() => store.definition?.syntax.find((rule): rule is AcyclicRule => rule.ruleType === 'acyclic'))
const disabled = computed(() => !store.currentVersion)
const connectionPlaceholders = ['source', 'target', 'connection']
const quantityPlaceholders = [...connectionPlaceholders, 'min', 'max']
const connectionFields = [
  { key: 'forbiddenMessageTemplate', title: 'Forbidden combination', description: 'Used when the selected elements may not be connected.' },
  { key: 'connectionTypeMessageTemplate', title: 'Connection type', description: 'Used when the connection type is not allowed for the selected elements.' },
  { key: 'endpointMessageTemplate', title: 'Connection points', description: 'Used when the selected connection points are not allowed together.' }
] as const
const cyclePlaceholders = computed(() => cycleRule.value?.config.mode === 'every' ? ['element'] : cycleRule.value?.config.mode === 'any' ? [] : ['source', 'target'])
const cycleDescription = computed(() => cycleRule.value?.config.mode === 'every' ? 'Used when an element must be part of a cycle.' : cycleRule.value?.config.mode === 'any' ? 'Used when the diagram must contain a cycle.' : 'Used when a connection would create a forbidden cycle.')
const relationKey = (relation: MultiplicityRelation) => JSON.stringify([relation.sourceType, relation.targetType])
const relationTarget = (relation: MultiplicityRelation): FeedbackTemplateTarget => ({ kind: 'relation', source: relation.sourceType, target: relation.targetType })
const routeTarget = (relation: MultiplicityRelation, index: number): FeedbackTemplateTarget => ({ kind: 'route', source: relation.sourceType, target: relation.targetType, index })
</script>
