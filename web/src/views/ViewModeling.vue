<template>
  <v-container fluid class="pa-4 modeling-view">
    <v-progress-linear v-if="loading" indeterminate class="model-loading" />
    <v-alert v-if="loadError" type="error" variant="tonal" density="compact" closable class="model-load-error" @click:close="loadError = null">{{ loadError }}</v-alert>
    <DrawingCanvas ref="canvas" v-model:model="graphModel" class="editor-canvas" model-management :languages="workspace.editorLanguages" :language-connections="connections" :connection-groups="connectionGroups" :connection-preferences="workspace.preferences" :language-syntax="syntax" @update:model="captureCanvas" @update:connection-preferences="workspace.updatePreferences" />
    <v-dialog v-model="recoveryDialog" max-width="1000" persistent
      ><v-card
        ><v-card-title>Unsaved changes found</v-card-title
        ><v-card-text
          ><p class="mb-3">A local draft is available. Review it before choosing whether to restore it.</p>
          <ModelSnapshotPreview :data="recoveryData" />
          <p class="text-caption text-medium-emphasis mt-2">The preview is read-only and does not change the server version.</p></v-card-text
        ><v-card-actions><v-btn @click="discardDraft">Open server version</v-btn><v-spacer /><v-btn color="primary" @click="restoreDraft">Restore local draft</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { GraphDataModel } from '@maxgraph/core'
import DrawingCanvas from '@/components/modeling/canvas/DrawingCanvas.vue'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { JsonObject } from '@/services/api/types/common'

interface Props {
  modelId?: string
}
const props = defineProps<Props>()
const router = useRouter()
const workspace = useModelWorkspaceStore()
const canvas = ref<{ serializeModel: () => JsonObject; loadPersistedModel: (data: JsonObject) => void } | null>(null)
const graphModel = ref<GraphDataModel>()
const recoveryDialog = ref(false)
const recoveryData = ref<JsonObject | null>(null)
const hydrating = ref(false)
const loading = ref(false)
const loadError = ref<string | null>(null)
const connections = computed(() => workspace.editorLanguages.flatMap((language) => language.connections))
const connectionGroups = computed(() =>
  workspace.editorLanguages
    .filter((language) => language.connections.length > 0)
    .map((language) => ({
      id: language.id,
      label: `${language.name} · v${language.version.versionNumber}`,
      connections: language.connections
    }))
)
const syntax = computed(() => workspace.editorLanguages.flatMap((language) => language.syntax))
const captureCanvas = () => {
  if (!hydrating.value && canvas.value) workspace.setData({ ...canvas.value.serializeModel(), name: workspace.model?.name ?? workspace.data.name })
}
const syncCanvas = async () => {
  hydrating.value = true
  try {
    await nextTick()
    canvas.value?.loadPersistedModel(workspace.data)
    await nextTick()
  } finally {
    hydrating.value = false
  }
}
const restoreDraft = async () => {
  if (await workspace.restoreRecoveryDraft()) await syncCanvas()
  recoveryDialog.value = false
}
const discardDraft = async () => {
  await workspace.discardRecoveryDraft()
  recoveryDialog.value = false
}
onMounted(async () => {
  loading.value = true
  loadError.value = null
  try {
    if (props.modelId) {
      await workspace.load(props.modelId)
      await syncCanvas()
      const recoverySnapshot = await workspace.getRecoverySnapshot()
      if (recoverySnapshot) {
        recoveryData.value = recoverySnapshot
        recoveryDialog.value = true
      }
    } else if (workspace.languages.length === 0) {
      await router.replace('/')
    }
  } catch {
    loadError.value = 'The model could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.modeling-view {
  position: relative;
  /* Keep the editor usable even when the footer extends below the viewport. */
  height: max(900px, calc(100vh - var(--v-layout-top, 0px)));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.model-loading {
  position: absolute;
  inset: 0 0 auto;
  z-index: 20;
}
.model-load-error {
  position: absolute;
  top: 24px;
  left: 50%;
  z-index: 20;
  width: min(480px, calc(100% - 48px));
  transform: translateX(-50%);
}
.editor-canvas {
  flex: 1;
  min-height: 0;
}
</style>
