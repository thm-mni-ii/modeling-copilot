<template>
  <section>
    <div class="d-flex align-center font-weight-semibold text-h6 mb-3">
      <v-icon color="primary" class="mr-2">mdi-sync-off</v-icon>
      <span>No Cycles</span>
    </div>

    <p class="text-body-2 text-medium-emphasis mb-3">Forbids Connections that close a cycle along the Connection direction. Without this rule, cycles are allowed.</p>

    <v-switch :model-value="rule !== undefined" color="primary" density="compact" hide-details label="Forbid cycles" :disabled="!store.definition" @update:model-value="(enabled: boolean | null) => store.setAcyclicRule(enabled ? DEFAULT_ACYCLIC_MESSAGE_TEMPLATE : null)" />

    <v-textarea v-if="rule" :model-value="rule.config.messageTemplate" rows="2" density="compact" variant="outlined" label="Error Message Template" auto-grow hint="Use placeholders such as {source}, {target}" persistent-hint class="mt-3" @update:model-value="(value: string) => store.setAcyclicRule(value ?? '')" />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AcyclicRule } from '@/model/Syntax'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import { DEFAULT_ACYCLIC_MESSAGE_TEMPLATE } from '@/utils/acyclic'

const store = useDiagramLanguages()

const rule = computed(() => store.definition?.syntax.find((entry): entry is AcyclicRule => entry.ruleType === 'acyclic'))
</script>
