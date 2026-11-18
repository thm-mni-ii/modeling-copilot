<template>
  <div class="pattern-feedback">
    <figure v-for="object in patterned" :key="object.cellId" class="pattern-feedback__figure">
      <figcaption class="d-flex align-center">
        <span>Strukturmuster</span>
        <v-spacer />
        <v-btn icon="mdi-arrow-expand" size="x-small" variant="text" aria-label="Strukturmuster vergrößern" @click="enlarged = object.xml" />
      </figcaption>
      <ModelExcerptPreview :xml="object.xml" :label="label" />
    </figure>
    <p v-if="!patterned.length" class="pattern-feedback__hint">Für dieses Objekt gibt es kein Strukturmuster, weil es keinem Element der Musterlösung zugeordnet werden konnte.</p>
    <v-dialog :model-value="!!enlarged" max-width="1100" @update:model-value="value => { if (!value) enlarged = null }">
      <v-card title="Strukturmuster">
        <template #append><v-btn icon="mdi-close" variant="text" aria-label="Schließen" @click="enlarged = null" /></template>
        <v-card-text><ModelExcerptPreview v-if="enlarged" :xml="enlarged" :label="label" :height="560" /></v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import ModelExcerptPreview from './ModelExcerptPreview.vue'
import type { HelpFeedbackEntry } from '@/services/api/types/evaluation'

// help.example: only the sample solution's structure pattern; placeholders are grey and dashed.
const props = defineProps<{ entry: HelpFeedbackEntry }>()
const label = 'Strukturmuster der Musterlösung: erkannte Elemente mit deiner Bezeichnung, übrige grau gestrichelt als Platzhalter mit ihrem Elementtyp'
const enlarged = ref<string | null>(null)
const patterned = computed(() => (props.entry.objects ?? []).flatMap(object =>
  object.pattern?.expected ? [{ cellId: object.cellId, xml: object.pattern.expected }] : []))
</script>

<style scoped>
.pattern-feedback__figure { margin: 0 0 8px; padding: 6px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.pattern-feedback__figure figcaption { font-size: 11px; font-weight: 600; margin-bottom: 4px; }
.pattern-feedback__figure :deep(.model-excerpt-preview) { border: 0; background-color: transparent; }
.pattern-feedback__hint { font-size: 12px; line-height: 1.5; }
</style>
